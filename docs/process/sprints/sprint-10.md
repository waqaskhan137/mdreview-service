---
id: sprint-10
name: dashboard-density
status: closed
start: 2026-06-19
end: 2026-06-19
goal: Remove the dashboard's remaining wasted space — fill sparse rows (auto-fit + lone-card cap), tighten the top gap, raise the width cap to 2000px.
close_review: none — out-of-cycle exception (user waived the gated close; no independent G7 staff-critic review). See Notes.
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

- `2026-06-19` — **Closed as an OUT-OF-CYCLE exception (user instruction).** Mid-implementation
  (MR-032's density CSS was written + render-validated, pre-commit), the user explicitly said *"make
  this exception, do not run the cycle, make the change without it"* and gave a **larger redesign
  brief**: replace the project-grouped default with **one flat continuous packed grid** (newest-
  activity first, project-as-inline-tag, zero gutters) plus a **"Group by project" toggle**. That
  shipped **directly to `dev`** (commit `0f44c1b`), with MR-032's density CSS folded into the grouped
  (toggle-on) mode.
- **What this means for the gates:** MR-032's plan **passed G1** (2 rounds, `reviews/dashboard-density-plan-review-2026-06-19*.md`) and the shipped change was **render-validated by the implementer via CDP** (flat=1 grid/13 cards; expand/group-toggle/search/delete/notes/version all confirmed; both panes). It was **NOT** put through an independent **G7** staff-critic review — that gate was **waived by the user's exception**, recorded here honestly rather than faked. No `sprint-10-render-evidence-*` dir / close-review file exists.
- **Carry-overs:** none — the dashboard-density scope is fully superseded by the shipped flat-grid redesign.

## Close gate (G7) — WAIVED (out-of-cycle exception)

Normally a sprint cannot close without an independent G7 staff-critic review. The user **explicitly
waived the cycle** for this change, so it shipped directly:

- [x] the committed ticket (MR-032) is `done` — its density CSS shipped within the direct redesign;
- [~] **G7 staff-critic close review — WAIVED by user instruction** (no independent review; the change
      was render-validated by the implementer via CDP, not gated by a critic);
- [x] this Notes section records the exception + carry-overs; `close_review:` set to the waiver note.
