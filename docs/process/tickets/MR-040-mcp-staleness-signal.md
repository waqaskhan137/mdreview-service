---
id: MR-040
title: "MCP staleness signal — tools_hash + server_info tool + --print-version"
status: ready
layer: svc
priority: P1
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: []
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Make a stale MCP server *detectable*: surface the running wrapper's identity (a code-derived
`tools_hash` + version) so a human/CI can compare it to the on-disk code and decide to reconnect.
Honestly scoped — the server can *signal* staleness, it cannot force a reconnect, and an MCP-only
agent has no on-disk comparand over MCP so it cannot self-detect (it surfaces its version for the
human/CI to compare).

## Acceptance criteria

- [ ] **One canonical hash.** A single `_tools_hash()` helper = `hashlib.sha256` over
      `json.dumps(TOOLS, sort_keys=True)` + the `INSTRUCTIONS` text, truncated to ~12 hex.
- [ ] **Three-way byte-identity (NIT-1).** `serverInfo.tools_hash` (on `initialize`), the `server_info`
      tool's `tools_hash`, and `python3 mcp_server.py --print-version`'s `tools_hash` are **byte-identical
      by construction** (all from `_tools_hash()`), asserted in `mcp_smoke.py` (MR-042).
- [ ] **`server_info` tool (16th tool, no args)** → `{name, version, protocol_version, tools_hash,
      tool_count, tool_names}`. **Dispatched locally in the wrapper** (reports the wrapper, not HTTP);
      a hard AC (NIT-2): it must succeed **with no service running and no `MDREVIEW_BASE`**, so a future
      refactor that routes it through `route()`/`http()` fails the smoke loudly.
- [ ] **`serverInfo` on `initialize`** gains `tools_hash` (now `{name, version, tools_hash}`).
- [ ] **`--print-version` argv** in `main()` prints `{version, tools_hash}` JSON and exits, touching no
      JSON-RPC loop.
- [ ] **Honest scoping (SHOULD-1).** `INSTRUCTIONS` + the `server_info` description state: `server_info`
      reports the **running** server's `tools_hash`/version; **comparison-to-on-disk is a human/CI step**
      (`--print-version`); an **MCP-only agent cannot self-detect** staleness; remedy = **reconnect**. No
      surface says "the agent detects staleness."
- [ ] **Existing 15-tool assertion updated to 16** (`mcp_smoke.py:63-67`) in this change, or the smoke
      breaks. Existing 22 assertions stay green.
- [ ] Local validation: `python3 -m py_compile mcp_server.py`; the MR-040 curl/stdio block in the plan
      (incl. the no-service `server_info` run) against a throwaway container on a non-:8139 port.

## Notes / context

- Epic: `epics/mcp-agent-effectiveness-plan.md` — Decision 1, Verification → MR-040.
- Code: `SERVER_INFO` (`mcp_server.py:31`), `handle_initialize`, `handle_tools_call`/`route()`,
  `main()`, `INSTRUCTIONS`. `mcp_server.py` is **not** containerized (no Dockerfile COPY change).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Option (b) — service publishes the *expected* wrapper hash as an MCP-reachable comparand (autonomous
  agent self-detect) — is a named non-goal/future, not built here.
