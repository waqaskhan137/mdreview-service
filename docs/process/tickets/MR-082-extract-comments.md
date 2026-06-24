---
id: MR-082
title: Extract comments.py + CommentService (threaded state machine, incl. the inline arms)
status: ready
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-081]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the threaded comment state machine (open→resolved→reopened) into `CommentService`, **including
the two arms the router does inline today** — `GET /comments/{cid}` and `DELETE /comments/{cid}` —
which were the G1 blocker (a cosmetic move would leave them mutating `/data` in the handler).

## Acceptance criteria

- [ ] `src/mdreview/comments.py` defines `CommentService(store)` with: `list_comments(rid, status)`,
      `get_comment(rid, cid)`, `create_comment(...)`, `apply_comment_transition(rid, cid, action, by,
      text)` (reply/resolve/reopen), **`delete_comment(rid, cid)`** (the read-filter-write-bump), and
      the `_comment_as_note` projection (byte-identical output). The pinned transition semantics and
      append-only `thread[]`/`status_history[]` are unchanged.
- [ ] The router's `GET /comments/{cid}` (`app.py:760`, was inline `_find_comment`) and `DELETE
      /comments/{cid}` (`app.py:765-772`, was inline `_read_json(_comments_path)` + filter +
      `_write_comments` + `bump`) now call `CommentService` — **no `_comments_path` / `_write_comments`
      / `_find_comment` left in the handler arms.**
- [ ] Comment-lifecycle curl: create → reply → resolve → **409** double-resolve → reopen → **200
      reopened** → **409** reopen-non-resolved → delete → **GET 404**. Each response byte-identical to
      the golden transcript.
- [ ] `python3 -m py_compile src/app.py src/mdreview/comments.py`.

## Notes / context

- `app.py:276-382` (the comment helpers + state machine) plus the inline arms at `app.py:760` and
  `app.py:765-772` (outside the 276-382 range — the G1 blocker's core).
- Epic: `comments.py` row (now naming `get_comment`/`delete_comment`) + the BLOCKER resolution in the
  G1 review (`reviews/oop-refactor-src-layout-plan-review-2026-06-25.md`).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
