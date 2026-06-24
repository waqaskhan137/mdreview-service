---
id: MR-079
title: Repoint the 3 live py_compile gate refs (incl. the G4 row) + CLAUDE.md to src/...
status: ready
layer: docs
priority: P2
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-078]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

The project's standing validation gate moves from `app.py` to the new tree. Update only the
forward-governing references so the enforced gate is correct; leave the frozen audit trail untouched.

## Acceptance criteria

- [ ] `docs/process/README.md`: the **Divergences** bullet, **Development-flow step 5**, and the
      **G4 pass-condition row** all quote the new command
      `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`.
- [ ] `CLAUDE.md`: the "Delivery process" validation-gate bullet updated to the same command.
- [ ] A grep proves the **G4 row text itself** (not merely the prose) contains `src/mdreview` — per
      the process's "wire enforcement into the gate row" rule.
- [ ] **Frozen history untouched:** the historical `py_compile app.py` mentions in `tickets/**`,
      `sprints/**`, `reviews/**`, and shipped epic plans remain verbatim (spot-check two; do not
      sweep-edit them).
- [ ] Local validation: `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py` is
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
