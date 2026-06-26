---
id: MR-082
title: Extract comments.py + CommentService (threaded state machine, incl. the inline arms)
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-081]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the threaded comment state machine (open→resolved→reopened) into `CommentService`, **including
the two arms the router does inline today** — `GET /comments/{cid}` and `DELETE /comments/{cid}` —
which were the G1 blocker (a cosmetic move would leave them mutating `/data` in the handler).

## Acceptance criteria

- [x] `src/mdreview/comments.py` defines `CommentService(store)` with: `list_comments(rid, status)`,
      `get_comment(rid, cid)`, `create_comment(...)`, `apply_comment_transition(rid, cid, action, by,
      text)` (reply/resolve/reopen), **`delete_comment(rid, cid)`** (the read-filter-write-bump), and
      the `_comment_as_note` projection (byte-identical output). The pinned transition semantics and
      append-only `thread[]`/`status_history[]` are unchanged.
- [x] The router's `GET /comments/{cid}` (`app.py:760`, was inline `_find_comment`) and `DELETE
      /comments/{cid}` (`app.py:765-772`, was inline `_read_json(_comments_path)` + filter +
      `_write_comments` + `bump`) now call `CommentService` — **no `_comments_path` / `_write_comments`
      / `_find_comment` left in the handler arms.**
- [x] Comment-lifecycle curl: create → reply → resolve → **409** double-resolve → reopen → **200
      reopened** → **409** reopen-non-resolved → delete → **GET 404**. Each response byte-identical to
      the golden transcript.
- [x] `python3 -m py_compile src/app.py src/mdreview/comments.py`.

## Notes / context

- `app.py:276-382` (the comment helpers + state machine) plus the inline arms at `app.py:760` and
  `app.py:765-772` (outside the 276-382 range — the G1 blocker's core).
- Epic: `comments.py` row (now naming `get_comment`/`delete_comment`) + the BLOCKER resolution in the
  G1 review (`reviews/oop-refactor-src-layout-plan-review-2026-06-25.md`).

## Work log

- `2026-06-25` — Created `src/mdreview/comments.py` with `CommentService(store)`: `list`, `get`
  (new, was the inline `_find_comment(list_comments(...))`), `create`, `delete` (new, was the inline
  read-filter-write), `apply_transition` (reply/resolve/reopen), `as_note` projection, plus `_path`
  / `_write` / `_find`. Logic moved verbatim. In `src/app.py`: `_comments =
  CommentService(_store)`; the 5 comment route arms now call `_comments.*`; the standalone comment
  functions are gone, leaving only `list_comments`/`_comment_as_note` shims (for the
  not-yet-extracted `summary()` + `/feedback`). Files: `src/mdreview/comments.py`, `src/app.py`.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/comments.py` → OK. **G1-blocker
  check:** `grep` finds zero `_comments_path(` / `_write_comments(` / `_find_comment(` in `src/app.py`
  (the GET/DELETE arms go through named methods, not inline `/data` mutation). Golden sweep →
  **byte-identical** (41/41), exercising create → reply → resolve → 409 double-resolve → reopen →
  200 reopened → 409 reopen-non-resolved → delete → GET 404.
- Note: a stale **foreign server on :8155** (the owner's `feat/ui-updates` preview, 15717-byte
  dashboard + seed reviews) caused a first false diff when my fresh server failed to bind 8155 and
  the sweep hit theirs. Fixed the harness: sweeps now run on a private port (8246) with a fail-loud
  busy-guard + a fresh-instance (empty-list) check, and the oracle normalises `localhost:<port>`.
  One stray `golden` review was left on the owner's :8155 preview (harmless; not deleted to avoid
  touching their running server).

## Follow-ups

Anything deliberately deferred.
