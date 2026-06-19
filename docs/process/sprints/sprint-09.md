---
id: sprint-09
name: dashboard-redesign
status: active
start: 2026-06-19
end: 2026-06-26
goal: Rewrite dashboard.html into a dense, full-width, searchable grid of collapsible cards with collapsible project groups, preserving all functionality.
close_review:          # reviews/sprint-09-close-review-YYYY-MM-DD.md — required by G7 before status: closed
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

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over;
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-09-close-review-YYYY-MM-DD.md`, verifying shipped work against MR-031's ACs;
      since a product page (`dashboard.html`) is touched, it rebuilds the container, runs
      `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh` against `/` asserting
      `.grid` `.card` `#search` `.group-header`, with the **required screenshot set** (wide/
      ultrawide/collapsed/expanded/search-filtered/group-collapsed + **both panes** via
      `--blink-settings=preferredColorScheme=0/1`) under `reviews/sprint-09-render-evidence-*`, **and
      exercises the preserved functionality** (Open / Delete on a throwaway review / version badge /
      notes-count) — not just the new layout;
- [ ] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
