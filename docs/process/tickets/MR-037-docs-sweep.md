---
id: MR-037
title: Docs sweep — README API table (+/comments, /status.comments_updated), CLAUDE.md, AGENTS.md, future-mcp, MCP docstring 10→14, comment-aware feedback/dashboard
status: ready
layer: docs
priority: P2
sprint: sprint-11
epic: comment-resolution
depends_on: [MR-033, MR-034, MR-035, MR-036]
branch:
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

_None expected._
