---
id: MR-043
title: "Docs sweep — server_info / 16-tool count + reconnect-on-stale guidance"
status: done
layer: docs
priority: P2
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: [MR-040]
branch: dev
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

- `2026-06-19` — `CLAUDE.md`/`README.md`/`AGENTS.md`/`docs/future-mcp.md`: tool count 15→16 +
  `server_info` added to each tool list (and a `server_info` row in future-mcp's table). Added a
  **Staleness** paragraph to all four: `server_info` reports the running wrapper's `tools_hash`; a
  **human/CI** compares it to `python3 mcp_server.py --print-version` and reconnects on a mismatch;
  the server signals, it cannot reload itself; an HTTP/render change needs no reconnect, a
  wrapper-code change does. Worded to avoid any "agent detects/self-detects staleness" claim.

## Validation

- `2026-06-19` — `grep -l server_info` hits all four docs; `16`/`reconnect` present in each;
  `grep -riE "agent (detects|can detect|self-detects) stale"` → **clean** (no positive self-detect
  claim); `--print-version` attributed to human/CI. `python3 -m py_compile app.py mcp_server.py` OK;
  `mcp_smoke` re-run against :8155 → **PASS** (no regression).

## Follow-ups

_None._
