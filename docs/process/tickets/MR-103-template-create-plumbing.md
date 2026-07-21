---
id: MR-103
title: template create plumbing (kwarg, POST 400, decorator seed/validate, bundled file-set copy-in)
status: done
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

- [x] `ReviewService.create` gains optional `template=""`, persisted only when set.
- [x] POST /api/reviews reads `b.get("template","")`, passes it through, and catches
      `ReviewCreateRejected` -> `e.status`/`e.payload` (core imports only the base type from
      `mdreview.errors`).
- [x] `LatexAwareReviews.create`: validates the id BEFORE create (raises `UnknownTemplate`, so no
      review is created on a bad id), seeds source from the starter ONLY when no `markdown` supplied
      (explicit source wins), records the id. No network, no assets.
- [x] `CompileWorker._prepare_job` reads `meta.template` and copies the template's companion files
      into the job dir by basename (same traversal-safe path as figures). CTAN classes contribute
      no files. **Bundling the top non-CTAN style(s) as actual files (owner decision 3) is deferred
      to MR-104**, where the download machinery + the per-style license check live (noted below).
- [x] Flag-off golden oracle 23/23 byte-identical; a `template=ieee` review compiles to an IEEE PDF.
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Where templates enter the compile". Precedence: explicit markdown wins; template still
contributes companion files. In-flight scope move: the "bundle the top non-CTAN styles" AC item is
handled in MR-104 (where the file-fetch + license verification live); MR-103 ships the plumbing +
CTAN proof.

## Work log

- `2026-07-21` — `reviews.py` create() `template` kwarg (persist when set). `server.py` POST arm
  reads `template`, catches `ReviewCreateRejected` -> 400 (imports the core base from
  `mdreview.errors`). `decorator.py` create() validates + seeds source (precedence: explicit wins).
  `compiler.py` _prepare_job copies template companion files by basename.

## Validation

- `2026-07-21` — py_compile green; flag-off oracle 23/23. End-to-end (flag-on, scratch port): (1)
  `template=ieee` no-source -> IEEE starter seeded (`IEEEtran`) -> compiles to a 11.5KB IEEE PDF;
  (2) unknown `template=madeup` -> 400 `{error:"unknown template", available:[acm,arxiv,elsevier,
  ieee,lncs]}`, no review created; (3) explicit source + `template=ieee` -> explicit source kept;
  (4) markdown review -> no `template` meta key (byte-identity preserved).

## Follow-ups

- MR-104 bundles the top non-CTAN style(s) as files (owner decision 3) alongside the registry/download
  work + the per-style redistribution-license check; the `_prepare_job` companion copy-in built here
  already handles bundled bytes.

## Follow-ups
