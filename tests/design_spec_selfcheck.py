#!/usr/bin/env python3
"""design_spec_selfcheck.py — docs/design/design-system-spec.md (#241).

WHAT THIS GUARDS. Tickets across this repo cite the design document by section (`§10 rule 01`,
`§05 rule 02`). Until now those citations pointed at a zip nobody could open without its own
renderer, so no reviewer could check whether a ticket quoted the rule correctly. This file is the
citation target; these checks keep it usable as one.

Two failure modes specifically:
  - a citation stops resolving because a heading lost its section number;
  - the standing reduced-motion rule evaporates when epic #152 closes, because this file was
    supposed to be its home and quietly is not.

Run: python3 tests/design_spec_selfcheck.py          (exit 0 = pass)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "docs", "design", "design-system-spec.md")
failed = []


def check(name, cond, why=""):
    print(("ok   - " if cond else "FAIL - ") + name + (("  <- " + why) if not cond and why else ""))
    if not cond:
        failed.append(name)


if not os.path.exists(SPEC):
    print("FAIL - docs/design/design-system-spec.md does not exist")
    sys.exit(1)

raw = open(SPEC, encoding="utf-8").read()
# The file is hard-wrapped AND the standing rule is a blockquote, so a phrase can be interrupted
# by both a newline and a "> " marker. Strip quote markers first, then collapse whitespace —
# otherwise a check fails on the FORMATTING while the content is perfectly present, which reads as
# a finding and is not one. (This exact false alarm has now happened twice.)
text = re.sub(r"\s+", " ", re.sub(r"^\s*>\s?", "", raw, flags=re.M))

# 1. All ten sections, each heading carrying its number so `§N` citations resolve by search.
heads = re.findall(r"^## (§\d\d) (.+)$", raw, re.M)
check("all ten sections are present", len(heads) == 10, "found %d" % len(heads))
for n in range(1, 11):
    tag = "§%02d" % n
    check("%s has a numbered heading (citations resolve)" % tag,
          any(h[0] == tag for h in heads),
          "an issue citing %s must find it by searching this file" % tag)

# 2. The rules that other tickets actually cite today. If these strings drift, the citations in
#    #184, #183 and #262 silently stop matching the document they name.
for tag, phrase in (("§10", "44px minimum hit target"),
                    ("§10", "becomes a tap target"),
                    ("§05", "No cards, no pills"),
                    ("§05", "One violet per screen")):
    check("%s rule text present: %r" % (tag, phrase[:28]), phrase in text)

# 3. The honesty preamble. Without it this reads as a spec and someone "fixes" code to match a
#    number that was never measured.
check("states it is an extract of a picture, not a spec",
      re.search(r"extract of a picture, not a spec", text, re.I) is not None)
check("states the shipped app wins where the file is silent",
      re.search(r"the shipped app wins", text, re.I) is not None)

# 4. Known divergences. The 40px headline is the concrete one: it does not exist in theme.css and
#    a ticket already cited it by mistake, so recording it prevents the same wrong fix twice.
check("known divergences are recorded", "Known divergences" in text)
check("the 40px headline divergence is named",
      re.search(r"40\s*->\s*27px", text) is not None and "32px" in text,
      "the document's headline baseline never existed in theme.css")

# 5. The standing motion rule — the load-bearing reason this file had to exist before #152 closes.
check("the standing reduced-motion rule is carried across",
      re.search(r"prefers-reduced-motion", text) is not None
      and re.search(r"ships its .?prefers-reduced-motion.? fallback in the same change", text) is not None,
      "this file is the rule's tracked home; #152 can close only once it is here")
check("the rule is attributed to its dated source comment",
      "2026-07-28" in text and "#152" in text,
      "an unattributed rule is advice; a dated, sourced one is a rule")
check("the rule keeps its verification method (computed style, never screenshot)",
      re.search(r"animationName", text) is not None and re.search(r"never by screenshot", text, re.I) is not None,
      "backgrounded automation tabs freeze CSS animation, so a screenshot cannot prove motion")
check("the rule states what would falsify it",
      re.search(r"Falsified if", text) is not None)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all design-spec cases pass"))
sys.exit(1 if failed else 0)
