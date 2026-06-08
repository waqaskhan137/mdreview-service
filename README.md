# mdreview-service

A containerized markdown review microservice. An agent POSTs markdown, gets back a review URL
for a human, and polls feedback over HTTP. One service handles many reviews, isolated by id.
No per-process spawning, no shared filesystem with the agent.

Stdlib Python only (tiny image, no pip installs). Self-contained: the Mermaid and marked
renderers are vendored and served from `/static`, so the browser needs no CDN.

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
| POST | `/api/reviews` | `{markdown, title?}` | `{id, review_url, feedback_url, source_url, status_url}` |
| GET | `/api/reviews/{id}` | | meta |
| DELETE | `/api/reviews/{id}` | | `{deleted}` |
| GET | `/api/reviews/{id}/source` | | raw markdown |
| PUT | `/api/reviews/{id}/source` | `{markdown}` | meta (triggers live-reload) |
| GET | `/api/reviews/{id}/feedback` | | `{markdown, notes[], ...meta}` |
| POST | `/api/reviews/{id}/feedback` | `{markdown, notes}` | `{ok}` (the viewer calls this) |
| GET | `/api/reviews/{id}/status` | | `{source_updated, feedback_updated}` |
| GET | `/review/{id}` | | viewer HTML (human opens) |
| GET | `/healthz` | | `{ok}` |

Feedback `notes[]` entries look like:
`{"num": "3", "quote": "...", "note": "tighten this", "addressed": false}`,
and `markdown` is the same feedback rendered as a readable block per note.

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | in-container listen port |
| `MDREVIEW_DATA` | `/data` | storage dir (mount a volume) |
| `MDREVIEW_PUBLIC_BASE` | empty | if set (e.g. `https://review.example.com`), `review_url`/`feedback_url` use it; otherwise the request Host header is used |

## Notes

- Multi-tenant by id, so concurrent reviews never collide. No auth (intended for trusted /
  local networks); put it behind a reverse proxy with auth if exposing it.
- For agent integration details, see [AGENTS.md](AGENTS.md).
- A non-Docker, per-file CLI version lives in `../mdreview` (writes feedback to a file next to
  the source). This service is the networked, multi-session form.
