---
id: MR-093
title: kind plumbing: POST /api/reviews + ReviewService.create, persisted only when latex
status: ready
layer: svc
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-092]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Let a review be created as `kind=latex` while keeping markdown reviews' persisted meta and API
output byte-identical (the critic's round-1 must-fix).

## Acceptance criteria

- [ ] `POST /api/reviews` reads optional `kind`, validated to {"markdown","latex"}, 400 otherwise.
- [ ] `ReviewService.create(kind=...)` persists `kind` in meta.json ONLY when != "markdown"; no
      default key is ever written (summary() is unwhitelisted, reviews.py:54).
- [ ] Readers use `meta.get("kind", "markdown")`.
- [ ] Golden transcript (MR-092 oracle) still diffs empty flag-off.
- [ ] A flag-off `kind=latex` create succeeds, meta carries the field, viewer serves markdown page
      (documented harmless state).
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "kind plumbing" (edits 4 and 5 of five). Create flow: server.py:305-322 ->
reviews.py:108-123.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

