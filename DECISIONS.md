# SearchHack: Decisions Log

Brainstorm notes from 2026-11-11 onward, recorded before the hackathon.

> **The current plan is in section 10 (the Hypothesis Tester).** Sections 1–9 are kept as the record of how the idea developed. Where they disagree with section 10, section 10 wins.

## 1. Constraints (from the interview)

| Question | Answer | Why it matters |
|---|---|---|
| Skill level | Beginner, but has called an API before | Keep the scope small and use familiar tools (Python, a simple UI) |
| Time / team | ~~10 hours~~ **About 4¾ hours of real building time** (11:00–4:15, minus lunch), probably solo | Build one sharp idea, not a big app. See section 6 for the event-day plan |
| Required tool | Telem AI (https://telem.ai/) | The idea has to show off what Telem does best |
| Demo style | "Clever technique" | Needs a measurable before/after number, not just a nice UI |
| What counts as clever | Saving tokens + smarter routing | Directly matches the hackathon's "faster, cheaper retrieval" and "routing" directions |
| Personal interest | Consulting projects | Gives a believable user: a consultant who needs fast research briefs |
| Everyday pain points (notes, study, video, code) | None of these | Skipped personal-data search ideas and used the consulting angle instead |

## 2. What Telem AI provides (and why it shapes the idea)

Telem is a routing layer over web search engines (Exa, Brave, Tavily, Perplexity, You.com, and others) with tracing built in.

- **Search API**: send one query to several engines. Choose them yourself (`providers.include`) or let `auto_routing: "accuracy"` pick.
- **Tiers** (`minimalist` → `default` → `extended` → `max`): control how much text comes back. **This is the main token-saving lever.**
- **Filters**: `num_results`, `include_domains`, `published_after` / `published_before`. **These are the routing levers.**
- **Fetch API**: clean page text for up to 5 URLs per call.
- **Monitors API**: scheduled searches that return only new items.
- **Observe console**: per-call cost, success rate, and quality. **This is the proof for the judges.**
- **Python SDK**: `pip install telem-sdk`. $20 free credit, about 4,000 queries.
- Not offered: memory or embeddings. This is why memory and graph ideas were ruled out.
- Telem's homepage advertises "37% fewer tokens" from its auto-routing. These are the company's own numbers. **Measure our own numbers; don't quote theirs.**

## 3. Ideas considered

### The test every idea must pass
The hackathon brief says: *"Retrieval that goes beyond keyword matching. Keyword search doesn't solve this, and neither does putting a chatbot on top of it."* Each idea below is checked against two questions **before** its description:

- **Q1. Does it go beyond keyword matching?** Does it decide what's relevant by *meaning or intent*, not by matching words?
- **Q2. Is it more than a chatbot on top?** Does *our own code* make retrieval decisions (what to search, what to read, what to throw away), or does it just pass search results to an LLM and display the answer?

Every check ends with a **"How it could fail"** note. These are shortcuts that would quietly turn the project back into keyword search or a chatbot wrapper.

### Idea 1: "Budget Brief", a research agent that saves tokens ⭐ CHOSEN AS CORE

> **Q1. Beyond keyword matching? ✅ Yes, if built right.**
> Telem's engines (e.g. Exa, which searches by meaning) find the candidates. Then our pipeline judges each snippet by whether it *answers the question*, using a cheap LLM or embeddings, not by counting shared words. Trimming works the same way: keep the paragraphs whose *meaning* matches the question. A page about "rivals in team wikis" survives a question about "Notion competitors" even with no keyword overlap.
>
> **Q2. More than a chatbot on top? ✅ Yes.**
> The LLM only writes the final brief. Before that, our code decides what's worth reading at all: cheap snippets first, ranking, dropping duplicates, fetching only the top 3, and trimming. That's a retrieval strategy, and the token scoreboard proves it changes the outcome.
>
> **How it could fail:** if ranking or trimming uses keyword overlap (e.g. "does the paragraph contain the word 'competitor'?"), it fails Q1. If the smart pipeline is skipped and everything is sent to the LLM, it fails Q2. **Rule: rank and trim by meaning (LLM score or embedding similarity), never by word matching.**

A consultant asks a question and gets back a cited one-page brief, plus a scoreboard comparing two approaches:
- **Naive:** search several engines, fetch everything in full, send all of it to the LLM.
- **Smart:** search with the `default` tier (titles + short summaries; `minimalist` turned out to return titles only, too little to rank on), have a cheap model score the results, drop duplicate URLs, fetch only the top 3, and trim them to the relevant paragraphs.

**Why chosen:**
- It produces a clear, measurable number (tokens and cost saved), which matches "clever technique."
- It uses Telem's distinctive features (tiers, fetch, Observe).
- It's a simple linear pipeline that a beginner can finish in 10 hours.
- The consulting use case makes the demo relatable.

### Idea 2: "Consulting Router", picking the right engine for each question type ➕ CHOSEN AS STRETCH

> **Q1. Beyond keyword matching? ⚠️ Only if the classifier understands intent.**
> The router has to work out what *kind of answer* the question needs (fresh news? official facts? customer opinions?) and change *where and how* it searches to match. "How do people feel about Notion's pricing?" is a sentiment question even though it never says "review" or "sentiment." Only an intent classifier (an LLM call that returns a label) catches that.
>
> **Q2. More than a chatbot on top? ✅ Yes.**
> It changes the search itself (engines, date window, domains, tier) *before* anything reaches an LLM, and shows its reasoning. A chatbot can't do that because it only sees whatever results it's given.
>
> **How it could fail:** a keyword if/else router (`if "news" in question: ...`) is exactly the keyword matching the brief rejects. **Change from the earlier plan:** the stretch goal is now an *LLM intent classifier*, not if/else rules.

An LLM intent classifier labels the question and sets Telem parameters to match:

| Question type | Routing decision |
|---|---|
| Recent news | `published_after` = last 30 days |
| Company facts | `include_domains` = company site + LinkedIn |
| Customer sentiment | Reddit/Yelp/Amazon-style sources |
| Market overview | 2 broad engines, `default` tier |

The tool shows *why* it routed each question that way. Compare against Telem's `auto_routing` and against searching every engine.

**Why it's only a stretch goal:** it covers the "smarter routing" interest, but a fair comparison needs a test set and some kind of relevance judgment, which is risky in 10 hours. A basic if/else version can sit on top of Idea 1 if time allows.

### Idea 3: "Client Watch", competitor monitoring ❌ NOT CHOSEN

> **Q1. Beyond keyword matching? ⚠️ Weak.**
> Telem's monitors find new items by re-running a search. Deciding whether an item is *actually* new (not the same story reworded by another outlet) needs meaning-based duplicate detection, and we'd have to build that ourselves.
>
> **Q2. More than a chatbot on top? ⚠️ Borderline.**
> Without the duplicate detection, it's a scheduled search plus an LLM summary, which is close to the "chatbot on top" the brief rejects.
>
> **How it could fail:** most of the cleverness comes from Telem's feature, not our code. This is another reason it wasn't chosen.

Uses Telem Monitors to report only new items about competitors, so old items are never sent to the LLM again.

**Why rejected:** it's practical, but there's no strong "clever technique" moment. Monitors run on a schedule, which makes a live demo hard in a 10-hour event.

### Ruled out early
> **Q1/Q2 not checked.** These were dropped because they didn't fit the user's interests or Telem's features, before the test applied.

- **Personal notes, study material, video, or code search:** none of these matched a pain point the user has, and Telem is a web search tool.
- **Memory systems and knowledge graphs:** Telem has no memory or embeddings feature, so these would mean building extra infrastructure. Too much for a solo beginner.

## 4. Original plan: Idea 1 core + Idea 2 stretch (superseded by section 6)

> This was planned for 10 hours, before the real schedule arrived. Section 6 replaces the timeline below.

**Tech choice:** Python + Telem SDK + one LLM API + Streamlit for the UI.
**Why:** this is the fewest moving parts, and Streamlit turns a Python script into a web page without any frontend code.

| Hours | Task | Reasoning |
|---|---|---|
| 0–1 | Telem key working; first `search` and `fetch` | Setup is the most common way beginners lose time, so clear it first |
| 1–3 | Naive pipeline: search → fetch all → LLM brief → count tokens | You need a baseline before you can claim savings |
| 3–6 | Smart pipeline: default tier (summaries) → rank by meaning → dedupe → fetch top 3 → trim by meaning | This is the core technique, so it gets the most time. Ranking and trimming by meaning is what passes Q1 |
| 6–7 | Run 5 test questions through both pipelines and record the numbers | Real measured numbers are the demo |
| 7–8.5 | Streamlit UI: question box, brief, comparison table | Make the numbers visible to judges |
| 8.5–9.5 | Stretch: LLM intent-classifier router | Only if the core works. Uses an LLM, not if/else rules, so it passes Q1 |
| 9.5–10 | Rehearse the demo; screenshot the Observe console | A working demo with a clear story beats extra features |

## 5. Final idea and starter project (decided 2026-11-11)

**Final pick: "Smart Research Brief"**, which combines Idea 1 and Idea 2. It works out what kind of answer is needed (router), searches in the right places, reads only what matters (rank + trim by meaning), and writes a cited brief. A scoreboard compares it against the naive pipeline.

| File | What it does | Plan hour |
|---|---|---|
| `check_setup.py` | Confirms both API keys work | 0–1 |
| `llm.py` | Claude calls + `Meter`, which counts tokens and cost for every call | — |
| `pipelines.py` | `naive()`, `smart()`, `route()`, `rank()`, `trim()`, `dedupe()` | 1–6, 8.5–9.5 |
| `bench.py` | Runs 5 test questions through both pipelines and writes `results.csv` | 6–7 |
| `app.py` | Streamlit demo: scoreboard, two briefs side by side, the smart pipeline's decisions | 7–8.5 |

**Decisions made while building:**
- **Models:** Claude Haiku 5.5 does the cheap judging (route, rank, trim) and Claude Opus 5.5 writes the brief. **Why:** judging is simple and repeated many times, so a cheap model is enough. The brief is what judges read, so it gets the strongest model. The scoreboard counts tokens from *every* model call, Haiku's included, so the savings aren't hidden.
- ~~Trimming uses an LLM, not embeddings.~~ Replaced by the local-embeddings decisions below.

**Local embeddings added (fastembed + `BAAI/bge-small-en-v1.5`, which runs on the laptop for 0 tokens and $0):**
- **Tested before trusting it.** Question: *"How do customers feel about Notion's pricing?"* The embedding model scored *"Notion's office is in San Francisco"* (0.63) above a real pricing complaint that never says "Notion" (0.52), and gave the complaint about the same score as cookie-policy junk. Two local rerankers (MiniLM, bge-reranker-base) made the same mistake. **Conclusion: small local models still lean on shared words when relevance is subtle, so relevance *judging* stays with Haiku.**
- **Embeddings are used where they're strong: "are these two texts the same thing?"**
  1. **Duplicate removal by meaning** (`dedupe_meaning`): drops the same story from different sites. Cutoff 0.83: same story measured 0.85, two different "Notion vs X" articles 0.79. The margin is narrow, so every drop is shown in the log.
  2. **Semantic memory** (`memory.py`): a reworded repeat question reuses the earlier brief for 0 tokens. Cutoff 0.86: rewordings measured 0.88–0.97, and "Notion pricing" vs "*Asana* pricing" 0.77. A wrong match gives the wrong company's answer, so the UI shows which question matched and memory can be switched off or cleared. This covers the "memory / user history" direction in the hackathon brief.
  3. **Cheap pre-filter before Haiku** (in `trim`): pages with more than 12 paragraphs keep only the half closest to the question before Haiku reads them. It's deliberately generous (it only removes the obvious junk) because the model's sense of relevance is weak.
- **Q1 check:** stronger than before. Meaning is now used at five points: memory, router, duplicate removal, ranking, trimming.
**Blind quality judge added (`judge.py`):**
- **Why:** the token savings alone invite the question "cheaper, but is it worse?" The judge turns the claim into *"X% cheaper at quality A vs B."*
- **Blind:** the two briefs are shuffled into "Brief 1" and "Brief 2" so the judge can't tell which pipeline wrote which. Models tend to favour the first answer they see, and shuffling cancels that out. Tested: scores mapped back to the correct pipeline in 40/40 shuffled runs.
- **Fixed rubric:** answers the question / specificity / evidence (citations) / client-ready, each 1–10. The overall score is averaged **in code**, and the judge is told length is not quality.
- **Opus judges,** with its tokens on a separate meter, so judging doesn't count against either pipeline.
- **Known limitation:** the judge sees the briefs, not the sources, so it grades usefulness, not factual accuracy. The citation checker (not built yet) would cover that.
- **Considered but not built yet:** search again when results are weak, the citation checker, and a comparison with Telem's auto-routing.

- **The benchmark runs with memory off** so the naive vs smart comparison stays fair. Memory is demoed separately (ask the same question twice in different words).
- **The naive pipeline is capped at 15 pages** so a single run can't get expensive. The cap is the same in every comparison, so it stays fair.
- **The smart pipeline reads at most 3 pages,** and only those scoring 5/10 or higher, so it can read fewer if nothing is relevant.
- **Brief call has `fallbacks="default"` turned on:** if Opus declines a request, the API retries it on a fallback model instead of failing the demo.
- **The router uses review sites (Reddit, G2, Trustpilot, Capterra, HN) for sentiment questions** through `include_domains`. **Why:** Telem's site-specific providers weren't fully documented, and domain filters are.

## 6. Event-day plan (real schedule)

| Official schedule | |
|---|---|
| 10:00 | Check-in, team formation |
| 10:30 | Kickoff, rules, judging criteria |
| 11:00 | Building starts |
| 1:00 | Lunch |
| **4:15** | **Submissions due**, demo prep |
| 4:30 | Judging |
| 5:30 | Final presentations (probably the top teams) |
| 6:15 | Winners announced |
| 7:00 | Wrap |

**Key fact: about 4¾ hours of building (11:00–4:15 minus lunch), not 10.** Submissions close 15 minutes before judging, so **treat 4:00 as the real deadline.**

### ✅ Answered (2026-11-13): the rules require using Telem AI and disclosing anything done before the competition
**Decision:** no more coding before the event. Time goes into brainstorming and fleshing out the idea instead. **Everything already made counts as pre-work and must be disclosed:** this document, the brainstorm, and the prototype code (whether or not it's used on the day).

### (Earlier) Open question: is pre-built code allowed?
The rules didn't say at first. Hackathons differ: many require the project to be built during the event, while allowing libraries, public tutorials and boilerplate; others allow existing code if you disclose it. **Never pretend pre-built code was written on the day.** If a judge asks, being caught out disqualifies you.

How to settle it, in order:
1. **Before the event:** message the organisers (email, Discord, or the event page contact). Template: *"Hi! Is it okay to bring code I prototyped before the event if I disclose it in my submission, or should everything be written during the hackathon?"*
2. **No reply:** ask at check-in (10:00) or right after the kickoff (10:30), before building starts.
3. **Still unclear:** play it safe and use **Case B**.

### Case A: Pre-built code allowed (disclose it in the submission)
| Time | What to do | Why |
|---|---|---|
| 10:00–10:30 | Check in, get a table with an outlet, start the app | Find setup problems before the clock starts |
| 10:30–11:00 | Note the judging criteria; find the Telem team | The criteria say what to optimise; sponsors help when APIs break |
| 11:00–11:45 | Try 3–4 real questions; fix what breaks | First contact with real data always finds bugs |
| 11:45–1:00 | Run `bench.py`; check the "dropped" lines and tune the cutoffs | Real numbers are the demo |
| 1:00–1:30 | Lunch | Tired brains write bugs |
| 1:30–2:45 | One extra: the answer-key check, or whatever the judging criteria reward. **Feature freeze at 2:45** | Something that works beats something ambitious that's broken |
| 2:45–3:30 | Slides (5 max) + backup screen recording | The live demo can fail on event wifi |
| 3:30–4:00 | Write and **submit by 4:00** | Submission sites slow down near the deadline |
| 4:00–4:30 | Rehearse the 3-minute pitch out loud 2–3 times | |

### Case B: Everything written on the day (the safe default)
**Scope cut to the core:** search → Haiku ranks the results by meaning → read the top 3 → Opus writes the brief, plus the token scoreboard comparing it with the naive pipeline. This still passes Q1 and Q2 (section 3). **Mention as "next steps" in the pitch:** semantic memory, duplicate removal by meaning, the embedding pre-filter, the router, the blind judge.

| Time | What to do |
|---|---|
| 10:00–11:00 | Check in, kickoff. Create the venv and install libraries (allowed: that's setup, not project code) |
| 11:00–11:30 | First Telem search + first Claude call working |
| 11:30–1:00 | Naive pipeline + smart pipeline (rank → top 3 → brief) + token counting |
| 1:00–1:30 | Lunch |
| 1:30–2:30 | Streamlit page with the scoreboard; run 3 test questions for numbers |
| 2:30–3:00 | Stretch only if everything works: the router (one Haiku call). **Feature freeze at 3:00** |
| 3:00–3:30 | Slides + backup screen recording |
| 3:30–4:00 | **Submit by 4:00** |
| 4:00–4:30 | Rehearse the pitch |

**How to prepare for Case B without breaking the rules:** what you *know* isn't restricted. Use the current code as a study guide: read it, understand each step, and **practise rebuilding the core from scratch at home 1–2 times**. Each rebuild should be faster. On the day, write it fresh.

## 7. Before the hackathon

- [ ] Sign up at app.telem.ai and claim the $20 free credit
- [ ] Create an API key (starts with `tlm_`) and run the quickstart search
- [ ] Confirm which LLM API key you'll use for writing the brief
- [ ] Message the organisers about pre-built code (template in section 6)
- [ ] Put real keys in `.env`; run `check_setup.py` and one question in the app (the most important item: this also downloads the embedding model)
- [ ] Run `bench.py` once to see real numbers and cost
- [ ] Practise rebuilding the core pipeline from scratch (for Case B)
- [ ] Draft the slides and submission text with blanks for the numbers
- [ ] Draft 5 consulting test questions (e.g. "Who are Notion's main competitors in the SMB market?")

## 8. Open questions

- Which LLM provider (your own key, or one the hackathon provides)?
- ~~Should the starter project be built before the event, or is that against the rules?~~ Resolved: pre-work is allowed if disclosed, and the user chose to **rebuild fresh on the day** (section 9).
- Project name? (ideas in section 9)
- A real personal story from consulting work to open the pitch?

## 9. Fleshing out the idea (2026-11-13)

**Decision: rebuild fresh on the day, using the Case B scope (section 6).** The existing prototype is only a study guide. **Disclose in the submission:** the brainstorming and planning (this document) and the earlier exploratory prototype, while stating that the submitted code was written during the event.

### 9a. Pitch and story

**Who it's for:** analysts and junior consultants doing desk research (competitor scans, customer sentiment, market overviews). Also any team running AI research agents at scale, where every wasted token costs money.

**The problem:** AI research tools read *everything* they find (menus, ads, duplicate stories, off-topic pages) and you pay for every word. More text also means more noise for the model to sift through.

**The insight:** a good analyst doesn't read every page. They **skim the headlines, pick the best few, and read only what matters.** Our pipeline works the same way.

**The solution in four words: Skim → Judge → Read → Write.**
1. **Skim:** Telem search returns titles + short summaries only
2. **Judge:** a cheap model (Haiku) scores each result on whether it actually answers the question, *by meaning, not keywords*
3. **Read:** fetch only the top 3, keep only the useful paragraphs
4. **Write:** the strong model (Opus) writes a cited one-page brief from that small, clean pile

**The proof:** the same question run both ways, side by side: tokens, cost, quality.

**3-minute pitch script** (fill in the blanks with numbers from the day):
> **[0:00 Hook]** "Every time an AI research agent answers a question, it reads dozens of pages, and most of it is junk. You pay for every word."
> **[0:20 Insight]** "Good analysts don't read everything. They skim, pick the best sources, then read closely. We taught an AI pipeline to do the same, using Telem."
> **[0:40 Live demo]** Type a consulting question → click Run → point at the scoreboard. "Same question. The usual approach read ___ tokens. Ours read ___."
> **[1:40 Proof]** "Across ___ test questions: ___% fewer tokens, ___% cheaper, and the answers covered ___ of ___ must-have facts vs ___ for the expensive version."
> **[2:10 Why Telem]** "Telem made the skim step possible: one API across many search engines, a cheap summary-only search for skimming, and fetch for reading only the winners. Here's Telem's own dashboard showing the difference."
> **[2:40 Next]** "Next: memory for repeat questions, meaning-based duplicate removal, and routing each question to the right sources."

**Name ideas:** *SkimFirst*, *ReadLess*, *Analyst Mode*, *Skim*, *Brief.ly*. Pick one that's easy to say out loud.

**Questions judges are likely to ask, with answers ready:**
| Question | Answer |
|---|---|
| "Isn't this just RAG?" | "RAG retrieves and stuffs. We decide *what's worth reading* before reading it, and we measure what that saves." |
| "How do you know quality didn't drop?" | "We compared both briefs against must-have facts for each question" (plus the blind judge, if built). "Here are the results, including where we lost." |
| "Why not just use a cheaper model?" | "We do, for the judging. The expensive model only writes the final answer, from a much smaller input." |
| "What was hardest?" | Prepare an honest one on the day (likely: getting ranking to judge meaning, not keywords). |
| "How did you use Telem?" | Search with summaries (skim), fetch (read), and the Observe console (proof). |
| "What would you do with more time?" | Memory, duplicate removal by meaning, routing, a citation checker. |

### 9b. Showcasing Telem (required by the rules, and it impresses the sponsor)

- **The technique is built on Telem's features:** the summary-only search *is* the skim step, and fetch *is* the read step. Say this explicitly in the pitch.
- **Use Telem's own dashboard as proof.** The SDK's `search()` and `fetch()` accept `session` and `metadata`. Tag every call `{"pipeline": "naive"}` or `{"pipeline": "smart"}`, then screenshot the **Observe console** showing call counts and costs side by side. Proof from the sponsor's own tool is more convincing than proof from ours.
- **Show multiple engines.** Mention that one Telem call searches several providers (Exa, Brave, Tavily...) and returns them in one format, so we didn't integrate each engine separately.
- **Stretch:** compare our ranking against Telem's built-in `auto_routing`, and present the result whichever way it goes.
- **"Next step" with Monitors:** "watch a client's competitors daily, and only read what's new." This is a natural extension using another Telem product.
- **At the kickoff:** introduce yourself to the Telem team and ask, *"Which feature would you most like to see used well?"* Then use it.

### 9c. Risks and backup plan

**Milestones:** each one is a working demo on its own, so if time runs out you still have something to show.
| By | Milestone | Demo if you stop here |
|---|---|---|
| 12:00 | One Telem search + one Claude brief working | "Here's a brief from live web search" |
| 1:00 | Naive vs smart both running, token counts printed in the terminal | Terminal side-by-side with numbers |
| 2:30 | Streamlit page with scoreboard + 3 test questions run | The full demo |
| 3:00 | (Stretch) Router or must-have-facts check. **Feature freeze** | Bonus |

**Risks:**
| Risk | Prevention | If it happens anyway |
|---|---|---|
| API key / credit problems | Create accounts and test keys **before** the event (account setup isn't project code) | Ask the Telem team at their booth immediately |
| Event wifi fails | Phone hotspot ready | Backup screen recording + screenshots |
| Rebuilding takes longer than planned | Milestones above; practise the flow mentally using the study guide | Present whichever milestone was reached |
| Smart brief is noticeably worse | Tune: read the top 5 instead of the top 3 | Present it honestly as a trade-off: "X% cheaper for Y% less coverage." Judges respect honest results |
| Router's site filter returns nothing useful | Keep the router a stretch goal | Fall back to an unfiltered search |
| Some page fetches fail | Skip failed pages (Telem returns them with a `failed` status rather than an error) | Fewer sources, still works |
| Live demo breaks in front of judges | Record a backup video by 3:30 | Play the video, show the results table |
| Late submission | Draft the submission text **before** the event (disclose it) | Submit by 4:00 regardless of state |
| Python install problems on the day | Install Python + libraries before 11:00 | Ask a mentor; Telem also has a JavaScript SDK |

**Backup idea (if the main build collapses by 1:00): "The Tier Experiment."**
A small Telem study that needs very little code: run the same 3 questions through Telem at each tier (`minimalist`, `default`, `extended`) and measure the tokens returned and the quality of the brief Claude writes from each. Present it as findings: *"How much context does an AI search answer actually need?"* It still uses Telem, still has a clever technique story, and works as a terminal script plus a results table.

## 10. Current plan: the Hypothesis Tester (2026-11-13 to 11-14)

### 10a. What it is
A research assistant for consulting questions. You type a claim (or an open question). It breaks the claim into three sub-hypotheses, uses Telem to search for evidence for and against each one, skims titles and summaries first, reads only the best few sources in full, and returns a verdict with the evidence behind it. A scoreboard compares its token use with a "read everything" version of the same job.

**The earlier skim-first idea (section 5) is the engine underneath.** The steps are the same: skim, judge, read, write.

### 10b. Why the idea changed
- **The trigger:** the question "what about research that goes against my question, maybe even disproving it?" The earlier design had a blind spot: it tended to confirm whatever the question assumed. Search engines match the question's framing, the scoring step dropped pages that didn't "answer" a loaded question, and the writer answered the question as asked.
- **Why it's better:** consultants already work this way (pressure-testing a hypothesis), and a tool that says "your assumption isn't supported" is a more memorable demo than "cheaper search" alone.
- **The cost:** searching both sides and three sub-hypotheses means more searching and judging per question, so the savings figure is measured against a read-everything version of the *same* job.

### 10c. The two test questions (section 3)
> **Q1. Beyond keyword matching? ✅** Opus splits the claim by reasoning about what would have to be true. Haiku scores each result on evidence strength and labels its stance, both judged by meaning. A source can contradict the claim without sharing any of its words.
>
> **Q2. More than a chatbot on top? ✅** Before any answer is written, the pipeline has chosen what to search (both sides), which sources to read, and which paragraphs to keep. A chatbot on top would read everything it was handed and agree with the question's framing.
>
> **How it could fail:** if the stance label or the "against" search is cut for time, it falls back to confirming the claim. If scoring is done by keyword matching, it fails Q1. **Rule: the scoring step with stance labels is not optional.**

### 10d. Other ideas considered on 2026-11-13
| Idea | Direction | Why not chosen |
|---|---|---|
| Issue-tree researcher | Agents that plan | Good fit; its splitting idea was absorbed into the sub-hypotheses |
| Engine scorecard (which engine wins for which question type) | Routing | Strong for the sponsor, but mostly a script and a table; less of a product |
| Claim checker (verify each claim in a text) | Verify, new interfaces | Tight for 4¾ hours |
| Client-aware search | User context | Risks being a prompt wrapper unless the context changes the search itself |
| Competitor map | Knowledge graphs | Leans on AI extraction more than retrieval; tight on time |
| Search across video and audio | Multimodal | Telem's support wasn't clearly documented; risky |

### 10e. The pipeline and who does each step
| Step | Done by | Why this choice |
|---|---|---|
| 1. Decide claim or open question; split into 3 sub-items; write the queries | **Opus** | The hardest thinking, and a mistake here spoils every later step. The input is one sentence, so a strong model adds almost no cost. (First planned for Haiku; changed after the user asked about quality.) |
| 2. Search: titles and short summaries | **Telem** | Several engines in one call; the "for" and "against" queries go in one request |
| 3. Drop repeats | **Plain code** (same web address) and **embeddings** (same story on different sites) | No token cost. Also stops one story counting as five sources |
| 4. Score each result 0–10, label stance and source type, pick the top 3 | **Haiku** | Runs for every result, so it must be cheap |
| 5. Fetch the top 3 pages | **Telem** | |
| 6. Keep only the paragraphs with evidence | **Haiku** | Reads the most text of any step; a stronger model here would undo the savings |
| 7. Write the verdicts | **Opus** | This is what the judges and the consultant read |
| 8. Show the page | **Streamlit** | A web page built in Python, running on the laptop |

Steps 2–6 repeat for each sub-hypothesis. **Call it a "pipeline" or "research assistant", not an "agent":** it follows fixed steps and doesn't choose its own next move.

**Fable vs Opus for the split:** untested. Try both on three claims on the day and compare. Stronger models answer more slowly, which shows in a live demo.

### 10f. Scoring rules
Haiku sees the sub-hypothesis and a numbered list of titles and summaries, all in one call, and returns three fields per result:
- **Evidence score, 0–10:** 0–3 off-topic or only shares words; 4–6 on-topic but no real evidence; 7–8 direct evidence for or against; 9–10 direct evidence with data.
- **Stance:** supports, contradicts, neutral.
- **Source type:** official data, independent research, news, user opinion, vendor marketing.

Then: drop anything under 5, read the top 3, and give one of the three places to a contradicting result if one scored 5 or more. **No forced balance:** if nothing credible contradicts the claim, the answer says so. Source type breaks ties and weights the verdict.

**Known limits:** Haiku judges from the summary only; scores can vary by a point between runs; source type is a guess. All three fields are shown in the log so they can be checked.

### 10g. Open questions as input
Example: "Who are Notion's competitors?" The same pipeline handles it with one extra field from step 1 (claim or open question):
- Sub-questions instead of sub-hypotheses; one query each; no stance label.
- The answer lists findings with evidence and notes where sources disagree.
- Source type matters more: "top 10 alternatives" articles are often written by a competitor.
- **Stretch:** find candidates first, then test each as a small claim.

**Demo focus is the claim path.** The open-question branch is added afterwards if time allows.

### 10h. Embeddings
- **Role:** remove the same story reported on different sites. Identical web addresses are removed by plain code.
- **Must not remove:** two sources that independently reached the same conclusion. The model can't always tell these apart (same story scored 0.85, different articles on a similar topic 0.79 in the earlier test), so every removal is logged with what it matched.
- **Build order:** after the core runs end to end. It's one function and one line between search and scoring, and it can be removed by deleting that line.
- **Installed 2026-11-13:** fastembed 0.9.1 and the `bge-small-en-v1.5` model (64 MB) in the project's `.models` folder, confirmed working offline. Two unused test models (about 1.1 GB) were deleted. Fresh code must point at `.models` or the model downloads again.

### 10i. What the consultant gets
The user's feedback on the first example: "this doesn't really help a consultant all that much." The short verdict alone was too thin. **Decision: layered output.** The verdict comes first; the detail opens underneath. For each sub-hypothesis:
- The verdict and a short paragraph of reasoning
- An evidence table: the finding (quoted), source, source type, date, stance, and a **clickable link to the exact page**
- How reliable the evidence is, and why
- What's missing
- Suggested next steps (data to request, people to interview)
- "So what" for the client

Also: numbered references in the text, a full source list, and the sources found but not read, with their scores.

**Honest limits to state in the pitch:** it sees only the public web (no client data, paid research or interviews); the AI can misstate a source, so the quoted passage is shown beside each link; it's "a first pass in minutes", not a finished answer.

### 10j. The page
Top to bottom: input box and button; overall verdict and confidence; a table of sub-hypotheses with verdicts and counts for and against; evidence sections that open on a click; the token scoreboard; a log of what the pipeline decided. Shown on the laptop, which is normal at hackathons.

### 10k. Keeping tokens down
1. Score all results for a sub-hypothesis in one call.
2. **Read only when the summaries disagree.** If every summary points the same way, give the verdict from the summaries and skip the fetch.
3. Reuse a fetched page across sub-hypotheses.

Changing a model changes the cost, not the token count, so the scoreboard shows both.

**Optional proof (not yet decided):** a keyword baseline as a third column, ranking the same results by shared words, to show the difference from keyword search directly.

### 10l. How Telem is used
Several queries in one call (both sides at once); summary-only search (the skim step); domain and date filters; fetch (the read step); call tags plus the Observe dashboard as proof of cost; Monitors as a "next step" in the pitch (re-test a hypothesis on a schedule). Telem's role is essential (all evidence arrives through it), while the judging and writing are done by Claude. Say in the pitch: "Telem's summary-only search is our skim step and its fetch is our read step."

### 10m. Build order for the day (11:00–4:15)
| By | Milestone |
|---|---|
| 12:00 | One claim → Telem search → Haiku's scores, stances and source types printed |
| 1:00 | One sub-hypothesis end to end: fetch, trim, Opus verdict, token count |
| 1:00–1:30 | Lunch |
| 2:15 | Opus split into 3 sub-hypotheses; the read-everything comparison |
| 2:45 | The Streamlit page |
| 3:00 | Embeddings, then the open-question branch if time. **Feature freeze** |
| 3:30 | Slides and a backup screen recording |
| 4:00 | Submitted |

**This is more than the earlier "core only" scope.** If the 1:00 milestone slips, drop the three sub-hypotheses and test the single claim with a "for" and "against" search. That is still a complete demo.

### 10n. Disclosure list
- This planning document and the brainstorming
- Check at the kickoff whether AI coding tools must be disclosed

### 10o. Presenting
Judges rarely ask for code. They want a working demo, a plain explanation of how it works, and results. Be able to explain every step in your own words. One snippet worth showing: the scoring instruction given to Haiku.

### 10p. Still open
- Which three claims and one open question to demo, and the must-have facts for each
- Project name
- A real consulting story to open the pitch
- What a consultant most wants at the end of the first hour of research (the user's own view)
