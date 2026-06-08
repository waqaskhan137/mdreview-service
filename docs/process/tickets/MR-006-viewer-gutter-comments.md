---
id: MR-006
title: viewer.html — Google-Docs gutter comments + minimal history view
status: ready
layer: ui
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-005]
branch:
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
