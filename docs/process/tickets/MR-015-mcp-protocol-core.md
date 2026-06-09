---
id: MR-015
title: mcp_server.py — stdio JSON-RPC core (initialize, notifications/initialized, tools/list)
status: done
layer: svc
priority: P1
sprint: sprint-04
epic: mcp-wrapper
depends_on: []
branch: dev (new file mcp_server.py)
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

- `2026-06-09` — new `mcp_server.py` (stdlib only): newline-delimited JSON-RPC 2.0 over stdio with
  isolated `read_messages`/`write_message`; `initialize` (echoes client protocolVersion if
  supported else offers `2025-06-18`, capabilities `{tools:{}}`, serverInfo `mdreview-mcp`);
  `notifications/initialized` and other notifications get no response; `tools/list` returns all 8
  static tool schemas; `ping` -> `{}`; unknown method -> `-32601`. `tools/call` dispatch is MR-016
  (currently unknown-method). Stdout flushed per response; loop exits on stdin EOF. Protocol
  grounded against the MCP spec rev 2025-06-18 (lifecycle + tools) via WebFetch.

## Validation

- `2026-06-09` — `python3 -m py_compile mcp_server.py` OK. Piped `initialize` +
  `notifications/initialized` + `tools/list` with **no service running**: exactly 2 responses (the
  notification got none); `initialize` returned `protocolVersion 2025-06-18`, `capabilities
  {tools:{}}`, `serverInfo.name mdreview-mcp`; `tools/list` returned the exact 8 tool names each
  with a description + object `inputSchema`. Unknown method -> `-32601`. Service-unchanged
  base-relative diff (app.py/UI/Docker/compose) is empty.

## Follow-ups

None.
