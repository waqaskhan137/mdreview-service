# #277 evidence — rev-3 token contract, self-hosted fonts

Captured 2026-07-30 against a local dev build of this branch (`PYTHONPATH=src python3 -m
mdreview` on :8271), real Chrome via the browser MCP, computed styles and the network log, never
CSS-text assertions (the #265 lesson). Dark was driven exactly the way #285's toggle will:
`document.documentElement.dataset.theme = 'dark'`.

| Shot | Surface | What it proves |
|---|---|---|
| `dashboard-light.jpg` | `/` light | Warm `#FCFBF9` ground, Geist UI, violet primary button (the Basecoat `--accent` collision fix holds: the button is violet, not a grey surface). |
| `dashboard-dark.jpg` | `/` with `data-theme="dark"` | `#14130F` ground, desaturated `#B5A7E6` accent, body weight 350. Identical DOM. |
| `viewer-light.jpg` | `/review/<id>` light | Source Serif 4 reading column (roman + italic), Geist Mono code block, warm chrome. |
| `viewer-dark.jpg` | same review, `data-theme="dark"` | Same DOM, token swap only; the reading column drops to weight 350. |

## Computed-outcome numbers (AC 4)

- Light dashboard `getComputedStyle(document.body).backgroundColor` = `rgb(252, 251, 249)`.
- With `data-theme='dark'`: `rgb(20, 19, 15)`; removing the attribute returns it to light, and an
  explicit `data-theme='light'` under system-dark also renders light (tri-state intact for #285).
- Dark body computed `font-weight` = `350` on both dashboard and viewer; `document.fonts.check`
  after `document.fonts.ready` on the viewer: `16px Geist`, `350 16px Geist`,
  `16px "Geist Mono"`, `550 16px "Geist Mono"`, `16px "Source Serif 4"` all true. 350 and 550
  cannot be satisfied by static cuts, so the variable axes demonstrably loaded.
- Viewer-load network log: font requests are exactly
  `/static/Geist-Variable.woff2`, `/static/GeistMono-Variable.woff2`,
  `/static/SourceSerif4Variable-Roman.woff2`, all same-origin 200s; zero requests to any other
  host (the italic serif face loads lazily on first italic render).

## Mutation evidence (AC 3), each applied, observed failing, reverted

| Mutation | `css_palette_selfcheck.js` finding |
|---|---|
| m1: dark `--accent` `#000` in one dark block only | `--accent in the media-dark block is '#000', contract says '#B5A7E6'` and `--accent diverged: media-dark '#000' vs explicit-dark '#b5a7e6'` |
| m2: `--surface-raised` deleted from the media-dark block | `--surface-raised missing from the media-dark block` and `--surface-raised only in the explicit-dark block` |
| m3: `background:#ffffff` added to a `dashboard.html` rule | `web/app/dashboard.html: ... unlisted literal #ffffff (x1)` |
| m4: `GeistMono-Variable.woff2` deleted, `@font-face` kept | `GeistMono-Variable.woff2 is declared but the file does not exist in web/app/static/` |
| m5: `fonts.googleapis` `<link>` added to `viewer.html` | `fonts.googleapis / fonts.gstatic appear nowhere under web/app <- CDN reference in: web/app/viewer.html` |

All five are semantic findings, not crashes; the suite exits 0 again after each revert.
