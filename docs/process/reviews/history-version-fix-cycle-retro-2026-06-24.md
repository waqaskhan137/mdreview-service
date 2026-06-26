---
review_of: epics/history-version-fix-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: Clean run — groomed GH issue #18 in, render-smoke modal wall finally solved (node-CDP), G1 1 round / G7 1 round, 0 parks, 0 carries.
status: resolved
---

# Cycle retrospective — history-version-fix (sprint-23, GH #18)

**Verdict:** Clean run. A groomed, code-grounded GH issue drove a two-ticket epic to PASS in one G1 and one G7 round, zero parks, zero carry-overs. The cycle's standout is that the *render-smoke-can't-open-the-modal* wall (waived as cosmetic in sprint-07) was diagnosed at G1 and **solved** at G7 with a node-CDP eval driver, not waived. This retro reviews the run, and proposes turning that one-off solve into a standing rule.

## What went well (load-bearing)

- **Groomed-issue → cycle is a clean input path.** The planner read `gh issue view 18` (code refs, two named defects with line-grounded root causes) and resolved both design forks in the plan — Defect A (list current draft as `current (vN)`) and Defect B (remove the count, not fake it, because comments were never per-round snapshotted so any retroactive count is a false 0). A groomed issue gave G1 a concrete consumer-grep to verify against rather than a vague brief.
- **Per-chunk G1 caught real *verification* gaps, not just design nits.** The blocking finding was that the named acceptance tool (`render-smoke.sh`) would false-pass the deliverable; two worth-considering caught a doc that would lie (`README.md:55` `/history` shape) and a v0/empty-rounds self-contradiction (`current (v0)` vs the dashboard hiding its badge below v1). All folded in one revision, no G1 round 2.
- **G7 re-drove independently.** The critic ran a *fresh* node-CDP script (not the implementer's), 11/11 including the live v0 edge — the modal DOM was verified by a real browser render, not a `--dump-dom` of a closed modal.

## Top suggestions (prioritized, suggest-only)

1. **Make node-CDP the written standard for any click-gated / JS-built viewer DOM.** `[process]` / `[skill]`
   This is the highest-value fix because it is a *recurring* class: sprint-07 hit this exact modal and **waived** it as cosmetic (`reviews/sprint-07-close-review-2026-06-18.md`); this sprint the modal DOM *was* the deliverable and couldn't be waived, so MR-065 had to (re)derive the node-CDP `agent_smoke.py:112-148` pattern from scratch under G1 pressure. Add a one-paragraph rule to `docs/process/README.md` (validation gate) and/or the feature-cycle skill: *`render-smoke.sh` (single `--dump-dom`, no click/eval) verifies first-paint and non-modal nodes only; any selector that exists only after a click or JS-build is verified by the node-CDP `Runtime.evaluate` driver (`agent_smoke.py:112-148`) — a 200 is not a render and a `--dump-dom` of a `display:none` modal is not a render.* The plan already spells the mechanism out across ~40 lines (epic plan, "JS-rendered surfaces" key constraint + Verification (b)); promote that prose to the process so the next JS-DOM ticket inherits it instead of rediscovering it.

2. **Promote the node-CDP driver from a per-ticket `.scratch/` script to a checked-in helper.** `[feature]`
   Both the implementer and the G7 critic wrote their own one-off CDP drivers this cycle (the critic's was deliberately independent — good for G7). But the *open + poll-until-populated + read-back* scaffold is identical each time and currently lives only inside `agent_smoke.py` as an embedded pattern. A thin `scripts/cdp-eval.sh <url> <js>` (or documented entrypoint into `agent_smoke.py`) would let the AC author write only the assertions, not the WebSocket/CDP plumbing — and keep G7's independent re-drive (re-run with a different assertion set, same harness). Backlog ticket; pairs with suggestion 1.

3. **Add the `reviews/` path to the skill's gate-artifact note.** `[skill]`
   A subagent this run falsely flagged the G1 review file as "missing" because it looked in repo-root `reviews/` instead of `docs/process/reviews/`. One line in the feature-cycle skill — *gate `.md` lives under `docs/process/reviews/`, not repo-root `reviews/`* — removes a recurring confusion. This is also the still-unwritten `reviews/` dir-split, now surfacing across roughly nine cycles; if the split keeps not happening, at least pin the real path so agents stop guessing.

## Metrics

- **G1 rounds:** 1 (PASS-WITH-NITS, 1 blocking + 2 worth-considering + 2 nits, all folded, no round 2).
- **G7 rounds:** 1 (PASS, 11/11 + live v0 edge, no blockers/must-fix/nits).
- **Tickets:** 2 shipped (MR-064 svc, MR-065 ui), 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0. The one plan claim the critic overturned ("no documented field is touched") was a missed consumer in the sweep, not a load-bearing design assumption — corrected by adding the `README.md:55` update to MR-064's scope before the ticket spawned.
