---
id: sprint-00
name: <short sprint name>
status: planning       # planning | active | closed
start: YYYY-MM-DD
end: YYYY-MM-DD
goal: <one sentence — what this sprint is meant to achieve>
close_review:          # reviews/sprint-NN-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

One short paragraph expanding on the sprint goal. What "success" looks like by the end date.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-000 | … | svc | P1 | ready |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-000 — …

## Notes / retro

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-NN-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
