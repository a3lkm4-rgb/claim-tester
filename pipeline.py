"""The Hypothesis Tester pipeline.

claim -> split (Opus) -> for each sub-hypothesis:
            skim (Telem search) -> drop repeats (embeddings) -> score (Haiku)
            -> read the relevant passages of the top 3 (Tavily)
      -> verdict (Opus) -> compare tokens with reading everything
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Literal
from urllib.parse import urlsplit

import numpy as np
from pydantic import BaseModel
from tavily import TavilyClient
from telem import Telem

import memory
from embed import embed, similarity_to
from llm import PRICES, STRONG, Meter, ask, count_tokens

NUM_RESULTS = 5          # results per search engine, per query
TOP_K = 3                # pages read in full per sub-hypothesis
MIN_SCORE = 5            # evidence score (0-10) needed to be read
SPARE = 2                # extra candidates fetched in case a page will not open
STRONG_SCORE = 7         # a result that offers direct evidence
                         # fewer than 2 of these and the tool searches again with new queries
DUP_THRESHOLD = 0.90     # summaries this similar count as the same story
                         # (0.83 was too strict on real results: it dropped different articles)
MAX_PARAGRAPHS = 40      # longer pages are pre-filtered by embeddings before Haiku
MAX_KEPT = 12            # most paragraphs kept from any one page
CHUNKS = 5               # relevant passages Tavily returns per page (its maximum)
BASELINE_MAX_PAGES = 30  # cap on the read-everything comparison

SOURCE_TYPES = ["official data", "independent research", "news", "user opinion", "vendor marketing"]

_telem = _tavily = None


def telem():
    global _telem
    if _telem is None:
        _telem = Telem()  # reads TELEM_API_KEY
    return _telem


def tavily():
    global _tavily
    if _tavily is None:
        _tavily = TavilyClient()  # reads TAVILY_API_KEY
    return _tavily


# ---------- Step 1: split the claim (Opus) ----------

class Sub(BaseModel):
    statement: str       # the sub-hypothesis
    query_for: str       # search query for evidence that supports it
    query_against: str   # search query for evidence against it


class Plan(BaseModel):
    subs: list[Sub]


SPLIT_PROMPT = """You are a strategy consultant pressure-testing a client's claim.

Break the claim into exactly 3 sub-hypotheses that together would settle it. Ask: "what would
have to be true for this claim to hold?" Each must be testable with public web evidence, and
they must not overlap.

For each one, write two short web search queries, the way a person would type them:
- query_for: looks for evidence that supports the sub-hypothesis
- query_against: looks for evidence that contradicts it

Claim: {claim}"""


def split(meter, claim):
    return ask(meter, "split", SPLIT_PROMPT.format(claim=claim), Plan, model=STRONG).subs[:3]


# ---------- Optional first step: pull the testable claims out of a memo (Opus) ----------

class MemoClaim(BaseModel):
    claim: str    # rewritten as one standalone, testable statement
    quote: str    # the passage in the memo it comes from
    importance: Literal["high", "medium", "low"]  # how much the memo's conclusion rests on it
    why: str      # one line: why it matters to the conclusion


class MemoClaims(BaseModel):
    claims: list[MemoClaim]


MEMO_PROMPT = """You are a diligence analyst reviewing a memo before it goes to an investment
or steering committee. List the factual claims that the memo's conclusion depends on and that
could be checked against public web evidence.

Rewrite each as one standalone statement that names the company or market, so it makes sense
without the memo. Skip opinions, internal figures nobody outside could check, and forecasts.
Give at most 8, ordered from the claim the conclusion depends on most to least.

