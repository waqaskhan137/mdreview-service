---
id: MR-105
title: GET /api/latex/templates listing
status: done
layer: svc
priority: P2
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-102]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Let an agent (or a human curling) discover the catalog.

## Acceptance criteria

- [x] `GET /api/latex/templates` claimed by `LatexModule.handle`, no core route, no `_authz`.
- [x] Response `{bundled, registry, cached}`; `cached` is the shared/global download set.
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Create + MCP + listing surface".

## Work log

- `2026-07-21` — one branch in `module.handle` for `/api/latex/templates` returning
  `self.templates.available()`.

## Validation

- `2026-07-21` — py_compile green; `GET /api/latex/templates` -> {bundled:[acl,acm,arxiv,elsevier,
  iclr2026,ieee,lncs], registry:[acl,iclr2026], cached:[]}.

## Follow-ups
