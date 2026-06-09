---
id: MR-019
title: Author buildless landing page (site/index.html) with dashboard tokens, static demo screenshot, and CNAME
status: ready
layer: ui
priority: P1
sprint: sprint-05
epic: landing-page
depends_on: []
branch:
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Give mdreview-service its public face: one hand-written, zero-build static page (`site/index.html`)
that sells the tool — tagline, a visual demo of the review loop, the curl flow at a glance, how to
run it, an MCP mention, and a prominent repo link — ready to be published to GitHub Pages (MR-020).
The page documents nothing the README already documents; it links there.

## Acceptance criteria

- [ ] `site/index.html` is a single hand-written HTML file with inline `<style>`; **no framework,
      bundler, generator, preprocessor, or dependency manifest of any kind**; vanilla JS only if
      genuinely needed.
- [ ] All six sections present, each with a stable landmark hook: `.hero` (name, tagline,
      what-it-is, CTAs), `.demo` with `<img class="demo-img">`, `.curl-flow` (`<pre>` teaser of
      POST -> hand off -> poll -> PUT), `.run-it` (`docker compose up -d --build`), `.mcp` (one
      paragraph + README link), `.repo-link` footer (repo URL, canonical URL).
- [ ] Design tokens reused from the dashboard: the **full** `:root` set from `dashboard.html:8`
      (including `--noteline:#d4a017`), the dark-mode block (`dashboard.html:9`), the system font
      stack (`dashboard.html:11`) and the `ui-monospace,SFMono-Regular,Menlo,monospace` stack —
      copied into the page's own inline `<style>`.
- [ ] Responsive as behavior, not pixels: single fluid column with `max-width` (dashboard uses
      `920px`), demo image `max-width:100%`, `<pre>` blocks scroll horizontally; no hard-coded
      pixel breakpoint for the core layout.
- [ ] `site/demo.png` exists — a screenshot of the local viewer **mid-review** (a human note
      visible AND an addressed/struck-through note), captured via procedure (a) manual browser
      capture (default) or (b) direct `chrome --headless=new --screenshot=...` (NOT via
      render-smoke, which cannot screenshot); `img.demo-img` references it with a descriptive
      `alt`. Record which procedure was used in the Work log.
- [ ] `site/CNAME` contains exactly `mdreview.waqasrana.space`.
- [ ] **No-drift check:** no README API table, config table, or MCP tool-list text copied inline —
      every changeable fact is an `href` into the README.
- [ ] **G4 validation target (ticket-level fact: this page is never in any container image, so the
      absent container rebuild is compliant):** `python3 -m http.server 8200 --directory site`
      serves the page and
      `scripts/render-smoke.sh http://localhost:8200/ .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link`
      exits 0.
- [ ] A screenshot of the rendered page is committed under
      `reviews/sprint-05-render-evidence/` as G4 evidence (manual capture — render-smoke does not
      produce images).
- [ ] Local validation passes: `python3 -m py_compile app.py` (trivially — `app.py` untouched).

## Notes / context

- Epic: `docs/process/epics/landing-page-plan.md` (Recommended approach -> UI; Decision 2;
  Verification -> Page render-smoke). Brief: `docs/process/requirements/landing-page.md`.
- Tokens: `dashboard.html:8` (light `:root`), `:9` (dark), `:11` (font stack), `:12`
  (`max-width:920px`).
- `scripts/render-smoke.sh` drives Chrome `--dump-dom` and asserts DOM nodes (matcher supports
  `tag`, `.class`, `tag.class`, `#id`); it never writes an image (`scripts/render-smoke.sh:32-41`
  is the Chrome-binary discovery the optional direct-screenshot command reuses).
- The Dockerfile is deliberately untouched: the page lives outside the image (the sprint-01
  "served file needs a Dockerfile COPY" footgun does not apply).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- MR-021 (backlog): swap `site/demo.png` for an animated GIF of the live loop, same slot.
