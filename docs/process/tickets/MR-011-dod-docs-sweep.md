---
id: MR-011
title: README — reconcile DoD with a bounded same-sprint docs-sweep (G7 row clause)
status: done
layer: docs
priority: P2
sprint: sprint-02
epic: process-hardening
depends_on: []
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Remove the contradiction between the Definition of Done ("docs in the same change") and the
docs-sweep ticket pattern the first sprint actually used (MR-001 deferred field docs to MR-007).
(Retro suggestion 4; resolves G1 findings B1a + B1b.)

## Acceptance criteria

- [ ] `README.md` Definition of Done and the **G5 row**: durable
      behavior docs ship in the same change **or** are deferred to a trailing **docs-sweep ticket
      within the same sprint**, provided the deferring ticket names its sweep ticket in its Work
      log.
- [ ] **G7 pass-condition row** gains a docs-currency clause: G7 does not pass
      while any committed ticket has docs deferred to a docs-sweep ticket that is not `done`
      (the actual enforcement point — B1a).
- [ ] The wording states a **docs-sweep ticket is ineligible for carry-over** (its
      non-completion fails G7), closing the cross-sprint-boundary loophole (B1b).
- [ ] Changes wording only; the gate set G0-G8 and the status lifecycle are unchanged.
- [ ] Validation: read-diff against the DoD, G5 row, and G7 row.

## Notes / context

Plan: `epics/process-hardening-plan.md` (Process section, Phase 3, Risks — this was the planner's
least-sure call, hard-bounded by the G7 clause + carry-over ineligibility, with a one-line
"forbid sweeps instead" override available if the owner prefers). G1 review B1a/B1b:
`reviews/process-hardening-plan-review-2026-06-08.md`.

## Work log

- `2026-06-09` — `README.md`: the Definition of Done now blesses deferring durable docs to a
  trailing **docs-sweep ticket within the same sprint** (deferring ticket names it in the Work
  log), and states a docs-sweep ticket is **ineligible for carry-over**. The G5 row mirrors the
  DoD. The **G7 pass-condition row** gains the enforcement clause: G7 does not pass while any
  committed ticket has docs deferred to a not-yet-`done` docs-sweep ticket, and a docs-sweep
  ticket is not eligible for carry-over (deferred docs are force-closed at sprint close). Gate set
  and lifecycle unchanged. (Also folded `scripts/render-smoke.sh` into the G7 render-smoke wording
  for consistency with MR-009/010.)

## Validation

- `2026-06-09` — read-diff against `README.md` DoD (`### Definition of Done`), the G5 row, and the
  G7 row. Confirmed: DoD blesses the same-sprint sweep; carry-over ineligibility stated in both
  the DoD and the G7 row; the G7 row carries the docs-currency clause; G5 mirrors it.

## Follow-ups

None.
