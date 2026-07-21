---
id: MR-106
title: MCP create_review template param + mcp_smoke
status: ready
layer: mcp
priority: P2
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-103]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Let the agent request a template by id when creating a latex review.

## Acceptance criteria

- [ ] `src/mcp/tools.py`: optional `template` FREE STRING on create_review's inputSchema (not an
      enum, so tools_hash stays stable as the catalog grows); well-known ids in the description.
- [ ] `src/mcp/client.py:56`: add `"template"` to the create_review whitelist tuple.
- [ ] `tools_hash` flips (`--print-version`); reconnect required (documented).
- [ ] `tests/mcp_smoke.py`: create_review with template=ieee -> id; get_review shows the template id.
- [ ] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Create + MCP + listing surface". One reconnect event; free-string validated server-side.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
