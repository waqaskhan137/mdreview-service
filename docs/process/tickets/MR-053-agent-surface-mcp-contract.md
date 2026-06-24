---
id: MR-053
title: Agent surface — hand_back MCP tool + lease-ping tool + CLAUDE.md contract note
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs  (mcp_server.py = svc; CLAUDE.md = docs, in-same-change)
priority: P2
sprint: sprint-16
epic: agent-handoff-baton
depends_on: [MR-051]
branch: MR-053-agent-surface-mcp-contract
created: 2026-06-23
updated: 2026-06-23
---

## Goal

Give an agent a first-class way to use the baton over MCP, and document the agent contract. Two thin
tools over the `/handoff` route MR-051 ships, plus a `CLAUDE.md` note describing the find-work loop,
the lease heartbeat, the blocked convention, and the reconnect requirement. `mcp_server.py` +
`CLAUDE.md`. Independent of MR-052.

## Acceptance criteria

- [ ] **`hand_back(document_id, message, state?)`** MCP tool → `POST /handoff {to:"reviewer", state,
      message}` (`state` defaults to `"done"`). Added to the `TOOLS` list (adjacent to the comment
      tools) and a `route()` arm (`mcp_server.py:349-407`, before `return None`).
- [ ] **Lease-ping tool, named `ping_working`** (or `renew_lease`) — **not** `take_turn` (G1 NIT-2:
      `take_turn` reads like the viewer's *reclaim*, the opposite of an agent lease heartbeat) →
      `POST /handoff {state:"working", owner, message?}`. Its description states it claims/renews the
      lease and that a foreign-owned lease returns `409` (the agent skips that review).
- [ ] **`get_status` passthrough confirmed** — no code change, no reconnect: the new `turn` /
      `turn_updated` / `handoff` / `agent_status` fields flow through `get_status` because it proxies
      `/status` verbatim (`mcp_server.py:363-364`). The smoke proves this.
- [ ] **`mcp_smoke.py`** covers: `tools/list` includes `hand_back` and `ping_working`; a `hand_back`
      call round-trips through a running service and flips `turn` to `reviewer`; `get_status` returns
      the new fields.
- [ ] **`CLAUDE.md` agent-contract note** (in the same change) documents: the find-work loop (poll
      `GET /api/reviews`, take owned reviews with `turn == agent`); the lease-heartbeat obligation
      (periodic `ping_working` while holding the turn); the **blocked** convention (a comment **reply**
      + `hand_back state:"blocked"`, never `reopen` — reopen is the reviewer's UI action, deliberately
      not an MCP tool); and **the reconnect requirement** (the stdio server loads its tool list at
      startup, so a human/CI must reconnect to pick up the two new tools; pure HTTP/render changes do
      not need a reconnect).
- [ ] **Validation.** `python3 -m py_compile mcp_server.py` passes; `MDREVIEW_BASE=$B python3
      mcp_smoke.py` exits 0 against a throwaway service; `python3 mcp_server.py --print-version`
      reports a **changed** `tools_hash` (`mcp_server.py:275-283`) vs the pre-MR-053 value (expected —
      two new tools), and the Work log records the **reconnect** obligation.

## Notes / context

- Epic plan §Agent surface (`mcp_server.py` + `CLAUDE.md`) and §Verification → MR-053.
- Anchors: `TOOLS` list `mcp_server.py:67-272`; `route()` `:349-407`; `get_status` proxy `:363-364`;
  `tools_hash` `:275-283`; `http()` raises `ToolError` on non-2xx `:342-344` (so a `409` foreign-owner
  lease claim surfaces as an error the agent treats as "skip this review").
- `hand_back` and `ping_working` are thin wrappers — no new server logic (MR-051 owns the route).

## Work log

- `2026-06-23` — **`mcp_server.py`:** added `hand_back` + `ping_working` to `TOOLS` (adjacent to the
  comment tools) and two `route()` arms mapping both onto `POST /handoff` (`hand_back` →
  `{to:"reviewer", state, message}`, `state` default `"done"`; `ping_working` →
  `{state:"working", owner, message?}`). A `409` foreign-owner lease surfaces through `http()` as a
  `ToolError` (the agent backs off). `get_status` unchanged — the `turn`/`agent_status` fields pass
  through (no reconnect for the passthrough; the two **new tools** do need a client reconnect).
  **`mcp_smoke.py`:** expected set 18→20 + both count checks (`tools/list`, `tool_count`) + a
  description check per new tool + a `ping_working`→`hand_back` round-trip.
- **Deliberate scope-widening** (blocking-rule, recorded so it isn't a phantom): to keep the epic's
  docs consistent at close rather than leave a trailing docs-sweep, the tool count **18→20** was
  updated across `CLAUDE.md` / `README.md` / `AGENTS.md` / `docs/future-mcp.md` + the in-code comment;
  `CLAUDE.md` gained a **"The turn baton"** agent-contract section (find-work loop, lease heartbeat,
  blocked-via-comment-reply, reconnect) and an explicit-handoff bullet under "Detecting the human is
  done"; the `README` API table gained the **`POST /handoff`** row and the new `/status` fields.

## Validation

- `2026-06-23` — `python3 -m py_compile mcp_server.py mcp_smoke.py app.py` OK. `mcp_smoke.py` against a
  throwaway service: **44/44 ok, exit 0** — including "tools/list returns exactly the **20** tools",
  "tool_count == **20**", the `hand_back`/`ping_working` description checks, and the round-trip
  (`ping_working` → `agent_status.owner` set; `hand_back` → `turn=reviewer` + `agent_status.state=done`).
  `python3 mcp_server.py --print-version` → `tools_hash a97fb4f09e7c` (**changed**; the two new tools
  require an MCP client **reconnect** to appear — pure HTTP/render changes, like MR-051/MR-052, do
  not). No `app.py` change.

## Follow-ups

- The CLAUDE.md "Detecting the human is done" heuristic section becomes superseded by the explicit
  baton; note (don't necessarily delete) it when writing the contract.
