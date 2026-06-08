---
id: sprint-01
name: Review dashboard
status: closed
start: 2026-06-08
end: 2026-06-15
goal: Ship the review dashboard, provenance, history, and Google-Docs gutter comments (MR-001..007).
close_review: reviews/sprint-01-close-review-2026-06-08.md
---

## Goal

Deliver the `review-dashboard` epic end to end: provenance tagging, a discoverable dashboard at
`/`, lightweight history, and Google-Docs style inline comments in the viewer. Success by the end
date: a human can open `/`, see reviews grouped by project and session with status at a glance,
open any of them, and leave anchored margin comments; an agent can list reviews and pull back past
history rounds.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-001 | Persist provenance (project/source_path/session) on POST + meta | svc | P1 | done |
| MR-002 | summary() + list_reviews() + GET /api/reviews | svc | P1 | done |
| MR-003 | Serve dashboard at /; move JSON descriptor to /api | svc | P1 | done |
| MR-005 | History snapshots on PUT + /history routes | svc | P2 | done |
| MR-004 | dashboard.html — Project>Session grouping, status pills, open/delete, revision badge | ui | P1 | done |
| MR-006 | viewer.html — Google-Docs gutter comments + minimal history view | ui | P1 | done |
| MR-007 | Docs — provenance/list/history fields + docs/future-mcp.md | docs | P2 | done |

## Preferred execution order

Service endpoints before the UI that consumes them; history before the dashboard so the revision
badge has data.

1. MR-001 — provenance fields
2. MR-002 — list + summary endpoint
3. MR-003 — dashboard route + /api descriptor
4. MR-005 — history snapshots + /history routes
5. MR-004 — dashboard.html
6. MR-006 — viewer gutter comments + history view
7. MR-007 — docs sweep + future-mcp.md

## Notes / retro

- All 7 committed tickets shipped to `dev` and are `done`. Service work (MR-001/002/003/005)
  validated with `py_compile` + curl smokes; UI work (MR-004/006) validated with headless-Chrome
  render evidence under `reviews/sprint-01-render-evidence-2026-06-08/`.
- **G7 render-smoke caught a real shipping bug:** the Dockerfile did not `COPY dashboard.html`,
  so the rebuilt container served an empty `200` at `/`. A route/200 check would have missed it;
  the render-smoke caught it (fixed in commit `1326462`). The gate did its job on the first cycle.
- Independent `staff-critic` close review: PASS-WITH-FIXES, no blockers. Both SHOULD-FIX items
  resolved (breakpoint AC reconciled to the gutter geometry; dynamic-render evidence strengthened
  with a `--dump-dom` node assertion). Nits acknowledged. See
  `reviews/sprint-01-close-review-2026-06-08.md`.
- **Carry-overs:** none functional. One evidence-tooling idea (automated post-interaction
  screenshot) parked in `backlog.md`.

## Close gate (G7)

- [x] every committed ticket is `done` (no carry-overs);
- [x] a staff-critic sprint-close review exists at `reviews/sprint-01-close-review-2026-06-08.md`,
      verifying shipped work against each ticket's AC, including a browser render-smoke of `/` and
      `/review/{id}` with screenshots under `reviews/sprint-01-render-evidence-2026-06-08/`;
- [x] retro + carry-overs recorded above, `close_review:` set.
