---
id: MR-097
title: latex-viewer.html: split panes, line anchors, PDF iframe, per approved mockup
status: ready
layer: ui
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-094, MR-095]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

The Overleaf-style review surface, implementing the owner-approved mockup (artifact
b1132f25-daf3-43d8-ba92-d41655fb68d4): source left, live PDF right, existing comment system
anchored to source lines, no turn baton.

## Acceptance criteria

- [ ] Self-contained `web/app/latex-viewer.html` using viewer.html's theme tokens; split panes
      with draggable divider; Source/PDF tabs under 880px.
- [ ] Source pane: per-line elements with `data-num="<line>"`, hand-rolled LaTeX tokenizer
      (commands/comments/math; hljs only if the vendored build already ships latex), hover `+`
      and text-selection comment affordances per the mockup.
- [ ] Comments: reuse `/comments` CRUD verbatim; `block_num` = line number; quoted-text fallback
      via concatenated `textContent` search mapped to a Range, wrapped per intersected text
      segment; `has-comment` margin treatment; same sanitization pipeline as viewer.html.
- [ ] PDF pane: `<iframe src="/api/latex/{id}/pdf">`; Download via HTML5 `download` attribute;
      compile-failed banner with log tail, last-good PDF kept visible; compile status piggybacks
      the 2s status poll.
- [ ] No turn banner, no handoff calls anywhere on the page.
- [ ] `tests/render-smoke.sh http://localhost:<scratch>/review/<latex-rid> "#srcpane" "#pdfpane" ".gcard"`
      passes from a rebuilt latex image on a scratch port.
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

UI contract: the approved mockup artifact (b1132f25-daf3-43d8-ba92-d41655fb68d4). Critic
checkpoint: Range cannot surroundContents across element boundaries, wrap per segment. Viewer API
usage documented in the epic plan "Viewer page".

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

