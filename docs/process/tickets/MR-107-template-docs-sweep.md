---
id: MR-107
title: Docs sweep: README templates + registry + egress/config + year-churn cadence
status: done
layer: docs
priority: P1
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-102, MR-103, MR-104, MR-105, MR-106]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Every durable behavior change reflected in live docs. Not carry-over eligible (G7): closes inside
sprint-30.

## Acceptance criteria

- [x] README "LaTeX paper review" section gains: a **Start from a template** create bullet
      (`template=<id>`, bundled + download-on-miss ids, the listing endpoint, no web picker) and a
      **Templates — operator notes** subsection (registry location + how to add/bump an entry,
      air-gapped `MDREVIEW_LATEX_TEMPLATE_DOWNLOAD=0`, egress hosts, custom registry, licensing).
- [x] Security bullet extended with the download containment; year-churn "fails closed" documented.
- [x] Bundling exception + per-style license note stated (bundling avoided w/o a confirmed license).
- [x] Gate refs unchanged — the py_compile glob already covers `src/latex_review/*.py` + `src/mcp/*.py`;
      puller.py/templates.py/errors.py auto-covered (confirmed).
- [x] Grep-gated: no live doc claims web template selection or downloaded-files-in-image.
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Deferring tickets name this sweep in their Work log. MR-100 is the precedent grep-gated sweep.

## Work log

- `2026-07-21` — README latex section: template create bullet + "Templates — operator notes"
  subsection + download-containment security note.

## Validation

- `2026-07-21` — py_compile green; grep gate: no live doc claims web template selection; README
  states "no web template picker" + downloaded files never in the image.

## Follow-ups
