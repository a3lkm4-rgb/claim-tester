# Devpost submission (paste each part into the matching field)

## Project name
Claim Tester

## Tagline (the one line under the name)
The audit layer for business claims: it searches for the evidence against you, reads only what matters, and checks its own quotes.

## Built with (tags)
python, telem, tavily, claude, anthropic, qdrant, fastembed, onnx, streamlit

## Try it out (links)
- GitHub repository: (add the link)
- Demo video: (add the link)

---

## About the project (the main story field)

## Inspiration
Every investment memo and strategy deck is a stack of claims: the market is growing, customers are loyal, a competitor is weak. In consulting work, the dangerous part is that you search for evidence and mostly find what agrees with you. Search tools and chatbots make this worse, because they answer the question as you asked it. I wanted a tool whose job is to argue back.

## What it does
Paste a memo or type a claim, such as "Peloton's revenue has grown every year since 2021". Claim Tester:

1. **Breaks the claim down** into three assumptions that would have to be true.
2. **Searches both sides.** For each assumption it looks for evidence for and against.
3. **Reads only what matters.** It screens every result from its summary, then opens only the strongest few.
4. **Returns a verdict** on each assumption: supported, contested, not supported or not enough evidence. Each comes with quoted evidence on both sides, linked sources, data gaps and next steps.
5. **Checks itself.** Every quote is verified word for word against its source.

Starting from a memo, it produces a **red-flag report**: which of the memo's key claims hold, and which do not.

## Results
On six claims with known answers, Claim Tester judged **5 of 6** correctly; a plain "search + chatbot" baseline judged 4 of 6. It used **90% fewer tokens** than opening every search result in full, at about **$0.15 and one minute per claim**. In three further runs, **40 of 40** quoted findings were verified against their sources. Six claims is a small sample, and the full results, including the miss, are in the repository.

## How I built it
- **Telem** does the skim. One request searches several engines with auto-routing, for and against at once, and returns only titles and summaries. Its fetch is the backup page reader, and every call is tagged for Telem's dashboard.
- **Tavily** does the read. Its query-aware extract opens only the chosen pages and returns only the passages relevant to each assumption. One page went from 26,300 characters to 3,100.
- **Claude Opus 5.5** reads memos, splits claims and writes verdicts. **Claude Haiku 5.5** screens every result for evidence strength, stance and source type, and rewrites the queries when evidence is thin.
- **A local embedding model** (bge-small, via fastembed) removes repeated stories at no token cost.
- **A Qdrant vector database** stores every passage read. Related passages are recalled for later claims, so the same page is never fetched or read twice.
- **A quote checker** in plain code verifies each finding against its source.
- Assumptions run in parallel, as do up to three claims from a memo. Every AI call is metered, and a test harness runs labelled claims against a baseline. The page is built in Streamlit.

## Why it is not keyword search or a chatbot on top
It decides what to search for, including the case against the claim. It judges each result by meaning: is this evidence, and for which side? And it decides what to read before reading it, which is where the token savings come from.

## The business
**Customer:** private equity and venture analysts doing due diligence, and boutique consulting firms.
**Product:** upload a deal memo and get a red-flag report on the claims it rests on, with an audit trail an investment committee can file.
**Why they keep paying:** claims go stale. Saved claims can be re-tested on a schedule (Telem Monitors is built for this), and every test adds to the firm's private evidence library.
**Why the technique matters:** at about $0.15 a claim, a 30-claim memo costs under $5 to test, which makes continuous re-testing affordable.
**Why not a general assistant:** assistants are built to be helpful and tend to agree. This is built to disagree, to show its sources, and to keep the record.
**Still unproven:** demand. The first step is interviews with ten analysts.

## Challenges
- Duplicate removal by meaning was too aggressive at first and dropped articles that only shared a topic. I raised the threshold after seeing it on real results.
- Many pages would not open. The tool now lines up spare sources and falls back to Telem's fetch.
- The local embedding model was poor at judging subtle relevance, so that job stays with Haiku and the embeddings handle duplicates and memory.

## What I learned
Reading less can be more accurate, because the model is not buried in noise. And a search that is told to look for disagreement finds it.

## What's next
Scheduled re-testing with Telem Monitors, analyst corrections that feed the firm's library, counting independent sources, and private documents alongside the public web.

## Disclosure
Before the event: brainstorming and planning (recorded in DECISIONS.md), an exploratory prototype of an earlier idea that was deleted before the event, and installing the fastembed library and its model. All code in the repository was written during the hackathon, with Claude Code as a coding assistant.

---

# Demo video script (aim for 2 minutes)

| Time | On screen | Say |
|---|---|---|
| 0:00 | Title | "Every deal memo is a stack of claims. Search tools find the evidence that agrees with you. This one argues back." |
| 0:10 | "Start from a memo" tab, load the sample memo, click Find the claims | "Here's a memo recommending an investment. The tool pulls out the claims its conclusion depends on." |
| 0:25 | Red-flag report (use a run finished beforehand) | "It tests them side by side. The central claim, that revenue has grown every year, comes back as a red flag." |
| 0:40 | Open that claim: evidence for and against, quote badges | "For each assumption it shows evidence on both sides, linked to the source. Every quote is verified against the page it came from." |
| 1:00 | Evidence map | "This is the whole argument in one picture." |
| 1:10 | Under the hood tab | "Telem skims several search engines at once. Tavily reads only the relevant passages of the best few pages. A vector database remembers what's been read." |
| 1:30 | Cost and method tab | "It used 90% fewer tokens than reading everything it found, for about fifteen cents a claim." |
| 1:40 | Results table in the README | "On six claims with known answers, it got five right. A search chatbot got four." |
| 1:50 | Title | "Claim Tester: the audit layer for business claims." |

Tip: run the memo test before recording, since it takes about two minutes. Record the result, not the wait.

# Screenshots for the image gallery (first one becomes the thumbnail)
1. The executive summary with a red "NOT SUPPORTED" badge and the headline numbers.
2. The red-flag report from the sample memo.
3. One assumption showing evidence for and against, with quote badges.
4. The evidence map.
5. The architecture diagram from the "Under the hood" tab.
