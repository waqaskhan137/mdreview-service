---
id: MR-004
title: dashboard.html — Project>Session grouping, status pills, open/delete, revision badge
status: ready
layer: ui
priority: P1
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-002, MR-003, MR-005]
branch:
created: 2026-06-08
updated: 2026-06-08
---

## Goal

The human front door: a self-contained dashboard listing every review grouped by project and
session, with status at a glance and the ability to open or delete.

## Acceptance criteria

- [ ] New `dashboard.html` at the project root (served by MR-003), self-contained, **no external
      assets**, matching `viewer.html`'s aesthetic (same CSS custom properties, light/dark via
      `prefers-color-scheme`, font stack, teal accent).
- [ ] On load `fetch('/api/reviews')`, group **Project > Session > files**: outer sections by
      `project || 'Ungrouped'`, inner by `session` (omit the sub-header when a review has no
      `session`).
- [ ] Each card shows: `title || id`, `source_path` (monospace, muted), relative `created` time,
      a note-count badge (`notes_total`, `· N done` when `notes_addressed`), a status pill colored
      by `status` (awaiting/feedback/resolved), and a `vN` revision badge when `revision > 0`.
- [ ] Actions: **Open** -> `/review/{id}`; **Delete** -> confirm, `DELETE /api/reviews/{id}`, then
      re-fetch. Empty state when no reviews exist.
- [ ] Validation: rebuild/serve, `curl /` returns the page, and **open `/` in a browser** to
      confirm it renders, groups correctly, and pre-existing reviews appear under "Ungrouped".
      Screenshot for the G7 evidence.

## Notes / context

- Mirror `viewer.html` styles (`viewer.html:7-65`). Consumes MR-002 (`/api/reviews`) and the
  `revision` from MR-005. Delete reuses the existing `DELETE /api/reviews/{id}` (`app.py:185`).
- Epic: `epics/review-dashboard-plan.md`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
