# Future: an MCP wrapper for mdreview-service

Status: **not built.** Deferred from the `review-dashboard` epic (2026-06-08). This is a sketch of
the intended shape so the follow-up is a clean, self-contained deliverable when picked up. See
`docs/process/backlog.md`.

## Why

The whole mdreview contract is already a small, stable HTTP API. An MCP server lets an agent call
it as first-class tools (with schemas and discovery) instead of hand-rolling `curl`/HTTP, which is
the more natural interface for agent runtimes that speak MCP. The HTTP service stays exactly as it
is; the wrapper is additive and optional.

## Shape

A thin **stdio MCP server** that holds a `BASE` URL (default `http://localhost:8137`) and maps
each tool call onto the existing HTTP endpoint. No state of its own; the HTTP service remains the
source of truth. Stdlib-only stays a goal — if written in Python, prefer a minimal MCP
implementation over a heavy SDK so the "no pip installs" spirit is preserved (or ship the wrapper
as a clearly separate, optional component with its own dependencies).

### Tools (1:1 with the HTTP API)

| Tool | Maps to | Notes |
|------|---------|-------|
| `create_review` | `POST /api/reviews` | args: `markdown`, `title?`, `project?`, `source_path?`, `session?`; returns `id` + urls |
| `list_reviews` | `GET /api/reviews` | returns the summaries (status, counts, revision) the dashboard uses |
| `get_review` | `GET /api/reviews/{id}` | meta |
| `get_feedback` | `GET /api/reviews/{id}/feedback` | `{markdown, notes[]}` |
| `get_status` | `GET /api/reviews/{id}/status` | cheap poll: `{source_updated, feedback_updated}` |
| `update_source` | `PUT /api/reviews/{id}/source` | pushes applied edits; snapshots a history round, live-reloads the human's page |
| `get_history` | `GET /api/reviews/{id}/history` (+ `/{n}`) | list rounds / fetch one past draft + its feedback |
| `delete_review` | `DELETE /api/reviews/{id}` | cleanup |

### Behavior to preserve

- **Provenance** flows straight through `create_review` (`project`/`session`/`source_path`).
- **Polling** stays the agent's job: `get_status` is the cheap signal; `get_feedback` returns the
  notes. The "human is done" heuristic in `AGENTS.md` is unchanged.
- **No auth** in the wrapper either; it inherits the trusted-network posture of the service.

## Out of scope for the wrapper

- Re-implementing review logic (it just proxies HTTP).
- Any change to the HTTP service or its storage format.

## How it would be delivered

Its own epic + sprint under `docs/process/` (a new `requirements/mcp-wrapper.md` brief -> epic ->
tickets), since it is an independent component with its own validation (an MCP client can list the
tools and round-trip a `create_review` -> `update_source`).
