---
id: MR-044
title: "create_comment MCP tool + anchor-by-quoted-text (agents author review comments)"
status: done
layer: svc
priority: P1
sprint: —
epic: mcp-agent-effectiveness
depends_on: []
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Out-of-cycle quick fix (user-approved: "Quick fix + retro-ticket"). An agent asked to *comment on a
doc* couldn't: the comment-resolution epic scoped comment authoring reviewer-side, so the MCP had
`list/get/reply/resolve` but no **create** — the agent reverse-engineered the raw `POST /comments`
and, lacking `block_num` (a rendered-viewer concept), produced comments that rendered as gutter cards
with **no inline highlight**. This makes agent-authored review comments a first-class, anchored
capability.

## Acceptance criteria

- [x] **`create_comment` MCP tool** (17th): `create_comment(document_id, quoted_text?, text,
      role?="agent")` → `POST /api/reviews/{id}/comments`. `quoted_text` anchors; omit for a doc-level
      note; role default `agent`. Returns the new `comment_id`.
- [x] **Viewer anchors by quoted-text when `block_num` is absent.** `highlightComment` now prefers the
      authored `block_num`, else scans every `.blk` for the quoted phrase — so an agent-authored
      comment (which can't know `block_num`) still highlights inline; the gutter card + margin bar
      derive their block from where the highlight landed.
- [x] `mcp_smoke` → **17 tools** + a `create_comment` → `list_comments` round-trip (anchored, role
      agent); `agent_smoke` `server_info` count → 17. Existing assertions green.
- [x] Docs: README/CLAUDE/AGENTS/future-mcp 16→17 + `create_comment`.
- [x] Local validation: `python3 -m py_compile`; `mcp_smoke` + `agent_smoke` PASS on throwaway :8155;
      viewer fix verified on :8139 (6 agent-authored comments with empty `block_num`: inline
      highlights **0 → 5**, the 6th posted with no quoted_text → gutter-only, correct).

## Notes / context

- Shipped commits: `acaafda` (viewer anchor-by-quoted-text), `49b93f2` (create_comment tool),
  `4633bd6` (docs). Out-of-cycle per the user's "quick fix + retro-ticket" choice; this ticket records
  it honestly (G1/G7 not run for this bundle — it's a 1:1 tool exposure + a one-function viewer fix,
  smoke-validated).
- Triggered by the same agent-self-serve theme as the `mcp-agent-effectiveness` epic — the second
  proof of that lesson (an operator had to hand-hold; the gap is now a tool).

## Work log

- `2026-06-19` — `mcp_server.py` (create_comment tool + route, 17), `viewer.html` (highlightComment
  all-block scan), `mcp_smoke.py` / `agent_smoke.py` (17 + round-trip), docs sweep. `:8139` rebuilt
  for the viewer fix.

## Validation

- `2026-06-19` — see Acceptance criteria. `mcp_smoke` PASS (17 tools, create→list round-trip);
  `agent_smoke` PASS (render loop intact, 17); viewer highlights 0→5 on the live review.

## Follow-ups

- **No `DELETE /comments/{cid}` route** — surfaced while the agent reverse-engineered the API (its junk
  probe comments could only be *resolved* out, not deleted). Decide whether to add a delete route /
  MCP tool, or accept resolve-as-cleanup. Logged for the owner.
- Consider whether agent-authored comments want a distinct viewer affordance beyond the `agent` role
  tint.
