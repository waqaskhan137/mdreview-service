---
id: MR-030
title: Docs — note footnotes + syntax highlighting now render in the viewer
status: done
layer: docs
priority: P2
sprint: sprint-08
epic: render-fidelity
depends_on: [MR-028, MR-029]
branch: dev
created: 2026-06-18
updated: 2026-06-18
---

## Goal

The durable behavior change from this epic — the viewer now renders GFM footnotes and syntax-
highlighted fenced code — is reflected in the docs an agent/user reads, so the "renders like the
published site" claim is accurate. The epic's same-sprint docs ticket. **Per G7 it is NOT carry-over
eligible** — must be `done` before sprint-08 closes. (May fold into MR-029's docs requirement per the
Definition of Done; kept separate here, droppable if MR-029 carries the note.)

## Acceptance criteria

- [x] **README.md / CLAUDE.md** "Rich content" / viewer-rendering note updated: the viewer now renders
      **GFM footnotes** (`[^id]` refs → an ordered back-ref section) and **syntax-highlighted** fenced
      code (vendored highlight.js, dual-scheme theme on both panes), alongside math/Mermaid. One or two
      lines; do not duplicate the API table.
- [x] **AGENTS.md** gets the same one-line behavior note if it lists viewer rendering capabilities.
- [x] **No overclaim:** highlighting uses the highlight.js **common** language set (unlabelled/exotic
      code → best-effort `highlightAuto`); footnote ids are document-global (history-modal id-dup is a
      known cosmetic non-goal). Don't document the cut/out-of-scope items as shipped.
- [x] Local validation: `python3 -m py_compile app.py` (sanity, no code change) + a read-through that
      the doc claims match what MR-028/MR-029 actually shipped.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — Rollout phase 3 (docs), Non-goals (common build,
  cosmetic id-dup). Brief: `requirements/render-fidelity.md`.
- Depends on MR-028 + MR-029 landing first so the docs describe the final behavior.
- Cite process sections by name, not line number; reserve line numbers for code.

## Work log

- `2026-06-18` — **README.md:** the vendored-renderers line now lists highlight.js + footnotes and
  the viewer-renders sentence names GFM footnotes + syntax-highlighted fenced code (dual-scheme)
  alongside math/Mermaid. **CLAUDE.md** "Rich content" gains a bullet (footnote refs → back-ref
  section; fenced code highlighted, unlabelled = best-effort auto-detect). **AGENTS.md** viewer-
  rendering line gains footnotes + highlighting.
- No overclaim: highlight.js **common** language set (exotic/unlabelled → `highlightAuto`); footnote
  ids document-global (history-modal id-dup is a known cosmetic non-goal). Out-of-scope items not
  documented as shipped.
- Files: `README.md`, `CLAUDE.md`, `AGENTS.md`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py` OK (no code change). Read-through: the doc claims
  (footnotes back-ref section; dual-scheme highlighting; common-build/auto-detect caveat) match what
  MR-028/MR-029 shipped and were render-verified.

## Follow-ups

- None expected; MR-021 / infra backlog items / cut local-dir read remain backlog, documented as such.
