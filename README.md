# Claim Tester

**Pressure-test a business claim in about a minute: evidence for and against, reading only what matters.**

Consultants and analysts start with a hypothesis ("Notion is losing small-business customers"). The risk is finding only the evidence that agrees with it. Search tools and chatbots answer the question as asked. Claim Tester tries to disprove it.

## What it does

You type a claim. It returns:

- a verdict (supported, partly supported, contested, not supported, or not enough evidence) with a confidence level
- three sub-hypotheses, each with its own verdict and quoted evidence **for** and **against**, linked to the source
- how reliable the evidence is, what is missing, and suggested next steps
- the strongest case against the claim, and a sharper version of the claim that the evidence does support
- an evidence map, a memo to download, and a token scoreboard

## How it works

```
 claim or memo
      │
      ▼  Opus          reads a memo and lists the claims its conclusion depends on (optional)
      ▼  Opus          splits a claim into 3 assumptions, each with a "for" and an "against" query
      │
      │   ┌──────────────── for each assumption, in parallel ────────────────┐
      ▼   │                                                                  │
   Qdrant │  recall      passages from earlier tests, close in meaning       │
   Telem  │  skim        both queries in one request, auto-routed to the     │
          │              best engines; titles and summaries only             │
   embed  │  drop        repeated pages and the same story on other sites    │
   Haiku  │  screen      score 0-10, stance, source type for every result    │
   Haiku  │  re-search   if fewer than 2 strong results: new queries, once   │
   Tavily │  read        only the top 3, a place kept for each side; returns │
          │              only the passages relevant to the assumption        │
          │              (Telem fetch is the backup if a page will not open) │
          └──────────────────────────────────────────────────────────────────┘
      ▼  Opus          writes a verdict on each assumption and overall
      ▼  code          checks every quoted finding against the text of its source
      ▼  Qdrant        stores the passages read, for future claims
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

The rest of the stack:

| Part | Role |
|---|---|
| **Claude Opus 5.5** | Reads memos, splits claims, writes verdicts. Every answer is returned in a fixed schema |
| **Claude Haiku 5.5** | Screens every search result; rewrites queries when the evidence is thin |
| **fastembed, `bge-small-en-v1.5`** | Embedding model that runs locally: duplicate removal and memory, at no token cost |
| **Qdrant** (local mode) | Vector database holding every passage read, recalled for related claims so a page is never read twice |
| **Quote checker** | Plain code that verifies each quoted finding appears in its source |
| **Thread pools** | Three assumptions in parallel; up to three claims from a memo in parallel |
| **Token meter and test harness** | Every AI call is metered; `bench.py` runs labelled claims against a baseline |
| **Streamlit** | The page: red-flag report, evidence cards, evidence map, architecture view |

## Results

See [results.csv](results.csv) and [bench_results.json](bench_results.json) for the true-or-false test: six claims with known answers, run through Claim Tester and through a plain "search + chatbot" baseline.

| Claim | Known answer | Claim Tester | Search + chatbot |
|---|---|---|---|
| AWS is the largest cloud infrastructure provider by market share | True | Supported ✓ | Supported ✓ |
| Nvidia's data center business generates most of its revenue | True | Supported ✓ | Not enough evidence ✗ |
| Netflix has grown its paid subscribers since its 2022 ad-supported plan | True | Supported ✓ | Supported ✓ |
| WeWork has never filed for bankruptcy | False | Not supported ✓ | Not supported ✓ |
| Peloton's revenue has grown every year since 2021 | False | Not supported ✓ | Not supported ✓ |
| US office vacancy rates have fallen since the shift to remote work | False | Partly supported ✗ | Partly supported ✗ |
| **Correct** | | **5 of 6** | **4 of 6** |

Measured on 14 November 2026, one run per claim:

- **Against reading everything:** opening every search result in full would have used 10 times the tokens. Claim Tester used 90% fewer tokens and 95% less reading cost.
- **Cost and time:** $0.15 and 72 seconds per claim on average.
- **Against the chatbot baseline:** the chatbot reads only 5 pages, so it is quicker and slightly cheaper overall ($0.78 against $0.91 for the six claims). It was also less accurate, and it gives one answer with no evidence against.

Caveats: six claims is a small sample. The one miss by both tools is an ambiguously worded claim: vacancy rose overall after 2020, but has edged down from its peak, so "partly supported" is defensible.

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
| `memory.py` | Evidence memory in a local Qdrant vector database |
| `app.py` | The Streamlit page |
| `bench.py`, `claims.json` | The true-or-false test |
| `DECISIONS.md` | The planning log: every idea considered and why |

## Limits

- It reads the public web only: no client data, paid research or interviews.
- A verdict is a first pass for an analyst to check, not a final answer. Every finding links to its source.
- Stance and source-type labels are made from a result's title and summary and can be wrong.
- The "read everything" figure on the scoreboard is counted with Anthropic's token counter, not run, unless the checkbox is ticked.


