---
id: MR-026
title: Docs sweep — README API table, CLAUDE.md contract, MCP docstring (math + assets)
status: ready
layer: docs
priority: P1
sprint: sprint-06
epic: rich-rendering
depends_on: [MR-022, MR-023, MR-024, MR-025]
branch:
created: 2026-06-18
updated: 2026-06-18
---

## Goal

The durable behavior changes from this epic — math now renders, and assets can be attached/served —
are reflected in the docs an agent and a user actually read, so the contract matches the running
service. This is the epic's named same-sprint docs-sweep ticket. **Per G7 it is NOT carry-over
eligible** — it must be `done` before sprint-06 closes (deferred docs are force-closed at sprint
close, never crossing a cycle boundary).

## Acceptance criteria

- [ ] **README.md** API table gains the new asset rows (`POST/GET /api/reviews/{id}/assets`,
      `GET /api/reviews/{id}/asset/{stored}`) with the base64 body and stored-name URL shape; a note
      on the `/static/` content-type widening (css/woff2) and that math renders in the viewer.
- [ ] **CLAUDE.md** "The contract" / agent loop documents the attach-asset step (attach images under
      the exact draft `src` string, base64, once per review — survives revisions) and a line that
      **math now renders** (KaTeX, Jekyll-matching delimiters). One line for the P1 SVG/animation
      note ("animated/filtered SVGs render once reachable") is in scope per the brief's "worth one
      doc line"; theme/footnotes/highlighting stay out.
- [ ] **mcp_server.py** docstring tool list includes `attach_asset` + `list_assets` (covered in
      MR-024; verify it's present and consistent here).
- [ ] **No drift / no overclaim.** Docs describe only what shipped — base64 transport only (no
      `path`/local-dir form, which was cut, S5); assets are review-scoped (not history-snapshotted).
- [ ] Local validation passes: `python3 -m py_compile app.py` (sanity; no code change expected) and
      a read-through that the documented endpoints/tools match the implemented ones from MR-022–025.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — Rollout phase 4 (Docs sweep), Definition of Done /
  G7 carry-over treatment. Brief: `requirements/rich-rendering.md` (the SVG/animation "one doc
  line"; the deferred P1/P2 stay out).
- Depends on all implementation tickets landing first so the docs describe the final shapes.
- Cite gates/sections by name in any process-doc edits (not line numbers); reserve line numbers for
  code.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- None expected; theme/footnotes/highlighting/local-dir-read remain backlog, documented as such.
