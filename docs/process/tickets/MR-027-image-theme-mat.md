---
id: MR-027
title: Viewer — neutral light mat behind #article img + .histdoc img (theme-safe images; excludes mermaid/katex)
status: ready
layer: ui
priority: P1
sprint: sprint-07
epic: theme-awareness
depends_on: []
branch: dev
created: 2026-06-18
updated: 2026-06-18
---

## Goal

A light-authored figure (a light/white-background PNG or SVG, including attached rich-rendering
assets) currently renders as an unreadable dark smear on a dark review pane. Give every embedded
`<img>` a stable near-white "paper" mat so light-authored figures stay legible on **both** panes,
without touching the surfaces that already theme themselves (Mermaid, KaTeX, prose). This is the
light-authored-on-dark majority case from `theme-awareness`; the inverse (dark-authored /
white-on-transparent figures) is an accepted non-goal — see the plan.

## Acceptance criteria

- [ ] **The mat.** A CSS rule in `viewer.html`'s top `<style>` gives `#article img, .histdoc img` a
      near-white `background` (literal `#fafaf9`, the existing light `--bg` value), `padding` (~8px),
      and `border-radius` (8px, matching the existing card radius), keeping `max-width:100%`. This
      extends the existing `#article img{max-width:100%}` rule (`viewer.html:~29`), not a new construct.
- [ ] **Image-only scope (no regression).** The selector matches only `<img>`; it must NOT match
      `.mermaid svg` (inline `<svg>`, `viewer.html:~35`) or `.katex` spans. A code comment above the
      rule states it must stay image-only (a later edit must not widen it to `#article > *` and break
      Mermaid's dark theme).
- [ ] **History modal covered.** `.histdoc img` (the version-history modal draft render, sibling of
      `.wrap` — `showRound()`) gets the same mat. (Per the plan, this arm isn't render-smokeable at
      first paint — the modal is closed in a `--dump-dom` load — so it's verified by rule presence +
      `showRound()` inspection, optionally a manual open-modal screenshot.)
- [ ] **No `color-scheme`.** Do NOT add `color-scheme` to `:root`/`html`/`body` or a
      `<meta name="color-scheme">` — measured not to reach `<img>` SVGs (plan's design-fork table).
- [ ] **No service/DOM change.** `app.py`, routes, storage, `meta.json`, `mcp_server.py` untouched;
      no JS image-wrapping in `render()`/`numberBlocks()`. CSS-only + a comment.
- [ ] **Default-safe.** A document with no `<img>` renders byte-identical to today on both panes
      (the rule matches nothing) — proven by the no-image screenshot.
- [ ] **GATING render evidence (both panes), from the rebuilt throwaway container (:8138):**
      `scripts/render-smoke.sh "$BASE/review/$ID" 'img' '#article' '.mermaid'` → all `ok` (≥1);
      light AND dark screenshots (`--blink-settings=preferredColorScheme=1`/`=0`) of a fixture page
      with a light-authored raster, a light SVG, a **white-on-transparent SVG** (the named non-goal,
      shown so the tradeoff is visible), and a Mermaid block — saved under
      `reviews/sprint-07-render-evidence-2026-06-18/`. Dark screenshot must show: light figures
      legible on the mat (fix), the transparent figure invisible (documented non-goal), Mermaid still
      dark-themed (no regression).
- [ ] **Docs note rides inside this ticket** (no separate docs-sweep): a one-line behavior note where
      warranted (e.g. README/CLAUDE viewer-rendering note that images render on a neutral mat;
      light-authored figures are the supported direction). Keep it minimal.
- [ ] Local validation: `python3 -m py_compile app.py` (sanity); `docker build`; the render-smoke +
      both-pane screenshots + no-image regression shot above.

## Notes / context

- Epic plan: `epics/theme-awareness-plan.md` — design fork (why `color-scheme` (b) is rejected, the
  measured 238→5 regression that makes the inverse a non-goal), Selector scope, Verification (the
  exact `preferredColorScheme` emulation commands and the 4 fixtures), Risks.
- Footguns: JS-rendered viewer — a 200 is not a render (both-pane screenshots are the proof, the bug
  is theme-specific); `render-smoke.sh` is a flat matcher (footgun 11) — use `'img' '#article'
  '.mermaid'`, never `'#article img'`; live instance is :8139 — throwaway container on :8138, never
  `docker compose`; no new served file (footgun 9) — `viewer.html` is already in the `Dockerfile COPY`.
- Mat hex / `#fff`-halo are implementer eyeball calls against the screenshots; the plan fixes the
  mechanism, not the exact literal.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Per-image luminance heuristic / "this figure is dark-authored" detection — the backlog fix for the
  accepted non-goal (white-on-transparent figures on a light mat). Separate effort, not this ticket.
