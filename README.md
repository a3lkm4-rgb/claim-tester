# Hypothesis Tester

**Pressure-test a business claim in about a minute: evidence for and against, reading only what matters.**

Consultants and analysts start with a hypothesis ("Notion is losing small-business customers"). The risk is finding only the evidence that agrees with it. Search tools and chatbots answer the question as asked. Hypothesis Tester tries to disprove it.

## What it does

You type a claim. It returns:

- a verdict (supported, partly supported, contested, not supported, or not enough evidence) with a confidence level
- three sub-hypotheses, each with its own verdict and quoted evidence **for** and **against**, linked to the source
- how reliable the evidence is, what is missing, and suggested next steps
- the strongest case against the claim, and a sharper version of the claim that the evidence does support
- an evidence map, a memo to download, and a token scoreboard

## How it works

```
claim
  │
  ▼  Opus          splits the claim into 3 sub-hypotheses, each with a "for" and an "against" query
  ▼  Telem         searches both queries in one request, auto-routed to the best engines;
  │                returns titles and short summaries only (the "skim")
  ▼  embeddings    drop repeated pages and the same story on different sites (local, no tokens)
  ▼  Haiku         scores every result 0-10 for evidence strength and labels its stance
  │                (supports / contradicts / neutral) and source type
  ▼  Tavily        opens only the top 3 per sub-hypothesis, keeping a place for each side,
  │                and returns only the passages relevant to that sub-hypothesis (the "read")
  ▼  Opus          writes the verdicts from that small, relevant set
  ▼  scoreboard    compares the tokens used with opening every result in full
```

Why it is not keyword search or a chatbot on top:

- **It decides what to search for.** It searches for evidence against the claim, not only for the claim as typed.
- **It judges by meaning.** A result is scored on whether it is evidence and which side it is on, not on shared words.
- **It decides what to read.** Most results are discarded from their summaries, before any page is opened.

## Sponsor tools

| Tool | Role |
|---|---|
| **Telem** | The skim: one request searches several engines with auto-routing and returns summaries. Calls are tagged so they appear in Telem's dashboard. Also the backup page fetcher. |
| **Tavily** | The read: query-aware extract returns only the relevant passages of each chosen page. Tavily is also one of the engines Telem routes to. |

Also used: Claude Opus 5.5 (split, verdict), Claude Haiku 5.5 (scoring), fastembed with `bge-small-en-v1.5` (duplicate removal), Streamlit (the page).

## Results

See [results.csv](results.csv) and [bench_results.json](bench_results.json) for the true-or-false test: six claims with known answers, run through Hypothesis Tester and through a plain "search + chatbot" baseline.

<!-- RESULTS -->

## Run it

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then add your Telem, Tavily and Anthropic keys
.venv\Scripts\python check_setup.py
.venv\Scripts\streamlit run app.py
```

Other entry points: `python run_once.py "your claim"` prints a run in the terminal, and `python bench.py` runs the true-or-false test on `claims.json`.

## Files

| File | What it is |
|---|---|
| `pipeline.py` | The whole process, one function per step |
| `llm.py` | Claude calls and the token meter |
| `embed.py` | Local embeddings |
| `app.py` | The Streamlit page |
| `bench.py`, `claims.json` | The true-or-false test |
| `DECISIONS.md` | The planning log: every idea considered and why |

## Limits

- It reads the public web only: no client data, paid research or interviews.
- A verdict is a first pass for an analyst to check, not a final answer. Every finding links to its source.
- Stance and source-type labels are made from a result's title and summary and can be wrong.
- The "read everything" figure on the scoreboard is counted with Anthropic's token counter, not run, unless the checkbox is ticked.


