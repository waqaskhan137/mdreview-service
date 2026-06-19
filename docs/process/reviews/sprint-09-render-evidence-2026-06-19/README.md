# sprint-09 (dashboard-redesign) — render evidence — 2026-06-19

Product page touched: `dashboard.html` (served inline at `GET /`). Rebuilt throwaway container on
:8138 (never compose/:8139). Screenshots captured via Chrome DevTools Protocol (Node built-in
WebSocket driver) so interaction states are real, and `prefers-color-scheme` is emulated via CDP
`Emulation.setEmulatedMedia` (NOT `--force-dark-mode`).

- `render-smoke.sh '/' '.grid' '.card' '#search' '.group-header'` → all ok (flat selectors).

**Screenshots:**
- `wide-5col.png` (1680px, dark) — dense grid, **5 columns** in the blog-2/run-1 grid; sticky search
  bar with chips (All/Has notes/Done) + Expand all/Collapse all; collapsible group headers (chevron +
  count); compact ~3-line cards.
- `ultrawide-capped.png` (2560px, dark) — columns **cap at 5** (the 1600px container cap), not
  edge-to-edge 8.
- `collapsed.png` (1280px, dark) — default collapsed cards: title + one meta row (~3 lines), no path,
  no actions.
- `expanded.png` (1280px, dark) — a clicked card reveals its **full path** (`tmp/del.md`) + **Open /
  Delete** actions; siblings stay collapsed.
- `search-filtered.png` (1280px, dark) — typing "pricing" shows only the matching card and **hides
  the empty "blog 2" group**.
- `group-collapsed.png` (1280px, dark) — the "blog 2" group collapsed (▸ chevron + count 12 visible,
  body hidden); the other group stays open.
- `dark-pane.png` / `light-pane.png` (1440px) — pane-adaptive theme, both panes legible
  (`preferredColorScheme` emulated).

**Preserved functionality (exercised, not just rendered):**
- **Open** — the card's `<a href="/review/{id}">`; `GET /review/{id}` → 200 (viewer renders).
- **Delete** — clicking Delete on a throwaway "Delete me" card → `confirm()` (CDP auto-accepted) →
  `DELETE /api/reviews/{id}` → `load()`: card count 14→13, card gone from the DOM **and** from
  `/api/reviews`. (Throwaway container only; live :8139 never touched.)
- **Version badge** — after two `PUT /source` bumps, the card shows **v2**.
- **Notes count** — after posting 2 notes (1 addressed), the card badge shows **"2 notes · 1 done"**
  (the preserved `noteLabel()`).
