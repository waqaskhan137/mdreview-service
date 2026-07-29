# HTTP API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | | **dashboard** HTML (or the descriptor JSON on `Accept: application/json`) |
| GET | `/api` | | service descriptor JSON |
| POST | `/api/reviews` | `{markdown, title?, project?, source_path?, session?}` | `{id, review_url, feedback_url, source_url, status_url}` |
| GET | `/api/reviews` | `?turn=agent` (optional, exact-match on the turn baton; empty/absent ⇒ all) | `{reviews[]}` — every review's meta + `notes_total`, `notes_addressed`, `revision`, `status`, `turn` |
| GET | `/api/reviews/wait` | `?since=<turn_updated>` **required** (edge cursor; missing ⇒ `now`, `0` ⇒ backlog) · `?turn=agent` · `?timeout=<s>` (capped to server max ≈25s, `MDREVIEW_WAIT_TIMEOUT_S`) | `{reviews[]}` — **long-poll**: blocks until a baton flips *newer* than `since` (each row carries its `turn_updated`), or `{reviews:[], timeout:true}` on expiry |
| GET | `/api/reviews/{id}` | | meta |
| DELETE | `/api/reviews/{id}` | | `{deleted}` |
| GET | `/api/reviews/{id}/source` | | raw markdown |
| PUT | `/api/reviews/{id}/source` | `{markdown}` | meta (snapshots a history round, then live-reloads) |
| GET | `/api/reviews/{id}/feedback` | | `{markdown, notes[], ...meta}` — `notes[]` is legacy notes **plus a projection of the comments** (so this read path stays live) |
| GET | `/api/reviews/{id}/status` | | `{source_updated, feedback_updated, comments_updated, turn, turn_updated, handoff, agent_status}` |
| POST | `/api/reviews/{id}/handoff` | `{to:"agent"}` · `{to:"reviewer", state, message}` · `{state:"working", owner, message?}` · `{to:"reviewer", by:"reviewer"}` | meta — the **turn baton**: flip to the agent, hand back (done/blocked), claim/renew the lease (`409` on a *fresh* foreign owner; a **stale** foreign lease — older than `LEASE_TTL_S`, 180s — is taken over unless already reclaimed), or reviewer reclaim; `400` on an unrecognized body |
| GET | `/api/reviews/{id}/history` | | `{rounds[]}` — `{round, ts}`, newest first |
| GET | `/api/reviews/{id}/history/{n}` | | one round: `{source, feedback, notes[], ...round meta}` |
| GET | `/api/reviews/{id}/comments` | `?status=open\|resolved\|reopened\|all` (default `all`) | `{comments[]}` — the threaded comments |
| POST | `/api/reviews/{id}/comments` | `{anchor{quoted_text, block_num?, start?, end?}, text, role?}` | `{comment}` (201; reviewer authors) |
| GET | `/api/reviews/{id}/comments/{cid}` | | `{comment}` — full `thread[]` + `status_history[]` |
| DELETE | `/api/reviews/{id}/comments/{cid}` | | `{deleted}` — hard-remove a junk comment (`404` if missing); distinct from resolve |
| POST | `/api/reviews/{id}/comments/{cid}/reply` | `{text, role?}` | `{comment}` — append a reply; status unchanged |
| POST | `/api/reviews/{id}/comments/{cid}/resolve` | `{justification?}` | `{comment}` — agent resolves (`409` if not open/reopened) |
| POST | `/api/reviews/{id}/comments/{cid}/reopen` | `{text?}` | `{comment}` — reviewer reopens (`409` if not resolved) |
| POST | `/api/reviews/{id}/assets` | `{name, content_b64}` | `{name, stored, url, bytes, ctype}` — attach an image (base64) the viewer serves at `url` |
| GET | `/api/reviews/{id}/assets` | | `{assets[]}` — `{name, stored, url, bytes, ctype, ts}` per attached asset |
| GET | `/api/reviews/{id}/asset/{stored}` | | the asset bytes (binary, with its stored content-type) |
| GET | `/review/{id}` | | viewer HTML (human opens) |
| GET | `/healthz` | | `{ok}` |

