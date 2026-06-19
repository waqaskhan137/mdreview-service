---
id: MR-031
title: Redesign dashboard.html — dense full-width grid, collapsible cards, sticky search, collapsible project groups
status: done
layer: ui
priority: P1
sprint: sprint-09
epic: dashboard-redesign
depends_on: []
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Rewrite `dashboard.html` (only that file) into a dense, full-width, searchable grid of collapsed
click-to-expand cards with collapsible project groups — so a reviewer stops scrolling endlessly past
tall 2-column cards. Same `GET /api/reviews` payload; no service/API/MCP/`viewer.html` change. All
current behavior survives: Open, Delete, version badge, notes-count, Project›Session grouping,
pane-adaptive theme.

## Acceptance criteria

- [x] **Full-width dense grid.** Container is full-width (side padding ~24px) **capped at
      `max-width:1600px`** centred (5×280 + 4×10 gap + 2×24 pad ≈ 1488 fits 5 columns; a 6th needs
      ~1778px, so 1600 tops out at 5). Each grid uses
      `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` (brief value), `gap:10px`.
      Density halved from today: card `padding:8px 10px` (was 13px 14px), inner `gap:5px`, body
      `14px/1.45`, card `border-radius:8px`.
- [x] **Collapsed card (default) = title + one metadata row.** Line 1: title, **single-line ellipsis**.
      Line 2: status pill · notes-count badge · version badge · relative date. File path and actions
      are **hidden** when collapsed. Natural collapsed height ~3 lines (≤ the brief's "5–6 lines"
      **upper bound** — do NOT pad to reach 5–6). File path renders single-line ellipsis (no wrap).
