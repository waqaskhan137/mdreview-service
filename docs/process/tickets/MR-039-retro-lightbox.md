---
id: MR-039
title: "Retro: click-to-zoom lightbox in the viewer (done-on-arrival)"
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

Retro-ticket for a fix already shipped this session: `#article` figures were capped at column width
with no way to enlarge. Added a click-to-zoom lightbox overlay. Documents the merged commit — **no
re-implementation**.

## Acceptance criteria

- [x] Clicking an `#article img` opens a full-screen `#lightbox` overlay (≤96vw/96vh); click anywhere
      or press Esc closes it — shipped in `viewer.html` (~15 lines, no library).
- [x] Render proof: the `#lightbox` overlay node + a figure `img` both exist in the rendered DOM
      (CDP-verified click → `display:flex` with the asset src; click/Esc → none).
- [x] Local validation: `python3 -m py_compile app.py`; `docker build`.

## Notes / context

- Shipped commit: `2ed9593` ("feat(ui): click figures to zoom (lightbox overlay)"). Files: `viewer.html`
  (`#lightbox` markup + CSS + the delegated click/keydown handlers).
- Epic: `epics/mcp-agent-effectiveness-plan.md` — Phase 0, Verification → MR-039.

## Work log

- `2026-06-19` — Shipped directly as `2ed9593` (before this epic's cycle), then retro-ticketed here.
  Added `#article img{cursor:zoom-in}`, `#lightbox` overlay CSS, the `<div id="lightbox">` node, and a
  document-level click/Esc handler. No further change.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK; `docker build` OK; render-smoke `/review/<id>`
  `#lightbox`/`img`/`#article` all present; Node-CDP: click → `#lightbox` `display:flex` showing the
  asset src, click/Esc → `none`.

## Follow-ups

_None._
