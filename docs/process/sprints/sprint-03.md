---
id: sprint-03
name: Process hardening 2
status: closed
start: 2026-06-09
end: 2026-06-16
goal: Wire gate-row enforcement discipline + cite-by-name into the planner/README/skill (MR-012..014).
close_review: reviews/sprint-03-close-review-2026-06-09.md
---

## Goal

Stop the recurring class of process friction: rules landing in prose instead of the enforcing gate
row, and stale line-number anchors. Sharpen the planner (wire enforcement into the named row; cite
by name), add the README citation convention + scope the G7 render clause to product-page changes,
and add a pre-G7 board-reconciliation rail. No product code; all `docs`.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-012 | Planner agent — wire-enforcement-into-row + cite-by-name rules | docs | P1 | done |
| MR-013 | README — citation-by-name convention + scope G7 render clause | docs | P2 | done |
| MR-014 | Skill — pre-G7 board-reconciliation rail + SKILL.md invariant | docs | P2 | done |

## Preferred execution order

All three are independent (no `depends_on`); order is by leverage.
1. MR-012 — planner rules (highest leverage; pre-empts the recurring G1-blocker class next plan)
2. MR-013 — README convention + G7 scope
3. MR-014 — skill close-step rail

## Notes / retro

- All 3 tickets `done`, no carry-overs. Docs-only sprint (planner agent, README, skill).
- **Dogfooded its own outputs twice:** the new pre-G7 board-reconciliation rail (MR-014) was used
  to reconcile the board before the G7 critic was spawned; and the cite-by-name rule (MR-012/013)
  was followed throughout (zero stale line anchors).
- **G7 caught a real dogfooding failure:** the sprint reworded G7 to keep the rebuild + curl smoke
  unconditional, then its own close checklist dropped it — the critic caught the sprint about to
  violate the clause it shipped. Fixed (smoke run + recorded; checklist corrected; README↔skill
  Phase 6 drift closed). See `reviews/sprint-03-close-review-2026-06-09.md`.
- **Carry-overs:** none.

## Close gate (G7)

- [x] every committed ticket is `done` or explicitly carried over (docs-sweep tickets ineligible
      for carry-over; n/a here);
- [x] an independent `staff-critic` close review at `reviews/sprint-03-close-review-YYYY-MM-DD.md`
      verifies shipped work against each ticket's AC. This is a docs-only sprint touching no
      product page, so per the (newly reworded) G7 clause the per-page render-smoke + screenshot
      are not owed — but the **unconditional** container rebuild + `curl /healthz` + `/api/reviews`
      smoke is still owed (evidence: `reviews/sprint-03-render-evidence-2026-06-09/smoke.txt`); the
      rest of verification is read-diff of the agent/README/skill against the plan;
- [x] retro + carry-overs recorded, `close_review:` set.
