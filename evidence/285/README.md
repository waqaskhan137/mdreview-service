# #285 evidence — theme toggle: light / dark / auto, persisted, all five pages

Captured 2026-07-30 against a local dev build of this branch (`PYTHONPATH=src python3 -m
mdreview` on :8397), headless Chrome via `scripts/cdp-shot.mjs`, every state reached by REAL
clicks on the toggle — no OS emulation and no attribute poking, because clicks are what the AC
measures. The full computed-value matrix is `bash tests/theme_toggle_selfcheck.sh` (below).

| Shot | Surface | What it proves |
|---|---|---|
| `dashboard-auto.png` | `/` fresh load | Auto state: monitor glyph (the documented judgement call for "system"; the mock never draws this state), light ground because the emulated OS is light. |
| `dashboard-light.png` | after 1 click | Explicit light: sun glyph, per the mock's light screens. |
| `dashboard-dark.png` | after 2 clicks | Explicit dark: moon glyph, `#14130F` ground, violet desaturated, identical DOM. |
| `viewer-dark.png` | `/review/<id>` after 2 clicks | Consumers follow the EFFECTIVE theme with no reload: Mermaid re-rendered in its dark theme, hljs dark palette, serif column at weight 350. |

## The runnable matrix (AC 9)

`bash tests/theme_toggle_selfcheck.sh` starts a local instance (dashboard, account, both
viewers; `MDREVIEW_ENABLE_LATEX=1`) plus a hosted one (`/admin` is hosted-only), wires the
Mermaid + python fixtures, and runs `scripts/theme-check.mjs` over the full matrix: 52 named
computed-value checks (AC 1-8), exit non-zero on any mismatch. Green on this branch.

## Mutation evidence (AC 9 + the standing rule), each applied, observed failing, reverted

Every failure below is the check's own named finding, not a crash; the suite exits 0 again
after each revert. m1 and m2 are the two mutations AC 9 names.

| Mutation | Caught by |
|---|---|
| m1: head applier removed (dashboard) | `AC3 ... first-rAF sample: bg=rgb(252, 251, 249) data-theme=null (want rgb(20, 19, 15) / dark)` + AC2 reload finding |
| m2: `data-theme` write removed from the click path | `AC1 cycle ... after click: body bg=... want ...` on all 10 page/scheme combos (29 findings) |
| m3: keysheet card colour pinned to `#111` | `AC5b ... card colour=rgb(17, 17, 17) want rgb(232, 228, 220)` (both mirror states) |
| m4: hljs keyword loses its dark side | `AC5c ... computed rgb(215, 58, 73), want rgb(255, 123, 114)` (dark state only) |
| m5: `initMermaid` back to `matchMedia` only | all three AC5a override checks (`fill stayed 'rgb(236, 236, 255)'` under explicit dark) |
| m6: `mdr:themechange` listener removed | ONLY `AC5a ... rethemes the diagram WITHOUT a reload` — discriminates from m5 |
| m7: `color-scheme: dark` flip removed | static: `[data-theme="dark"] color-scheme is 'undefined'`; matrix: 19 findings across AC1/AC4/AC7 |
| m8: `localStorage.setItem` removed | `AC2 ... after choosing dark, mdr.theme='null'` + `the key did not survive the reload` |
| m9: aria-label update removed | `AC1 ... aria-label='Theme: system' want 'Theme: light'` on all 10 combos |
| m10: rival machinery wired (`.dark` class + `themeMode` key) | `AC6 ... a .dark class appeared on <html> (basecoat.theme is running)` on all 3 Basecoat pages |
| m11 (x3, static): dark table duplicated / dark literal drifted / light flip removed | `css_palette_selfcheck.js`: `--bg declared 2x`, `contract says 'light-dark(#fcfbf9, #14130f)'`, `missing: explicit light` |
| m12: transition snuck onto the toggle | `AC8 the toggle ships no transition of its own <- transition-duration=0.15s` |
