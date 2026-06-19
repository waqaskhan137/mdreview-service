---
id: MR-035
title: MCP tools — list_comments/get_comment/reply_to_comment/resolve_comment + agent-expectation descriptions + mcp_smoke round-trip
status: ready
layer: svc
priority: P1
sprint: sprint-11
epic: comment-resolution
depends_on: [MR-033, MR-034]
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Expose the comment workflow to agents over MCP as four thin 1:1 wrappers (the established TOOLS-entry +
`route()`-branch pattern), with the brief's AGENT EXPECTATIONS encoded into the tool descriptions and
server instructions so the agent follows the workflow without extra prompting. No `reopen` tool
(reviewer-only by convention — stated honestly, not security).

## Acceptance criteria

- [ ] **Four tools**, `document_id` = review `id`: `list_comments` (`GET /comments?status=`,
      `document_id` req, `status` open|resolved|reopened|all default **open**); `get_comment`
      (`GET /comments/{cid}`, `document_id`+`comment_id` req); `reply_to_comment`
      (`POST /comments/{cid}/reply` role=agent, `document_id`+`comment_id`+`text` req); `resolve_comment`
      (`POST /comments/{cid}/resolve` role=agent, `document_id`+`comment_id` req, `justification`
      optional) → `{comment_id,status:"resolved",resolved_by:"agent",resolved_at}`.
- [ ] **Descriptions encode the workflow** (in tool descriptions **and** the module/server-instruction
      docstring): always `list_comments(status="open")` first; `reply_to_comment` for questions/
      discussion vs `resolve_comment` only when actually addressed; `justification` optional-but-
      recommended (reviewer can reopen); the agent never reopens — after a reviewer reopen it sees the
      comment again via `list_comments` (status `reopened`/`open`). State the no-reopen-tool boundary as
      convention.
- [ ] **`route()` branches** follow the existing `KeyError`-on-missing-arg pattern (mcp_server.py:165-192).
- [ ] **Docstring tool count 10 → 14** (module docstring + the `tools/call` comment).
- [ ] **`mcp_smoke.py` updates BOTH** (a) the `expected` tool-name set literal (add the four names) and
      (b) the `== 10`/`"the 10 tools"` count assertion → **14** (mcp_smoke.py:60-63) — a count-only bump
      would fail `names == expected`, so both move together.
- [ ] **Round-trip in `mcp_smoke.py`:** seed a review + a comment via HTTP `POST /comments`
      (create is reviewer-side), then `list_comments(open)` returns it → `get_comment` returns the
      thread → `reply_to_comment` grows it → `resolve_comment` (no justification) returns
      `status:"resolved",resolved_by:"agent"`; then `list_comments(open)` excludes it and
      `list_comments(resolved)` includes it.
- [ ] Local validation passes: `python3 -m py_compile app.py`; `MDREVIEW_BASE=http://localhost:8138
      python3 mcp_smoke.py` exits 0 against a rebuilt throwaway container.

## Notes / context

- Epic: `epics/comment-resolution-plan.md` — MCP section (tool table + descriptions), Verification →
  MR-035. Pattern: existing wrappers in `mcp_server.py` (TOOLS schema, `route()` dispatch,
  mcp_smoke.py:60-63 tool-count/`expected` assertion).
- Depends on MR-033 (routes) + MR-034 (resolve transition).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

_None expected._
