---
id: MR-103
title: template create plumbing (kwarg, POST 400, decorator seed/validate, bundled file-set copy-in)
status: ready
layer: svc
priority: P1
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-102]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Wire `template` through create, seeding the source and materializing bundled companion files at
compile, IoC-correct (validation via the module's typed exception; companions in the worker).

## Acceptance criteria

- [ ] `ReviewService.create` gains optional `template=""` (`reviews.py:108-109`), persisted in meta
      only when set (mirrors kind, `reviews.py:127-128`).
- [ ] POST /api/reviews (`server.py:328-333`) reads `b.get("template","")`, passes it through, and
      catches `ReviewCreateRejected` -> 400 with its `available` list (core imports only the base type).
- [ ] `LatexAwareReviews.create`: validates the id (raises `UnknownTemplate`), seeds source from the
      starter `.tex` ONLY when no `markdown` supplied (explicit source wins), records the id. No
      network, no assets.
- [ ] `CompileWorker._prepare_job` reads `meta.template`, materializes the bundled file-set and copies
      each file into the job dir by basename (`compiler.py:147-152` path). Bundle the top non-CTAN
      style(s) as files here (owner decision 3) with a verified redistribution license.
- [ ] Flag-off golden oracle still empty; a bundled-template review compiles.
- [ ] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Where templates enter the compile". Precedence: explicit markdown wins; template still
contributes companion files.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
