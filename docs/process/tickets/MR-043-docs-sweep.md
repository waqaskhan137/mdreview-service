---
id: MR-043
title: "Docs sweep — server_info / 16-tool count + reconnect-on-stale guidance"
status: ready
layer: docs
priority: P2
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: [MR-040]
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Document the new MCP surface and the staleness/reconnect remedy so an agent's operator knows what
`server_info` is for and what to do when the running wrapper is stale. Docs-sweep is not
carry-over-eligible — must be `done` before sprint-12 closes (G7).

## Acceptance criteria

- [ ] **16-tool count.** Every "15 tools" string corrected to 16 (verified spots: `CLAUDE.md:137`,
      `docs/future-mcp.md:45`); `server_info` added to the tool enumeration in `CLAUDE.md` + `README.md`
      + `AGENTS.md` + `docs/future-mcp.md`.
- [ ] **Staleness/reconnect guidance** documented: `server_info` reports the running wrapper's
      `tools_hash`/version; `python3 mcp_server.py --print-version` gives the on-disk comparand; on a
      mismatch, **reconnect** the MCP client (the server signals, it cannot remediate).
- [ ] **Honest scoping (SHOULD-1):** the comparison is attributed to a **human/CI**; **no** doc claims
      the agent self-detects staleness (grep-asserted: `! grep -rin "agent detects stale\|agent.*self-detect"
      README.md AGENTS.md CLAUDE.md docs/future-mcp.md`).
- [ ] Local validation: `grep -l "server_info" README.md AGENTS.md CLAUDE.md docs/future-mcp.md` (all
      four); `python3 -m py_compile app.py` and `mcp_smoke.py` still pass (re-run to prove no regression).

## Notes / context

- Epic: `epics/mcp-agent-effectiveness-plan.md` — Decision 1 docs, Verification → MR-043.
- Touches: `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/future-mcp.md`. No behavior change.
- Depends on MR-040 (documents `server_info`/the reconnect remedy).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

_None._
