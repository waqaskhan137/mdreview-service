#!/usr/bin/env python3
"""Regression guard for the rules in `docs/process/autonomous-run.md` that were written because a
run already broke without them (#216).

WHAT THIS CAN AND CANNOT DO, stated up front so it is not mistaken for more than it is:
it asserts the TEXT IS PRESENT. It cannot assert that an agent executing the run obeys it. That is
the honest ceiling for a documentation change. It is a guard against the rule being deleted or
quietly reworded into nothing during a later edit, and nothing more.

Why the rule exists: on the 2026-07-27 run (#189, D9) the stage-6 `.deployed-digest` read returned
an empty string, the merge proceeded, and stage 7 briefly had no before-value to compare against.
It was recoverable only because the marker had not moved yet. The doc now says an empty or failed
read stops the run before merging.

Three places must agree, which is the actual failure mode this guards: a reader who consults the
table, a reader who consults the prose, and a reader who reads the diagram must not come away with
different rules.

ponytail: substring assertions over the raw markdown, same shape as tests/pr_checks_guard.py. No
markdown parser in this repo and none needed to catch a deletion.

Run: python3 tests/process_doc_selfcheck.py   (exit 0 = present, 1 = a rule went missing)
"""
import pathlib
import re
import sys

DOC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "process" / "autonomous-run.md"

failed = []


def check(name, cond, detail=""):
    if cond:
        print("ok   - " + name)
    else:
        print("FAIL - " + name + (("  (" + detail + ")") if detail else ""))
        failed.append(name)


if not DOC.is_file():
    print("FAIL - autonomous-run.md not found at " + str(DOC))
    sys.exit(1)

text = DOC.read_text()


def section(heading):
    """The body under a `## heading`, up to the next `## `."""
    m = re.search(r"^## " + re.escape(heading) + r"\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def flat(s):
    """Collapse whitespace and drop emphasis markers before matching prose.

    Markdown wraps. A quoted sentence broken across two lines, or one that gains a `**bold**` on a
    later edit, is still the same sentence — matching the raw text would fail on a pure reflow and
    send someone hunting for a deleted rule that is still there. This normalisation makes the check
    correct about markdown; it does not make it laxer, because every phrase asserted below is
    specific enough that no unrelated prose contains it.
    """
    return re.sub(r"\s+", " ", s.replace("**", "").replace("*", ""))


stages = section("Stages")
failure = section("Failure protocol")
preconditions = section("Preconditions")

# 1. The stage-6 table row itself. A reader who only scans the table must still see the rule.
stage6_row = ""
for line in stages.splitlines():
    if line.startswith("| 6 ") or line.startswith("|6 "):
        stage6_row = line
        break
check("the Stages table has a stage-6 row", bool(stage6_row))
check("stage-6 row still requires recording the digest BEFORE merging",
      "recorded before merging" in flat(stage6_row),
      "row=" + stage6_row[:80])
check("stage-6 row says an empty or failed read stops the run before merging",
      bool(re.search(r"empty or failed", stage6_row, re.I))
      and bool(re.search(r"stop before merging", flat(stage6_row), re.I)),
      "the row must carry the rule, not just the prose below it")

# 2. The Failure protocol prose, with the OBSERVABLE named. "handle failures gracefully" would
#    pass a laxer check and tell an implementer nothing.
check("Failure protocol covers the empty/failed digest read",
      bool(re.search(r"empty or failed .*digest|digest.*empty", flat(failure), re.I)))
check("Failure protocol names the observable (empty string AND non-zero exit)",
      "empty string" in flat(failure) and bool(re.search(r"non-?zero", flat(failure), re.I)),
      "a rule you cannot observe is not enforceable")
check("Failure protocol forbids merging first and re-reading afterwards",
      bool(re.search(r"after the merge|afterwards", flat(failure), re.I)),
      "the tempting wrong fix must be named, or someone will do it")

# 3. The inherited rule is cited by its HEADING, not a section number. The original ticket cited
#    a '§2.2' that does not resolve in this file; hard rule 8 applied to prose.
check("the Preconditions rule it inherits actually exists there",
      "unevaluable is not the same as true" in flat(preconditions))
check("Failure protocol cites Preconditions by name and quotes the sentence",
      "Preconditions" in flat(failure) and "unevaluable is not the same as true" in flat(failure))
check("no bare section-number citation was reintroduced",
      not re.search(r"§\s*\d", failure),
      "cite the heading; this file has no numbered sections")

# 4. The diagram must not contradict the table. This is the specific way the three drift apart.
check("the mermaid flowchart gives stage 6 a stop edge",
      bool(re.search(r"S6\s*-\.[^.]*\.->", stages)),
      "diagram would otherwise show stage 6 flowing only to stage 7")

print("\n" + (str(len(failed)) + " rule(s) missing" if failed else "all process rules present"))
sys.exit(1 if failed else 0)
