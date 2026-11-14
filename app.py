"""The page.  Run:  streamlit run app.py"""
import json
import textwrap
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from pipeline import run  # noqa: E402

COLOUR = {"supported": "green", "partly supported": "orange", "contested": "orange",
          "not supported": "red", "not enough evidence": "gray"}


def badge(verdict):
    return f":{COLOUR[verdict]}[**{verdict.upper()}**]"


def memo(r):
    """The whole result as a markdown memo the consultant can download."""
    rep, src = r["report"], {e["n"]: e for f in r["found"] for e in f["evidence"]}
    out = [f"# Claim: {r['claim']}", "",
           f"**Verdict: {rep.overall_verdict}** (confidence: {rep.confidence})", "", rep.summary, "",
           f"**Sharper claim:** {rep.sharper_claim}", "",
           f"**Strongest case against:** {rep.strongest_case_against}", "",
           f"**What would change the verdict:** {rep.would_change_verdict}", ""]
    for i, (f, sv) in enumerate(zip(r["found"], rep.subs), 1):
        out += [f"## {i}. {f['sub'].statement}", f"**{sv.verdict}.** {sv.reasoning}", ""]
        out += [f"- ({x.stance}) \"{x.quote}\" [{x.source}]" for x in sv.findings]
        out += ["", f"**Reliability:** {sv.reliability}", f"**Missing:** {sv.missing}",
                "**Next steps:** " + "; ".join(sv.next_steps), f"**So what:** {sv.so_what}", ""]
    out += ["## Sources"] + [f"[{n}] {e['title']} ({e['source_type']}) {e['url']}"
                             for n, e in sorted(src.items())]
    return "\n".join(out)


FILL = {"supported": "#c8e6c9", "partly supported": "#ffe0b2", "contested": "#ffe0b2",
        "not supported": "#ffcdd2", "not enough evidence": "#e0e0e0",
        "supports": "#c8e6c9", "contradicts": "#ffcdd2", "neutral": "#e0e0e0"}


def label(text, width=34, limit=110):
    """Shorten and wrap text so it fits in a box on the map."""
    text = textwrap.shorten(text, limit, placeholder="…").replace('"', "'")
    return "\\n".join(textwrap.wrap(text, width))


