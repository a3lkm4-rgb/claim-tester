"""The page.  Run:  streamlit run app.py"""
import json
import textwrap
from datetime import date
from html import escape
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

import memory  # noqa: E402
from llm import Meter  # noqa: E402
from pipeline import extract_claims, run, run_many  # noqa: E402

EXAMPLES = ["Notion is losing small-business customers",
            "Duolingo is losing users because of its AI-first strategy",
            "US office vacancy rates have fallen since the shift to remote work"]

SAMPLE_MEMO = """SAMPLE MEMO (fictional, for demonstration)

Recommendation: take a minority stake in Peloton Interactive.

Peloton is a recovering growth story. Its revenue has grown every year since 2021, and the company has returned to consistent profitability. Its connected-fitness subscribers churn at under 2% a month, which is low for a consumer subscription. Peloton remains the largest connected-fitness brand in the US by subscribers. Meanwhile, demand for at-home fitness equipment is still rising after the pandemic. We recommend proceeding to confirmatory diligence."""

# what each verdict means for a memo that relies on the claim
FLAG = {"not supported": "Red flag", "contested": "Disputed", "partly supported": "Partly holds",
        "supported": "Holds", "not enough evidence": "No evidence found"}

# verdict or stance -> badge style and map colour
STYLE = {"supported": "good", "partly supported": "warn", "contested": "warn",
         "not supported": "bad", "not enough evidence": "none"}
FILL = {"supported": "#c8e6c9", "partly supported": "#ffe0b2", "contested": "#ffe0b2",
        "not supported": "#ffcdd2", "not enough evidence": "#e0e0e0",
        "supports": "#c8e6c9", "contradicts": "#ffcdd2", "neutral": "#e0e0e0"}

CSS = """<style>
.block-container {padding-top: 2.2rem; max-width: 1250px;}
.eyebrow {font-size:.72rem; letter-spacing:.09em; text-transform:uppercase; color:#6B7785;
          margin-bottom:.15rem;}
.brand {font-size:1.9rem; font-weight:700; color:#0B3954; margin:0;}
.tagline {color:#55606E; margin:.1rem 0 1.1rem;}
.claim {font-size:1.45rem; font-weight:600; line-height:1.25; margin:.1rem 0 .7rem; color:#0B3954;}
.pill {display:inline-block; font-weight:600; font-size:.78rem; letter-spacing:.05em;
       padding:.25rem .75rem; border-radius:999px; vertical-align:middle;}
.good {background:#E3F4E6; color:#1B5E20;} .warn {background:#FFF1D6; color:#8A5300;}
.bad {background:#FDE4E4; color:#B71C1C;} .none {background:#ECEFF1; color:#455A64;}
.conf {color:#55606E; font-size:.9rem; margin-left:.6rem;}
.ev {border-left:4px solid; padding:.55rem .8rem; margin:.5rem 0; background:#F7F9FB;
     border-radius:4px; font-size:.92rem; line-height:1.4;}
.ev.for {border-color:#2E7D32;} .ev.against {border-color:#C62828;}
.ev a {font-size:.82rem; color:#0B3954;}
.chip {display:inline-block; font-size:.7rem; padding:.08rem .5rem; border-radius:999px;
       background:#E3E8EE; color:#33475B; margin-left:.35rem;}
.chip.ok {background:#E3F4E6; color:#1B5E20;} .chip.no {background:#FDE4E4; color:#B71C1C;}
.chip.near {background:#FFF1D6; color:#8A5300;} .chip.mem {background:#E1F5FE; color:#01579B;}
.step {font-size:.9rem; color:#33475B;} .step b {color:#0B3954;}
.assume {font-size:1.05rem; font-weight:600; margin:.1rem 0 .4rem;}
</style>"""


def pill(verdict):
    return f'<span class="pill {STYLE[verdict]}">{escape(verdict.upper())}</span>'


CHECK = {"verified": '<span class="chip ok">quote verified in source</span>',
         "close match": '<span class="chip near">close match in source</span>',
         "not found": '<span class="chip no">quote not found in source</span>'}


def evidence_card(finding, sources, check):
    side = "for" if finding.stance == "supports" else "against"
    e = sources.get(finding.source)
    link = (f'<a href="{escape(e["url"], quote=True)}" target="_blank">[{finding.source}] '
            f'{escape(textwrap.shorten(e["title"], 70, placeholder="…"))}</a>'
            f'<span class="chip">{escape(e["source_type"])}</span>'
            + ('<span class="chip mem">reused from memory</span>' if e.get("memory") else "")
            ) if e else f"[{finding.source}]"
    return (f'<div class="ev {side}">“{escape(finding.quote)}”<br>{link}'
            f'{CHECK.get(check, "")}</div>')


