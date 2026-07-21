---
id: MR-102
title: TemplateService + BundledCatalog + DataCache + ReviewCreateRejected + build() injection
status: done
layer: svc
priority: P1
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-101]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

The IoC foundation: a `TemplateService` resolver chain (bundled + /data cache) injected at the
module's `build()` composition root, plus the core-defined base exception, plus starter skeletons
for the CTAN classes. No network yet.

## Acceptance criteria

- [x] `src/mdreview/errors.py`: core-defined `ReviewCreateRejected` (status + payload); core does
      not import `latex_review` (flag-off import graph unchanged, grep-verified).
- [x] `src/latex_review/templates.py`: `TemplateService`, `BundledCatalog`, `DataCache`,
      `UnknownTemplate(ReviewCreateRejected)`; `known_ids/available/require/starter/companion_files`.
- [x] Starter `.tex` skeletons for IEEE/ACM/arXiv/LNCS/Elsevier (CTAN classes; empty companion set).
- [x] `build()` assembles `TemplateService(BundledCatalog(), DataCache(store))` and injects it into
      `CompileWorker`, `LatexAwareReviews`, `LatexModule` (constructors gained the arg, stored, not
      yet used in create/compile — that is MR-103/104). Puller NOT added (MR-104).
- [x] IoC: registry disabled ⇒ `svc._puller is None` (unit-verified).
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "IoC wiring" + "Files". CompileWorker currently constructed without `comments`
(`__init__.py:17`); it gains `templates`. Verify a redistribution-OK license before bundling any
non-CTAN style (deferred to MR-103 where the top styles are bundled).

## Work log

- `2026-07-21` — `src/mdreview/errors.py` (ReviewCreateRejected). `src/latex_review/templates.py`
  (TemplateService + BundledCatalog + DataCache + UnknownTemplate). 5 CTAN starter dirs under
  `src/latex_review/templates/`. `build()` assembles + injects the service; CompileWorker /
  LatexAwareReviews / LatexModule constructors gained a `templates` arg.

## Validation

- `2026-07-21` — py_compile green. Unit: 5 starters resolve with the right class names; CTAN classes
  return `[]` companions; unknown id → `UnknownTemplate(ReviewCreateRejected)` status 400 + available
  list; `_puller is None` when registry disabled. Flag-on boots; a base latex review still compiles
  (no regression from the constructor changes). Flag-off golden oracle: 23/23 byte-identical
  (errors.py unimported by core; build() flag-gated).

## Follow-ups
