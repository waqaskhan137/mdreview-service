# sprint-28 render evidence — viewer-dashboard-reskin (2026-06-25)

Captured from a **rebuilt throwaway container** (`docker build -t mdreview:reskin-g7 .`, run on
scratch port `:8166` with a fresh volume — never the live `:8139` or compose `:8137`). Both product
pages (`dashboard.html`, `viewer.html`) were touched this sprint, so G7 owes per-page DOM assertions
+ screenshots.

## Container smoke
- `GET /healthz` → `{"ok": true}`
- `GET /api/reviews` → sane JSON (empty pre-seed, then the seeded fixtures).

## render-smoke.sh (DOM-node assertions, rebuilt container)
- **Dashboard** `/`: `.side .nav-item(6) #projlist #search .eyebrow .card(5) .badge(5) .divider(5)
  .countline(5) .del(5)` — all ≥1 node, exit 0.
- **Viewer** `/review/<id>`: `.topbar .breadcrumb #doctitle #turnbanner #sendbtn #reclaimbtn
  .blk(6) .num(6) #gutter .gcard(2) .gref(2) #dock #resbtn #histbtn mark.cmt(2)` — all ≥1, exit 0.

## Screenshots (both panes, `--blink-settings=preferredColorScheme=1|0`, never `--force-dark-mode`)
- `dashboard-light.png` / `dashboard-dark.png`
- `viewer-light.png` / `viewer-dark.png`

## Computed-style check (theme work — beyond node-count, per the G7 render-fidelity lesson)
Drove headless Chrome on the **dark** pane (the invisibility-risk pane) and read
`getComputedStyle(el).color` vs the resolved background for every high-risk node. **All passed**
(luminance contrast ≫ the 25 floor; nothing rendered black-on-dark):
- Viewer: `#turntext` (197), `#article h2` blue heading (172), `.gentry .gtext` (165),
  `.gentry.reviewer .grole` violet label (104), `.gref` (158), `#doctitle` (218), `.breadcrumb`,
  `#topstate`, `mark.cmt`.
- Dashboard: `h1` (218), `.nav-item.active .nm` (198), `.card .title` (210), `.badge.your-turn`
  (136), `.badge.agent-working` (153), `.badge.resolved` (135), `.crumb .seg`, `.countline`,
  `.eyebrow`. `allOk: true`.

## Functional regression (live, during implementation — see MR-088/089 Validation)
Baton Send (now in the banner) flips `turn`→`agent` + `#topstate`→"waiting for agent" + disables;
reclaim → `reviewer`; resolving a comment live-updates the rail (3→2 cards) via the poll; comment
anchoring (`mark.cmt`) intact; `body.gutter-on` wide-mode engages at **~1315px** and docks below
(pre-existing geometry — `git diff 8d4227c^ -- viewer.html` shows the `+320` fit constant and
`max-width:720` unchanged). No second STALE_S mirror on the dashboard:
`grep -E 'STALE_S *=|<= *STALE_S' dashboard.html` → 0 (the two literal `STALE_S` hits are
explanatory comments). `viewer.html` STALE_S=180 with its `app.py:57` mirror comment intact.
