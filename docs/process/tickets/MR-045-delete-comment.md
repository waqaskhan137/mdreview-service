---
id: MR-045
title: "delete_comment — hard-remove junk comments (DELETE route + MCP tool)"
status: done
layer: svc
priority: P2
sprint: —
epic: mcp-agent-effectiveness
depends_on: [MR-044]
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Out-of-cycle quick fix (user-approved follow-up to MR-044). While reverse-engineering `POST /comments`,
an agent created junk probe comments it **could not delete** — `DELETE /comments/{cid}` had no route, so
junk could only be *resolved* out (still in the store). Add a real hard delete for junk cleanup.

## Acceptance criteria

- [x] `DELETE /api/reviews/{id}/comments/{cid}` → `{deleted: cid}`; removes the comment from
      `comments.json` under `_lock`, bumps `comments_updated`; `404` if the comment is missing.
      Distinct from resolve (which only hides a real comment in the Resolved panel).
- [x] `delete_comment(document_id, comment_id)` MCP tool (18th); description draws the line (delete a
      junk/mistaken comment irreversibly vs resolve real feedback; never delete the reviewer's feedback).
- [x] docstring 17→18; `mcp_smoke` **18 tools** + a `create_comment → delete_comment → list` round-trip
      (gone after delete); `agent_smoke` `server_info` count → 18; docs (README API row + tool lists;
      CLAUDE/AGENTS/future-mcp).
- [x] Local validation: `python3 -m py_compile`; curl `DELETE → {deleted}`, list empties, re-delete
      `404`; `mcp_smoke` + `agent_smoke` PASS on throwaway :8155; `:8139` rebuilt (DELETE is in `app.py`).

## Notes / context

- Shipped commit: `b4de302`. Out-of-cycle per the user's request; recorded honestly (no G1/G7 for this
  one-route + one-tool addition; smoke-validated). The MR-044 follow-up "no DELETE route" is now closed.
- Roles are attribution-only; delete is not access-gated. The tool description is the only guard
  (use on your own junk, not to dismiss feedback).

## Work log

- `2026-06-19` — `app.py` (DELETE on `/comments/{cid}` + docstring), `mcp_server.py` (delete_comment
  tool + route, 18), `mcp_smoke.py`/`agent_smoke.py` (18 + delete round-trip), docs. `:8139` rebuilt.

## Validation

- `2026-06-19` — curl: create → `DELETE` → `{deleted}`, `list` count 0, re-delete → `404`. `mcp_smoke`
  PASS (18 tools, create→delete→list round-trip); `agent_smoke` PASS (render loop intact, 18).

## Follow-ups

- No viewer delete affordance (delete is API/MCP only); a human cleans junk via resolve or asks the
  agent. Add a gutter "delete" control only if wanted.