ARCHITECTURE = """digraph {
rankdir=TB; bgcolor="transparent"; nodesep=0.5; ranksep=0.35;
node [shape=box, style="rounded,filled", fillcolor="#F4F6F8", fontname="Helvetica", fontsize=13,
      fontcolor="black", margin="0.18,0.1"];
edge [color="#888888", fontname="Helvetica", fontsize=11, fontcolor="#555555"];
claim [label="Claim or memo", fillcolor="#c5cae9"];
split [label="Split into assumptions\nand for / against queries\n(Claude Opus)"];
skim [label="Skim: multi-engine search,\nauto-routed (Telem)"];
dedupe [label="Drop repeats\n(local embedding model)"];
screen [label="Screen each result: score,\nstance, source type\n(Claude Haiku)"];
again [label="Evidence thin?\nRewrite the queries\n(Claude Haiku)", fillcolor="#fff3e0"];
read [label="Read only the relevant\npassages (Tavily extract,\nTelem fetch as backup)"];
verdict [label="Verdict on each\nassumption (Claude Opus)"];
check [label="Check every quote\nagainst its source\n(plain code)"];
out [label="Report, evidence map,\nmemo", fillcolor="#c5cae9"];
mem [label="Evidence memory\n(Qdrant vector database)", shape=cylinder, fillcolor="#e1f5fe"];
claim -> split -> skim -> dedupe -> screen -> read -> verdict -> check -> out;
screen -> again [label="thin"]; again -> skim [label="search again"];
mem -> dedupe [label="recall"]; read -> mem [label="store"];
}"""


def label(text, width=34, limit=110):
    """Shorten and wrap text so it fits in a box on the map."""
    text = textwrap.shorten(text, limit, placeholder="…").replace('"', "'")
    return "\\n".join(textwrap.wrap(text, width))


def evidence_map(r):
    """The argument as a picture: claim -> key assumptions -> the sources read for each.
    Green = supports, red = contradicts, grey = neutral."""
    dot = ['digraph {', 'rankdir=LR; bgcolor="transparent";',
           'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, '
           'fontcolor="black"]; edge [color="#888888"];',
           f'claim [label="{label(r["claim"])}", fillcolor="#c5cae9", fontsize=13];']
    for i, (f, sv) in enumerate(zip(r["found"], r["report"].subs), 1):
        dot.append(f's{i} [label="{i}. {label(f["sub"].statement)}\\n{sv.verdict.upper()}", '
                   f'fillcolor="{FILL[sv.verdict]}"];')
        dot.append(f'claim -> s{i};')
        for e in f["evidence"]:
            dot.append(f'e{e["n"]} [label="[{e["n"]}] {label(e["title"], 30, 60)}\\n({e["source_type"]})", '
                       f'fillcolor="{FILL[e["stance"]]}", fontsize=10];')
            dot.append(f's{i} -> e{e["n"]};')
    return "\n".join(dot + ["}"])


def memo(r):
    """The whole result as a markdown memo the consultant can download."""
    rep, src = r["report"], {e["n"]: e for f in r["found"] for e in f["evidence"]}
    out = [f"# Claim test: {r['claim']}", f"*{date.today():%d %B %Y}*", "",
           "## Executive summary",
           f"**Verdict: {rep.overall_verdict}** (confidence: {rep.confidence})", "", rep.summary, "",
           f"**Refined hypothesis:** {rep.sharper_claim}", "",
           f"**Strongest counter-argument:** {rep.strongest_case_against}", "",
           f"**What would change our view:** {rep.would_change_verdict}", "",
           "## Key assumptions"]
    for i, (f, sv) in enumerate(zip(r["found"], rep.subs), 1):
        out += [f"### {i}. {f['sub'].statement}", f"**{sv.verdict.capitalize()}.** {sv.reasoning}", ""]
        out += [f"- ({x.stance}) \"{x.quote}\" [{x.source}]" for x in sv.findings]
        out += ["", f"**Reliability of evidence:** {sv.reliability}", "",
                f"**Data gaps:** {sv.missing}", "",
                "**Recommended next steps:** " + "; ".join(sv.next_steps), "",
                f"**Implication for the client:** {sv.so_what}", ""]
    out += ["## Sources"] + [f"[{n}] {e['title']} ({e['source_type']}) {e['url']}"
                             for n, e in sorted(src.items())]
    return "\n".join(out)


