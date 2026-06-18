---
id: MR-029
title: Vendor highlight.js (common) + marked-highlight + dual-scheme theme; highlight fenced code at parse time (skip mermaid)
status: ready
layer: ui
priority: P2
sprint: sprint-08
epic: render-fidelity
depends_on: [MR-028]
branch: dev
created: 2026-06-18
updated: 2026-06-18
---

## Goal

Fenced code blocks (```` ```python ````) render with syntax-highlight token colors that read on
**both** the light and dark panes, instead of flat monospace — matching the published post. Phase 2
of render-fidelity. Depends on MR-028 only to avoid a trivial `setupMarked()`/head merge conflict
(technically independent).

## Acceptance criteria

- [ ] **Vendored (4 files into `static/`, committed, pinned):** `highlight.min.js` (highlight.js
      v11.x **common** build, ~127 KB, ~34 langs), `marked-highlight.umd.js`
      (`marked-highlight@2.1.4`, ~3.1 KB UMD), and a hand-curated dual-scheme `hljs-github.css`
      (~2.5 KB). Tags added: `<link rel="stylesheet" href="/static/hljs-github.css">` and
      `<script>`s for `highlight.min.js` (before its callback use) and `marked-highlight.umd.js`
      (after `marked.min.js`).
- [ ] **Registered at parse time (default-safe, the exact global shape):** in `setupMarked()`, after
      math + footnotes — `window.markedHighlight` is a **namespace object**, the factory is
      `window.markedHighlight.markedHighlight` (**bare `markedHighlight(...)` throws**). Use verbatim:
      ```js
      const mh = window.markedHighlight && window.markedHighlight.markedHighlight;
      if (mh && window.hljs) marked.use(mh({
        langPrefix: 'hljs language-',
        highlight(code, lang){
          if (lang === 'mermaid') return code;                       // leave raw for renderMermaid()
          if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, {language: lang}).value;
          return hljs.highlightAuto(code).value;
        }
      }));
      ```
      The guard tests the resolved factory **and** `window.hljs`, so a missing asset silently skips
      registration (footgun 8). Sync `highlight` callback (no `async:true`) → `marked.parse` stays a
      string (the viewer calls it synchronously).
- [ ] **Mermaid not regressed:** the callback returns raw `code` for `lang==='mermaid'`, so
      `code.language-mermaid` is still matched by `renderMermaid()` and rendered as a **diagram**, not
      highlighted code. (The common build has no mermaid grammar anyway.)
- [ ] **Dual-scheme theme:** `hljs-github.css` = github-light token rules at top level + github-dark
      rules under `@media (prefers-color-scheme: dark)`, with each theme's `.hljs{background;color}`
      base rule **stripped** so the viewer's existing pane-adaptive `#article pre` background shows
      through (no white box on the dark pane). `.css` served `text/css` by the existing route.
- [ ] **Peer-dep deviation recorded:** `marked-highlight@2.1.4` declares `peerDependencies: marked
      ">=4 <15"`; the vendored marked is **v18.0.4** — out of range but **verified working** in the
      browser-global path (G1 reproduction). Note it in the Work log with a **re-probe trigger**: if
      `static/marked.min.js` is ever bumped, re-run the browser-global coexistence probe.
      (`marked-footnote@1.4.0` peer `>=7.0.0` is in range.)
- [ ] **GATING render evidence (rebuilt throwaway :8138):**
      `scripts/render-smoke.sh "$BASE/review/$ID" 'pre' '.hljs' '.hljs-keyword' '#article'` → all ok;
      `scripts/render-smoke.sh "$BASE/review/$ID" '.katex' '.mermaid' 'table'` → all ok (no
      regression); MIME via GET header-dump → `highlight.min.js`=`text/javascript`,
      `hljs-github.css`=`text/css`; `curl -s .../static/highlight.min.js | wc -c` → `> 100000`
      (non-empty floor, not an exact count); **both light AND dark screenshots** (the theme is
      theme-sensitive) showing token-colored code legible on each pane, mermaid still a diagram.
      Default-safe: a no-code doc shows no `.hljs`.
- [ ] Local validation: `python3 -m py_compile app.py` (sanity); `docker build`; the above.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — UI step 3 (the exact `window.markedHighlight.markedHighlight`
  snippet + mermaid skip), M3 (engine/integration/mermaid), M4 (dual-scheme theme, screenshotted),
  Risks (peer-dep deviation + re-probe trigger).
- Footguns: stdlib-only/no-CDN; a 200 is not a render (render-smoke + both-pane screenshot); footgun
  11 — flat selectors `'pre' '.hljs' '.hljs-keyword'`, never `'#article pre code'` (exit 2); footgun
  10 — GET header-dump for MIME; live instance :8139 — throwaway :8138, never compose; footgun 9 — no
  Dockerfile change (`COPY static/` covers it).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- A different dual theme is a drop-in `hljs-github.css` swap if github isn't preferred.
