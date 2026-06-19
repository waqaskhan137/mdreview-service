---
id: MR-037
title: Docs sweep — README API table (+/comments, /status.comments_updated), CLAUDE.md, AGENTS.md, future-mcp, MCP docstring 10→14, comment-aware feedback/dashboard
status: done
layer: docs
priority: P2
sprint: sprint-11
epic: comment-resolution
depends_on: [MR-033, MR-034, MR-035, MR-036]
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Bring the docs in line with the shipped comment-resolution workflow so an agent reading the contract
knows the new routes, the four MCP tools, and — important — that `GET /feedback`/the dashboard are now
comment-aware. Docs-sweep is not carry-over-eligible: must be `done` before the sprint closes (G7).

## Acceptance criteria

- [ ] **README API table** gains the `/comments` rows (GET list `?status=`, POST create, GET `{cid}`,
      POST reply/resolve/reopen) and the `comments_updated` field on `GET /status`.
- [ ] **CLAUDE.md contract** documents: the comment workflow + state machine (open→resolved→reopened),
      that resolve is agent-side / reopen reviewer-side (convention not auth), and that `GET /feedback`
      now returns the **union** of legacy notes + projected comments (so existing `get_feedback`-based
      agents keep seeing live human input), with the structured threads via `GET /comments`/MCP.
- [ ] **AGENTS.md / `docs/future-mcp.md`** updated for the four new MCP tools and the AGENT EXPECTATIONS
      (list-first; reply vs resolve; justification optional-but-recommended; agent never reopens).
- [ ] **MCP docstring tool count** reads **14** (consistent with MR-035).
- [ ] **Comment-aware reads documented** wherever note counts / dashboard status are described (no stale
      "counts come only from notes.json" claim).
- [ ] Local validation passes: `python3 -m py_compile app.py`; `MDREVIEW_BASE=http://localhost:8138
      python3 mcp_smoke.py` exits 0 (docs-only, re-run to prove nothing regressed); grep the README for
      the `/comments` rows + `comments_updated` and the MCP docstring for `14`.

## Notes / context

- Epic: `epics/comment-resolution-plan.md` — Phase 5, Verification → MR-037.
- Touches: `README.md` (API table), `CLAUDE.md`, `AGENTS.md`, `docs/future-mcp.md`, `mcp_server.py`
  docstring. No behavior change.
- Depends on all of MR-033–036 (documents their shipped surface).

## Work log

- `2026-06-19` — `README.md`: added the six `/comments` API rows + `comments_updated` on `/status`;
  updated the `/feedback` row + status/counts note (comment-aware, union projection); new "Comments
  (threaded resolution)" paragraph; MCP tools list → 14 with the four comment tools + the no-reopen
  convention. `CLAUDE.md`: new "Comments (threaded resolution)" workflow section (list→reply→resolve,
  never-reopen, attribution-not-auth), `notes[]`-now-projects-comments note, MCP list → 14.
  `AGENTS.md`: same Comments section + tools-list → 14. `docs/future-mcp.md`: comment-tool rows +
  `get_status`/`get_feedback` updates + a 14-tools note.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py mcp_server.py mcp_smoke.py` OK;
  `MDREVIEW_BASE=http://localhost:8138 python3 mcp_smoke.py` → **PASS** (docs-only, re-run to prove no
  regression). Greps: README has the `/comments` rows (7 hits) + `comments_updated` (2); the MCP
  docstring reads `14 schemas`/`14 tools`; all four docs (`README`/`CLAUDE`/`AGENTS`/`future-mcp`)
  reference `reply_to_comment`/`resolve_comment`.

## Follow-ups

_None expected._
