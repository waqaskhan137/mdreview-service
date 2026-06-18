---
slug: theme-awareness
captured: 2026-06-18
source: P1 item from the rich-rendering real-review feedback (requirements/rich-rendering.md), promoted to its own epic on the user's go-ahead this session (waqas, 2026-06-18) after the two rich-rendering P0s shipped (sprint-06, merged to main PR #5)
related_epic: epics/theme-awareness-plan.md
---

# Theme awareness in the review viewer

Verbatim ask (the P1 item from the rich-rendering brief). Do not edit; append dated notes under
Amendments if the requirement changes.

> **P1 — Theme awareness**
>
> - Problem: an image that assumes a light background looks wrong on a dark review pane (exactly
>   the bug we just hit on the site).
> - Want: either render the doc/images on a consistent neutral card regardless of pane theme, or
>   set the host color-scheme so `@media (prefers-color-scheme)` inside `<img>` SVGs fires and
>   theme-aware diagrams adapt.

## Goal

A reviewer opening `/review/{id}` on **either** a light or a dark pane sees images and diagrams
that don't look broken: a figure authored for a light background must not render as a dark smear on
a dark pane (and vice-versa). Prose, math, and Mermaid — which already adapt — must not regress.

## What's already theme-aware (don't rebuild)

- The viewer pane itself themes via `@media (prefers-color-scheme: dark)` on `:root` token vars
  (`viewer.html` top `<style>`).
- **Mermaid** picks its dark/default theme by `matchMedia` (`initMermaid`).
- **KaTeX** math inherits the pane text colour.

The gap is **raster/SVG images** authored for a light background, shown on a dark pane (or the
inverse).

## Decisions for the plan (not pre-made here)

- **The fix mechanism** — choose and justify one:
  - **(a) Neutral card** — render the document/images on a consistent neutral surface regardless of
    pane theme. Surgical variant: a neutral card behind **images only**, leaving prose/math on the
    pane theme.
  - **(b) Host `color-scheme`** — set the page `color-scheme` so `@media (prefers-color-scheme)`
    inside `<img>`-loaded SVGs fires and theme-aware diagrams adapt to the pane.
  - **(hybrid)** — some combination.
  The plan must pick what actually fixes the reported bug **without** making Mermaid/diagram theming
  worse or fighting the existing dark theme, and must weigh the tradeoff (a global neutral card
  changes the whole reading surface; an image-only card is more surgical but only helps images).
- **Scope of the surface** — images only, or the whole `#article`? Whichever the chosen mechanism
  implies; state it.

## Out of scope

- Footnotes and syntax highlighting (P2) — separate backlog thread.
- The animated GIF demo (MR-021) — separate backlog thread.
- Any service/API/MCP change — this is a `viewer.html`-only concern.
- A user-facing theme toggle — the pane follows the OS `prefers-color-scheme`; a manual switch is
  not asked for.

## Amendments

_None yet._
