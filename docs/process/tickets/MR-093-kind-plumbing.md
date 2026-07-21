---
id: MR-093
title: kind plumbing: POST /api/reviews + ReviewService.create, persisted only when latex
status: done
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

- [x] `POST /api/reviews` reads optional `kind`, validated to {"markdown","latex"}, 400 otherwise.
- [x] `ReviewService.create(kind=...)` persists `kind` in meta.json ONLY when != "markdown"; no
      default key is ever written (summary() is unwhitelisted, reviews.py:54).
- [x] Readers use `meta.get("kind", "markdown")` (no core reader exists yet; the latex module and
      dashboard read it in MR-094/MR-098, this ticket establishes the storage contract).
- [x] Golden transcript (MR-092 oracle) still diffs empty flag-off.
- [x] A flag-off `kind=latex` create succeeds, meta carries the field, viewer serves markdown page
      (documented harmless state).
- [x] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "kind plumbing" (edits 4 and 5 of five). Create flow: server.py:305-322 ->
reviews.py:108-123.

## Work log

- `2026-07-21` — `src/mdreview/server.py` POST /api/reviews arm: optional `kind` read + validated
  (400 on anything but markdown/latex). `src/mdreview/reviews.py` create(): optional `kind`
  param, persisted only when != "markdown", with the why-comment naming the unwhitelisted
  summary() surface.

## Validation

- `2026-07-21` — py_compile green. Oracle vs 94671c1 baseline: 24 steps identical (flag off,
  no-kind create path byte-identical). Functional (new build, flag off, scratch port 18262,
  throwaway data): kind=latex create -> meta.kind == "latex"; explicit kind=markdown -> meta has
  NO kind key; kind=pdf -> 400; GET /review/{latex-rid} -> 200 markdown viewer page.

## Follow-ups

