---
id: MR-087
title: Dashboard re-skin — sidebar inbox + projects filter + restyled cards with baton badges
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: []
branch:                # MR-087-dashboard-reskin, once work starts
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Re-skin `dashboard.html` to the new mockup (`.scratch/mockup-viewer-dashboard.html`): a left
sidebar (brand, **Inbox** section, **Projects** section) plus a main column (active-filter heading,
sub-count, top-right search, card grid). Cards are restyled to the mockup with a turn-baton status
badge. The mockup's IA replaces the current chip filters and grouped/flat toggle — but every durable
behavior (search, hover-delete, empty state, live refresh) is carried forward. No backend change.

See epic decisions **D1** (IA replacement) and **D2** (card badge, no `STALE_S` on the dashboard).

## Acceptance criteria

- [ ] Left sidebar renders: brand, an **Inbox** with `All reviews`, `Needs you`, `Agent working`,
      `Resolved` (each a button with a live count), and a **Projects** list derived from the distinct
      `project` values in `allReviews`. Active item is highlighted. The mockup's
      `agent watcher · connected` indicator is **omitted** (epic assumption 3).
- [ ] Inbox filter predicates (client-side over `/api/reviews` rows, per epic D1):
      `Needs you` = `turn==="reviewer" && status!=="resolved"`; `Agent working` = `turn==="agent"`;
      `Resolved` = `status==="resolved"`; `All reviews` = no filter. Clicking a Project scopes the
      grid to that project. Counts match the filtered set.
- [ ] Cards restyled to the mockup: project/session/path line, title, **baton status badge**
      (`Your turn` / `Agent working` / `Waiting for agent` / `Resolved`) derived per D2 with
      **no `STALE_S` freshness test** (badge uses `agent_status.state==="working"`; no
      `(now − at) <= STALE_S`), open/resolved count line, version `vN`, relative time.
- [ ] `dashboard.html` introduces **no** `STALE_S` constant: `grep -c STALE_S dashboard.html` → `0`
      (epic R1 / Key constraint #2).
- [ ] Durable behaviors carried forward and verified: whole-card `<a href="/review/{id}">` link;
      `#search` filters title/project/path; `.del` hover-trash deletes via `DELETE /api/reviews/{id}`
      with the `confirm()` guard; empty state (`No reviews yet … POST /api/reviews`) shows when zero
      reviews; `load()` fetch + `render()` still drive the page. Chip and group-by code (and their
      event handlers + dead CSS) are removed together — no orphaned handler, no dead selector.
- [ ] `rel()` relative-time + `toLocaleDateString()` fallback unchanged (Europe/London / locale).
- [ ] Legacy back-compat: a review row with no `project`/`session`/`turn` keys renders a card without
      error (badge defaults to `Your turn` via `turn==="reviewer"`; breadcrumb shows only present
      segments). (epic R5)
- [ ] Dark mode preserved: the mockup's light palette is the `:root` light theme and the existing
      `@media (prefers-color-scheme: dark)` token swap still derives a dark palette (epic D4).
- [ ] Local validation passes: `python3 -m py_compile app.py` (unchanged but green) +
      `docker build` of the image serving the edited file, then from the rebuilt container:
      `scripts/render-smoke.sh "$BASE/" '#sidebar-or-final-id' '.inbox-item' '.project-item'
      '#search' '.card' '.badge-turn-or-final-id' '.del'` — every selector ≥1 node (final class
      names pinned during implementation; flat selectors only). Plus both-pane screenshots of `/`
      via `--blink-settings=preferredColorScheme=1` and `=0` (never `--force-dark-mode`).
- [ ] Manual click-through from the rebuilt container: each inbox filter narrows the grid; a project
      scopes it; search filters; hover-trash deletes (confirm dialog); empty state shows.

## Notes / context

- Epic plan: [`epics/viewer-dashboard-reskin-plan.md`](../epics/viewer-dashboard-reskin-plan.md) —
  decisions D1, D2, R1, R5, R7; Verification §2.
- Current file: `dashboard.html` — `#search` (line 81), chips (82–86), `renderGrouped` (186),
  `applyFilter()` (224), `.del` delete handler (246), `rel()` (102), `card()` (125).
- Data backing (no new endpoint): `summary()` at `app.py:147` returns `turn`, `agent_status`,
  `status`, `notes_total/addressed`, `revision`, `project`/`session`/`source_path` on each
  `/api/reviews` row (served at `app.py:503`). `dashboard.html` is served at `/` via `_read`
  (`app.py:500`).
- Footguns: render-smoke selectors are flat (`tag`/`.class`/`tag.class`/`#id`, no descendant
  combinators); a 200 is not a render; bare headless Chrome resolves dark by default so capture
  light/dark via `preferredColorScheme`.
- **Re-skin the DOM, not the wiring** (epic Core principle): keep ids the JS reads where possible;
  any renamed id/class is updated at every JS reference in THIS ticket.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Session-level grouping tree is a deliberate non-goal (epic D1); revisit only if a reviewer needs it.