Memo:
{memo}"""


def extract_claims(meter, memo):
    return ask(meter, "memo", MEMO_PROMPT.format(memo=memo), MemoClaims, model=STRONG).claims[:8]


def run_many(claims, use_memory=True):
    """Test several claims side by side. Returns results in the same order."""
    embed(["warm up"])  # load the embedding model once, before the parallel work starts
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(lambda c: run(c, use_memory=use_memory), claims))


# ---------- Step 2: skim (Telem searches several engines, both sides in one request) ----------

def skim(sub):
    providers = [p.strip() for p in os.getenv("TELEM_PROVIDERS", "").split(",") if p.strip()]
    # Auto-routing: Telem picks the best few engines for each query instead of calling them all.
    # Set TELEM_AUTO_ROUTING=off in .env to compare against searching every default engine.
    routing = None if os.getenv("TELEM_AUTO_ROUTING", "").lower() == "off" else "accuracy"
    resp = telem().search([sub.query_for, sub.query_against], num_results=NUM_RESULTS,
                          tier="default", providers_include=providers or None,
                          auto_routing=routing,
                          metadata={"app": "hypothesis-tester", "step": "skim"})  # shows in Telem's dashboard
    return resp.results  # titles + short summaries only; no pages opened yet


# ---------- Step 3: drop repeats ----------

def _address(url):
    p = urlsplit(url)
    return p.netloc.lower().removeprefix("www.") + p.path.rstrip("/")


def drop_repeats(results, log):
    # (a) the same page returned twice
    seen, unique = set(), []
    for r in results:
        if _address(r.url) not in seen:
            seen.add(_address(r.url))
            unique.append(r)
    # (b) the same story on different sites, judged by meaning
    if len(unique) > 1:
        v = embed(f"{r.title or ''}: {r.summary or ''}" for r in unique)
        kept = []
        for i, r in enumerate(unique):
            twin = next((j for j in kept if v[i] @ v[j] >= DUP_THRESHOLD), None)
            if twin is None:
                kept.append(i)
            else:
                log.append(f"- same story dropped: *{r.title or r.url}* ≈ "
                           f"*{unique[twin].title or unique[twin].url}* ({v[i] @ v[twin]:.2f})")
        unique = [unique[i] for i in kept]
    log.insert(0, f"Skim: {len(results)} results → {len(unique)} after dropping repeats")
    return unique


# ---------- Step 4: score each result from its title and summary (Haiku) ----------

class Rating(BaseModel):
    id: int
    score: int
    stance: Literal["supports", "contradicts", "neutral"]
    source_type: Literal["official data", "independent research", "news", "user opinion",
                         "vendor marketing"]


class Ratings(BaseModel):
    ratings: list[Rating]


SCORE_PROMPT = """You are screening search results for a consultant who is testing a hypothesis.
You see only each result's website, title and summary.

For every result give:
- score (0-10), the strength of evidence it offers for OR against the hypothesis:
  0-3 off-topic, or it only shares words with the hypothesis
  4-6 on-topic but offers no real evidence either way
  7-8 direct evidence for or against
  9-10 direct evidence backed by data (figures, a survey, filings)
- stance: supports, contradicts or neutral
- source_type: official data, independent research, news, user opinion or vendor marketing
  (a company's own website describing itself is vendor marketing; official data means filings,
  government or regulator figures, or statistics the company formally reports)

Judge by meaning, not shared words: a result can be strong evidence without using any words
from the hypothesis. Evidence against the hypothesis is as valuable as evidence for it.

Hypothesis: {hypothesis}

