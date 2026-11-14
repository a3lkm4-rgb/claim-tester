"""The true-or-false test.

Runs every claim in claims.json (each has a known answer) through:
  - the Hypothesis Tester, and
  - a plain "search + chatbot": search the claim as typed, read the top 5 pages in full,
    ask Opus whether it is true.
Saves results.csv and bench_results.json, and prints a summary.

Run:  python bench.py        (about 2 minutes and $0.20-0.50 per claim)
"""
import csv
import json
import time

from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel  # noqa: E402

from llm import PRICES, STRONG, Meter, ask  # noqa: E402
from pipeline import NUM_RESULTS, Verdict, read, run, telem  # noqa: E402

CHATBOT_PAGES = 5


class Answer(BaseModel):
    verdict: Verdict
    summary: str  # 2-3 sentences


def chatbot(claim):
    """The baseline: no splitting, no search for evidence against, no scoring."""
    meter, t0 = Meter(), time.time()
    results = telem().search(claim, num_results=NUM_RESULTS, tier="default",
                             auto_routing="accuracy",
                             metadata={"app": "hypothesis-tester", "step": "chatbot-baseline"}).results
    urls = list(dict.fromkeys(r.url for r in results))[:CHATBOT_PAGES]
    pages = read(urls, {})
    sources = "\n\n".join(f"[{i}] {u}\n{text}" for i, (u, text) in enumerate(pages.items(), 1))
    answer = ask(meter, "chatbot", f"Is this claim true?\n\nClaim: {claim}\n\nSources:\n\n{sources}",
                 Answer, model=STRONG,
                 system="You are a helpful research assistant. Answer using the sources provided.")
    return {"verdict": answer.verdict, "summary": answer.summary, "pages": len(pages),
            "input_tokens": meter.total("input"), "cost": meter.total("cost"),
            "seconds": time.time() - t0}


def correct(verdict, answer):
    """A true claim should come back supported; a false one should come back not supported."""
    if answer == "true":
        return verdict in ("supported", "partly supported")
    return verdict == "not supported"


rows, details = [], []
for item in json.load(open("claims.json", encoding="utf-8")):
    claim, answer = item["claim"], item["answer"]
    print(f"\n=== {claim}  (known answer: {answer})")
    row = {"claim": claim, "answer": answer}
    try:
        r = run(claim, use_memory=False)  # memory off, so every claim starts cold
        rep, s, b = r["report"], r["smart"], r["baseline"]
        row.update(tester_verdict=rep.overall_verdict, tester_correct=correct(rep.overall_verdict, answer),
                   tester_confidence=rep.confidence, tester_pages=s["pages"],
                   tester_tokens=s["input_tokens"], tester_cost=round(s["total_cost"], 4),
                   tester_seconds=round(r["seconds"]), everything_pages=b["pages"],
                   everything_tokens=b["input_tokens"],
                   everything_reading_cost=round(b["input_cost"], 4),
                   tester_reading_cost=round(s["input_cost"], 4))
        details.append({"claim": claim, "answer": answer, "verdict": rep.overall_verdict,
                        "confidence": rep.confidence, "summary": rep.summary,
                        "sharper_claim": rep.sharper_claim,
                        "subs": [{"statement": f["sub"].statement, "verdict": sv.verdict}
                                 for f, sv in zip(r["found"], rep.subs)]})
        print(f"  Hypothesis Tester: {rep.overall_verdict} ({'correct' if row['tester_correct'] else 'WRONG'})"
              f"  {s['input_tokens']:,} tokens, ${s['total_cost']:.3f}, {r['seconds']:.0f}s")
    except Exception as e:
        row["tester_verdict"] = f"failed: {type(e).__name__}: {str(e)[:120]}"
        print("  Hypothesis Tester FAILED:", row["tester_verdict"])
    try:
        c = chatbot(claim)
        row.update(chatbot_verdict=c["verdict"], chatbot_correct=correct(c["verdict"], answer),
                   chatbot_pages=c["pages"], chatbot_tokens=c["input_tokens"],
                   chatbot_cost=round(c["cost"], 4), chatbot_seconds=round(c["seconds"]))
        print(f"  Search + chatbot:  {c['verdict']} ({'correct' if row['chatbot_correct'] else 'WRONG'})"
              f"  {c['input_tokens']:,} tokens, ${c['cost']:.3f}, {c['seconds']:.0f}s")
    except Exception as e:
        row["chatbot_verdict"] = f"failed: {type(e).__name__}: {str(e)[:120]}"
        print("  Search + chatbot FAILED:", row["chatbot_verdict"])
    rows.append(row)

    # save after every claim, so a crash part-way through loses nothing
    fields = list(dict.fromkeys(k for r_ in rows for k in r_))
    with open("results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    json.dump(details, open("bench_results.json", "w", encoding="utf-8"), indent=2)

done = [r for r in rows if "tester_tokens" in r]
print("\n================ SUMMARY ================")
for name, key in (("Hypothesis Tester", "tester_correct"), ("Search + chatbot", "chatbot_correct")):
    scored = [r for r in rows if key in r]
    for answer in ("true", "false"):
        group = [r for r in scored if r["answer"] == answer]
        print(f"{name}: {sum(r[key] for r in group)} of {len(group)} {answer} claims judged correctly")
if done:
    t, e = sum(r["tester_tokens"] for r in done), sum(r["everything_tokens"] for r in done)
    tc, ec = sum(r["tester_reading_cost"] for r in done), sum(r["everything_reading_cost"] for r in done)
    print(f"\nAcross {len(done)} claims, against reading everything:")
    print(f"  tokens saved: {1 - t / e:.0%}   reading cost saved: {1 - tc / ec:.0%}")
    print(f"  average cost per claim: ${sum(r['tester_cost'] for r in done) / len(done):.3f}   "
          f"average time: {sum(r['tester_seconds'] for r in done) / len(done):.0f}s")
    print(f"  (Opus input price used: ${PRICES[STRONG][0]}/million tokens)")
print("Saved results.csv and bench_results.json")
