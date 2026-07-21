---
id: MR-099
title: MCP: create_review kind param + latex-aware tool wording
status: ready
layer: svc
priority: P2
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-093]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Let an agent create and drive latex reviews first-class over MCP, in exactly one reconnect event.

## Acceptance criteria

- [ ] `src/mcp/client.py`: `"kind"` added to the create_review body whitelist tuple (client.py:56).
- [ ] `src/mcp/tools.py`: optional `kind` in create_review's inputSchema; INSTRUCTIONS plus
      `update_source`/`get_source` descriptions state that a latex review's source is raw LaTeX
      end-to-end and the markdown authoring rules do not apply; hand_back/ping_working noted as
      not applicable to latex reviews.
- [ ] `tools_hash` changes (staleness signal fires); `--print-version` reflects it.
- [ ] `tests/mcp_smoke.py` extended: create_review with kind=latex round-trips (meta carries the
      field server-side).
- [ ] All MCP edits in this single ticket (one reconnect event, documented in the work log).
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Route builder whitelist-filters args (client.py:53-119); no arg validation in the wrapper, so the
schema edit is discoverability + hash, the whitelist edit is function. Stdio clients load code at
startup: reconnect required after this lands (memory: mcp-no-restart-needed).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

