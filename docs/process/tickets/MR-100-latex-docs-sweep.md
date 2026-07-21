---
id: MR-100
title: Docs sweep: README, gate refs, latex-image runbook
status: ready
layer: docs
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-092, MR-093, MR-094, MR-095, MR-096, MR-097, MR-098, MR-099]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Every durable behavior change from sprint-29 reflected in live docs. Docs-sweep tickets are not
eligible for carry-over (G7): this closes inside sprint-29.

## Acceptance criteria

- [ ] README: latex review mode section (enable flag, latex image, what works, non-goals incl.
      biblatex/XeTeX/bare-filename figures), stdlib-only claim gains the one-sentence
      qualification (opt-in image adds a system binary).
- [ ] Live gate refs gain `src/latex_review/*.py`: docs/process/README.md validation-gate
      statement, development-flow step 5, the G4 row, and templates/ticket.md AC line. Historical
      records stay frozen.
- [ ] G7 product-page enumeration gains `web/app/latex-viewer.html`.
- [ ] Runbook for the latex image: build/run commands, scratch-port throwaway validation pattern,
      one-time `chmod 700 /data` for pre-existing volumes, MCP reconnect note.
- [ ] Grep-gated: no live doc still claims the py_compile gate without the latex glob; no doc
      claims zero system binaries unqualified.
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Deferring tickets must name this sweep in their Work log (Definition of Done). MR-090 is the
precedent grep-gated sweep.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

