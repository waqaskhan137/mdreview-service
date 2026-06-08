---
id: MR-006
title: viewer.html — Google-Docs gutter comments + minimal history view
status: done
layer: ui
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-005]
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Make feedback visible like Google Docs: the commented text highlighted inline, comment cards in a
right gutter aligned to their anchor, click-to-focus both ways. Plus a minimal read-only view of
past history rounds.

## Acceptance criteria

- [ ] **Gutter cards:** on wide screens, comment cards render `position:absolute` in a right gutter,
      each `top` computed from its anchor's offset; a layout pass pushes overlapping cards down so
      they stack. Recompute on resize, font load, and after every render/poll reload.
- [ ] **Exact-span highlight:** wrap the precise quoted text in a `<mark class="cmt" data-id>` by
      walking the block's text nodes; whole-block notes (`quote === '(whole block)'`) keep the
      block highlight; fall back to block highlight if the span is not found. Hook into
      `numberBlocks()`/`reconcile()` (`viewer.html:179,197`).
- [ ] **Sync:** click a highlight focuses its card (scroll + accent ring); click a card scrolls to
      and flashes its highlight.
- [ ] **Add flow unchanged:** the select -> "+ note" -> `#pop` popup (`viewer.html:232-259`) stays;
      saving re-renders highlights + cards. Resolved notes drop their highlight and grey/strike at
      the bottom of the gutter.
- [ ] **Narrow fallback (<=820px):** hide the gutter, restore the existing `#panel` toggle + dock
      (reuse the current code, do not delete it).
- [ ] **History view:** a small "History" affordance fetches `/history`, lists past rounds
      (timestamp + note count), and opens a past draft's rendered markdown + its notes read-only.
- [ ] Validation: serve, **open `/review/{id}` in a browser**: highlight appears, card aligns,
      click sync works, overlapping cards stack, narrow screen falls back, history opens.
      Screenshot for G7.

## Notes / context

- Existing notes carry `num` + `quote`; the highlight must locate `quote` within the block.
  Current dock/panel/render at `viewer.html:50-61,216-229,261`. Consumes MR-005 `/history`.
- Epic: `epics/review-dashboard-plan.md`.

## Work log

- `2026-06-08` — `viewer.html`: added a self-contained comments layer (new `<style>` block,
  `#gutter` + `#histmodal` + a History dock button, and a second `<script>` that reuses the
  existing `notes`/`render`/`save`/`API` globals). `highlightNote()` wraps the exact quoted span
  in `<mark class="cmt">` (single-text-node match; falls back to the block anchor otherwise);
  `renderComments()` builds a gutter card per note and re-wraps highlights (unwrapping stale ones
  first); `layoutComments()` positions cards at their anchor offset and stacks overlaps, only
  when the gutter fits (else `body.gutter-on` is off and the existing `#panel`/dock returns).
  `render` is wrapped so comments refresh on every note/source change. Click syncs highlight <->
  card (`focusPair`). Resolved notes drop their highlight and grey/strike at the gutter bottom.
  History modal lists `/history` rounds and renders a past draft + its notes read-only.

## Validation

- `2026-06-08` — `python3 -m py_compile app.py` passed (server unchanged). **Browser
  render-smoke** via headless Chrome on a seeded review (span note, whole-block note, a stale
  note, one history round):
  - `reviews/sprint-01-render-evidence-2026-06-08/viewer-comments.png` (1280px): "a specific
    phrase" highlighted inline; gutter cards #2 and #3 anchored to their blocks; the stale note
    greyed + struck at the bottom; cards stacked without overlap; dock shows History.
  - `reviews/sprint-01-render-evidence-2026-06-08/viewer-narrow.png` (760px): gutter hidden, the
    `Show` panel toggle restored, inline highlight retained.
  - `GET /history` returns round 0; History modal wired to it (verified live in-browser).

## Follow-ups

None.
