---
id: MR-092
title: Core IoC seam: ENABLE_LATEX flag, Services.modules, route dispatch loop
status: done
layer: svc
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-091]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Give the core server one small extension seam so feature modules can register routes/pages at
startup, gated by `MDREVIEW_ENABLE_LATEX`. Flag off must be byte-identical to today.

## Acceptance criteria

- [x] `config.py`: `ENABLE_LATEX` truthy-env flag (REQUIRE_AUTH pattern, config.py:20).
- [x] `Services.__init__`: `self.modules = []`; conditional import + registration of
      `latex_review` ONLY inside the `ENABLE_LATEX` branch (core never imports it at module
      level). Flag ON without the package fails LOUD at boot (ModuleNotFoundError), deliberately:
      a misconfiguration must never boot half-enabled. (Supersedes the drafted ImportError-guard
      wording: silent degradation contradicts errors-at-boundaries.)
- [x] `H.route(m)`: module dispatch loop after the trailing-slash/MAX_BODY guards
      (server.py:227-231), before the first core arm; returns on first module claim.
- [x] `tests/golden_transcript.sh`: scripted request transcript (today's request shapes) run
      against a baseline build and this build with the flag off; diff empty.
- [x] Import isolation: flag-off `import mdreview.server` leaves `latex_review` out of
      `sys.modules` (replaces the drafted source-grep, which the in-branch import line itself
      would trip; the sys.modules assertion is the non-gameable form, epic Verification item 3
      updated to match).
- [x] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "The IoC seam"; route chain at src/mdreview/server.py:224-557, composition root at
server.py:49-60. Oracle may run against two local `python -m mdreview` processes on scratch ports
with throwaway `MDREVIEW_DATA` under `.scratch/` when Docker is unavailable; G7 re-runs it from
rebuilt images.

## Work log

- `2026-07-21` — `src/mdreview/config.py`: ENABLE_LATEX flag (+ feature-modules comment block).
  `src/mdreview/server.py`: ENABLE_LATEX import; `Services.modules` list with flag-gated
  conditional import of `latex_review`; module dispatch loop in `H.route` after the MAX_BODY
  guard. New `tests/golden_transcript.sh` (24-step normalized transcript differ; normalizes rid,
  cid, base URL, and volatile timestamp keys; HTML bodies compare as sha256).

## Validation

- `2026-07-21` — py_compile gate green. Oracle: baseline worktree @ 94671c1 vs this tree, both
  flag-off, local `python -m mdreview` on scratch ports 18261/18262 with throwaway MDREVIEW_DATA
  under `.scratch/`: "OK: transcripts identical (24 steps)". Import isolation: flag-off import of
  `mdreview.server` leaves `latex_review` absent from `sys.modules`. Flag-on without the package:
  `Services(Store(...))` raises ModuleNotFoundError (loud, as intended). Docker-image rerun of the
  oracle owed at G7.

## Follow-ups

- G7 re-runs the oracle from rebuilt images (this run was local-process).
