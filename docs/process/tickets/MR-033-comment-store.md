---
id: MR-033
title: Comment store (comments.json) + POST/GET /comments + GET /comments/{cid} + comments_updated + comment-aware GET /feedback & summary()
status: ready
layer: svc
priority: P1
sprint: sprint-11
epic: comment-resolution
depends_on: []
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Add the shared server-side comment store the whole epic builds on: a per-review `comments.json`
(sibling of `notes.json`), the create/list/get routes, a `comments_updated` live-reload timestamp,
and — load-bearing — make the legacy read paths (`GET /feedback`, `summary()`/dashboard) **comment-aware
by read-time projection** so nothing the human says is lost once viewer authoring moves onto comments
(plan BLOCKER-2). No state transitions yet (MR-034); no disk migration of `notes.json`.

## Acceptance criteria

- [ ] **Store + helpers.** `comments.json` under `_dir(rid)`, default `[]` via `_read_json(path, [])`;
      helpers `_comments_path`, `list_comments(rid, status="all")`, `_write_comments` (caller holds
      `_lock`), `_find_comment`, and the pure `_comment_as_note(c)` projection
      (`{num:block_num, quote:quoted_text, note:<thread text>, addressed: status=="resolved"}`).
- [ ] **Comment model on create.** `comment_id="c"+secrets.token_hex(5)` (11 chars), `status:"open"`,
      `anchor{quoted_text,block_num,start,end}`, `thread:[{author,role:"reviewer",text,ts}]`,
      `created_by`, `created_at`, `resolved_by:null`, `resolved_at:null`,
      `status_history:[{from:null,to:"open",by:"reviewer",ts}]`.
- [ ] **Routes** (new regex rows, inserted between the `/assets` block end (~app.py:437) and
      `/asset/{stored}` (~app.py:439); `RID` reused; `{cid}` = `(c[A-Za-z0-9]{10})`):
      `GET /api/reviews/{id}/comments?status=` (default `all`) → `{"comments":[...]}`;
      `POST /api/reviews/{id}/comments` → `201 {comment}` (role defaults `reviewer`);
      `GET /api/reviews/{id}/comments/{cid}` → `200 {comment}` / `404`.
- [ ] **Live-reload.** Each comment write calls `bump(rid,"comments_updated")`; `GET /status` adds
      `comments_updated` (default `0`). Asserted **== 0 before** the first comment and **> 0 after**.
- [ ] **Comment-aware `GET /feedback` (BLOCKER-2).** `notes[]` becomes the **union** of on-disk
      `notes.json` entries and `[_comment_as_note(c) for c in list_comments(rid)]`. A review with an
      open comment and no `notes.json` returns that comment projected (`quote`=anchor text,
      `addressed=false`). `notes.json` on disk is **not** rewritten.
- [ ] **Comment-aware `summary()` (BLOCKER-2).** Counts/status fold comments in: `notes_total` counts
      all comments, `notes_addressed` counts `status=="resolved"`, status reads `"feedback"` while any
      comment/feedback exists and never `"0 / awaiting"` for a review with an open comment; `"resolved"`
      only when all notes addressed **and** all comments resolved. (Counting all-vs-open toward total is
      a confined one-liner if grooming flips it — recommend all.)
- [ ] **No-comment back-compat (re-verified, not assumed).** A fresh review with no `comments.json`:
      `GET /comments` → `{"comments":[]}`, `GET /feedback` byte-identical to today, dashboard reads
      `0 / awaiting` exactly as before. No 500/KeyError anywhere.
- [ ] Local validation passes: `python3 -m py_compile app.py` + the MR-033 curl block in the epic plan
      (Verification → MR-033) against a rebuilt throwaway container on :8138 (never :8139 / `docker
      compose`).

## Notes / context

- Epic: `epics/comment-resolution-plan.md` — Service section (storage, `_comment_as_note`, the two
  read projections), Back-compat guarantees #1–3, Verification → MR-033.
- Current model mapped at plan "Current model": `notes.json` `create_review` app.py:176, `POST/GET
  /feedback` app.py:355-364, `summary()` app.py:120-135, `_read_json`, `bump`/`GET /status`
  app.py:368-377, `_lock`/`attach_asset` pattern app.py:214-226.
- Router order verified safe (all `re.fullmatch`, app.py:323-468) — `comments` shadows nothing.
- The `addressed` half of the mapping only fully exercises once `resolve` exists (MR-034 re-asserts the
  flip); MR-033 ships `addressed` keyed on create-time status (`open` ⇒ false).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Count-only-open-comments-toward-total is a confined alternative if grooming wants it.
