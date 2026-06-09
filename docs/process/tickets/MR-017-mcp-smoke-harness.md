---
id: MR-017
title: mcp_smoke.py — stdlib JSON-RPC smoke harness + container round-trip
status: done
layer: svc
priority: P1
sprint: sprint-04
epic: mcp-wrapper
depends_on: [MR-016]
branch: dev (mcp_smoke.py)
created: 2026-06-09
updated: 2026-06-09
---

## Goal

A repeatable, dependency-free smoke for the wrapper (the MCP analogue of
`scripts/render-smoke.sh`): feed a handcrafted JSON-RPC sequence into `mcp_server.py`, parse and
assert the responses, and round-trip against a running container.

## Acceptance criteria

- [ ] **Service unchanged:** same base-relative empty-diff check as MR-015.
- [ ] **Stdlib only:** `mcp_smoke.py` uses only `json` + `subprocess` (+ `os`/`sys`); **no `jq`, no
      pip** (bash + jq would reintroduce a dependency — the whole point of the stdlib spine).
- [ ] Asserts: the MR-015 protocol surface (8 tools, pinned `initialize` shape); the MR-016
      happy-path envelope; the `isError:true` 404 path; the `-32602` unknown-tool path; and the
      container `create_review` → `update_source` round-trip (extract `id`, parse
      `content[0].text`).
- [ ] Exits nonzero with a clear message on any failed assertion; exit 0 when all pass.
- [ ] Local validation: `python3 -m py_compile mcp_smoke.py`; run it against a rebuilt container and
      capture output as the G4/G7 evidence.

## Notes / context

Plan: `epics/mcp-wrapper-plan.md` (Phase 3; Per-ticket AC — MR-017). Becomes this epic's smoke
evidence at close.

## Work log

- `2026-06-09` — new `mcp_smoke.py` (stdlib `json`+`subprocess`+`os`/`sys`; no jq/pip). Drives
  `mcp_server.py` over stdio and asserts: notification gets no response; pinned `initialize` shape
  (protocolVersion 2025-06-18, tools-only, serverInfo); exactly the 8 tools with schemas;
  `tools/call` text-content envelope; `create_review`->`update_source` round-trip (revision>=1,
  then deletes the smoke review); bad id -> `isError:true`; unknown tool -> `-32602`. Exits nonzero
  naming any failed assertion.

## Validation

- `2026-06-09` — `py_compile` OK. Ran against the live container: **11/11 assertions pass, exit 0**.
  Confirmed stdlib-only imports (os/sys/json/subprocess). Service-unchanged diff empty.

## Follow-ups

None.
