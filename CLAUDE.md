# mdreview-service for agents

A networked, human-in-the-loop markdown review service. You POST markdown over HTTP, hand a
human the returned URL, and poll feedback back. It is a single running service; each review is
an isolated session keyed by `id`. You never spawn a process or touch shared files.

Base URL: wherever the container is published (default `http://localhost:8137`).

## The contract

```bash
BASE=http://localhost:8137

# 1. Submit a document for review. project/session/source_path are optional provenance
#    that groups the review on the dashboard (project > session > files).
resp=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"My draft","markdown":"# My draft\n\nFirst paragraph...\n",
       "project":"my-repo","session":"run-42","source_path":"docs/my-draft.md"}')
# resp = {"id":"...", "review_url":"...", "feedback_url":"...", "status_url":"...", ...}

# 2. Give review_url to the human. They open it and annotate.

# 3. Poll for feedback. status_url is cheap; feedback_url returns the notes.
curl -s "$BASE/api/reviews/<id>/status"     # {"source_updated":..., "feedback_updated":...}
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

- Poll `status_url` and watch `feedback_updated`. When it has not changed for a while (e.g. a
  few minutes) and is non-zero, treat the round as complete.
- Or just tell the human "reply 'done' when finished," and read `feedback_url` once on their
  signal.

`notes` is the structured form (each has `num`, `quote`, `note`, `addressed`); `markdown` is the
same content as a readable block per note. Use whichever you prefer.

## Discovering and revisiting reviews

- `GET /api/reviews` lists every review with `notes_total`, `notes_addressed`, `revision`, and a
  derived `status` (`awaiting` | `feedback` | `resolved`) — the same data the dashboard at `/`
  renders. Use it to find reviews you created or to poll many at once.
- Each `PUT /source` snapshots a **history round** (the outgoing draft + the feedback it
  accumulated) and bumps `revision`. Revisit past versions with
  `GET /api/reviews/{id}/history` and `GET /api/reviews/{id}/history/{n}`. An earlier draft and
  the feedback it received are always recoverable, not just the latest state.

## Calling it over MCP (optional)

`mcp_server.py` is a thin, stdlib-only stdio MCP server (JSON-RPC 2.0, spec rev `2025-06-18`)
exposing the API as tools (`create_review`, `list_reviews`, `get_review`, `get_feedback`,
`get_status`, `update_source`, `get_history`, `delete_review`). Run
`MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py`; smoke with `mcp_smoke.py`. It wraps a
running service and adds no state. Set `MDREVIEW_PUBLIC_BASE` on the service so a relayed
`review_url` is reachable. See `README.md` and `docs/future-mcp.md`.

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

## Delivery process

Feature work in this repo runs through a file-based, gated delivery process under
`docs/process/` (committed + pushed, so any session reconstructs state from frontmatter + git).
Read `docs/process/README.md` for the gates (G0-G8), conventions, and layout. The
`/feature-cycle` skill (`.claude/skills/feature-cycle/`) drives a brief through
plan -> independent review (G1) -> tickets -> sprint -> implement -> close review (G7) -> PR,
using the `mdreview-planner` and `cycle-retrospective` agents and the global `staff-critic`.

- Tickets `MR-###` in `docs/process/tickets/`; the board is `docs/process/TRACKER.md`.
- Validation gate: `python3 -m py_compile app.py` (+ `docker build` for infra, a browser render
  for UI). No test framework.
- Commits: conventional subject with the ticket ID; this repo keeps the `Co-Authored-By: Claude`
  trailer.
- For the current epic / sprint and shipped history, see `docs/process/TRACKER.md` (source of
  truth) — don't hard-code it here, it goes stale.
