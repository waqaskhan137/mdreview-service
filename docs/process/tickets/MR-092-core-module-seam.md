---
id: MR-092
title: Core IoC seam: ENABLE_LATEX flag, Services.modules, route dispatch loop
status: ready
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

- [ ] `config.py`: `ENABLE_LATEX` truthy-env flag (REQUIRE_AUTH pattern, config.py:20).
- [ ] `Services.__init__`: `self.modules = []`; conditional import + registration of
      `latex_review` ONLY inside the `ENABLE_LATEX` branch (core never imports it at module level).
      Until MR-094 exists, the branch guards on ImportError so the seam lands independently.
- [ ] `H.route(m)`: module dispatch loop after the trailing-slash/MAX_BODY guards
      (server.py:227-231), before the first core arm; returns on first module claim.
- [ ] `tests/golden_transcript.sh`: scripted request transcript (today's request shapes) run
      against a baseline build and this build with the flag off; diff empty.
- [ ] Import isolation: `grep -rn "latex_review" src/mdreview/ | grep -v ENABLE_LATEX` is empty.
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "The IoC seam"; route chain at src/mdreview/server.py:224-557, composition root at
server.py:49-60. Oracle may run against two local `python -m mdreview` processes on scratch ports
with throwaway `MDREVIEW_DATA` under `.scratch/` when Docker is unavailable; G7 re-runs it from
rebuilt images.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

