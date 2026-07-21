---
id: MR-100
title: Docs sweep: README, gate refs, latex-image runbook
status: done
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

- [x] README: "LaTeX paper review (optional)" section (enable flag + latex image, create via MCP/
      HTTP, what compiles, bare-filename figures, biblatex/XeTeX non-goals, compile-failure UX,
      networking, security); stdlib-only claim qualified (opt-in image adds one system binary).
- [x] Live gate refs gain `src/latex_review/*.py`: docs/process/README.md validation-gate
      statement, dev-flow step 5, the G4 row, and templates/ticket.md AC line. Historical records
      untouched.
- [x] G7 product-page enumeration + the `ui` layer table gain `web/app/latex-viewer.html`.
- [x] Runbook for the latex image: build/smoke (throwaway container + scratch port + throwaway
      volume), one-time `chmod 700 /data` for pre-existing volumes, MCP reconnect note, egress note.
- [x] Grep-gated: no live gate ref lacks the latex glob; stdlib claim qualified.
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Deferring tickets must name this sweep in their Work log (Definition of Done). MR-090 is the
precedent grep-gated sweep.

## Work log

- `2026-07-21` — README latex section + `MDREVIEW_ENABLE_LATEX` config row + operator runbook +
  stdlib-qualification. `docs/process/README.md`: 3 live py_compile gate refs, the `ui` layer-table
  row, and the G7 product-page enumeration all gain the latex paths. `templates/ticket.md` gate
  line updated. Epic plan security section amended for the --only-cached decision.

## Validation

- `2026-07-21` — grep gate: `grep -rn "py_compile src/mdreview" README.md docs/process/README.md
  templates/ticket.md | grep -v latex_review` is EMPTY (all live refs carry the glob); README
  carries the qualified stdlib claim. Historical TRACKER/sprint/ticket mentions left frozen.

## Follow-ups

