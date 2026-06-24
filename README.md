# mdreview-service

A containerized markdown review microservice. An agent POSTs markdown, gets back a review URL
for a human, and polls feedback over HTTP. One service handles many reviews, isolated by id.
No per-process spawning, no shared filesystem with the agent.

**Landing page:** [mdreview.waqasrana.space](https://mdreview.waqasrana.space/) (served from the
`gh-pages` branch; source in `site/`).

Stdlib Python only (tiny image, no pip installs). Self-contained: the marked, Mermaid, KaTeX,
highlight.js, and footnote renderers are vendored and served from `/static`, so the browser needs no
CDN. The viewer renders Markdown the way a Jekyll/MathJax site does: **LaTeX math** (inline `$…$` /
`\(…\)`, display `$$…$$` / `\[…\]`; prose/currency `$` left literal), **Mermaid** diagrams, **GFM
footnotes** (`[^id]` refs → an ordered back-ref section), and **syntax-highlighted** fenced code (a
dual-scheme theme that reads on light and dark panes).

## Run

```bash
docker compose up -d --build        # serves on http://localhost:8137
# or:
docker build -t mdreview-service .
docker run -d -p 8137:8080 -v mdreview-data:/data mdreview-service
```

Health check: `curl localhost:8137/healthz` -> `{"ok":true}`.

Feedback and source persist in the `/data` volume across restarts.

## The flow

1. Agent: `POST /api/reviews {markdown, title}` -> `{id, review_url, feedback_url, ...}`
2. Agent hands `review_url` to a human.
3. Human opens it, selects text or clicks a paragraph number, types notes (auto-saved).
4. Agent polls `GET /api/reviews/{id}/status` then `GET /api/reviews/{id}/feedback`.
5. Agent applies edits and `PUT /api/reviews/{id}/source {markdown}` -> the human's page
   live-reloads and addressed notes are struck through. Repeat as needed.

## API

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
| GET | `/api/reviews/{id}/history` | | `{rounds[]}` — `{round, ts, notes_total, notes_addressed}`, newest first |
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

**Provenance (optional, on POST):** `project` and `session` group a review on the dashboard
(`project › session › files`); `source_path` records the file it came from. Untagged reviews
group under "Ungrouped". The fields are stored in `meta.json`; existing reviews without them are
unaffected.

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

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | in-container listen port |
| `MDREVIEW_DATA` | `/data` | storage dir (mount a volume) |
| `MDREVIEW_PUBLIC_BASE` | empty | if set (e.g. `https://review.example.com`), `review_url`/`feedback_url` use it; otherwise the request Host header is used |

## MCP server (optional)

`mcp_server.py` is a thin, stdlib-only **MCP** server (stdio, JSON-RPC 2.0, spec rev `2025-06-18`)
that exposes the review API as first-class tools, so an MCP-speaking agent can call it without
hand-rolling HTTP. It wraps the running HTTP service and adds no state — the service is unchanged.

```bash
# point it at a running mdreview-service and run it over stdio
MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py
# smoke it (stdlib only, no deps):
MDREVIEW_BASE=http://localhost:8137 python3 mcp_smoke.py
```

Example MCP client config (stdio):

```json
{
  "mcpServers": {
    "mdreview": {
      "command": "python3",
      "args": ["/path/to/mdreview-service/mcp_server.py"],
      "env": { "MDREVIEW_BASE": "http://localhost:8137" }
    }
  }
}
```

**Tools (20):** `create_review` (markdown, title?, project?, session?,
source_path?), `list_reviews`, `get_review` (id), `get_source` (id), `get_feedback` (id), `get_status` (id),
`update_source` (id, markdown), `get_history` (id, round?), `attach_asset` (id, name, path|content_b64),
`list_assets` (id), `delete_review` (id), `server_info`, `create_comment` (author a comment), the **comment** tools `list_comments` (document_id, status?=open), `get_comment` (document_id,
comment_id), `reply_to_comment` (document_id, comment_id, text), `resolve_comment` (document_id,
comment_id, justification?), `delete_comment` (document_id, comment_id — hard-remove a junk comment),
and the **turn-baton** tools `hand_back` (document_id, message, state?=done) and `ping_working` (document_id, owner, message?) — both map onto `POST /handoff`.
`document_id` is the review id.
There is **no `reopen` tool** — reopen is the reviewer's UI action (a convention on the no-auth
service, not an enforced boundary); after a reopen the agent sees the comment again via
`list_comments`. The agent workflow (`list_comments(status="open")` first; reply to discuss, resolve
when addressed; justification optional but recommended) is encoded in the tool descriptions. A failed
call (bad/expired id, service down) returns an `isError: true` result; an unknown tool name is a
JSON-RPC `-32602` error.

**Staleness.** A stdio MCP server loads its code + tool list once at process start; editing
`mcp_server.py` does nothing until the client **reconnects**. `server_info` reports the *running*
wrapper's `tools_hash`/version; a **human/CI** compares it to the on-disk `python3 mcp_server.py
--print-version` and reconnects on a mismatch (the server can signal its identity but cannot reload
itself; an HTTP/render change needs no reconnect — the wrapper just proxies — a change to
`mcp_server.py` itself does).

**Reachable `review_url`.** The wrapper relays the service's `review_url`, which the service
derives from the request `Host` header unless `MDREVIEW_PUBLIC_BASE` is set. So a human handed the
link can reach it, set `MDREVIEW_PUBLIC_BASE` on the **service** (not the wrapper) to a
host-reachable URL (e.g. `https://review.example.com`); otherwise the link may be an unreachable
`localhost`.

**Exposure.** `list_reviews` (like `GET /api/reviews` and the dashboard) returns every review with
no auth — fine for the trusted-network posture, but keep auth in front if exposed.

## Notes

- Multi-tenant by id, so concurrent reviews never collide. No auth (intended for trusted /
  local networks); put it behind a reverse proxy with auth if exposing it.
- The dashboard (`/`) and `GET /api/reviews` list **across all reviews** — fine for the
  trusted-network posture, but a reason to keep auth in front when exposed.
- The **MCP wrapper** above was designed in [docs/future-mcp.md](docs/future-mcp.md), kept as its
  design/decision record.
- For agent integration details, see [AGENTS.md](AGENTS.md).
- A non-Docker, per-file CLI version lives in `../mdreview` (writes feedback to a file next to
  the source). This service is the networked, multi-session form.