Results:
{listing}"""


def score(meter, sub, results):
    listing = "\n".join(
        f"{i}. [{urlsplit(r.url).netloc}] {r.title or ''}: {(r.summary or '')[:400]}"
        for i, r in enumerate(results))
    ratings = ask(meter, "score", SCORE_PROMPT.format(hypothesis=sub.statement, listing=listing),
                  Ratings).ratings
    by_id = {x.id: x for x in ratings}
    rated = [{"url": r.url, "title": r.title or r.url, "date": str(r.publish_date or "")[:10],
              "score": by_id[i].score, "stance": by_id[i].stance,
              "source_type": by_id[i].source_type}
             for i, r in enumerate(results) if i in by_id]
    return sorted(rated, key=_rank)


def _rank(x):
    """Best first; a more trustworthy source type wins a tie."""
    return (-x["score"], SOURCE_TYPES.index(x["source_type"]))


def pick(rated):
    """Every result with a score of 5+, in reading order: the best source on each side first,
    then the rest by score. The first 3 that open are the ones read."""
    eligible = [x for x in rated if x["score"] >= MIN_SCORE]  # already sorted best first
    # the best source on each side goes in first, then the rest by score
    reserved = [next((x for x in eligible if x["stance"] == s), None)
                for s in ("contradicts", "supports")]
    reserved = [x for x in reserved if x]
    return reserved + [x for x in eligible if x not in reserved]


# ---------- Step 5: read the chosen pages in full (Tavily) ----------

def read(urls, cache):
    """Fill `cache` (url -> page text) for any urls not fetched yet. 20 per Tavily call."""
    todo = [u for u in urls if u not in cache]
    for i in range(0, len(todo), 20):
        for page in tavily().extract(urls=todo[i:i + 20], format="markdown").get("results", []):
            if page.get("raw_content"):
                cache[page["url"]] = page["raw_content"]
    # pages Tavily could not open get a second try through Telem's fetch (5 per call)
    missed = [u for u in todo if u not in cache]
    for i in range(0, len(missed), 5):
        batch = missed[i:i + 5]
        try:
            for url, page in zip(batch, telem().fetch(batch).results):
                if page.content:
                    cache[url] = page.content
        except Exception:
            pass  # a failed second try just means the page stays unread
    return {u: cache[u] for u in urls if u in cache}


def read_relevant(urls, hypothesis):
    """Tavily opens each page and returns only the passages relevant to the hypothesis,
    so the AI never sees the rest of the page. Returns url -> passages."""
    if not urls:
        return {}
    resp = tavily().extract(urls=urls, format="markdown", query=hypothesis,
                            chunks_per_source=CHUNKS)
    return {p["url"]: p["raw_content"] for p in resp.get("results", []) if p.get("raw_content")}


# ---------- Fallback for pages Tavily cannot open: trim the full page (embeddings, then Haiku) ----------

class Keep(BaseModel):
    keep: list[int]


TRIM_PROMPT = """Below are numbered paragraphs from a web page. Return the numbers of the
paragraphs that contain evidence for OR against the hypothesis: facts, figures, first-hand
accounts, comparisons. Leave out navigation, adverts and off-topic text.
List the strongest evidence first and return at most {limit} numbers.

Hypothesis: {hypothesis}

{listing}"""


def trim(meter, sub, text):
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
    total = len(paras)
    if total > MAX_PARAGRAPHS:  # free pre-filter: keep the paragraphs closest in meaning
        closest = np.argsort(-similarity_to(sub.statement, paras))[:MAX_PARAGRAPHS]
        paras = [paras[i] for i in sorted(closest)]
    if not paras:
        return "", total, 0
    listing = "\n\n".join(f"<<{i}>> {p}" for i, p in enumerate(paras))
    keep = ask(meter, "trim", TRIM_PROMPT.format(hypothesis=sub.statement, listing=listing,
                                          limit=MAX_KEPT), Keep).keep[:MAX_KEPT]
    kept = [paras[i] for i in sorted(set(keep)) if 0 <= i < len(paras)]
    return "\n\n".join(kept), total, len(kept)


# ---------- Adaptive re-search: if the evidence is thin, try new queries once (Haiku) ----------

class Requery(BaseModel):
    query_for: str
    query_against: str


REQUERY_PROMPT = """A consultant searched the web to test a hypothesis and found only weak evidence.
Write two new web search queries of at most 8 words each that come at it from a different angle:
name a specific metric, data source, report or synonym that the first queries missed.
- query_for: looks for evidence that supports the hypothesis
- query_against: looks for evidence that contradicts it

