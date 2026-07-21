---
id: MR-097
title: latex-viewer.html: split panes, line anchors, PDF iframe, per approved mockup
status: done
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

- [x] Self-contained `web/app/latex-viewer.html` using viewer.html's theme tokens; split panes
      with draggable divider; Source/PDF tabs under 880px.
- [x] Source pane: per-line elements with `data-num="<line>"`, hand-rolled LaTeX tokenizer
      (commands/comments/math), hover `+`, line-number click, and text-selection comment
      affordances.
- [x] Comments: reuse `/comments` CRUD verbatim; `block_num` = line number; exact-line lookup then
      concatenated `textContent` search mapped to a Range, wrapped PER intersected text segment
      (Range cannot surroundContents across element boundaries); `has-c` margin treatment; same
      escape->marked->url-strip sanitization as viewer.html.
- [x] PDF pane: `<iframe src="/api/latex/{id}/pdf?v=rev">` (reloads only on a new build);
      Download via HTML5 `download` anchor; compile-failed banner with collapsible log tail,
      last-good PDF kept visible; compile status piggybacks the 2s status poll.
- [x] No turn banner, no handoff calls anywhere on the page.
- [x] `tests/render-smoke.sh` passes on a scratch port (locally, flag-on `python -m mdreview`;
      G7 re-runs from the rebuilt image).
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

UI contract: the approved mockup artifact (b1132f25-daf3-43d8-ba92-d41655fb68d4). The rail shows
beside the source when the pane is >=640px wide; narrower, cards move to the bottom dock (both are
the same cards). Loads the vendored `/static/marked.min.js` for comment markdown (graceful-degrades
if absent).

## Work log

- `2026-07-21` — Rewrote `web/app/latex-viewer.html` from the MR-094 stub to the full split viewer:
  theme tokens, draggable divider, Source/PDF tabs, LaTeX line tokenizer, offset-mapped per-segment
  quote highlight, ported comment CRUD (create/reply/reopen/delete + inline two-step delete),
  rail + narrow dock, selection/hover-+/line-number affordances, PDF iframe + compile-status poll +
  error banner, HTML5 download anchor.

## Validation

- `2026-07-21` — py_compile green (no py change; page is static). Flag-on local server
  (scratch port, warmed cache): a real 11pt paper compiled OK, `GET /pdf` -> 200 application/pdf
  23,584 bytes; a comment anchored to line 8 via quoted_text "3.1" renders the offset-mapped
  `mark.cmt` highlight + margin bar. `render-smoke.sh` (headless Chrome) asserts `.srcpane`,
  `.pdfpane`, `.ln` (15), `#pdfframe`, `.gcard` (2: rail + dock), `mark.cmt` (1) -> exit 0. Also
  verified the compile-FAILED UX repeatedly (error banner + log_tail) on papers whose resources
  the local cache lacked. Screenshot: docs/process/reviews/sprint-29-render-evidence-2026-07-21/
  latex-viewer-light.png (the dark PDF pane there is a headless-screenshot artifact; the iframe
  src is set and /pdf serves the PDF in a real browser).

## Follow-ups

- Surfaced a compile-coverage finding (Tectonic `--only-cached` fails on any resource the warm
  cache lacks: 11pt option, title fonts, cmsy10 all missed a thin warm set). Tracked against
  MR-096 / the epic security posture as an OPEN owner decision (keep zero-network + broad warm set,
  vs allow the tectonic-bundle fetch). See the mdreview review comment.

## Follow-ups

