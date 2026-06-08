---
id: MR-011
title: README — reconcile DoD with a bounded same-sprint docs-sweep (G7 row clause)
status: ready
layer: docs
priority: P2
sprint: sprint-02
epic: process-hardening
depends_on: []
branch:
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Remove the contradiction between the Definition of Done ("docs in the same change") and the
docs-sweep ticket pattern the first sprint actually used (MR-001 deferred field docs to MR-007).
(Retro suggestion 4; resolves G1 findings B1a + B1b.)

## Acceptance criteria

- [ ] `README.md` Definition of Done (`README.md:130-134`) and the **G5 row (`:156`)**: durable
      behavior docs ship in the same change **or** are deferred to a trailing **docs-sweep ticket
      within the same sprint**, provided the deferring ticket names its sweep ticket in its Work
      log.
- [ ] **G7 pass-condition row (`README.md:158`)** gains a docs-currency clause: G7 does not pass
      while any committed ticket has docs deferred to a docs-sweep ticket that is not `done`
      (the actual enforcement point — B1a).
- [ ] The wording states a **docs-sweep ticket is ineligible for carry-over** (its
      non-completion fails G7), closing the cross-sprint-boundary loophole (B1b).
- [ ] Changes wording only; the gate set G0-G8 and the status lifecycle are unchanged.
- [ ] Validation: read-diff against `README.md:130-134`, `:156`, `:158`.

## Notes / context

Plan: `epics/process-hardening-plan.md` (Process section, Phase 3, Risks — this was the planner's
least-sure call, hard-bounded by the G7 clause + carry-over ineligibility, with a one-line
"forbid sweeps instead" override available if the owner prefers). G1 review B1a/B1b:
`reviews/process-hardening-plan-review-2026-06-08.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
