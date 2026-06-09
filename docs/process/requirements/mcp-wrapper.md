---
slug: mcp-wrapper
captured: 2026-06-09
source: user request 2026-06-09 (waqas) — "feature-cycle the MCP wrapper"; design input docs/future-mcp.md (sketched at MR-007); backlog.md entry
related_epic: epics/mcp-wrapper-plan.md
audience: developer tooling (agents that speak MCP); not a client demo
---

# MCP wrapper for mdreview-service

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> Build the MCP wrapper for mdreview-service: a thin stdio MCP server over the existing HTTP API.
> See `docs/future-mcp.md` (the sketch) and the `backlog.md` entry. It lets an agent call the
> review service as first-class MCP tools instead of hand-rolling HTTP. The HTTP service stays
> exactly as it is; the wrapper is additive and optional.

Design input already on record (`docs/future-mcp.md`, written in MR-007):
- A thin **stdio MCP server** holding a `BASE` URL (default `http://localhost:8137`), mapping each
  tool call onto the existing HTTP endpoint. No state of its own; the HTTP service stays the
  source of truth.
- Intended tools (1:1 with the HTTP API): `create_review`, `list_reviews`, `get_review`,
  `get_feedback`, `get_status`, `update_source`, `get_history`, `delete_review`.
- Preserve: provenance flows through `create_review` (`project`/`session`/`source_path`); polling
  stays the agent's job (`get_status` cheap, `get_feedback` returns notes); no auth in the wrapper
  (inherits the trusted-network posture).
- Prefer to keep the stdlib-only / zero-pip spirit if written in Python (a minimal JSON-RPC-over-
  stdio implementation over a heavy SDK), OR ship as a clearly separate optional component with
  its own dependencies — a decision for the plan.

## Carry-over note (from the process-hardening-2 retrospective)

- This cycle's **open** carries process-hardening-2 retro **suggestion 1**: the pre-G7 board
  rail should not only reconcile the board but also **run and record the unconditional
  rebuild + `curl /healthz` + `/api/reviews` smoke**. It is a `[skill]` process tweak, not part
  of the MCP feature; apply it when closing this cycle's sprint (run + record the smoke in the G7
  evidence) and consider grooming it into the process backlog rather than letting it ride only as
  a memory.

## Amendments

(none yet)