Hypothesis: {hypothesis}
Queries already tried: "{q1}" and "{q2}"
Best results so far:
{titles}"""


def search_again(meter, sub, rated, log):
    """One more search with rewritten queries. Returns the rated list with any new results added."""
    titles = "\n".join(f"- ({x['score']}/10) {x['title']}" for x in rated[:6]) or "(none)"
    new = ask(meter, "requery", REQUERY_PROMPT.format(
        hypothesis=sub.statement, q1=sub.query_for, q2=sub.query_against, titles=titles), Requery)
    more = skim(Sub(statement=sub.statement, query_for=new.query_for,
                    query_against=new.query_against))
    seen = {_address(x["url"]) for x in rated}
    fresh = [r for r in drop_repeats(more, []) if _address(r.url) not in seen]
    before = max((x["score"] for x in rated), default=0)
    if fresh:
        rated = sorted(rated + score(meter, sub, fresh), key=_rank)
    log.append(f"- evidence was thin (best score {before}/10), so it searched again with "
               f"\"{new.query_for}\" and \"{new.query_against}\": {len(fresh)} new results, "
               f"best score now {max((x['score'] for x in rated), default=0)}/10")
    return rated, (new.query_for, new.query_against)


# ---------- Steps 2-6 for one sub-hypothesis ----------

def investigate(meter, sub, cache, use_memory=True):
    t0, log = time.time(), []

    # evidence memory: passages read in earlier tests that are close in meaning to this assumption
    recalled = {}
    if use_memory:
        try:
            recalled = {m["url"]: m for m in memory.recall(sub.statement)}
        except Exception as e:
            log.append(f"- evidence memory unavailable ({type(e).__name__})")

    found = skim(sub)
    engines = sorted({r.provider for r in found if getattr(r, "provider", None)})
    # recalled passages join the fresh results as candidates and are screened in the same way
    remembered = [SimpleNamespace(url=m["url"], title=m["title"], summary=m["text"][:400],
                                  publish_date=None, provider="memory") for m in recalled.values()]
    results = drop_repeats(remembered + found, log)
    log.insert(1, f"- engines Telem used: {', '.join(engines) or 'not reported'}")
    if recalled:
        log.insert(2, f"- recalled {len(recalled)} passages from earlier tests as extra candidates")

    rated = score(meter, sub, results) if results else []
    retry = None
    if sum(x["score"] >= STRONG_SCORE for x in rated) < 2:
        rated, retry = search_again(meter, sub, rated, log)

    candidates = pick(rated)[:TOP_K + SPARE]
    urls = [x["url"] for x in candidates]
    to_fetch = [u for u in urls if u not in recalled]
    passages = read_relevant(to_fetch, sub.statement)
    # anything Tavily could not open gets a second try through Telem's fetch
    backup = read([u for u in to_fetch if u not in passages], cache)
    chosen = [x for x in candidates
              if x["url"] in recalled or x["url"] in passages or x["url"] in backup][:TOP_K]
    for x in rated:
        x["read"] = x in chosen
        x["memory"] = x["url"] in recalled
    log += [f"- could not open {u}" for u in to_fetch if u not in passages and u not in backup]
    evidence = []
    for x in chosen:
        if x["url"] in recalled:
            text = recalled[x["url"]]["text"]
            log.append(f"- reused *{x['title']}* from memory, no fetch needed "
                       f"(first read when testing \"{recalled[x['url']]['claim']}\")")
        elif x["url"] in passages:
            text = passages[x["url"]]
            log.append(f"- read *{x['title']}*: Tavily returned {len(text):,} characters "
                       f"of relevant passages")
        else:
            text, total, kept = trim(meter, sub, backup[x["url"]])
            log.append(f"- read *{x['title']}* (via Telem): kept {kept} of {total} paragraphs")
        if text:
            evidence.append({**x, "text": text})
    return {"sub": sub, "rated": rated, "evidence": evidence, "log": log, "retry": retry,
            "engines": engines, "seconds": time.time() - t0}


# ---------- Quote check: does every quoted finding really appear in its source? (plain code) ----------

def _plain(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def check_quote(quote, source_text):
    """'verified' = found word for word; 'close match' = found with small differences;
    'not found' = the source does not contain it."""
    text = _plain(source_text)
    pieces = re.split(r"\[\.\.\.\]|\.\.\.|\u2026", quote)  # the model may join passages with "..."
    parts = [p for p in (_plain(x) for x in pieces) if len(p) >= 12]
    if not parts:
        return "not checked"
    if all(p in text for p in parts):
        return "verified"

    def covered(part):  # share of the part's three-word runs that appear in the source
        words = part.split()
        runs = [" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))]
        return sum(run in text for run in runs) / len(runs)

    return "close match" if min(covered(p) for p in parts) >= 0.6 else "not found"


def check_quotes(report, found):
    """One result per finding, in the same order as report.subs[i].findings."""
    sources = {e["n"]: e for f in found for e in f["evidence"]}
    return [[check_quote(x.quote, sources[x.source]["text"]) if x.source in sources
             else "not found" for x in sv.findings] for sv in report.subs]


# ---------- Step 7: the verdict (Opus) ----------

Verdict = Literal["supported", "partly supported", "contested", "not supported",
                  "not enough evidence"]


class Finding(BaseModel):
    quote: str    # a short passage taken from the source
    source: int   # the source's reference number
    stance: Literal["supports", "contradicts"]


class SubVerdict(BaseModel):
    verdict: Verdict
    reasoning: str          # 2-3 sentences
    findings: list[Finding]
    reliability: str        # how far this evidence can be trusted, and why
    missing: str            # what evidence was not found
    next_steps: list[str]   # data to request, people to interview
    so_what: str            # one line for the client


class Report(BaseModel):
    overall_verdict: Verdict
    confidence: Literal["low", "medium", "high"]
    summary: str                 # 2-3 sentences, answer first
    subs: list[SubVerdict]       # same order as the sub-hypotheses given
    strongest_case_against: str  # the best counter-argument, even if the claim holds
    would_change_verdict: str    # what new evidence would flip the verdict
    sharper_claim: str           # a more precise version of the claim that the evidence supports


VERDICT_SYSTEM = """You are a research analyst writing for a consulting team that is
pressure-testing a client's claim. Use ONLY the numbered sources provided.

