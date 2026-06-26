---
id: MR-079
title: Repoint the 3 live py_compile gate refs (incl. the G4 row) + CLAUDE.md to src/...
status: done
layer: docs
priority: P2
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-078]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

The project's standing validation gate moves from `app.py` to the new tree. Update only the
forward-governing references so the enforced gate is correct; leave the frozen audit trail untouched.

## Acceptance criteria

- [x] `docs/process/README.md`: the **Divergences** bullet, **Development-flow step 5**, and the
      **G4 pass-condition row** all quote the new command
      `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`.
- [x] `CLAUDE.md`: the "Delivery process" validation-gate bullet updated to the same command.
- [x] A grep proves the **G4 row text itself** (not merely the prose) contains `src/mdreview` — per
      the process's "wire enforcement into the gate row" rule.
- [x] **Frozen history untouched:** the historical `py_compile app.py` mentions in `tickets/**`,
      `sprints/**`, `reviews/**`, and shipped epic plans remain verbatim (spot-check two; do not
      sweep-edit them).
- [x] Local validation: `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py` is
      runnable (at this point `src/mdreview/` may not exist yet — assert the command is the documented
      gate and that the `src/mcp_server.py`/`src/watch.py` paths resolve; the `src/mdreview/*` glob
      becomes non-empty from MR-080 on).

## Notes / context

- Epic: "Key constraints → Only the LIVE gate refs change in docs; history is frozen" and the
  "Enforcement note (G4 row)". The three README refs are the Divergences bullet, Dev-flow step 5, and
  the G4 row; the only other live run-ref is `CLAUDE.md`'s validation-gate bullet. README/AGENTS
  "run your own instance" sections are `docker`-based and unaffected.
- This ticket completes Phase 0; the Phase-1 extractions (MR-080+) validate against this new gate.

## Work log

- `2026-06-25` — Repointed the live, forward-governing gate refs in `docs/process/README.md` and
  `CLAUDE.md`: `python3 -m py_compile app.py` → `python3 -m py_compile src/mdreview/*.py
  src/mcp_server.py src/watch.py` at the Divergences bullet, Dev-flow step 5, and the **G4
  pass-condition row** (+ the CLAUDE.md gate bullet). Also fixed the other relocation-stale forward
  refs in the same process doc (slightly beyond the literal py_compile scope, but all
  move-broken live refs): `scripts/render-smoke.sh` → `tests/render-smoke.sh` (Dev-flow + G4 + G7
  rows), the layer-table examples (`app.py` → `src/mdreview/**`; `viewer.html`/`dashboard.html`/
  `static/**` → `web/...`), and the G7 product-page paths → `web/...`. Files: `docs/process/README.md`,
  `CLAUDE.md`.
- Left untouched: the `app.py:NNN` citation-format example (illustrative, not a path), and **all
  frozen history** (tickets/sprints/reviews/shipped-epics).

## Validation

- `2026-06-25` — `grep` confirms the **G4 row text itself** quotes `python3 -m py_compile
  src/mdreview/*.py src/mcp_server.py src/watch.py` (enforcement-in-the-row rule). No forward doc
  (`docs/process/README.md`, `CLAUDE.md`, `AGENTS.md`, root `README.md`) still contains `py_compile
  app.py` or `scripts/render-smoke.sh`. 83 frozen-history files still carry the historical `py_compile
  app.py` (unmodified — `git status` shows only `README.md`/`CLAUDE.md` changed). New gate paths
  resolve: `src/mcp_server.py`/`src/watch.py` exist now; the `src/mdreview/*.py` glob fills from
  MR-080 on (the epic ships as one PR, so the steady-state command is correct at merge).

## Follow-ups

Anything deliberately deferred.
