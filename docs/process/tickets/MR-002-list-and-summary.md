---
id: MR-002
title: summary() + list_reviews() + GET /api/reviews
status: ready
layer: svc
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-001]
branch:
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Make reviews discoverable. There is no way to enumerate reviews today (`/api/reviews` only handles
POST). Add a list endpoint with per-review status the dashboard can render.

## Acceptance criteria

- [ ] `summary(rid)` returns `meta` augmented with `notes_total`, `notes_addressed`, `revision`
      (default 0 if absent), and a derived `status`: `awaiting` (feedback_updated 0 and no notes),
      `resolved` (notes exist and all addressed), else `feedback`.
- [ ] `list_reviews()` scans `DATA_DIR` for subdirs containing `meta.json`, maps through
      `summary()`, sorts by `created` desc. Reuses `_exists`/`_read_json`/`meta`.
- [ ] `GET /api/reviews` returns `{"reviews": [...]}`; the existing `POST /api/reviews` is
      unchanged (extend the `path == "/api/reviews"` block at `app.py:166` to handle GET).
- [ ] Local validation: `python3 -m py_compile app.py`; `curl /api/reviews` lists seeded reviews
      with the new fields.

## Notes / context

- Reuse `_read_json`, `meta` (`app.py:49-71`). Note the cross-review exposure in the epic's Key
  constraints (acceptable for trusted-network).
- Epic: `epics/review-dashboard-plan.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
