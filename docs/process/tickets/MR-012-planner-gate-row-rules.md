---
id: MR-012
title: Planner agent — "wire enforcement into the named gate row" + "cite by name, not line number" rules
status: ready
layer: docs
priority: P1
sprint: sprint-03
epic: process-hardening-2
depends_on: []
branch:
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Pre-empt the recurring G1-blocker class (three of five blockers last cycle were the same defect:
rules landing in DoD/prose/G5 instead of the enforcing gate row) and stop the planner emitting
stale line-number anchors. (Retro suggestions 1 + 2, agent half.)

## Acceptance criteria

- [ ] `.claude/agents/mdreview-planner.md` **Method** carries a standing rule: every new rule a
      plan proposes must have its enforcement **written into (added to) the named gate
      pass-condition row's text** — wired into the row, not merely cited next to a prose-only
      rule; citing a row alone is **explicitly insufficient**, and any Definition of Done / G5 /
      prose restatement is a non-enforcing **pointer**. Rationale cited: three of five G1 blockers
      last cycle collapsed to this class.
- [ ] A standing rule: in process docs and plans, **cite gates and sections by name** (e.g. "the
      G7 pass-condition row"); **reserve line numbers for code citations**. The existing Method
      instruction to "cite real `path:line` references for each claim" is narrowed to **code**
      claims.
- [ ] Additive (existing instructions preserved); no other agent behavior changed.
- [ ] Validation: read-diff.

## Notes / context

Plan: `epics/process-hardening-2-plan.md` (Agent section). Evidence:
`reviews/process-hardening-cycle-retro-2026-06-09.md`, `reviews/sprint-02-close-review-2026-06-09.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
