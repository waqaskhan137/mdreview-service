---
id: MR-107
title: Docs sweep: README templates + registry + egress/config + year-churn cadence
status: ready
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

- [ ] README latex section gains a Templates subsection: `template=<id>` on create, the bundled
      catalog, the pinned registry (download-on-miss, conference-source origin), operator config
      (registry enable/allowlist/egress hosts), and the year-churn manifest-update cadence.
- [ ] README notes the top-styles bundling exception + the per-style redistribution-license check.
- [ ] Gate refs unchanged (the py_compile glob already covers src/latex_review + src/mcp); confirm.
- [ ] Runbook: how to add/pin a registry entry, how to disable the puller (air-gapped), egress hosts.
- [ ] Grep-gated: no live doc claims templates are web-selected or that downloaded files ship in the image.
- [ ] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Deferring tickets name this sweep in their Work log. MR-100 is the precedent grep-gated sweep.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
