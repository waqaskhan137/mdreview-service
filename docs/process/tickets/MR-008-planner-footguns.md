---
id: MR-008
title: Planner agent — fit-based-layout rule + Dockerfile-COPY footgun
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

Sharpen the `mdreview-planner` agent so it stops emitting the two mistakes the first cycle hit:
a hard-coded responsive breakpoint, and a new served file with no matching Dockerfile COPY.
(Retro suggestions 5 + 6.)

## Acceptance criteria

- [ ] `.claude/agents/mdreview-planner.md`: footgun 6 (JS-rendered surfaces) and the Method
      verification guidance state a **fit-based-layout rule** — the planner specifies responsive
      *behavior* ("show the element only when it physically fits the viewport"), never a pixel
      breakpoint it has not computed. Cites the sprint-01 lesson (a ~820px threshold was wrong;
      a 284px gutter cannot fit at 820px; reconciled to fit-based at G7).
- [ ] A new numbered **Dockerfile-COPY footgun** is added: a new root-level served file (sibling
      of `viewer.html`/`dashboard.html`) needs a matching `COPY` in the `Dockerfile`, and the
      `ui` ticket that adds the asset must carry that infra change, or the rebuilt container
      serves an empty 200 (the sprint-01 bug, commit `1326462`).
- [ ] Edits are additive to standing instructions; no other agent behavior changed.
- [ ] Validation: read-diff (no `py_compile`; `app.py` untouched).

## Notes / context

Plan: `epics/process-hardening-plan.md` (Agent section). Evidence:
`reviews/review-dashboard-cycle-retro-2026-06-08.md`, `reviews/sprint-01-close-review-2026-06-08.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
