# An MCP wrapper for mdreview-service

Status: **SHIPPED** (2026-06-09, epic `mcp-wrapper` / sprint-04). Built as **`mcp_server.py`**
(the stdlib stdio server) with **`mcp_smoke.py`** (the dependency-free smoke). This file was the
original sketch; the shape below is what was built. To run:
`MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py` (see `README.md` for the client config
and the `MDREVIEW_PUBLIC_BASE` reachability note).

The implementation followed this sketch with two refinements decided during review: it is
**stdlib-only** (newline-delimited JSON-RPC 2.0, no SDK/pip), and `get_history` is **one tool**
covering both `/history` and `/history/{n}` via an optional `round` arg.

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
| `get_feedback` | `GET /api/reviews/{id}/feedback` | `{markdown, notes[]}` — `notes[]` now also projects the comments |
| `get_status` | `GET /api/reviews/{id}/status` | cheap poll: `{source_updated, feedback_updated, comments_updated}` |
| `update_source` | `PUT /api/reviews/{id}/source` | pushes applied edits; snapshots a history round, live-reloads the human's page |
| `get_history` | `GET /api/reviews/{id}/history` (+ `/{n}`) | list rounds / fetch one past draft + its feedback |
| `delete_review` | `DELETE /api/reviews/{id}` | cleanup |
| `list_comments` | `GET /api/reviews/{id}/comments?status=` | `document_id` (=id), `status?`=open; the threaded comments |
| `get_comment` | `GET /api/reviews/{id}/comments/{cid}` | one full thread + `status_history` |
| `reply_to_comment` | `POST /api/reviews/{id}/comments/{cid}/reply` | discuss without resolving |
| `resolve_comment` | `POST /api/reviews/{id}/comments/{cid}/resolve` | agent resolves; `justification?`. No `reopen` tool — reviewer-only UI action |
| `server_info` | (local — no HTTP) | the running wrapper's `{name, version, protocol_version, tools_hash, tool_count, tool_names}`; for staleness detection |

> The shipped server also exposes `attach_asset`/`list_assets` (images) — **16 tools** total. See
> `README.md` / `CLAUDE.md` for the current full set.

**Staleness.** A stdio MCP server loads its code + tool list once at process start; editing
`mcp_server.py` does nothing until the client **reconnects**. `server_info` reports the *running*
wrapper's `tools_hash`; a **human/CI** compares it to the on-disk `python3 mcp_server.py
--print-version` and reconnects on a mismatch (the server signals its identity, it cannot reload
itself — an HTTP/render change needs no reconnect; a wrapper-code change does).

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
