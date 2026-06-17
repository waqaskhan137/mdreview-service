---
slug: rich-rendering
captured: 2026-06-18
source: this session — feature feedback from an agent that drove mdreview through a real review (a long, image- and math-heavy research post via the MCP), pasted by user (waqas) 2026-06-18
related_epic: epics/rich-rendering-plan.md
scope: epic scoped by the user this session to the two P0s (render math; serve local/relative images). The P1/P2 items below are captured as the record of what was asked but are deferred to backlog — see Amendments.
---

# mdreview: rich-rendering feedback from a real review

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> mdreview: feature requests (from an agent driving it through a real review)
>
> I reviewed a long, image- and math-heavy research post via the MCP. These are the gaps that
> broke a clean review loop, prioritised.
>
> **P0 — Render math**
>
> - Problem: LaTeX isn't rendered. `$$...$$` and `$...$` show as raw text, so equations (this
>   post has calibration and proper-scoring-rule formulas) can't be reviewed visually.
> - Want: client-side rendering via KaTeX (lighter/faster) or MathJax 3.
> - Delimiters: match Jekyll/MathJax so the review matches the published site, inline `$...$` and
>   `\(...\)`, display `$$...$$` and `\[...\]`. Don't trip on a lone `$` in prose.
>
> **P0 — Serve local/relative images (the biggest friction)**
>
> - Problem: mdreview renders `<img>` but can't fetch images referenced by site paths
>   (`/assets/...`) or paths relative to the source file, it 404s, because it serves only the
>   document, not the asset directory. I had to run a separate static server and rewrite every
>   image src to `http://127.0.0.1:PORT/...`, which then diverges from the real draft.
> - Want, best first:
>   - a. An attach-asset MCP method, e.g. `attach_asset(review_id, bytes|path, name)` or
>     `register_asset_dir(review_id, dir)`, that mdreview serves at a stable URL. This also fixes
>     the "huge base64 is impractical to author through update_source" problem.
>   - b. Resolve images relative to `source_path` (you already store it), so
>     `<img src="relative.svg">` works.
>   - c. A configurable site-root mapping so `/assets/...` resolves to a local dir.
> - Confirmed working: inline data-URI images render
>   (`<img src="data:image/svg+xml;base64,...">`). Good as a fallback, but only for tiny assets,
>   since update_source resends the whole document, a 100KB+ blob is unworkable. The attach-asset
>   method is the real fix.
>
> **P1 — SVG / animation (what already works, so just don't break it)**
>
> - Animated SVGs work once reachable: CSS `@keyframes` and SMIL inside an `<img>`-loaded SVG
>   animate (D2 flow arrows rendered fine).
> - SVG filters work: `feTurbulence` / `feDisplacementMap` (the hand-drawn bicycle) render
>   in-browser.
> - So no special animation handling is needed, the only blocker is image reachability (P0 above).
>   Worth one doc line saying so.
>
> **P1 — Theme awareness**
>
> - Problem: an image that assumes a light background looks wrong on a dark review pane (exactly
>   the bug we just hit on the site).
> - Want: either render the doc/images on a consistent neutral card regardless of pane theme, or
>   set the host color-scheme so `@media (prefers-color-scheme)` inside `<img>` SVGs fires and
>   theme-aware diagrams adapt.
>
> **P2 — Nice-to-haves**
>
> - Mermaid fenced-block rendering (Jekyll posts use ```` ```mermaid ````; shows as code now).
> - Parse/hide YAML front matter (the `---` block currently shows as text).
> - Confirm GFM tables, footnotes, syntax highlighting.
>
> Bottom line: two changes remove ~all the friction: (1) render math, and (2) serve assets
> (attach-asset call or resolve relative to source_path).

## Out of scope for this epic (deferred to backlog)

These were captured because they were asked, but the user scoped this cycle (2026-06-18) to the
two P0s. They are follow-ups, not this epic's work:

- **P1 — Theme awareness.** Backlog.
- **P1 — SVG/animation doc line.** Backlog (one-line doc note; nothing to build).
- **P2 — Footnotes + syntax highlighting.** Backlog (footnotes need a marked extension; no
  highlighter is bundled today).

## Correction to the brief (verified against current source, 2026-06-18)

Two of the P2 items are **already implemented in the current source** and are NOT gaps in this
repo — the agent's report reflects a likely-stale deployed instance, not `dev`:

- **Mermaid fenced blocks already render.** `mermaid.min.js` is bundled in `static/` and
  `renderMermaid()` converts `code.language-mermaid` blocks (`viewer.html` `renderMermaid`).
- **YAML front matter is already extracted and stripped** before render (`viewer.html` `load`).

These are therefore explicitly out of scope (nothing to build); if the live instance still shows
them raw, that is a redeploy concern, not a feature.

## Amendments

- **2026-06-18 (waqas, this session):** Scoped the epic to the **two P0s only** — render math and
  serve local/relative images. P1 (theme awareness, SVG doc line) and P2 (footnotes, syntax
  highlighting) deferred to backlog. Mermaid and front-matter parsing confirmed already shipped in
  `dev` (see Correction above) and excluded from scope.
