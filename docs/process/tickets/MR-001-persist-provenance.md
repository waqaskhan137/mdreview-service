---
id: MR-001
title: Persist provenance (project/source_path/session) on POST + meta
status: done
layer: svc
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: []
branch: dev (small/solo change)
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

- `2026-06-08` — `app.py`: `create_review(markdown, title, project="", source_path="",
  session="")` now writes `project`/`source_path`/`session` into `meta.json`; the
  `POST /api/reviews` handler reads the three optional fields from the body and passes them
  through. Additive and default-safe; no new dependency. Committed to `dev` (small change).
- Docs for these agent-facing fields are tracked by **MR-007** (the epic's docs sweep, same
  sprint) — deliberate deferral, not dropped.

## Validation

- `2026-06-08` — `python3 -m py_compile app.py` passed. Ran on an isolated port/data dir
  (`PORT=8199 MDREVIEW_DATA=/tmp/mr001`):
  - POST with `project/session/source_path` -> `GET /api/reviews/{id}` returns all three in meta.
  - POST with none -> the three fields default to `""` (review still created).
  - A hand-written legacy review dir with OLD meta (no new keys) still serves `GET` `200`
    (back-compat confirmed).

## Follow-ups

None (docs via MR-007).
