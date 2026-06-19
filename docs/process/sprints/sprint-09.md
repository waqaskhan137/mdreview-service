---
id: sprint-09
name: dashboard-redesign
status: closed
start: 2026-06-19
end: 2026-06-19
goal: Rewrite dashboard.html into a dense, full-width, searchable grid of collapsible cards with collapsible project groups, preserving all functionality.
close_review: reviews/sprint-09-close-review-2026-06-19.md   # G7 staff-critic PASS, resolved
---

## Goal

By the end of the sprint, the reviews dashboard at `GET /` fits 3–5 review cards per row on desktop,
each a ~3-line collapsed card (title + one metadata row) that expands in place to reveal its full
path, notes, and Open/Delete actions; with a sticky search bar that live-filters by title/project/
path (hiding empty groups), collapsible project groups (chevron + count + expand/collapse-all,
session-memory state), and dark-theme polish. All current behavior — Open, Delete, the version
badge, the notes-count display, Project›Session grouping, and the pane-adaptive theme — survives.
`dashboard.html` only; no service/API/MCP/`viewer.html`/`Dockerfile` change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-031 | Redesign `dashboard.html` — dense full-width grid, collapsible cards, sticky search, collapsible project groups (preserve open/delete/version/notes) | ui | P1 | done |

Single-ticket sprint (the plan resolved to one cohesive `dashboard.html` rewrite; a 2-ticket split is
a recorded fallback only). No other backlog committed.

## Preferred execution order

1. **MR-031** — build internally Phase 1 (dense grid + collapse/expand cards) → Phase 2 (sticky
   search + collapsible groups + chip) → Phase 3 (polish + both-pane evidence), all in `dashboard.html`.

## Notes / retro

- `2026-06-19` — MR-031 shipped same-day: one cohesive `dashboard.html` rewrite (sticky search,
  dense capped grid, collapsed click-to-expand cards, collapsible project groups, dark-theme polish),
  reusing the existing `esc`/`rel`/`noteLabel`/`groupBy` helpers; `app.py`/routes/Dockerfile untouched.
- `2026-06-19` — **The new computed-style/CDP evidence habit paid off again.** A node-count
  render-smoke + a flat screenshot can't prove *interaction* states or *preserved behavior*, so the
  evidence was captured by **driving Chrome over CDP** (Node built-in WebSocket): real clicks
  (expand, group-collapse, Delete-with-confirm), `Emulation.setEmulatedMedia` for both panes (not
  `--force-dark-mode`), and `getBoundingClientRect` to *measure* the column count. The G7 critic
  re-ran the same CDP measurements rather than eyeballing the PNG — and caught (then retracted) its
  own miscount of the downscaled screenshot by measuring the live layout.
- `2026-06-19` — **Preserve-functionality was treated as load-bearing and exercised, not assumed:**
  Delete clicked → card gone from DOM *and* `/api/reviews`; `v2` + `2 notes · 1 done` from real
  `PUT /source` + `POST /feedback`; the three click-guards (Open-link nav, Delete, text-selection)
  reproduced. The brief's "preserve all existing functionality" is exactly the kind of constraint a
  pure visual review would skip.
- `2026-06-19` — **Closed at G7: staff-critic PASS** (`reviews/sprint-09-close-review-2026-06-19.md`,
  resolved). 0 blockers, 0 shoulds, 2 NITs (a downscaled-PNG miscount the critic re-measured to 5
  columns; a page-global selection guard matching the plan's Fork-1 decision) — both accepted.
- **Carry-overs:** none. The A4 1600px cap shipped as the default; if the user wants true edge-to-edge
  on a 4K monitor (columns be damned), that's a one-line change recorded in MR-031 follow-ups.
- **Retro:** a clean prescriptive-brief cycle. The planner measured the two render-observable forks
  (column overshoot, collapsed-card height) and the theme model (pane-adaptive, not dark-only) up
  front, so G1 had one verification-flag SHOULD and G7 was a first-pass PASS. The cumulative habit
  (measure forks, verify hand-derived/interaction output, CDP for dynamic state) carried straight in.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-09-close-review-YYYY-MM-DD.md`, verifying shipped work against MR-031's ACs;
      since a product page (`dashboard.html`) is touched, it rebuilds the container, runs
      `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh` against `/` asserting
      `.grid` `.card` `#search` `.group-header`, with the **required screenshot set** (wide/
      ultrawide/collapsed/expanded/search-filtered/group-collapsed + **both panes** via
      `--blink-settings=preferredColorScheme=0/1`) under `reviews/sprint-09-render-evidence-*`, **and
      exercises the preserved functionality** (Open / Delete on a throwaway review / version badge /
      notes-count) — not just the new layout;
- [x] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
