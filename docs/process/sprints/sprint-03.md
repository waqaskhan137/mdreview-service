---
id: sprint-03
name: Process hardening 2
status: active
start: 2026-06-09
end: 2026-06-16
goal: Wire gate-row enforcement discipline + cite-by-name into the planner/README/skill (MR-012..014).
close_review:
---

## Goal

Stop the recurring class of process friction: rules landing in prose instead of the enforcing gate
row, and stale line-number anchors. Sharpen the planner (wire enforcement into the named row; cite
by name), add the README citation convention + scope the G7 render clause to product-page changes,
and add a pre-G7 board-reconciliation rail. No product code; all `docs`.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-012 | Planner agent — wire-enforcement-into-row + cite-by-name rules | docs | P1 | ready |
| MR-013 | README — citation-by-name convention + scope G7 render clause | docs | P2 | ready |
| MR-014 | Skill — pre-G7 board-reconciliation rail + SKILL.md invariant | docs | P2 | ready |

## Preferred execution order

All three are independent (no `depends_on`); order is by leverage.
1. MR-012 — planner rules (highest leverage; pre-empts the recurring G1-blocker class next plan)
2. MR-013 — README convention + G7 scope
3. MR-014 — skill close-step rail

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

- [ ] every committed ticket is `done` or explicitly carried over (docs-sweep tickets ineligible
      for carry-over; n/a here);
- [ ] an independent `staff-critic` close review at `reviews/sprint-03-close-review-YYYY-MM-DD.md`
      verifies shipped work against each ticket's AC. This is a docs-only sprint touching no
      product page, so per the (newly reworded) G7 clause the per-page render-smoke + screenshot
      are not owed; verification is read-diff of the agent/README/skill against the plan;
- [ ] retro + carry-overs recorded, `close_review:` set.
