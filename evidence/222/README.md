# #222 stage-8 evidence — staging.mdreview.space, 2026-07-28

Captured with `node scripts/cdp-shot.mjs` against **staging**, signed in as the owner through the
real magic-link redeem flow, driving real `KeyboardEvent`s. Deployed image
`sha256:209e6199…`, adopted 18:03:15 after CI concluded for merge `de7ae8a`.

| Shot | Surface | What it proves |
|---|---|---|
| `staging-dashboard-sheet.png` | `/` | `⌘/` and `?` open the sheet; it lists the re-derived dashboard binds (`/`, `p`, `1`, `2`, `3`) generated from the live registry. |
| `staging-viewer-sheet.png` | `/review/<md>` | Viewer binds registered and listed. `c` toggles `#gutter.docked`, i.e. it drives the real control. |
| `staging-latex-sheet.png` | `/review/<latex>` | **The surface that could not be checked locally** — the local build serves no latex reviews. `1`/`2` flip `aria-pressed` on the source/PDF tabs. |
| `help-sheet-viewer.png` | local | Kept as the before/after record for E6 (see below). |

## Assertions run on staging, beyond the screenshots

- **The `/` vs `?` trap, proven on the real deployment:** `/` focuses `#search` and does **not**
  open the sheet; `?` then opens it. Same physical key, two behaviours.
- `Escape` closes the sheet on all three surfaces.
- `2` on the dashboard puts `.filt[data-filter=working]` into `.on`.
- `1`/`2` on latex-viewer set `aria-pressed=true` on `#tab-src` / `#tab-pdf`.

## Contrast, measured not eyeballed

`getComputedStyle` on both dashboard and viewer: page background `rgb(15,16,20)`, card background
`rgb(15,16,20)`, card text `rgb(238,238,238)`.

The card fill is **identical** to the page. Separation comes from its 1px border, its shadow, and
the backdrop dimming everything behind it. That reads correctly (the screenshots confirm it), but it
is worth stating plainly rather than claiming the card is elevated. Text contrast is 238-on-15,
which is not marginal.

## E6, kept here because it is the lesson

Every stage-5 assertion passed while the keycaps were **unreadable**: the dark-mode block restated
the keycap background and border but not its `color`, leaving near-black glyphs on a dark card. The
assertions were checking that `<kbd>` elements existed, which they did.

"A node is in the DOM" and "a user can read it" are different claims, and only the first is cheap to
assert. The screenshot is not decoration in this folder; it is the only thing that caught it.

## Not covered

`account.html` and `admin.html` load `keys.js` but register no page-specific bindings, so they get
the global help sheet only. Not separately captured.
