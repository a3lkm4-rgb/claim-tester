"""Run one claim from the terminal and print the result.
Run:  python run_once.py "Notion is losing small-business customers"
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from pipeline import run  # noqa: E402

claim = sys.argv[1] if len(sys.argv) > 1 else "Notion is losing small-business customers"
r = run(claim, status=print)
rep = r["report"]

print(f"\nCLAIM: {claim}")
print(f"VERDICT: {rep.overall_verdict} (confidence: {rep.confidence})")
print(rep.summary)
print(f"SHARPER CLAIM: {rep.sharper_claim}")
for i, (f, sv) in enumerate(zip(r["found"], rep.subs), 1):
    print(f"\n{i}. {f['sub'].statement}\n   -> {sv.verdict}: {sv.reasoning}")
    print(f"   for: \"{f['sub'].query_for}\" | against: \"{f['sub'].query_against}\"")
    for line in f["log"]:
        print("   " + line)
    for x in f["rated"][:8]:
        print(f"   {'READ' if x['read'] else '    '} {x['score']:>2} {x['stance']:11} "
              f"{x['source_type']:20} {x['title'][:60]}")
    for x in sv.findings:
        print(f"   [{x.source}] ({x.stance}) \"{x.quote[:110]}\"")

s, b = r["smart"], r["baseline"]
print(f"\nSCOREBOARD ({r['seconds']:.0f} seconds)")
print(f"  Read everything:   {b['pages']:>3} pages  {b['input_tokens']:>9,} tokens ({b['how']})  "
      f"${b['input_cost']:.3f} reading cost")
print(f"  Claim Tester: {s['pages']:>3} pages  {s['input_tokens']:>9,} tokens (measured)  "
      f"${s['input_cost']:.3f} reading cost   (total ${s['total_cost']:.3f})")
if b["input_tokens"]:
    print(f"  Tokens saved: {1 - s['input_tokens'] / b['input_tokens']:.0%}   "
          f"Reading cost saved: {1 - s['input_cost'] / b['input_cost']:.0%}")
for c in r["meter"].calls:
    print(f"    {c['step']:8} {c['model']:18} in {c['input']:>7,}  out {c['output']:>6,}  ${c['cost']:.4f}")
