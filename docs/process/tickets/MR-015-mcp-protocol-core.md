---
id: MR-015
title: mcp_server.py — stdio JSON-RPC core (initialize, notifications/initialized, tools/list)
status: ready
layer: svc
priority: P1
sprint: sprint-04
epic: mcp-wrapper
depends_on: []
branch:
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Stand up the MCP protocol surface as a new standalone `mcp_server.py` (stdlib only, newline-
delimited JSON-RPC 2.0 over stdio) — `initialize`, `notifications/initialized`, `tools/list` with
all 8 static tool schemas — provable in isolation with no HTTP service running. Does not touch
`app.py`.

## Acceptance criteria

- [ ] **Service unchanged:** `git diff --stat "$(git merge-base origin/main HEAD)"...HEAD -- app.py viewer.html dashboard.html static Dockerfile docker-compose.yml` is **empty**.
- [ ] **Pinned protocol (build-time verify):** `initialize` returns
      `{protocolVersion:"2025-06-18", capabilities:{tools:{}}, serverInfo:{name:"mdreview-mcp", version:<str>}}`. Confirm `"2025-06-18"` against the official MCP spec/SDK at build time and correct if the spec moved.
- [ ] Capabilities advertise **tools only** (`{tools:{}}`; no resources/prompts).
- [ ] `notifications/initialized` (id-less) is acknowledged with **no** response line.
- [ ] `tools/list` returns `{tools:[…]}` whose `.name` set is exactly the 8 tools, each with a
      `description` + `inputSchema` (JSON Schema object).
- [ ] **Stream hygiene:** flush stdout after each response; exit cleanly on stdin EOF (a piped
      `printf … | python3 mcp_server.py` smoke completes, does not hang).
- [ ] Framing isolated behind a `read_message`/`write_message` pair (one-function fix if the spec's
      framing differs). Local validation: `python3 -m py_compile mcp_server.py`; pipe `initialize`
      + `tools/list` with no service running and assert the responses.

## Notes / context

Plan: `epics/mcp-wrapper-plan.md` (Tool surface; Per-ticket acceptance criteria — MR-015). **Verify
the MCP envelope/handshake against the authoritative MCP spec before writing the protocol code**
(the planner flagged it build-time-verify). Tool→endpoint table cites `app.py` lines.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
