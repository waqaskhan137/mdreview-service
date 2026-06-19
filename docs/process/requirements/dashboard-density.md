---
slug: dashboard-density
captured: 2026-06-19
source: user request 2026-06-19 (waqas) — follow-up on the shipped dashboard redesign (MR-031 / sprint-09 / PR #8); "Show me the result when done." Full feature-cycle (lean).
related_epic: epics/dashboard-density-plan.md
---

# Dashboard density — remove remaining wasted space

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> The dashboard is denser now, but fix the remaining wasted space:
>
> **GAP ABOVE CONTENT**
> - Reduce the vertical gap between the top bar (search/filters) and the first project. Tighten the
>   "43 reviews across 14 projects" line — minimal margin above and below it. Aim for the first
>   project header to sit just under the search bar.
>
> **EMPTY RIGHT SIDE OF ROWS**
> - Right now each project's cards stay narrow and leave the rest of the row empty (e.g. "agit" has
>   1 card, the other ~75% of the row is blank).
> - Make cards stretch to fill the available row width. With a `repeat(auto-fit, minmax(280px, 1fr))`
>   grid, a project with 1 card should have that card span the full width (or a sensible max), and 2
>   cards split evenly — no large empty gutter on the right.
> - Alternatively, raise the column count / card min-width so wide screens are actually filled.
>
> **OVERALL DENSITY**
> - Trim outer page padding and the whitespace around/between project groups and cards generally. The
>   page should feel full edge-to-edge, not floating in empty space.
>
> Keep all existing functionality, search/filter, and collapse/expand behavior.
> Show me the result when done.

## Scope notes (for grooming, not changes to the ask)

- `ui`-only follow-up to MR-031; touches **only `dashboard.html`**. No service/API/MCP change.
- This explicitly **overrides the MR-031 A4 decision** (the `max-width:1600px` cap chosen to honor
  "3–5 columns"): the user now wants edge-to-edge / wide screens filled. The cap is reconsidered.
- The named fix is `auto-fill → auto-fit` so sparse rows fill; the "sensible max" for a lone card is
  the one design judgment to settle by measurement.
- Preserve every existing behavior: search/filter, chips, card + group collapse/expand,
  expand/collapse-all, Open/Delete/version/notes, pane-adaptive theme.

## Out of scope

- Any change to `app.py`, the API, the MCP wrapper, `viewer.html`, routing, or the data payload.
- New features (the brief is density/layout only).

## Amendments

_None yet._
