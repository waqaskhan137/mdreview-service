---
id: MR-099
title: MCP: create_review kind param + latex-aware tool wording
status: done
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

- [x] `src/mcp/client.py`: `"kind"` added to the create_review body whitelist tuple.
- [x] `src/mcp/tools.py`: optional `kind` (enum markdown/latex) in create_review's inputSchema;
      INSTRUCTIONS plus create_review/`update_source`/`get_source` descriptions state a latex
      review's source is raw LaTeX end-to-end and the markdown/mermaid rule does not apply;
      hand_back/ping_working noted not applicable.
- [x] `tools_hash` changed to cb0d063a4ee4 (staleness signal fires); `--print-version` reflects it.
- [x] `tests/mcp_smoke.py` extended: create_review kind=latex -> id, get_review reports kind=latex.
- [x] All MCP edits in this single ticket (one reconnect event for this repo's MCP clients).
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Route builder whitelist-filters args (client.py:53-119); no arg validation in the wrapper, so the
schema edit is discoverability + hash, the whitelist edit is function. Stdio clients load code at
startup: reconnect required after this lands (memory: mcp-no-restart-needed).

## Work log

- `2026-07-21` — `src/mcp/client.py` create_review whitelist gains "kind". `src/mcp/tools.py`:
  create_review inputSchema kind enum + description, get_source/update_source latex wording, and a
  LATEX paragraph in INSTRUCTIONS. `tests/mcp_smoke.py` latex round-trip assertions.

## Validation

- `2026-07-21` — full py_compile green. `route('create_review', {kind:'latex'})` body includes
  kind (whitelist passes it). `--print-version` -> tools_hash cb0d063a4ee4 (bumped). mcp_smoke
  against a flag-on server: PASS all assertions incl. "create_review kind=latex -> id" and
  "get_review reports kind=latex". Reconnect note: editing tools.py changes tools_hash, so any
  connected stdio client of THIS repo's mcp_server must reconnect to see the new schema.

## Follow-ups

