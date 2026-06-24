---
id: MR-084
title: Extract reviews.py + ReviewService (lifecycle, summary/list, history, inline doc reads)
status: ready
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-083]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the review lifecycle, summary/list, history snapshot+reads, and the raw `source.md`/
`feedback.md`/`notes.json` reads the router does inline into `ReviewService`, so the handler reaches
`/data` for review state only through this service.

## Acceptance criteria

- [ ] `src/mdreview/reviews.py` defines `ReviewService(store, comments)` with: `meta`, `bump(rid,
      field)`, `summary` (verbatim, folds comment counts via `CommentService`), `list_reviews`,
      `snapshot_round`, `create_review`, `exists(rid)`, `read_source(rid)`, `feedback(rid)` (the
      `feedback.md` + `notes.json` + `_comment_as_note` projection), `history(rid)`, `history_round(rid,
      n)`.
- [ ] The router's existence guard, `GET /source` raw read (`app.py:551`), `GET /feedback`
      (`app.py:566-574`), and both `/history` arms (`app.py:677-704`) call `ReviewService`; `bump`
      goes through `ReviewService.bump`, taken under the lock exactly where it is today.
- [ ] **(G1 nit) The `/feedback` projection diff runs WITH a comment present** — create a comment,
      then read `/feedback` and diff — so `_comment_as_note` (`app.py:573`, its only call site) is
      actually exercised, not just the zero-comment path. Plus POST → 2×PUT → `GET /history` shows the
      rounds; `summary` counts fold the comment.
- [ ] **Additive-default-safe reads preserved:** missing `turn`/`revision`/`handoff`/`agent_status`
      default (no `KeyError`) for legacy reviews; `summary()` stays lock-free.
- [ ] Golden-transcript byte-identical; `python3 -m py_compile src/app.py src/mdreview/reviews.py`.

## Notes / context

- `app.py:136-222` (lifecycle), `app.py:551` (source read), `app.py:566-574` (feedback +
  projection), `app.py:677-704` (history), `app.py:165` / `app.py:594-597` (additive-default-safe).
- Epic: `reviews.py` row + the G1 SHOULD on the `/feedback` projection diff
  (`reviews/oop-refactor-src-layout-plan-review-2026-06-25-r2.md`).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
