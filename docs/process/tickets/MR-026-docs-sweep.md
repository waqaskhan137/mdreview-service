---
id: MR-026
title: Docs sweep — README API table, CLAUDE.md contract, MCP docstring (math + assets)
status: done
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

- [x] **README.md** API table gains the new asset rows (`POST/GET /api/reviews/{id}/assets`,
      `GET /api/reviews/{id}/asset/{stored}`) with the base64 body and stored-name URL shape; a note
      on the `/static/` content-type widening (css/woff2) and that math renders in the viewer.
- [x] **CLAUDE.md** "The contract" / agent loop documents the attach-asset step (attach images under
      the exact draft `src` string, base64, once per review — survives revisions) and a line that
      **math now renders** (KaTeX, Jekyll-matching delimiters). One line for the P1 SVG/animation
      note ("animated/filtered SVGs render once reachable") is in scope per the brief's "worth one
      doc line"; theme/footnotes/highlighting stay out.
- [x] **mcp_server.py** docstring tool list includes `attach_asset` + `list_assets` (covered in
      MR-024; verify it's present and consistent here).
- [x] **No drift / no overclaim.** Docs describe only what shipped — base64 transport only (no
      `path`/local-dir form, which was cut, S5); assets are review-scoped (not history-snapshotted).
- [x] Local validation passes: `python3 -m py_compile app.py` (sanity; no code change expected) and
      a read-through that the documented endpoints/tools match the implemented ones from MR-022–025.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — Rollout phase 4 (Docs sweep), Definition of Done /
  G7 carry-over treatment. Brief: `requirements/rich-rendering.md` (the SVG/animation "one doc
  line"; the deferred P1/P2 stay out).
- Depends on all implementation tickets landing first so the docs describe the final shapes.
- Cite gates/sections by name in any process-doc edits (not line numbers); reserve line numbers for
  code.

## Work log

- `2026-06-18` — **README.md:** API table gained the three asset rows (`POST/GET /assets`,
  `GET /asset/{stored}`); the vendored-renderers line now lists KaTeX + that the viewer renders math
  (all four delimiters, prose-`$` literal); a new **Assets (images)** paragraph documents attach-once
  / survives-revisions / viewer rewrite / base64-only / stored-name URL; MCP tools list gained
  `attach_asset` + `list_assets`.
- `2026-06-18` — **CLAUDE.md:** new **Rich content: math and images** section (math delimiters +
  prose-`$`; Mermaid + front-matter noted as already working — correcting the stale brief; the
  `attach_asset` curl flow; SVG/animation one-line note per the brief's P1). MCP tool list updated.
- `2026-06-18` — **AGENTS.md:** MCP tool list updated to include `attach_asset`/`list_assets`; a
  math + image-attach note added (cross-links CLAUDE.md).
- `2026-06-18` — **mcp_server.py docstring** already updated in MR-024 (`...10 schemas`,
  `# The 10 tools`) — verified present + consistent here.
- No-overclaim: docs describe base64 transport only (no `path`/local-dir form, S5) and review-scoped
  (not history-snapshotted) assets.
- Files: `README.md`, `CLAUDE.md`, `AGENTS.md`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py mcp_server.py` OK (no code change in this ticket).
- `2026-06-18` — **Cross-check docs ↔ implementation:** all 10 tool names declared in
  `mcp_server.py` (`attach_asset`, `list_assets` included); asset routes present in `app.py`;
  README/CLAUDE.md/AGENTS.md each name `attach_asset` + `list_assets` and the math rendering. No
  documented endpoint/tool without an implementation, and vice-versa for this epic's surface.

## Follow-ups

- None expected; theme/footnotes/highlighting/local-dir-read remain backlog, documented as such.
