---
id: MR-003
title: Serve dashboard at /; move JSON descriptor to /api
status: done
layer: svc
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-002]
branch: dev (small/solo change)
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

- `2026-06-08` — `app.py`: the `/` GET branch now content-negotiates — serves
  `dashboard.html` as `text/html` for browsers, or the JSON descriptor when `Accept` contains
  `application/json`. Added `/api` (same branch) always returning the descriptor. Descriptor
  updated to document `list_reviews` and the new POST provenance fields. `dashboard.html` itself
  lands in MR-004 (served from disk; until then `_read` returns empty HTML gracefully).

## Validation

- `2026-06-08` — `python3 -m py_compile app.py` passed. On an isolated instance:
  - `GET /` (no Accept) -> `200` `text/html`.
  - `GET /` with `Accept: application/json` and `GET /api` -> the descriptor JSON.
  - `GET /healthz` and `GET /api/reviews` still `200` (no route shadowing).

## Follow-ups

None.