- [x] **Click-to-expand in place.** Clicking the card toggles `.expanded`, revealing: the full
      `source_path` (own line) + the full notes label + small inline **Open** / **Delete** buttons.
      The whole-card click handler returns early if `e.target.closest('a, button')` (so Open/Delete
      fire their own behavior, never toggle) **or** if `window.getSelection().toString()` is non-empty
      (so selecting text to copy doesn't toggle). Actions are hidden collapsed, shown **on hover OR
      when expanded**.
- [x] **Accessibility.** Card has `role="button"`, `tabindex="0"`, `aria-expanded` (synced with
      `.expanded`); an Enter/Space `keydown` handler toggles it **with the same `closest('a,button')`
      + selection guard** as the click handler (no double-fire on a focused Open/Delete).
- [x] **Sticky search bar.** A sticky top bar (`position:sticky;top:0`, opaque `--bg`, z-index) with
      `<input id="search">`. Typing live-filters the **already-rendered** cards (case-insensitive
      substring over title + project + source_path, read from `data-` attrs — no re-fetch). Non-matching
      cards get `.is-hidden`; any session sub-group **and** project group left with zero visible cards
      is hidden too. Empty query clears the filter (group-collapse state independent).
- [x] **Expand all / Collapse all** controls near the search bar toggle every project group.
- [x] **Status chip toggle** (All / Has notes / Done) next to search, ANDed with the text query
      (has-notes = `status∈{feedback,resolved}`; done = `status==resolved`). (Brief's "optional but
      nice"; the natural cut line if scope runs long.)
- [x] **Collapsible project groups.** Each project `<section>` has a clickable `.group-header`
      (chevron + project name + count badge). Click toggles `.collapsed` (hides body; chevron
      rotates; count badge stays visible). State = a **session-lifetime JS `Set`** of collapsed
      project names (**NOT localStorage** — brief says session only); `load()` re-reads it so collapse
      survives a delete-triggered re-render but resets on reload. Grouping stays **project-level**;
      session sub-groups remain as non-collapsible sub-labels (A2).
- [x] **Polish (dark theme kept = pane-adaptive).** Hover lift + accent border on `.card:hover`,
      consistent radii (8px card / 6px btn / 20px pill), tighter type scale. Keep the existing
      `:root` + `@media (prefers-color-scheme: dark)` tokens — do **not** collapse to dark-only (A1).
      Any **new** literal color gets a light value + a dark override, verified on the dark pane.
- [x] **Preserved functionality (load-bearing, verified by clicking, not just layout):**
      - **Open** = `<a href="/review/{id}">` → navigates to the viewer.
      - **Delete** = button → `confirm()` → `DELETE /api/reviews/{id}` → `load()`; card disappears.
        (Tested only against a **throwaway** review on the throwaway container.)
      - **Version badge** `v{n}` renders for `revision>0`.
      - **Notes count** (`noteLabel`) renders "no notes" / "N notes · M done". (Don't duplicate it as
        a second badge in the expanded view — restate the same label.)
- [x] **No service/infra change.** `app.py`, routes, `Dockerfile` untouched; `dashboard.html` is
      already served at `GET /` and already in the `COPY`. `python3 -m py_compile app.py` still passes.
- [x] **GATING render evidence (rebuilt throwaway :8138):**
      `scripts/render-smoke.sh "$BASE/" '.grid' '.card' '#search' '.group-header'` → all ok (flat
      selectors, footgun 11 — never `.grid .card`). **Required screenshots** under
      `reviews/sprint-09-render-evidence-2026-06-19/`: `wide-5col.png` (3–5 cols @1680), 
      `ultrawide-capped.png` (≤5 @2560), `collapsed.png` (~3-line cards), `expanded.png` (path +
      actions + notes), `search-filtered.png` (only matching cards/groups, no empty headers),
      `group-collapsed.png` (collapsed group, chevron + count visible), `dark-pane.png`
      (`--blink-settings=preferredColorScheme=0`) + `light-pane.png` (`=1`) — both legible. **Use
      `preferredColorScheme=0/1`, never `--force-dark-mode`** (auto-invert ≠ scheme emulation).
- [x] Local validation: `python3 -m py_compile app.py`; `docker build`; the render-smoke + screenshot
      set + the Open/Delete/version/notes checks above.

## Notes / context

- Epic plan: `epics/dashboard-redesign-plan.md` — current-state map, the 5 mechanisms, Forks 1–5
  (click handling, density numbers, search, groups, theme), Verification (exact commands + the
  8 required screenshots), Risks. Reuse the existing `load`/`groupBy`/`esc`/`rel`/`noteLabel` helpers.
- A3: "full notes" = the notes-**count** label (the payload has no note bodies — ruled correct at G1).
- A4: the 1600px cap is the default; the brief gives both `minmax(280px,1fr)` and "3–5 columns" and
  this reconciles them — flagged for the user to override toward true edge-to-edge if wanted.
- Footguns: a 200 is not a render (screenshots are the binding proof); flat render-smoke selectors;
  live instance :8139 — throwaway :8138, never `docker compose`; delete test on a throwaway review only.

## Work log

- `2026-06-19` — Rewrote `dashboard.html` (only file). Reused `esc`/`rel`/`noteLabel`/`groupBy`;
  rewrote the `<style>`, `card()`, `load()`, and interaction handlers. **No `app.py`/Dockerfile/
  route change.**
- **Layout/density:** sticky `.bar` (search + chips + Expand/Collapse-all) with a 1600px-capped
  inner; `.wrap` 1600px-capped; `.grid` = `repeat(auto-fill, minmax(280px,1fr))`, `gap:10px`; card
  `padding:8px 10px` (halved), `14px/1.45`, `radius:8px`. Title single-line ellipsis with
  `padding-right` for the action cluster.
- **Collapsed/expanded:** default collapsed (title + meta row). One delegated click handler: delete
  first (confirm→DELETE→load), `closest('a')` lets Open navigate, group-header toggles the section,
  chips set the status filter, Expand/Collapse-all loop the sections; otherwise toggle `.expanded`
  on the card (guarded by `closest('a,button')` + non-empty `getSelection()`). `.path` shows only
  when `.expanded`; `.actions` (absolute top-right) show on hover OR expanded. `role/tabindex/
  aria-expanded` + an Enter/Space keydown handler with the **same** guard (a11y parity).
- **Search/filter:** `#search` `input` → `applyFilter()` over already-rendered cards (case-insensitive
  substring on `data-title/project/path`); status chip ANDs (`notes`=feedback|resolved,
  `done`=resolved); empty `.session` and `.project` get `.is-hidden`; a `#noresults` line when nothing
  matches. No re-fetch.
- **Collapsible groups:** per-project `.group-header` (chevron + name + count badge); `.collapsed`
  toggles the body; state held in a **session-lifetime `Set`** (not localStorage) re-applied by
  `load()` so collapse survives a delete re-render; Expand/Collapse-all clear/fill the Set.
- **Polish:** hover lift + accent border + shadow; small radii; tighter type scale; pane-adaptive
  tokens kept (no new literal colors — chip-active reuses `--accent`, so no new dark-pane risk).
- Files: `dashboard.html`.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK (unchanged); `docker build` OK; validated from a
  rebuilt throwaway container on :8138 (never compose/:8139). CDP-driven (Node built-in WebSocket;
  `prefers-color-scheme` via `Emulation.setEmulatedMedia`, not `--force-dark-mode`).
- `2026-06-19` — `render-smoke.sh '/' '.grid' '.card' '#search' '.group-header'` → all ok (.grid 4 /
  .card 6 / #search 1 / .group-header 2).
- `2026-06-19` — **8 screenshots** under `reviews/sprint-09-render-evidence-2026-06-19/`:
  `wide-5col` (5 columns), `ultrawide-capped` (caps at 5, not 8), `collapsed` (~3-line cards),
  `expanded` (path + Open/Delete revealed, siblings collapsed), `search-filtered` ("pricing" → only
  the match, empty "blog 2" group hidden), `group-collapsed` (▸ + count, body hidden), `dark-pane` +
  `light-pane` (both legible).
- `2026-06-19` — **Preserved functionality, exercised:** Open → `GET /review/{id}` 200; **Delete**
  clicked → `confirm()` accepted → `DELETE` → card 14→13, gone from DOM **and** `/api/reviews`;
  **version** badge "v2" after two `PUT /source`; **notes** badge "2 notes · 1 done" after posting
  feedback. Card expand/collapse, group collapse, search, chips, expand/collapse-all all confirmed.

## Follow-ups

- Per-note bodies in the expanded card would need a new `/api/reviews` field — separate epic (A3).
- "True edge-to-edge on 4K" (drop the 1600px cap) — one-line change if the user prefers it (A4).
