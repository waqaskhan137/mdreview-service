---
id: MR-030
title: Docs — note footnotes + syntax highlighting now render in the viewer
status: ready
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

- [ ] **README.md / CLAUDE.md** "Rich content" / viewer-rendering note updated: the viewer now renders
      **GFM footnotes** (`[^id]` refs → an ordered back-ref section) and **syntax-highlighted** fenced
      code (vendored highlight.js, dual-scheme theme on both panes), alongside math/Mermaid. One or two
      lines; do not duplicate the API table.
- [ ] **AGENTS.md** gets the same one-line behavior note if it lists viewer rendering capabilities.
- [ ] **No overclaim:** highlighting uses the highlight.js **common** language set (unlabelled/exotic
      code → best-effort `highlightAuto`); footnote ids are document-global (history-modal id-dup is a
      known cosmetic non-goal). Don't document the cut/out-of-scope items as shipped.
- [ ] Local validation: `python3 -m py_compile app.py` (sanity, no code change) + a read-through that
      the doc claims match what MR-028/MR-029 actually shipped.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — Rollout phase 3 (docs), Non-goals (common build,
  cosmetic id-dup). Brief: `requirements/render-fidelity.md`.
- Depends on MR-028 + MR-029 landing first so the docs describe the final behavior.
- Cite process sections by name, not line number; reserve line numbers for code.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- None expected; MR-021 / infra backlog items / cut local-dir read remain backlog, documented as such.
