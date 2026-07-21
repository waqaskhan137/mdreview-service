---
id: MR-105
title: GET /api/latex/templates listing
status: ready
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

- [ ] `GET /api/latex/templates` claimed by `LatexModule.handle` (`module.py:29-63`), no core route,
      no per-review authz (returns catalog, not review data).
- [ ] Response `{bundled:[ids], registry:[ids], cached:[ids]}` where `cached` is the shared/global
      set (no tenant data, no cross-tenant leak).
- [ ] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Create + MCP + listing surface".

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