LIBRARY = Path(__file__).parent / "library.json"


def load_library():
    try:
        return json.loads(LIBRARY.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_to_library(r):
    """Keep every tested claim, so a firm builds up its own evidence library."""
    entries = [e for e in load_library() if e["claim"] != r["claim"]]
    entries.append({"date": date.today().isoformat(), "claim": r["claim"],
                    "verdict": r["report"].overall_verdict, "confidence": r["report"].confidence,
                    "sharper_claim": r["report"].sharper_claim,
                    "sources": [e["url"] for f in r["found"] for e in f["evidence"]]})
    LIBRARY.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ page

st.set_page_config(page_title="Claim Tester", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### How it works")
    st.markdown(
        '<div class="step"><b>1. Break down.</b> The claim is split into three assumptions '
        'that would have to be true.</div><br>'
        '<div class="step"><b>2. Search both sides.</b> Telem searches for evidence for and '
        'against each one, across several search engines.</div><br>'
        '<div class="step"><b>3. Read what matters.</b> Every result is screened from its '
        'summary. Tavily opens only the strongest few and returns the relevant passages.</div><br>'
        '<div class="step"><b>4. Verdict.</b> A verdict on each assumption, with quoted '
        'evidence, data gaps and next steps.</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### Try an example")
    for example in EXAMPLES:
        st.button(example, on_click=lambda e=example: st.session_state.update(claim=e),
                  width="stretch")
    st.divider()
    use_memory = st.checkbox("Use evidence memory", value=True, help=(
        "Passages read in earlier tests are kept in a local vector database. Related ones are "
        "recalled as candidates, and reused without fetching the page again."))
    run_baseline = st.checkbox("Also run the read-everything version", help=(
        "Slower and costs more. Opens every search result in full and asks for a second "
        "verdict, so you can compare quality."))

st.markdown('<p class="brand">Claim Tester</p>'
            '<p class="tagline">Pressure-test a business claim: evidence for and against, '
            'reading only what matters.</p>', unsafe_allow_html=True)

mode_claim, mode_memo = st.tabs(["Test a claim", "Start from a memo"])

with mode_claim:
    with st.form("test", border=False):
        box, button = st.columns([6, 1], vertical_alignment="bottom")
        claim = box.text_input("Claim or question to test", key="claim",
                               placeholder="e.g. Notion is losing small-business customers, "
                                           "or: Is Notion losing small-business customers?")
        go = button.form_submit_button("Test claim", type="primary", width="stretch")
    if go and claim:
        with st.status("Testing the claim...", expanded=True) as progress:
            st.session_state["results"] = [run(claim, run_baseline, status=progress.write,
                                               use_memory=use_memory)]
            save_to_library(st.session_state["results"][0])
            progress.update(label="Done", state="complete", expanded=False)

with mode_memo:
    st.caption("Paste an investment memo, a strategy paper or a slide's text. The tool lists the "
               "claims its conclusion depends on, then tests the ones you choose.")
    st.button("Load a sample memo", on_click=lambda: st.session_state.update(memo=SAMPLE_MEMO))
    memo_text = st.text_area("Memo", key="memo", height=200, label_visibility="collapsed",
                             placeholder="Paste the memo text here")
    if st.button("Find the claims to test") and memo_text:
        with st.spinner("Reading the memo..."):
            st.session_state["memo_claims"] = extract_claims(Meter(), memo_text)
    memo_claims = st.session_state.get("memo_claims")
    if memo_claims:
        st.dataframe([{"Claim": c.claim, "Importance": c.importance, "Why it matters": c.why,
                       "From the memo": c.quote} for c in memo_claims], hide_index=True)
        picked = st.multiselect("Claims to test (up to 3 at a time)",
                                [c.claim for c in memo_claims],
                                default=[c.claim for c in memo_claims[:3]], max_selections=3)
        if st.button("Test selected claims", type="primary") and picked:
            with st.spinner(f"Testing {len(picked)} claims side by side. About two minutes..."):
                st.session_state["results"] = run_many(picked, use_memory)
            for done in st.session_state["results"]:
                save_to_library(done)

results = st.session_state.get("results", [])
library = load_library()
r = results[0] if results else None

if len(results) > 1:
    with st.container(border=True):
        st.markdown('<div class="eyebrow">Red-flag report</div>', unsafe_allow_html=True)
        for x in results:
            v = x["report"].overall_verdict
            st.markdown(f'{pill(v)} <b style="margin-left:.5rem">{FLAG[v]}:</b> '
                        f'{escape(x["claim"])} <span class="conf">confidence: '
                        f'{x["report"].confidence}</span>', unsafe_allow_html=True)
        shown = st.selectbox("Show the detail for", range(len(results)),
                             format_func=lambda i: results[i]["claim"])
        r = results[shown]

if not r:
    st.info("Enter a claim or a question above, or pick an example from the sidebar. "
            "A test takes about a minute.")
    if library:
        st.markdown("#### Claim library")
        st.dataframe([{"Date": e["date"], "Claim": e["claim"], "Verdict": e["verdict"],
                       "Confidence": e["confidence"], "Refined hypothesis": e["sharper_claim"]}
                      for e in reversed(library)], hide_index=True)
    st.stop()

rep, smart, base = r["report"], r["smart"], r["baseline"]
sources = {e["n"]: e for f in r["found"] for e in f["evidence"]}

# ---- executive summary
with st.container(border=True):
    st.markdown(f'<div class="eyebrow">Claim tested</div><div class="claim">{escape(r["claim"])}</div>'
                f'{pill(rep.overall_verdict)}<span class="conf">Confidence: {rep.confidence}</span>',
                unsafe_allow_html=True)
    if r["asked"].strip() != r["claim"].strip():
        st.caption(f"You asked: “{r['asked']}”. It was restated as the claim above, so that "
                   f"the assumption behind the question is tested.")
    st.write("")
    st.write(rep.summary)
    st.markdown(f'<div class="eyebrow">Refined hypothesis the evidence supports</div>',
                unsafe_allow_html=True)
    st.markdown(f"**{rep.sharper_claim}**")
    left, right = st.columns(2)
    left.markdown('<div class="eyebrow">Strongest counter-argument</div>', unsafe_allow_html=True)
    left.write(rep.strongest_case_against)
    right.markdown('<div class="eyebrow">What would change our view</div>', unsafe_allow_html=True)
    right.write(rep.would_change_verdict)
    st.download_button("Download memo", memo(r), file_name="claim-test-memo.md")

# ---- headline numbers
checked = [c for sub_checks in r["checks"] for c in sub_checks]
k = st.columns(6)
k[0].metric("Sources screened", sum(len(f["rated"]) for f in r["found"]), border=True)
k[1].metric("Read in full", f"{smart['pages']} of {base['pages']}", border=True,
            help="Pages opened, against the number a read-everything approach would open")
k[2].metric("Tokens saved", f"{1 - smart['input_tokens'] / base['input_tokens']:.0%}"
            if base["input_tokens"] else "n/a", border=True)
k[3].metric("Cost of this test", f"${smart['total_cost']:.2f}", border=True)
k[4].metric("Time", f"{r['seconds']:.0f} sec", border=True)
k[5].metric("Quotes verified", f"{checked.count('verified')} of {len(checked)}", border=True,
            help="Every quoted finding is checked, word for word, against the text of its source")

tab_assume, tab_map, tab_cost, tab_hood, tab_library = st.tabs(
    ["Key assumptions", "Evidence map", "Cost and method", "Under the hood",
     f"Claim library ({len(library)})"])

# ---- key assumptions
with tab_assume:
    for i, (f, sv) in enumerate(zip(r["found"], rep.subs), 1):
        with st.container(border=True):
            st.markdown(f'<div class="eyebrow">Assumption {i}</div>'
                        f'<div class="assume">{escape(f["sub"].statement)}</div>{pill(sv.verdict)}',
                        unsafe_allow_html=True)
            st.write("")
            st.write(sv.reasoning)
            left, right = st.columns(2)
            for col, stance, title, empty in (
                    (left, "supports", "Evidence for", "None found."),
                    (right, "contradicts", "Evidence against",
                     "We searched for evidence against this and found none.")):
                items = [(x, c) for x, c in zip(sv.findings, r["checks"][i - 1])
                         if x.stance == stance]
                cards = "".join(evidence_card(x, sources, c) for x, c in items)
                col.markdown(f'<div class="eyebrow">{title} ({len(items)})</div>'
                             + (cards or f'<div class="step">{empty}</div>'),
                             unsafe_allow_html=True)
            st.write("")
            a, b = st.columns(2)
            a.markdown('<div class="eyebrow">Reliability of evidence</div>', unsafe_allow_html=True)
            a.write(sv.reliability)
            a.markdown('<div class="eyebrow">Data gaps</div>', unsafe_allow_html=True)
            a.write(sv.missing)
            b.markdown('<div class="eyebrow">Recommended next steps</div>', unsafe_allow_html=True)
            b.markdown("\n".join(f"- {step}" for step in sv.next_steps))
            b.markdown('<div class="eyebrow">Implication for the client</div>',
                       unsafe_allow_html=True)
            b.write(sv.so_what)
            with st.expander(f"All {len(f['rated'])} sources screened for this assumption"):
                st.caption(f"Searched for: “{f['sub'].query_for}” and against: "
                           f"“{f['sub'].query_against}”")
                if f["retry"]:
                    st.caption(f"The first results were thin, so it searched again with: "
                               f"“{f['retry'][0]}” and “{f['retry'][1]}”")
                st.dataframe([{"Read": ("from memory" if x["memory"] else "yes") if x["read"] else "",
                               "Score": x["score"],
                               "Stance": x["stance"], "Source type": x["source_type"],
                               "Title": x["title"], "Link": x["url"]} for x in f["rated"]],
                             column_config={"Link": st.column_config.LinkColumn()},
                             hide_index=True)

# ---- evidence map
with tab_map:
    st.caption("Each box on the right is a source that was read in full. "
               "Green supports the assumption, red contradicts it, grey is neutral.")
    st.graphviz_chart(evidence_map(r), width="stretch")

# ---- cost and method
with tab_cost:
    st.markdown("#### Reading less, on purpose")
    st.table([
        {"Approach": "Read everything", "Pages read in full": base["pages"],
         "Tokens read by AI": f"{base['input_tokens']:,} ({base['how']})",
         "Reading cost": f"${base['input_cost']:.3f}"},
        {"Approach": "Claim Tester", "Pages read in full": smart["pages"],
         "Tokens read by AI": f"{smart['input_tokens']:,} (measured)",
         "Reading cost": f"${smart['input_cost']:.3f}"}])
    if base["input_cost"]:
        st.markdown(f"**{1 - smart['input_tokens'] / base['input_tokens']:.0%} fewer tokens** and "
                    f"**{1 - smart['input_cost'] / base['input_cost']:.0%} lower reading cost** "
                    f"than opening every search result.")
    st.caption("'Read everything' means every search result opened in full and given to the "
               "strongest model, capped at 30 pages. 'Counted' means the tokens were counted "
               "without running it; 'measured' means it was run.")
    if base["report"]:
        st.markdown("#### Quality check against reading everything")
        st.table([{"Assumption": f["sub"].statement, "Claim Tester": sv.verdict,
                   "Read everything": bv.verdict}
                  for f, sv, bv in zip(r["found"], rep.subs, base["report"].subs)]
                 + [{"Assumption": "Overall", "Claim Tester": rep.overall_verdict,
                     "Read everything": base["report"].overall_verdict}])
    with st.expander("Audit trail: what was searched, dropped and read"):
        for i, f in enumerate(r["found"], 1):
            st.markdown(f"**Assumption {i}**\n\n" + "\n".join(f["log"]))

# ---- under the hood
with tab_hood:
    diagram, trace = st.columns([2, 3])
    with diagram:
        st.markdown("#### How a claim moves through the system")
        st.graphviz_chart(ARCHITECTURE, width="content")
        st.caption("The three assumptions run in parallel. Up to three claims from a memo run "
                   "in parallel as well.")
    with trace:
        st.markdown("#### What happened in this test")
        st.dataframe(r["trace"], hide_index=True)
    left, right = st.columns(2)
    with left:
        st.markdown("#### Every AI call")
        st.dataframe(r["meter"].calls, hide_index=True)
    with right:
        st.markdown("#### The stack")
        try:
            stored = memory.size()
        except Exception:
            stored = "unavailable"
        st.markdown(
            "- **Telem**: multi-engine search with auto-routing; backup page fetch\n"
            "- **Tavily**: query-aware extraction of the relevant passages\n"
            "- **Claude Opus 5.5**: splits the claim, reads memos, writes the verdict\n"
            "- **Claude Haiku 5.5**: screens every result; rewrites queries when evidence is thin\n"
            "- **bge-small embedding model** (runs locally): drops repeats, powers memory\n"
            f"- **Qdrant vector database** (local): evidence memory, {stored} passages stored\n"
            "- **Quote checker** (plain code): verifies each quote against its source\n"
            "- **Streamlit**: this page")

# ---- claim library
with tab_library:
    st.caption("Every claim tested is kept, so a team builds up its own record of evidence.")
    st.dataframe([{"Date": e["date"], "Claim": e["claim"], "Verdict": e["verdict"],
                   "Confidence": e["confidence"], "Refined hypothesis": e["sharper_claim"],
                   "Sources": len(e["sources"])} for e in reversed(library)], hide_index=True)