**Provenance (optional, on POST):** `project` and `session` organize a review on the dashboard —
the left sidebar lists **Projects** you can filter the grid by, and each card shows a
`project / session / source_path` crumb; `source_path` records the file it came from. Untagged
reviews still appear under **All reviews** (just not under a project). The fields are stored in
`meta.json`; existing reviews without them are unaffected.

The dashboard sidebar also has a turn-baton **Inbox** — *All reviews*, *Needs you* (your turn),
*Agent working*, *Resolved* — and each card carries the matching status badge, derived from the
same `turn`/`status` already on `GET /api/reviews` (no extra call).

**Status** (in the list/dashboard) is derived per review: `awaiting` (no feedback yet),
`feedback` (notes/comments outstanding), `resolved` (all notes addressed **and** all comments
resolved). Counts (`notes_total`/`notes_addressed`) are comment-aware — an open comment counts
toward the total, a resolved one toward addressed — so a review with live comments never reads as
"0 / awaiting".

**History:** each `PUT /source` archives the outgoing draft plus the feedback it accumulated as a
numbered round under `{id}/history/round-{N}/`, and bumps `revision`. Past rounds are read-only
via the history routes; the viewer exposes them behind its **History** button.

**Assets (images):** attach a draft's images to a review once with `POST /assets` — base64 body,
keyed by the exact `src` the draft uses (e.g. `/assets/x.png` or `fig/y.svg`). The bytes are stored
under the review by a content-hash name and **survive every `PUT /source` revision** (attach once,
never resend blobs). The viewer rewrites local/relative/site-root `<img src>` to the served `url`,
so a math- and image-heavy draft renders in review the way it does on the published site. base64 is
the only transport; the served `url` keys on the hash name (no encoded slashes), so it survives a
reverse proxy. Assets are review-scoped (not history-snapshotted) and removed with the review.
Like the rest of the service, asset serving inherits the **no-auth, id-only** posture: bytes are
served with the content-type inferred from the attached `name`, so treat an attached asset like the
draft's own HTML — don't attach bytes you wouldn't trust in `source.md`. (Responses carry
`X-Content-Type-Options: nosniff`; keep auth in front if you expose the service.)

Feedback `notes[]` entries look like:
`{"num": "3", "quote": "...", "note": "tighten this", "addressed": false}`,
and `markdown` is the same feedback rendered as a readable block per note. Each entry is either a
legacy note or a **projected comment** (`note` = the thread, `addressed` = the comment is resolved).

**Comments (threaded resolution).** A reviewer highlights text and starts a comment; it opens as a
**thread** in the viewer margin. The agent (over HTTP or MCP) lists open comments, replies to discuss,
or **resolves** one — optionally with a justification appended to the thread (`resolved_by`/`resolved_at`
are recorded). A resolved comment leaves the active document and moves to a **Resolved** panel; the
reviewer can **reopen** it (status back to `reopened`), after which the agent can resolve again. The
`open → resolved → reopened` machine is enforced server-side, so the viewer and MCP share one state.
`thread[]` and `status_history[]` are append-only (full history, never overwritten). A comment is
`{comment_id, status, anchor{quoted_text, block_num, start, end}, thread[{author, role, text, ts}],
created_by, created_at, resolved_by, resolved_at, status_history[]}`. Roles `reviewer`/`agent` are
**attribution, not auth**; "reviewer-only reopen" and "no MCP reopen tool" are conventions on the
no-auth service. Poll `comments_updated` (on `GET /status`) to live-reload threads.

---

Moved out of `README.md` by #257. Commands, ports, paths and env vars are
byte-identical to what shipped there; nothing was corrected in the move.
