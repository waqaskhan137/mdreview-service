---
id: MR-003
title: Serve dashboard at /; move JSON descriptor to /api
status: ready
layer: svc
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-002]
branch:
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Give humans a front door. Today `/` returns a tiny JSON descriptor. Serve the dashboard HTML there
for browsers while keeping the descriptor reachable for anything that probes `/`.

## Acceptance criteria

- [ ] `GET /` serves `dashboard.html` (via `_read(os.path.join(HERE, "dashboard.html"))`, like
      `viewer.html` at `app.py:238`) as `text/html`, UNLESS the request `Accept` header contains
      `application/json`, in which case it returns the existing descriptor dict.
- [ ] New `GET /api` returns the descriptor JSON (document the new routes/fields in it).
- [ ] Existing routes still resolve (no shadowing); `curl /healthz`, `/review/{id}`, `/static/*`
      unaffected.
- [ ] Local validation: `python3 -m py_compile app.py`; `curl /` (no Accept) returns HTML,
      `curl -H 'Accept: application/json' /` and `curl /api` return the descriptor.

## Notes / context

- `/` branch at `app.py:159`; viewer-serving pattern at `app.py:233-239`. `dashboard.html` is
  created in MR-004; until then `/` may 404 the file gracefully — order the sprint so MR-004 lands
  before the render-smoke.
- Epic: `epics/review-dashboard-plan.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
