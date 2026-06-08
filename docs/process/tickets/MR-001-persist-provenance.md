---
id: MR-001
title: Persist provenance (project/source_path/session) on POST + meta
status: ready
layer: svc
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: []
branch:
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Let an agent tag a review with where it came from, so reviews can later be grouped by project and
session. Today `POST /api/reviews` only takes `markdown` + `title`; nothing records provenance.

## Acceptance criteria

- [ ] `create_review` accepts `project`, `source_path`, `session` (all optional, default "") and
      writes them into `meta.json` (`app.py:81-93`).
- [ ] `POST /api/reviews` reads `project`/`source_path`/`session` from the body and passes them
      through (`app.py:166-176`).
- [ ] Fields are optional: a POST with none still succeeds; existing reviews on disk (no new keys)
      are unaffected and `GET /api/reviews/{id}` still returns their meta.
- [ ] Local validation passes: `python3 -m py_compile app.py`, then `POST` with and without the
      fields and confirm `meta.json` contents via `GET /api/reviews/{id}`.

## Notes / context

- `create_review` at `app.py:81`; POST handler at `app.py:166`. Keep additive and default-safe per
  the epic's core principle. No new dependency.
- Epic: `epics/review-dashboard-plan.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
