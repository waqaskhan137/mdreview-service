---
id: MR-102
title: TemplateService + BundledCatalog + DataCache + ReviewCreateRejected + build() injection
status: ready
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

- [ ] `src/mdreview/` gains a core-defined `ReviewCreateRejected` base exception (carries `status` +
      `available`); core never imports `latex_review`.
- [ ] `src/latex_review/templates.py`: `TemplateService`, `BundledCatalog`, `DataCache`,
      `UnknownTemplate(ReviewCreateRejected)`; `resolve/starter/companion_files/available`.
- [ ] `src/latex_review/templates/<id>/` starter `.tex` skeletons for IEEE/ACM/arXiv/LNCS/Elsevier
      (CTAN classes; no companion files needed).
- [ ] `build()` (`__init__.py:16-21`) assembles the resolver chain and injects `templates` into
      `CompileWorker`, `LatexAwareReviews`, `LatexModule` (constructors gain the arg); puller NOT
      added yet (MR-104). Flag-off unaffected.
- [ ] IoC test: with the registry disabled, the resolver chain has no puller (test double).
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "IoC wiring" + "Files". CompileWorker currently constructed without `comments`
(`__init__.py:17`); it gains `templates`. Verify a redistribution-OK license before bundling any
non-CTAN style (deferred to MR-103 where the top styles are bundled).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
