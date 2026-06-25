# mdreview-service for agents

A networked, human-in-the-loop markdown review service. You POST markdown over HTTP, hand a
human the returned URL, and poll feedback back. It is a single running service; each review is
an isolated session keyed by `id`. You never spawn a process or touch shared files.

Base URL: wherever the container is published (default `http://localhost:8137`).

## The contract

```bash
BASE=http://localhost:8137

# 1. Submit a document for review. project/session/source_path are optional provenance
#    shown on the dashboard (a sidebar Projects filter + a project/session/source_path card crumb).
resp=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"My draft","markdown":"# My draft\n\nFirst paragraph...\n",
       "project":"my-repo","session":"run-42","source_path":"docs/my-draft.md"}')
# resp = {"id":"...", "review_url":"...", "feedback_url":"...", "status_url":"...", ...}

# 2. Give review_url to the human. They open it and annotate.

# 3. Poll for feedback. status_url is cheap; feedback_url returns the notes.
curl -s "$BASE/api/reviews/<id>/status"     # {"source_updated":..., "feedback_updated":..., "comments_updated":...}
curl -s "$BASE/api/reviews/<id>/feedback"   # {"markdown":"...", "notes":[...], ...}

# 4. Apply the edits, then push the new version (the human's page live-reloads,
#    and notes your edit addressed get struck through).
curl -s -X PUT "$BASE/api/reviews/<id>/source" -H 'Content-Type: application/json' \
  -d '{"markdown":"# My draft\n\nTighter first paragraph...\n"}'

# 5. (optional) clean up
curl -s -X DELETE "$BASE/api/reviews/<id>"
```

## Detecting "the human is done"

There is no explicit "submit" from the human; feedback streams as they type. Practical options:

- Poll `status_url` and watch `comments_updated` — the live signal the viewer bumps as the human
  comments. When it has not changed for a while (e.g. a few minutes) and is non-zero, treat the
  round as complete. (`feedback_updated` is legacy: the pre-MR-036 notes write was retired, so
  nothing bumps it anymore — watch `comments_updated` instead.)
- Or just tell the human "reply 'done' when finished," and read `feedback_url` once on their
  signal.

`notes` is the structured form (each has `num`, `quote`, `note`, `addressed`); `markdown` is the
same content as a readable block per note. Use whichever you prefer. `notes[]` also includes a
projection of the **comments** (below), so this read path keeps surfacing the human's live input.

## Comments (threaded resolution)

The viewer's primary feedback surface is **threaded comments** anchored to highlighted text, shared
server-side with an `open → resolved → reopened` machine the service enforces. List → reply →
resolve:

```bash
curl -s "$BASE/api/reviews/<id>/comments?status=open"   # list what the reviewer raised (default open)
curl -s "$BASE/api/reviews/<id>/comments/<cid>"         # one full thread + status_history
curl -s -X POST "$BASE/api/reviews/<id>/comments/<cid>/reply" \
  -H 'Content-Type: application/json' -d '{"text":"clarifying question","role":"agent"}'
curl -s -X POST "$BASE/api/reviews/<id>/comments/<cid>/resolve" \
  -H 'Content-Type: application/json' -d '{"justification":"fixed in the next revision"}'  # justification optional
```

Always list `status="open"` first; reply to discuss, resolve only when actually addressed
(justification optional but recommended). **You never reopen** — that's the reviewer's UI action;
you'll see a reopened comment again via the list. Roles are attribution, not auth. Poll
`comments_updated` (on `GET /status`) for thread changes.

## Discovering and revisiting reviews

- `GET /api/reviews` lists every review with `notes_total`, `notes_addressed`, `revision`, and a
  derived `status` (`awaiting` | `feedback` | `resolved`) — the same data the dashboard at `/`
  renders. Use it to find reviews you created or to poll many at once.
- Each `PUT /source` snapshots a **history round** (the outgoing draft + the feedback it
  accumulated) and bumps `revision`. Revisit past versions with
  `GET /api/reviews/{id}/history` (the list, newest first) and
  `GET /api/reviews/{id}/history/{n}` (one round's `source`, `feedback`, `notes`). So an earlier
  draft and the feedback it received are always recoverable, not just the latest state.

## Calling it over MCP (optional)

If your runtime speaks MCP, `mcp_server.py` exposes the whole API as tools so you don't hand-roll
HTTP. It is a thin, stdlib-only stdio server (JSON-RPC 2.0, spec rev `2025-06-18`) that wraps a
running service and adds no state. Run it as `MDREVIEW_BASE=http://localhost:8137 python3
mcp_server.py`; wire it into your client's `mcpServers` as a stdio command (see `README.md`).

Tools map to the API (20): `create_review` (with optional `project`/`session`/`source_path`
provenance), `list_reviews`, `get_review`, `get_source`, `get_feedback`, `get_status`, `update_source`,
`get_history` (optional `round`), `attach_asset` (id, name, path|content_b64), `list_assets` (id),
`delete_review`, `server_info`, `create_comment`, the comment tools `list_comments` (`document_id`, `status?`=open),
`get_comment`, `reply_to_comment`, `resolve_comment` (`justification?`), `delete_comment` (junk cleanup), and the **turn-baton** tools `hand_back` (return the turn) + `ping_working` (claim/renew the lease) — `document_id` is the
review id, and there is **no `reopen` tool** (reopen is the reviewer's UI action). The same workflow
applies — `create_review`, hand the human the `review_url`, poll `get_status`/`get_feedback` or
`list_comments`, reply/resolve comments, then `update_source`. A failed call returns an `isError`
result; an unknown tool name is a `-32602` error. Set `MDREVIEW_PUBLIC_BASE` on the service so the
`review_url` you hand a human is reachable.

If a tool you expect is missing, the running MCP server is probably **stale** — a stdio server loads
its tools once at startup, so editing `mcp_server.py` needs a **reconnect**. `server_info` reports the
running wrapper's `tools_hash`; a **human/CI** compares it to `python3 mcp_server.py --print-version`
and reconnects on a mismatch (the server signals, it cannot reload itself).

The viewer renders **GFM footnotes** (`[^id]` → ordered back-ref section) and **syntax-highlighted**
fenced code (dual-scheme, both panes), plus **LaTeX math** (inline `$…$` / `\(…\)`, display `$$…$$` / `\[…\]`; prose/currency
`$` stays literal) and Mermaid. For **images** with a local/relative/site-root `src`, `attach_asset`
the bytes once (base64, keyed by the exact draft `src`); they survive every `update_source` and the
viewer repoints the `<img>` — see `CLAUDE.md` "Rich content: math and images".

## Why this shape

- **One service, many sessions.** Isolated by `id`, so any number of agents and reviews run
  concurrently with no port juggling and no shared state.
- **Decoupled.** You talk HTTP; you do not need the service's filesystem, a local process, or
  the same machine. Point `BASE` at wherever it runs.
- **Stateless client.** The POST response is your handle. Persist the `id` / urls on your side.

## Rules

- Treat `id` as opaque. Operate only on reviews you created.
- The service has no auth. If it is exposed beyond localhost, expect a proxy/token in front;
  do not assume isolation between tenants beyond the `id` namespace.
- `PUT /source` is for pushing your applied edits; do not use it to overwrite a review you did
  not create.

## Running your own instance

```bash
cd mdreview-service
docker compose up -d --build         # localhost:8137
# or pick another host port:
docker run -d -p 9000:8080 -v my-mdreview:/data mdreview-service
```

Each container is independent; point your `BASE` at it. See `README.md` for the full API table
and config.
