---
id: MR-038
title: "Retro: GFM table CSS in the viewer (done-on-arrival)"
status: done
layer: ui
priority: P2
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: []
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Retro-ticket for a fix already shipped this session: the viewer rendered GFM tables as unstyled
browser-default HTML (no borders/padding) because `#article` had no table CSS. Documents the merged
commit so the board reflects reality — **no re-implementation**.

## Acceptance criteria

- [x] `#article table/th/td` styled (border-collapse, cell borders + padding, header tint, zebra rows,
      horizontal scroll for wide tables) — shipped in `viewer.html`.
- [x] Render proof (the *already-merged* code renders a table): post a markdown table, render-smoke the
      `<table>` node from a rebuilt throwaway container.
- [x] Local validation: `python3 -m py_compile app.py`.

## Notes / context

- Shipped commit: `dae815e` ("fix(ui): style GFM tables in the viewer"). Files: `viewer.html`.
- Epic: `epics/mcp-agent-effectiveness-plan.md` — Phase 0, Verification → MR-038.

## Work log

- `2026-06-19` — Shipped directly as `dae815e` (before this epic's cycle), then retro-ticketed here.
  Added 5 CSS rules under `#article` (`viewer.html`). No further change.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK; rebuilt throwaway container, posted a markdown
  table, `render-smoke.sh /review/<id> 'table' '#article'` → `table` ≥1, `#article` 1. Confirmed across
  the live :8139 reviews (the heaviest had 7 tables / 23 th / 177 td render with borders).

## Follow-ups

_None._
