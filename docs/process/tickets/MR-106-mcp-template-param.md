---
id: MR-106
title: MCP create_review template param + mcp_smoke
status: done
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

- [x] `src/mcp/tools.py`: optional `template` free string on create_review's inputSchema + the
      well-known ids in the description + a line in INSTRUCTIONS. Not an enum (tools_hash stable).
- [x] `src/mcp/client.py:56`: `"template"` added to the whitelist tuple.
- [x] `tools_hash` flipped to 7c3de6863ce4; reconnect required (documented; MEMORY mcp-no-restart).
- [x] `tests/mcp_smoke.py`: create_review template=ieee -> id; get_review shows template=ieee.
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Create + MCP + listing surface". One reconnect event; free-string validated server-side.

## Work log

- `2026-07-21` — tools.py create_review `template` property + description + INSTRUCTIONS line;
  client.py whitelist; mcp_smoke template round-trip.

## Validation

- `2026-07-21` — py_compile green; `route('create_review',{template:'ieee'})` forwards template;
  --print-version tools_hash 7c3de6863ce4; mcp_smoke PASS incl. "template=ieee -> id" and
  "get_review reports template=ieee".

## Follow-ups
