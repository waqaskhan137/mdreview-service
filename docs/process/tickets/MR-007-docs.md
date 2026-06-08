---
id: MR-007
title: Docs — provenance/list/history fields + docs/future-mcp.md
status: done
layer: docs
priority: P2
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-001, MR-002, MR-003, MR-004, MR-005, MR-006]
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Keep the docs true to the shipped behavior, and capture the deferred MCP wrapper so it is not
lost.

## Acceptance criteria

- [ ] `README.md` + `AGENTS.md` + `CLAUDE.md`: document the optional `project`/`source_path`/
      `session` POST fields (API table + the agent contract example), the new `GET /api/reviews`
      list endpoint, the `/api/reviews/{id}/history` + `/history/{n}` routes, the dashboard at `/`,
      and that `/api` (and `Accept: application/json` on `/`) serves the JSON descriptor.
- [ ] New `docs/future-mcp.md` sketches the follow-up MCP wrapper: a thin stdio server mapping
      tools (`create_review`, `list_reviews`, `get_feedback`, `update_source`, `delete_review`)
      onto the existing HTTP endpoints. No code.
- [ ] `docs/process/backlog.md` has an entry for the MCP wrapper follow-up.
- [ ] Note the cross-review exposure of the list/dashboard in the README (trusted-network posture).
- [ ] Validation: docs match the actual routes/fields shipped in MR-001..006 (cross-check against
      `app.py`).

## Notes / context

- Per Definition of Done, durable behavior docs normally ship in the same change as the behavior;
  this ticket is the consolidation/sweep for anything not already updated in MR-001..006.
- Epic: `epics/review-dashboard-plan.md`.

## Work log

- `2026-06-08` — `README.md`: rewrote the API table to add `GET /`, `GET /api`,
  `GET /api/reviews`, the two `/history` routes, and the optional `project`/`source_path`/
  `session` POST fields; added provenance, status, history, and cross-review exposure notes.
  `AGENTS.md` + `CLAUDE.md`: added the provenance fields to the contract example and a
  "Discovering and revisiting reviews" section (list + history). New `docs/future-mcp.md`
  sketches the deferred MCP wrapper (tool surface mapped 1:1 to the HTTP API). `backlog.md`
  already carried the MCP follow-up from the seed.

## Validation

- `2026-06-08` — cross-checked every documented route against `app.py` route matchers: `/`,
  `/api`, `/api/reviews` (GET+POST), `/api/reviews/{id}` (+`/source`,`/feedback`,`/status`),
  `/history` (+`/{n}`), `/review/{id}`, `/static`, `/healthz` — all present. Confirmed
  `docs/future-mcp.md` exists and `backlog.md` references the MCP wrapper.

## Follow-ups

The MCP wrapper itself (separate epic).
