---
id: MR-087
title: Dashboard re-skin — sidebar inbox + projects filter + restyled cards with baton badges
status: done           # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: []
branch: feat/ui-updates   # cycle runs on feat/ui-updates (off dev), single-flight; commits carry the ticket ID
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
- [x] `dashboard.html` introduces **no** `STALE_S` constant and no lease-freshness test:
      `grep -E 'STALE_S *=|now *- *.*\.at|<= *STALE_S' dashboard.html` → `0` matches (the only two
      `STALE_S` occurrences are explanatory comments stating the absence, not code). (epic R1 / Key
      constraint #2).
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

- `2026-06-25` — Rewrote `dashboard.html` to the mockup. New flex shell: 256px left sidebar
  (brand, **Inbox** nav with live counts, **Projects** list derived from distinct `project`
  values) + main column (active-filter `#h1`, sub-count, top-right `#search`, "Recent activity"
  eyebrow, card grid). Cards restyled to the mockup: project-only crumb (left) + `vN` (right),
  bold title, baton status badge + relative time, hairline divider, status-colored footer dot +
  open/resolved count. Status-colored left accent per card (`s-your-turn`/`s-agent-working`/
  `s-waiting`/`s-resolved`). `statusOf()` derives the four baton labels from `turn`+`agent_status`+
  `status` with **no `STALE_S` freshness test** (D2/R1). Removed the chip filters + grouped/flat
  tree and their handlers; rewired `applyFilter()` to the inbox/project predicates (`INBOX` map) +
  search, looking reviews up by `data-id`. Kept `load()`, `rel()` (+ `toLocaleDateString`
  fallback), `esc()`, the hover-`.del` delete with `confirm()`, the empty state, and the whole-card
  `<a href="/review/{id}">` link. Dark theme preserved via the `@media (prefers-color-scheme:dark)`
  token swap; no new font (system sans stack, not Geist — no-pip footgun). No `app.py` change.

## Validation

- `2026-06-25` — `python3 -m py_compile app.py` green; inline-JS parses (`new Function`).
- Render-smoke (throwaway instance, scratch port 8155, 5 seeded baton-state fixtures + a legacy
  no-provenance review): `.side .brand .nav-item(7) #projlist #search .eyebrow .grid .card(6)
  .badge(6) .divider(6) .countline(6) .del(6)` all ≥1 node, exit 0.
- `grep -E 'STALE_S *=|<= *STALE_S' dashboard.html` → 0 code matches (R1 satisfied — no second
  mirror; the two literal `STALE_S` hits are explanatory comments stating the absence). (G7 F2)
- Functional click-through (live tab): Inbox filters partition correctly — Needs you → 2
  `your-turn`; Agent working → 3 `turn===agent` (`agent-working`+`waiting`); Resolved → 1
  `resolved`. Search "cache" → 2 matching titles. Project "inference-gateway" → scopes to 3 +
  `#h1` updates. Hover-delete buttons present (6).
- Both panes: light screenshot matches the mockup (`.scratch/shots/dash-mine-light2.png` vs
  `dash-mock-light.png` — captured via `preferredColorScheme=1`, never `--force-dark-mode`); dark
  pane verified in the live OS-dark tab.

## Follow-ups

- Session-level grouping tree is a deliberate non-goal (epic D1); revisit only if a reviewer needs it.
