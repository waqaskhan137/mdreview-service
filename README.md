# mdreview-service

A containerized markdown review microservice. An agent POSTs markdown, gets back a review URL
for a human, and polls feedback over HTTP. One service handles many reviews, isolated by id.
No per-process spawning, no shared filesystem with the agent.

**Landing page:** [mdreview.waqasrana.space](https://mdreview.waqasrana.space/) (served from the
`gh-pages` branch; source in `site/`).

Stdlib Python only (tiny image, no pip installs). Self-contained: the marked, Mermaid, and KaTeX
renderers are vendored and served from `/static`, so the browser needs no CDN. The viewer renders
Markdown, Mermaid diagrams, and **LaTeX math** — inline `$…$` / `\(…\)` and display `$$…$$` /
`\[…\]`, matching a Jekyll/MathJax site (prose/currency `$` is left literal).

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
| GET | `/api/reviews` | | `{reviews[]}` — every review's meta + `notes_total`, `notes_addressed`, `revision`, `status` |
| GET | `/api/reviews/{id}` | | meta |
| DELETE | `/api/reviews/{id}` | | `{deleted}` |
| GET | `/api/reviews/{id}/source` | | raw markdown |
| PUT | `/api/reviews/{id}/source` | `{markdown}` | meta (snapshots a history round, then live-reloads) |
| GET | `/api/reviews/{id}/feedback` | | `{markdown, notes[], ...meta}` |
| POST | `/api/reviews/{id}/feedback` | `{markdown, notes}` | `{ok}` (the viewer calls this) |
| GET | `/api/reviews/{id}/status` | | `{source_updated, feedback_updated}` |
| GET | `/api/reviews/{id}/history` | | `{rounds[]}` — `{round, ts, notes_total, notes_addressed}`, newest first |
| GET | `/api/reviews/{id}/history/{n}` | | one round: `{source, feedback, notes[], ...round meta}` |
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
`feedback` (notes outstanding), `resolved` (all notes addressed).

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

Feedback `notes[]` entries look like:
`{"num": "3", "quote": "...", "note": "tighten this", "addressed": false}`,
and `markdown` is the same feedback rendered as a readable block per note.

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

**Tools (1:1 with the HTTP API):** `create_review` (markdown, title?, project?, session?,
source_path?), `list_reviews`, `get_review` (id), `get_feedback` (id), `get_status` (id),
`update_source` (id, markdown), `get_history` (id, round?), `attach_asset` (id, name, content_b64),
`list_assets` (id), `delete_review` (id). A failed call (bad/expired id, service down) returns an
`isError: true` result; an unknown tool name is a JSON-RPC `-32602` error.

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