def evidence_map(r):
    """The argument as a picture: claim -> sub-hypotheses -> the sources read for each.
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


st.set_page_config(page_title="Hypothesis Tester", layout="wide")
st.title("Hypothesis Tester")
st.caption("Pressure-test a business claim: evidence for and against, reading only what matters.")

claim = st.text_input("Enter a claim to test", "Notion is losing small-business customers")
run_baseline = st.checkbox("Also run the read-everything version (slower, costs more; "
                           "gives a second verdict to compare quality)")

if st.button("Test this claim", type="primary") and claim:
    with st.status("Working...", expanded=True) as box:
        st.session_state["result"] = run(claim, run_baseline, status=box.write)
        save_to_library(st.session_state["result"])
        box.update(label="Done", state="complete", expanded=False)

r = st.session_state.get("result")
if r:
    rep, smart, base = r["report"], r["smart"], r["baseline"]
    sources = {e["n"]: e for f in r["found"] for e in f["evidence"]}

    st.subheader(f"Verdict: {badge(rep.overall_verdict)}  ·  confidence: {rep.confidence}")
    st.write(rep.summary)
    st.info(f"**Sharper claim the evidence supports:** {rep.sharper_claim}")

    st.table([{"Sub-hypothesis": f["sub"].statement, "Verdict": sv.verdict,
               "For": sum(x.stance == "supports" for x in sv.findings),
               "Against": sum(x.stance == "contradicts" for x in sv.findings)}
              for f, sv in zip(r["found"], rep.subs)])

    st.subheader("Evidence map")
    st.caption("Each box on the right is a source that was read. "
               "Green supports, red contradicts, grey is neutral.")
    st.graphviz_chart(evidence_map(r), width="stretch")

    for i, (f, sv) in enumerate(zip(r["found"], rep.subs), 1):
        with st.expander(f"{i}. {f['sub'].statement}  —  {sv.verdict}"):
            st.markdown(f"{badge(sv.verdict)}  {sv.reasoning}")
            left, right = st.columns(2)
            for col, stance, title in ((left, "supports", "Evidence for"),
                                       (right, "contradicts", "Evidence against")):
                with col:
                    st.markdown(f"**{title}**")
                    items = [x for x in sv.findings if x.stance == stance]
                    if not items:
                        st.caption("None found." if stance == "supports" else
                                   "We searched for evidence against this and found none.")
                    for x in items:
                        e = sources.get(x.source)
                        link = f"[[{x.source}] {e['title']}]({e['url']}) · {e['source_type']}" \
                            if e else f"[{x.source}]"
                        st.markdown(f"> {x.quote}\n\n{link}")
            st.markdown(f"**How reliable:** {sv.reliability}  \n**What's missing:** {sv.missing}  \n"
                        f"**Next steps:** {'; '.join(sv.next_steps)}  \n**So what:** {sv.so_what}")
            st.caption(f"Searched for: \"{f['sub'].query_for}\"  and against: "
                       f"\"{f['sub'].query_against}\"")
            st.dataframe([{"Read": "yes" if x["read"] else "", "Score": x["score"],
                           "Stance": x["stance"], "Source type": x["source_type"],
                           "Title": x["title"], "Link": x["url"]} for x in f["rated"]],
                         column_config={"Link": st.column_config.LinkColumn()},
                         hide_index=True)

    a, b = st.columns(2)
    a.warning(f"**Strongest case against:** {rep.strongest_case_against}")
    b.warning(f"**What would change the verdict:** {rep.would_change_verdict}")

    st.subheader("Token scoreboard")
    st.table([
        {"Approach": "Read everything", "Pages read in full": base["pages"],
         "Tokens read by AI": f"{base['input_tokens']:,} ({base['how']})",
         "Reading cost": f"${base['input_cost']:.3f}"},
        {"Approach": "Hypothesis Tester", "Pages read in full": smart["pages"],
         "Tokens read by AI": f"{smart['input_tokens']:,} (measured)",
         "Reading cost": f"${smart['input_cost']:.3f}"}])
    k1, k2, k3 = st.columns(3)
    if base["input_tokens"]:
        k1.metric("Tokens saved", f"{1 - smart['input_tokens'] / base['input_tokens']:.0%}")
    if base["input_cost"]:
        k2.metric("Reading cost saved", f"{1 - smart['input_cost'] / base['input_cost']:.0%}")
    k3.metric("Total cost of this test", f"${smart['total_cost']:.3f}",
              help="All AI calls, including writing the answer")
    st.caption(f"Took {r['seconds']:.0f} seconds. 'Read everything' = every search result opened "
               f"in full and given to Opus (capped at 30 pages). "
               f"'{base['how']}' = how that token figure was obtained.")

    if base["report"]:
        st.subheader("Quality check: the read-everything verdict")
        st.markdown(f"{badge(base['report'].overall_verdict)} · confidence: "
                    f"{base['report'].confidence}  \n{base['report'].summary}")
        st.table([{"Sub-hypothesis": f["sub"].statement, "Hypothesis Tester": sv.verdict,
                   "Read everything": bv.verdict}
                  for f, sv, bv in zip(r["found"], rep.subs, base["report"].subs)])

    st.download_button("Download as a memo", memo(r), file_name="claim-memo.md")
    with st.expander("What the pipeline decided"):
        for i, f in enumerate(r["found"], 1):
            st.markdown(f"**Sub-hypothesis {i}**\n\n" + "\n".join(f["log"]))
        st.table(r["meter"].calls)

library = load_library()
if library:
    with st.expander(f"Claim library: {len(library)} claims tested so far"):
        st.dataframe([{"Date": e["date"], "Claim": e["claim"], "Verdict": e["verdict"],
                       "Confidence": e["confidence"], "Sharper claim": e["sharper_claim"],
                       "Sources": len(e["sources"])} for e in reversed(library)],
                     hide_index=True)
