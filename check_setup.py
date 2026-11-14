"""Confirms the three API keys and the embedding model work.  Run:  python check_setup.py"""
import os

from dotenv import load_dotenv

load_dotenv()

for key in ("TELEM_API_KEY", "TAVILY_API_KEY", "ANTHROPIC_API_KEY"):
    print(f"{key}: {'set' if os.getenv(key) else 'MISSING (add it to .env)'}")

from pipeline import tavily, telem  # noqa: E402

res = telem().search("Notion pricing small teams", num_results=2)
print(f"\nTelem search OK: {len(res.results)} results")
print("  engines that answered:", sorted({r.provider for r in res.results if r.provider}))
print("  first result:", res.results[0].title, "|", (res.results[0].summary or "")[:80])

page = tavily().extract(urls=[res.results[0].url], format="markdown")
got = page.get("results", [])
print(f"Tavily extract OK: {len(got[0]['raw_content']) if got else 0} characters "
      f"({len(page.get('failed_results', []))} failed)")

from llm import CHEAP, client  # noqa: E402

r = client().messages.create(model=CHEAP, max_tokens=200,
                             messages=[{"role": "user", "content": "Say 'ready' and nothing else."}])
print("Claude OK:", "".join(b.text for b in r.content if b.type == "text"))

from embed import embed  # noqa: E402

v = embed(["Notion raises prices", "Notion hikes its pricing"])
print(f"Embeddings OK: similarity {v[0] @ v[1]:.2f}")
print("\nAll set. Next:  streamlit run app.py")
