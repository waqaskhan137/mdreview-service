---
id: MR-034
title: Comment state machine — reply/resolve/reopen routes, status_history, 409 on illegal transitions
status: done
layer: svc
priority: P1
sprint: sprint-11
epic: comment-resolution
depends_on: [MR-033]
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Add the server-enforced `open → resolved → reopened → resolved …` state machine on top of the MR-033
store, as the single writer shared by the viewer and MCP so the two can never diverge. Replies and
transitions append (never overwrite); illegal transitions are rejected; a resolve flips the
comment-aware `GET /feedback`/dashboard projections from MR-033.

## Acceptance criteria

- [ ] **Single writer.** All transition logic in one helper
      `apply_comment_transition(rid, cid, action, by, text=None)`, called under `_lock`, used by every
      route below — the viewer route and the MCP-backed route share this one implementation.
- [ ] **Routes** (rows in the `/comments` family from MR-033):
      `POST .../comments/{cid}/reply` `{text,author?,role?}` → `200 {comment}` (append, status
      unchanged); `POST .../comments/{cid}/resolve` `{justification?}` (role forced `agent`) →
      `200 {comment}` / `409`; `POST .../comments/{cid}/reopen` `{text?}` (role forced `reviewer`) →
      `200 {comment}` / `409`.
- [ ] **Legal transitions + writes** per the plan table: reply legal in **every** state (open/reopened/
      resolved), status unchanged, `thread += entry`. resolve from `open`|`reopened`: if `justification`
      given append an agent thread entry first, then `status="resolved"`, `resolved_by="agent"`,
      `resolved_at=ts`, `status_history += {to:"resolved",by:"agent"}`. reopen from `resolved`: optional
      reviewer reply appended first, then `status="reopened"`, clear `resolved_by`/`resolved_at`,
      `status_history += {from:"resolved",to:"reopened",by:"reviewer"}`.
- [ ] **Illegal → 409 / missing → 404.** resolve an already-`resolved` → `409 {error,status}`; reopen a
      non-`resolved` (`open`/`reopened`) → `409`; any action on a missing `comment_id` → `404`. Each
      proven by curl.
- [ ] **Append-only invariant.** A reply-then-resolve-then-reopen walk only ever grows `thread` and
      `status_history` (counts never shrink); the `open→resolved→reopened→resolved` walk leaves
      `status_history` length 4.
- [ ] **Resolve flips the MR-033 projections (BLOCKER-2).** After a resolve, `GET /feedback`'s projected
      `addressed` for that comment is `true`, `summary()`/dashboard `notes_addressed` grows, and once all
      comments resolved + all notes addressed the dashboard `status` reads `"resolved"`. A reopen flips
      them back.
- [ ] Local validation passes: `python3 -m py_compile app.py` + the MR-034 curl block in the epic plan
      (Verification → MR-034) against a rebuilt throwaway container on :8138.

## Notes / context

- Epic: `epics/comment-resolution-plan.md` — state-machine table + 409/404 list, "single helper" note,
  Verification → MR-034. Lock discipline mirrors `attach_asset`/`POST /feedback` (app.py:214-226,
  344-348).
- Depends on MR-033 (store, routes, `comments_updated`, the read projections).

## Work log

- `2026-06-19` — `app.py`: added `apply_comment_transition(rid, cid, action, by, text=None)` — the
  single writer (under `_lock`), returning `(code, payload)` (200/409/404). reply legal in every
  state (append, status unchanged); resolve from open|reopened (optional justification appended as a
  final agent entry, sets `resolved_by="agent"`/`resolved_at`, `409` otherwise); reopen from resolved
  (optional reviewer reply, clears resolved fields, `409` otherwise). Added the combined
  `POST /comments/{cid}/(reply|resolve|reopen)` route (role forced agent for resolve, reviewer for
  reopen; reply role from body, default reviewer); `bump(comments_updated)` on success.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK; rebuilt throwaway :8138; ran the epic plan's
  MR-034 curl block. reply → `open`/thread 2; resolve+justification → `resolved`,
  `resolved_by:"agent"`, `resolved_at` set, thread 3 (last role agent); double-resolve → **409**;
  reopen → `reopened`, resolved fields cleared; reopen-non-resolved → **409**; silent resolve →
  `resolved`; the `open→resolved→reopened→resolved` walk leaves `status_history` length **4**
  (`[null→open, open→resolved, resolved→reopened, reopened→resolved]`) and `thread` length 4 (never
  shrinks); missing id → **404**. **BLOCKER-2:** resolve flips the `GET /feedback` projection
  `addressed`→true and the dashboard to `1/1 resolved`; reopen flips both back to `addressed`=false /
  `1/0 feedback`.

## Follow-ups

_None expected._