For each sub-hypothesis, in the order given: a verdict; 2-3 sentences of reasoning; the key
findings, each a short passage quoted from a source with its reference number and whether it
supports or contradicts; how reliable the evidence is; what is missing; suggested next steps;
and a one-line "so what" for the client. Use "contested" when credible sources disagree, and
"not enough evidence" when the sources do not settle it.

Then give an overall verdict and confidence, a 2-3 sentence summary that leads with the answer,
the strongest case against the claim (even if it holds), what evidence would change the verdict,
and a sharper, more precise version of the claim that the evidence does support.

Never state a fact that is not in the sources. If the evidence is weak or one-sided, say so.
Do not force balance: if nothing credible contradicts the claim, say that."""


def verdict_prompt(claim, sections):
    """sections: list of (sub-hypothesis statement, [evidence items with n, url, text...])."""
    parts = [f"Claim: {claim}"]
    for i, (statement, items) in enumerate(sections, 1):
        parts.append(f"\n## Sub-hypothesis {i}: {statement}")
        if not items:
            parts.append("(no sources found)")
        for e in items:
            label = f"{e['source_type']}, screened as: {e['stance']}" if e.get("stance") else "unscreened"
            parts.append(f"\n[{e['n']}] {e['title']} ({label}) {e['url']}\n{e['text']}")
    return "\n".join(parts)


# ---------- The whole run ----------

def run(claim, run_baseline=False, status=lambda msg: None, use_memory=True):
    meter, t0, cache, trace = Meter(), time.time(), {}, []

    status("Opus is splitting the claim into sub-hypotheses...")
    subs = split(meter, claim)
    trace.append({"step": "Split the claim", "done by": "Claude Opus",
                  "detail": f"{len(subs)} assumptions, {2 * len(subs)} search queries",
                  "seconds": round(time.time() - t0, 1)})

    status("Skimming, scoring and reading for each sub-hypothesis...")
    embed(["warm up"])  # load the embedding model once, before the parallel work starts
    with ThreadPoolExecutor(max_workers=3) as pool:
        found = list(pool.map(lambda s: investigate(meter, s, cache, use_memory), subs))
    for i, f in enumerate(found, 1):
        reused = sum(x["memory"] and x["read"] for x in f["rated"])
        trace.append({"step": f"Assumption {i}: skim, screen, read",
                      "done by": f"Telem ({', '.join(f['engines']) or 'engines'}), embeddings, "
                                 f"Claude Haiku, Tavily",
                      "detail": f"{len(f['rated'])} results screened, {len(f['evidence'])} read"
                                + (", searched again with new queries" if f["retry"] else "")
                                + (f", {reused} reused from memory" if reused else ""),
                      "seconds": round(f["seconds"], 1)})

    n = 0  # number the evidence [1], [2], ... across all sub-hypotheses
    for f in found:
        for e in f["evidence"]:
            n += 1
            e["n"] = n

    status("Opus is writing the verdict...")
    smart_prompt = verdict_prompt(claim, [(f["sub"].statement, f["evidence"]) for f in found])
    t1 = time.time()
    report = ask(meter, "verdict", smart_prompt, Report, model=STRONG, system=VERDICT_SYSTEM)
    trace.append({"step": "Write the verdict", "done by": "Claude Opus",
                  "detail": f"from {n} sources", "seconds": round(time.time() - t1, 1)})

    t1 = time.time()
    checks = check_quotes(report, found)
    flat = [c for sub_checks in checks for c in sub_checks]
    trace.append({"step": "Check every quote against its source", "done by": "plain code",
                  "detail": f"{flat.count('verified')} verified word for word, "
                            f"{flat.count('close match')} close match, "
                            f"{flat.count('not found')} not found",
                  "seconds": round(time.time() - t1, 1)})

    if use_memory:
        t1 = time.time()
        try:
            stored = sum(memory.remember(claim, f["sub"].statement, f["evidence"]) for f in found)
            trace.append({"step": "Store the evidence", "done by": "Qdrant vector database",
                          "detail": f"{stored} passages stored, {memory.size()} in memory",
                          "seconds": round(time.time() - t1, 1)})
        except Exception as e:
            trace.append({"step": "Store the evidence", "done by": "Qdrant vector database",
                          "detail": f"unavailable ({type(e).__name__})", "seconds": 0})

    # ----- comparison: what "read everything" would cost for the same job -----
    status("Measuring the read-everything comparison...")
    everything, m, used = [], 0, set()
    for f in found:
        items = []
        for x in f["rated"]:
            if x["url"] not in used and len(used) < BASELINE_MAX_PAGES:
                used.add(x["url"])
                items.append(x)
        everything.append((f["sub"].statement, items))
    pages = read(list(used), cache)
    sections = []
    for statement, items in everything:
        full = []
        for x in items:
            if x["url"] in pages:
                m += 1
                full.append({"n": m, "url": x["url"], "title": x["title"],
                             "source_type": x["source_type"], "text": pages[x["url"]]})
        sections.append((statement, full))
    base_prompt = verdict_prompt(claim, sections)
    base_tokens, how = count_tokens(VERDICT_SYSTEM, base_prompt)
    split_tokens = meter.total("input", {"split"})

    baseline = {"pages": m, "input_tokens": split_tokens + base_tokens, "how": how,
                "input_cost": (split_tokens + base_tokens) * PRICES[STRONG][0] / 1e6,
                "report": None, "sources": [e for _, items in sections for e in items]}
    if run_baseline:
        status("Running the read-everything version for a quality comparison...")
        base_meter = Meter()
        baseline["report"] = ask(base_meter, "verdict", base_prompt, Report, model=STRONG,
                                 system=VERDICT_SYSTEM)
        baseline["input_tokens"] = split_tokens + base_meter.total("input")
        baseline["input_cost"] = baseline["input_tokens"] * PRICES[STRONG][0] / 1e6
        baseline["how"] = "measured"

    smart_in = meter.total("input")
    smart_in_cost = sum(c["input"] * PRICES.get(c["model"], PRICES[STRONG])[0] / 1e6
                        for c in meter.calls)
    return {"claim": claim, "found": found, "report": report, "meter": meter,
            "checks": checks, "trace": trace,
            "seconds": time.time() - t0, "baseline": baseline,
            "smart": {"pages": len({e["url"] for f in found for e in f["evidence"]}),
                      "input_tokens": smart_in, "input_cost": smart_in_cost,
                      "total_cost": meter.total("cost")}}
