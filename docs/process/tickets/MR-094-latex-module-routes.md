---
id: MR-094
title: latex_review package: module routes, auth parity, self-heal enqueue
status: done
layer: svc
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-092, MR-093]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

The self-contained `src/latex_review/` package: route claims and handlers for the latex viewer
page, PDF serving, and compile status, with the same auth/disk contract as core arms.

## Acceptance criteria

- [x] Package `src/latex_review/` (`__init__.build(store, reviews, comments)` -> (module, wrapped
      reviews)); core reaches it only via the MR-092 seam (the seam now also rebinds self.reviews
      to the compile-triggering decorator).
- [x] `GET /review/{rid}` claimed only when meta kind=="latex": serves `web/app/latex-viewer.html`
      (placeholder page; MR-097 replaces it). Markdown reviews fall through to the core viewer.
- [x] `GET /api/latex/{rid}/pdf`: latest PDF inline, application/pdf; 404 JSON with the compile
      status when none built yet.
- [x] `GET /api/latex/{rid}/compile`: {state, revision, finished_at, log_tail} from status.json.
- [x] Every handler: `_authz(rid)` first (404-not-403 foreign), `_disk_low()` before the
      self-heal enqueue, early return when plane is None; non-latex review on an /api/latex route
      -> 404.
- [x] Self-heal: missing status.json, or status.revision < meta revision with nothing
      queued/running, enqueues a compile (no thrash: failed-at-current-revision does NOT
      re-enqueue).
- [x] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "The module". RID regex reused from config.py:51. Compile worker's real Tectonic
subprocess is MR-095; this ticket ships the full queue/coalescing/status/self-heal/decorator
machinery with `_produce_pdf` stubbed (every compile reports failed with a "not wired yet" log),
which is exactly the local-without-tectonic behavior anyway.

## Work log

- `2026-07-21` — New package `src/latex_review/`: `__init__.build`, `module.LatexModule`
  (route claims + auth parity + self-heal), `compiler.CompileWorker` (queue + per-rid coalescing
  with redo-on-running + status persistence, `_produce_pdf` stubbed), `decorator.LatexAwareReviews`
  (recompile on create/put_source via __getattr__ delegation). `src/mdreview/server.py` seam
  rebinds `self.reviews` to the decorator when the flag is on. Placeholder
  `web/app/latex-viewer.html` (MR-097 replaces).

## Validation

- `2026-07-21` — py_compile green (incl src/latex_review/*.py). Flag-off oracle vs 94671c1: 24/24
  identical (the seam reassignment only fires flag-on). Flag-on (scratch port 18270, throwaway
  data): latex `GET /review/{id}` served by the module (html, #srcpane) while a markdown review
  still gets the core viewer (turnbanner present); `/compile` returns failed@rev0 (stub);
  `/pdf` -> 404 with the log; `/compile` on a markdown review -> 404 not-latex; foreign id -> 404;
  `PUT /source` bumped revision 0->1 and the decorator re-enqueued (status rev=1). Real-PDF path
  proven in MR-095 under the latex image.

## Follow-ups

