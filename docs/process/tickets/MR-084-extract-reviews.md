---
id: MR-084
title: Extract reviews.py + ReviewService (lifecycle, summary/list, history, inline doc reads)
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-083]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the review lifecycle, summary/list, history snapshot+reads, and the raw `source.md`/
`feedback.md`/`notes.json` reads the router does inline into `ReviewService`, so the handler reaches
`/data` for review state only through this service.

## Acceptance criteria

- [x] `src/mdreview/reviews.py` defines `ReviewService(store, comments)` with: `meta`, `bump(rid,
      field)`, `summary` (verbatim, folds comment counts via `CommentService`), `list_reviews`,
      `snapshot_round`, `create_review`, `exists(rid)`, `read_source(rid)`, `feedback(rid)` (the
      `feedback.md` + `notes.json` + `_comment_as_note` projection), `history(rid)`, `history_round(rid,
      n)`.
- [x] The router's existence guard, `GET /source` raw read (`app.py:551`), `GET /feedback`
      (`app.py:566-574`), and both `/history` arms (`app.py:677-704`) call `ReviewService`; `bump`
      goes through `ReviewService.bump`, taken under the lock exactly where it is today.
- [x] **(G1 nit) The `/feedback` projection diff runs WITH a comment present** — create a comment,
      then read `/feedback` and diff — so `_comment_as_note` (`app.py:573`, its only call site) is
      actually exercised, not just the zero-comment path. Plus POST → 2×PUT → `GET /history` shows the
      rounds; `summary` counts fold the comment.
- [x] **Additive-default-safe reads preserved:** missing `turn`/`revision`/`handoff`/`agent_status`
      default (no `KeyError`) for legacy reviews; `summary()` stays lock-free.
- [x] Golden-transcript byte-identical; `python3 -m py_compile src/app.py src/mdreview/reviews.py`.

## Notes / context

- `app.py:136-222` (lifecycle), `app.py:551` (source read), `app.py:566-574` (feedback +
  projection), `app.py:677-704` (history), `app.py:165` / `app.py:594-597` (additive-default-safe).
- Epic: `reviews.py` row + the G1 SHOULD on the `/feedback` projection diff
  (`reviews/oop-refactor-src-layout-plan-review-2026-06-25-r2.md`).

## Work log

- `2026-06-25` — Created `src/mdreview/reviews.py` with `ReviewService(store, comments)`: `meta`,
  `bump`, `summary` (comment-aware, via `self.comments`), `list_reviews`, `snapshot_round`,
  `create`, `exists`, `read_source`, `put_source` (snapshot+overwrite+bump), `feedback` (the
  projection, delegating to `CommentService.as_note`), `delete` (rmtree), `history`,
  `history_round`. Logic moved verbatim. In `src/app.py`: `_reviews = ReviewService(_store,
  _comments)`; removed the 6 review defs + the `list_comments`/`_comment_as_note` shims; converted
  ~13 existence guards + `meta`/`bump`/`list_reviews`/`create`/source/feedback/history/delete arms to
  `_reviews.*`; dropped the now-unused `_exists` store shim and the `secrets`/`shutil` imports.
  Files: `src/mdreview/reviews.py`, `src/app.py`.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/reviews.py` → OK. Golden sweep →
  **byte-identical** (41/41): create, list (with `?turn=` filter), meta, GET/PUT source (snapshot +
  revision bump), GET feedback **with a comment present** (2 oracle sections exercise
  `_comment_as_note` for open + resolved, the folded G1 nit), status, GET `/history` +
  `/history/{n}` + missing-round 404, DELETE review. The handler's remaining store-shim users are
  the handoff arm (`_dir`/`_read_json`/`_write` -> MR-085) and the web/static/asset/`_wait` reads
  (-> MR-086); `_exists` is fully gone.

## Follow-ups

Anything deliberately deferred.
