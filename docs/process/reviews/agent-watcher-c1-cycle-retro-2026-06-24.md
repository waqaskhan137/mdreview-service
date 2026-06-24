---
review_of: epics/agent-watcher-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: smooth run, one self-corrected mid-implementation race; friction was git-hygiene around subagent commits, not the gates
status: resolved
---

# Cycle Retrospective — agent-watcher Chunk 1 (sprint-17, MR-054 + MR-055)

Reviews the RUN, not the feature. Persisted to disk so the learnings survive the session (a prior
retro's own suggestion). C1 shipped the three server primitives the watcher will poll (`?turn=agent`
filter, `/wait` long-poll, stale-lease takeover) entirely inside the existing container: G1
PASS-WITH-NITS (one substantive finding, folded, no second round), G7 PASS first-pass, no carry-overs,
no parks. The epic plan covers C1–C3 but ticketed C1 only, mirroring agent-handoff-baton's
one-epic-many-sprints shape.

## What went well (load-bearing)

- **The gates worked; the friction was off to the side.** G1 caught the one finding that mattered
  (F1: `/wait` matched a level not an edge → busy-loop in steady state), the planner folded it into a
  required `?since=` cursor with author-preserved independence, and G7 independently re-ran everything
  on throwaway instances. The plan→critique→close spine was clean.
- **A pinned micro-optimization got a correctness check at implementation and lost to the simpler
  correct version.** The G1 plan pinned an O(1) `_last_change` rid-carry for `/wait`; verifying the
  merged code surfaced a missed-edge race under rapid flips (a matching flip overwritten by a
  non-matching one before the woken waiter re-acquires the lock). The orchestrator replaced it with
  rescan-on-wake plus a deterministic regression smoke, and the G7 critic reproduced both the
  would-be-bug and the fix (`sprint-17-close-review`, "Rapid double-flip edge", 0.41s return).

## Prioritized suggestions (SUGGEST-ONLY — not applied)

1. **[skill] Pin subagent git conventions: who commits what, and when.** The run's only real friction.
   The ticketing subagent left the planning artifacts (epic, requirement, G1 review, sprint, the
   MR-055 ticket) and a modified TRACKER **uncommitted** in the working tree while the implementation
   subagent committed MR-054 on a branch — so the scaffold had to be reconstructed *after* MR-054 was
   already merged (`5bc1ee3 docs(process): scaffold agent-watcher epic` lands between the two ticket
   merges; the MR-054 ticket file rode inside the `d258528` MR-054 merge while its siblings were
   stranded). The orchestrator also once ran `git merge` while still **on** the MR-055 branch (a no-op
   "Already up to date") before noticing and switching to `dev`. Add to the feature-cycle skill a
   delegation rule: **the orchestrator scaffolds-and-commits all planning artifacts to `dev` before
   any implementation subagent is dispatched**, and a subagent commits **only** the ticket it owns on
   its own branch; the orchestrator merges from `dev`, never from a ticket branch. This prevents a
   recurring class (stranded artifacts + wrong-branch merge), not a one-off.

2. **[process] Ratify the `reviews/` directory split — this is now a THIRD recurrence.** Named in the
   `legacy-feedback-retire` retro and again in the `agent-handoff-baton` retro (#2), still un-actioned.
   This cycle again split it by hand: gate `.md` under `docs/process/reviews/` and bulky render
   evidence under repo-root `reviews/sprint-17-render-evidence-2026-06-24/`. The convention **held**
   (it matches sprints 11/12/15), but it is still unwritten — the G7 row says
   `reviews/sprint-NN-render-evidence-*` with no tree prefix, and the repo has the same evidence under
   *both* trees historically (sprints 06–09 under `docs/process/reviews/`). One line in the README
   Layout closes it permanently (gate `.md` → `docs/process/reviews/`; bulky evidence → repo-root
   `reviews/`). A fix named three times and never landed is the highest-value class to close. (Minor:
   `reviews/sprint-17-render-evidence-2026-06-24/` is still untracked at retro time — confirm it gets
   committed.)

3. **[process] Make "a pinned micro-optimization still owes a correctness check at implementation" a
   standing expectation, not luck.** The `_last_change` rid-carry was a plausible, critic-passed
   optimization that was wrong under rapid flips; it was caught only because the orchestrator chose to
   verify the merged diff rather than trust the plan. Add a one-line G4/G5 note: **when an AC pins a
   specific performance shortcut over the obvious correct version, the ticket owes an explicit
   adversarial check of the shortcut (here, the rapid-double-flip smoke) before it counts as done.**
   Turns this cycle's good catch into a default for the next planner who pins an optimization.

4. **[agent] mdreview-planner: stop pinning concurrency micro-optimizations as the load-bearing
   default; offer them as a justified upgrade over a stated-correct baseline.** The plan pinned the
   rid-carry as the recommendation with the O(all-reviews) rescan as a grudging fallback — exactly
   inverted from what shipped (rescan won on correctness; the per-wake cost is trivial at this scale).
   The planner should default to the obviously-correct version and pin an optimization only with the
   failure mode it must survive spelled out. Pairs with #3 from the author side.

5. **[process] A ticket whose AC wording is self-contradictory should be caught at G2, not silently
   resolved at G7.** The G7 review (finding #2) flags MR-054's `?turn=` filter wording — "unknown ⇒
   all" vs "`?turn=agent` with no match ⇒ empty" — as internally contradictory; the implementer
   resolved it the only sound way (empty ⇒ all, non-empty ⇒ exact match) and documented the reading.
   Fine here, but it relied on implementer judgment. A light G2 check ("acceptance criteria are
   internally consistent") would catch this class before code.

## Metrics

G1 rounds: 1 (PASS-WITH-NITS; F1/F2/WC-1 folded into MR-054, no re-review). G7 rounds: 1 (PASS
first-pass; 4 nits, 7 worth-considering, 0 blocking). Tickets shipped: 2 (MR-054, MR-055); carried: 0.
Parks: 0. Wrong load-bearing assumptions: 0 at plan level — the one overturned plan item (the
`_last_change` rid-carry) was a pinned *implementation optimization*, not a load-bearing assumption,
and it was caught and replaced in-cycle (`98a2512 fix(svc): rescan /wait on wake`). Recurrence flagged:
the `reviews/` directory split (3rd retro).

## Resolution log

- 2026-06-24 — Retro produced at C1 sprint close (sprint-17). Suggestions are advisory; none applied
  (cycle-retrospective never edits process/skill/agents). #1 (subagent git conventions) is the run's
  top friction; #2 (`reviews/` split) is a third-time recurrence and the strongest candidate for a
  `docs` follow-up ticket.
