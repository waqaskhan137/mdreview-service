---
id: sprint-10
name: dashboard-density
status: active
start: 2026-06-19
end: 2026-06-26
goal: Remove the dashboard's remaining wasted space — fill sparse rows (auto-fit + lone-card cap), tighten the top gap, raise the width cap to 2000px.
close_review:          # reviews/sprint-10-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

By the end of the sprint, the dashboard fills the row (sparse projects no longer leave a big empty
right gutter), the first project header sits just under the search bar, and the page feels
edge-to-edge to 2000px instead of floating in a 1600px column. A lone card caps at a sensible width;
2+ card session rows split evenly and fill. All existing behavior — search/filter, chips, card +
group collapse/expand, expand/collapse-all, Open/Delete/version/notes, pane-adaptive theme —
preserved. `dashboard.html` only.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-032 | Dashboard density — auto-fit row-fill + lone-card `:has()` cap + raise width cap to 2000px + trim whitespace | ui | P1 | ready |

Single-ticket sprint (a focused CSS refinement to the just-shipped `dashboard.html`).

## Preferred execution order

1. **MR-032** — the CSS edits in `dashboard.html`, then CDP render evidence + the preserve-functionality re-check.

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over;
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-10-close-review-YYYY-MM-DD.md`, verifying shipped work against MR-032's ACs;
      since a product page (`dashboard.html`) is touched, it rebuilds the container, runs
      `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh` against `/`, with the
      screenshot set (top-gap / sparse-row-fill / multisession / wide edge-to-edge / both panes via
      `preferredColorScheme=0/1`) under `reviews/sprint-10-render-evidence-*`, **and re-exercises the
      preserved functionality** (search/filter / chips / collapse-expand / Open / Delete on a
      throwaway / version / notes) — not just the new density;
- [ ] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
