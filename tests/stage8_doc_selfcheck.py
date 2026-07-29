#!/usr/bin/env python3
"""stage8_doc_selfcheck.py — the stage-8 input rules in docs/process/autonomous-run.md (#254).

WHAT THIS GUARDS. Stage 8 is the only gate that touches a real browser, and it has failed twice by
substitution rather than by error: a constructed KeyboardEvent kept #222 green while `?` was
broken, and a "the tool cannot do this" claim parked work that a differently-shaped call could
reach. Prose decays into advice; these are the load-bearing clauses, asserted as text.

Each check names the specific failure it prevents. A check that would still pass with the rule
gutted is not a check, so every assertion here is tied to a concrete phrase, not a topic word:
grepping for "keyboard" would pass on a doc that said the opposite.

Run: python3 tests/stage8_doc_selfcheck.py        (exit 0 = pass)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "docs", "process", "autonomous-run.md")
raw = open(DOC, encoding="utf-8").read()
# The doc is hard-wrapped at ~95 chars, so a load-bearing phrase can straddle a newline
# ("every check stayed\ngreen"). Matching against the raw text would fail on the WRAP rather than
# on the content, which is a false alarm dressed as a finding. Collapse whitespace first.
text = re.sub(r"\s+", " ", raw)
low = text.lower()
failed = []


def check(name, cond, why=""):
    print(("ok   - " if cond else "FAIL - ") + name + (("  <- " + why) if not cond and why else ""))
    if not cond:
        failed.append(name)


# 1. The prohibition must be absolute AND carry its evidence. "Prefer real events" is advice;
#    "never acceptable, and here is the ticket where the substitution hid a real bug" is a rule.
check("constructed KeyboardEvent is banned as evidence",
      re.search(r"constructed\s+`?KeyboardEvent`?\s+is\s+never\s+acceptable", text, re.I) is not None,
      "the ban must be stated as never-acceptable, not as a preference")
check("the ban cites #222, the case where it hid a real bug",
      re.search(r"#222", text) is not None and "stayed green" in low,
      "a rule without its scar tissue gets relaxed by the next reader")

# 1b. The ban's permitted half (#243 AC1, restored by #299). This repo's stage-4 runnable checks
#     ARE headless CDP; a doc that reads as a blanket ban forces every groomer to re-derive the
#     stage-4/stage-8 distinction in issue comments, which is the re-litigation the AC exists to
#     stop.
check("headless is stated legitimate at stage 4 and never as stage-8 evidence",
      re.search(r"legitimate as the stage-4 runnable check and never as stage-8 evidence",
                text, re.I) is not None,
      "without the permitted half the ban contradicts the repo's own runnable checks")

# 2. The working route. The three ingredients that were each proven necessary by a zero-event
#    variation: batching, the click, and the throwaway key. Losing any one silently returns the
#    reader to the broken path, so each is asserted separately.
check("the route requires ONE browser_batch", "browser_batch" in text,
      "unbatched calls deliver zero events")
check("the route requires a click before the key", re.search(r"left_click", text) is not None)
check("the route requires a throwaway key press", "throwaway" in low)
check("navigate must be outside the batch",
      re.search(r"navigate[^\n]*not\s+inside\s+the\s+batch", text, re.I) is not None,
      "navigate inside the batch was measured at zero events")

# 3. Evidence discipline: the tool lies by omission here. It reports success for a key the page
#    never received, which is exactly how a green check can mean nothing.
check("the doc says to read the page, not the tool's success report",
      re.search(r"read the logger, not the tool", text, re.I) is not None,
      "'Pressed 1 key' is reported whether or not the page saw it")

# 3b. Reproducibility honesty. The first version of this doc claimed a "4/4 reproducible" route;
#     it then failed twice in a row on the very next fresh window. A recipe stated as reliable,
#     that is not, is worse than no recipe: the next agent follows it, sees nothing, and either
#     gives up or fabricates. The doc must say intermittent AND give the retry-then-park bound.
check("the route is stated to be necessary but NOT sufficient",
      re.search(r"necessary but NOT sufficient", text) is not None,
      "a recipe presented as reliable, that is not, invites giving up or faking")
check("intermittency is named",
      re.search(r"intermittent", text, re.I) is not None)
check("a zero-event reading is framed as ordinary, not as breakage",
      re.search(r"zero-event reading as ordinary", text, re.I) is not None)
check("the retry bound before parking is stated",
      re.search(r"up to\s+three times", text, re.I) is not None,
      "an unbounded retry is how a run hangs instead of parking")
check("document.hasFocus is called out as an unusable signal",
      re.search(r"hasFocus\(\)[^.]*true", text) is not None,
      "it returned true during a zero-event run; trusting it would mislead the next agent")

# 3c. The precondition, confirmed by experiment on 2026-07-29. Without it the doc leaves the next
#     agent with "sometimes it works", which is indistinguishable from "the tool is broken" and
#     leads to a park that a five-second ask would have avoided.
check("OS-frontmost is stated as the confirmed cause, not a guess",
      re.search(r"Confirmed[^.]*frontmost", text, re.I) is not None,
      "'leading hypothesis' invites the next agent to ignore it")
check("the logger is named as the only reliable tell",
      re.search(r"only reliable tell is the logger", text, re.I) is not None)
check("the doc gives the specific small ask to unblock",
      re.search(r"bring Chrome to the\s*front and say so", text, re.I) is not None,
      "a park without a concrete human ask wastes the owner's availability")

# 3d. #243: the viewport route. Each clause below was bought with a measured failure, so losing
#     any of them returns the next agent to a trap that has already cost time twice.
check("the viewport route resizes BEFORE navigating",
      re.search(r"resize_window\s*->\s*BEFORE any navigation|BEFORE any navigation", text, re.I) is not None,
      "resize after navigation silently no-ops")
check("the maximised-window trap and its two-attempt budget are recorded",
      re.search(r"maximised window", text, re.I) is not None and re.search(r"two attempts", text, re.I) is not None,
      "attempt one lands maximised often enough that a one-shot route reads as broken")
check("size inheritance is recorded (a new tab is not a fresh default)",
      re.search(r"inherit the previous window", text, re.I) is not None)
check("the OS minimum width is recorded as a measured floor",
      re.search(r"606 is the floor", text, re.I) is not None,
      "without it, an agent will keep requesting 380 and recording a number it never got")
check("requested width is distinguished from measured width",
      re.search(r"requested width is a request", text, re.I) is not None,
      "recording the requested number is how a viewport claim becomes fiction")

# 3e. #243 inherits #254's confound rather than restating a cause it cannot support.
check("the viewport+keys combination is stated as untested, not as impossible",
      re.search(r"never been obtained in the same window", text, re.I) is not None
      and re.search(r"confounded", text, re.I) is not None,
      "the earlier version asserted 'narrow windows refuse keys', which the evidence cannot support")
check("the experiment that would settle the confound is named",
      re.search(r"experiment that settles it", text, re.I) is not None)

# 4. SUPERSEDED by 3e. This asserted the phrase "never been obtained together", which #243 rewrote
#    to "never been obtained in the same window" while correcting the CAUSE the sentence implied.
#    Keeping a second assertion on the old wording would only re-break whenever the sentence is
#    improved; 3e asserts the same guarantee plus the confound it must not drop.

# 5. Park procedure. A park that is not recorded is indistinguishable from work that was skipped.
check("a negative result is stated to be a pass",
      re.search(r"negative result is a pass", text, re.I) is not None)
check("an unrecorded park is stated NOT to be a pass",
      re.search(r"unrecorded park is not", text, re.I) is not None,
      "without this, 'I could not verify it' becomes silent")
check("parked tickets are barred from status:review",
      re.search(r"not earned\s+`?status:review`?|has not earned", text, re.I) is not None)
check("documenting a problem must not stand in for fixing it",
      re.search(r"stand in for|masquerade", text, re.I) is not None)

# 6. The shared taxonomy — the point is that it is SHARED and closed, so #243 and #254 cannot
#    each invent one. All four reasons must be present or the vocabulary has already forked.
for reason in ("no-session", "no-key-delivery", "no-viewport-control", "surface-unreachable"):
    check("park reason `%s` is in the taxonomy" % reason, reason in text)
check("the taxonomy names its residue (what a human must do)",
      low.count("residue") >= 1 and "~30 seconds" in text,
      "a park reason without a human next-step is a dead end")

# 7. The meta-rule that produced this whole section, and that was wrong twice.
check("'I tried and it did not work' is framed as a claim about the approach",
      re.search(r"statement about your approach", text, re.I) is not None)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all stage-8 doc cases pass"))
sys.exit(1 if failed else 0)
