---
id: MR-094
title: latex_review package: module routes, auth parity, self-heal enqueue
status: ready
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

- [ ] Package `src/latex_review/` (`__init__.build(store, reviews, comments)` -> LatexModule);
      core reaches it only via the MR-092 seam.
- [ ] `GET /review/{rid}` claimed only when meta kind=="latex": serves `web/app/latex-viewer.html`
      (placeholder page acceptable until MR-097).
- [ ] `GET /api/latex/{rid}/pdf`: latest PDF inline, application/pdf; 404 JSON when none and
      nothing compiled yet (self-heal enqueues).
- [ ] `GET /api/latex/{rid}/compile`: {state, revision, finished_at, log_tail} from status.json.
- [ ] Every handler: `_authz(rid)` first (404-not-403 foreign), `_disk_low()` before any write,
      early return when plane is None.
- [ ] Self-heal: missing status.json, or status.revision < meta revision with nothing
      queued/running, enqueues a compile (no thrash: failed-at-current-revision does NOT re-enqueue).
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "The module". RID regex parity with core (config.py:51). Compile worker itself is
MR-095; this ticket may stub the worker interface (enqueue records intent).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

