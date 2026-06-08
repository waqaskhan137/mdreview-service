---
id: MR-014
title: Skill — pre-G7 board-reconciliation rail (Phase 6) + SKILL.md invariant
status: done
layer: docs
priority: P2
sprint: sprint-03
epic: process-hardening-2
depends_on: []
branch: dev (small/solo change)
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Keep the independent G7 reviewer on substance, not bookkeeping: reconcile the board to reality
before the critic is spawned. (Retro suggestion 3.)

## Acceptance criteria

- [ ] `.claude/skills/feature-cycle/references/04-close-and-ship.md` **Phase 6** gains a
      board-reconciliation step that runs **before** the `staff-critic` spawn: every committed
      ticket is `done` in its frontmatter (restates an existing Phase 6 precondition); **(new)**
      the sprint file's committed-ticket checkboxes are checked to match; **(new)** `TRACKER.md`
      rows are moved to match each ticket's `status`.
- [ ] The rail **explicitly excludes** setting `close_review:` / `status: closed` / writing the
      retro — those remain in **Phase 8** (because `close_review:` names the file the critic
      produces and cannot exist pre-critic).
- [ ] `SKILL.md` **Invariants** list gains a one-line invariant: reconcile the board to reality
      (tickets `done`, sprint checkboxes checked, TRACKER moved) **before** spawning the G7 critic;
      `close_review`/`status: closed` are set post-review in Phase 8. Points at the Phase 6 detail,
      does not restate it.
- [ ] Additive; no gate pass-condition changed (the rail asserts an existing G7 precondition
      earlier, it does not redefine G7).
- [ ] Validation: read-diff.

## Notes / context

Plan: `epics/process-hardening-2-plan.md` (Skill section). The least-sure scoping call (rail =
board-reality only, not `close_review`) was confirmed correct by the G1 reviewer.

## Work log

- `2026-06-09` — `.claude/skills/feature-cycle/references/04-close-and-ship.md`: Phase 6 gains a
  step 0 "Reconcile the board to reality (you), BEFORE spawning the critic" — committed tickets
  `done`, sprint checkboxes/table updated, TRACKER rows moved; explicitly excludes
  `close_review`/`status: closed`/retro (those stay in Phase 8). `SKILL.md` Invariants list gains
  the matching one-line invariant pointing at Phase 6.

## Validation

- `2026-06-09` — read-diff. Phase 6 step 0 precedes the staff-critic spawn step; the rail excludes
  `close_review` (kept in Phase 8); the SKILL invariant is present.

## Follow-ups

None.
