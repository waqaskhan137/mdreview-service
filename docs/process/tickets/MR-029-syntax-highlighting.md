---
id: MR-029
title: Vendor highlight.js (common) + marked-highlight + dual-scheme theme; highlight fenced code at parse time (skip mermaid)
status: done
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

- [x] **Vendored (4 files into `static/`, committed, pinned):** `highlight.min.js` (highlight.js
      v11.x **common** build, ~127 KB, ~34 langs), `marked-highlight.umd.js`
      (`marked-highlight@2.1.4`, ~3.1 KB UMD), and a hand-curated dual-scheme `hljs-github.css`
      (~2.5 KB). Tags added: `<link rel="stylesheet" href="/static/hljs-github.css">` and
      `<script>`s for `highlight.min.js` (before its callback use) and `marked-highlight.umd.js`
      (after `marked.min.js`).
- [x] **Registered at parse time (default-safe, the exact global shape):** in `setupMarked()`, after
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
- [x] **Mermaid not regressed:** the callback returns raw `code` for `lang==='mermaid'`, so
      `code.language-mermaid` is still matched by `renderMermaid()` and rendered as a **diagram**, not
      highlighted code. (The common build has no mermaid grammar anyway.)
- [x] **Dual-scheme theme:** `hljs-github.css` = github-light token rules at top level + github-dark
      rules under `@media (prefers-color-scheme: dark)`, with each theme's `.hljs{background;color}`
      base rule **stripped** so the viewer's existing pane-adaptive `#article pre` background shows
      through (no white box on the dark pane). `.css` served `text/css` by the existing route.
- [x] **Peer-dep deviation recorded:** `marked-highlight@2.1.4` declares `peerDependencies: marked
      ">=4 <15"`; the vendored marked is **v18.0.4** — out of range but **verified working** in the
      browser-global path (G1 reproduction). Note it in the Work log with a **re-probe trigger**: if
      `static/marked.min.js` is ever bumped, re-run the browser-global coexistence probe.
      (`marked-footnote@1.4.0` peer `>=7.0.0` is in range.)
- [x] **GATING render evidence (rebuilt throwaway :8138):**
      `scripts/render-smoke.sh "$BASE/review/$ID" 'pre' '.hljs' '.hljs-keyword' '#article'` → all ok;
      `scripts/render-smoke.sh "$BASE/review/$ID" '.katex' '.mermaid' 'table'` → all ok (no
      regression); MIME via GET header-dump → `highlight.min.js`=`text/javascript`,
      `hljs-github.css`=`text/css`; `curl -s .../static/highlight.min.js | wc -c` → `> 100000`
      (non-empty floor, not an exact count); **both light AND dark screenshots** (the theme is
      theme-sensitive) showing token-colored code legible on each pane, mermaid still a diagram.
      Default-safe: a no-code doc shows no `.hljs`.
- [x] Local validation: `python3 -m py_compile app.py` (sanity); `docker build`; the above.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — UI step 3 (the exact `window.markedHighlight.markedHighlight`
  snippet + mermaid skip), M3 (engine/integration/mermaid), M4 (dual-scheme theme, screenshotted),
  Risks (peer-dep deviation + re-probe trigger).
- Footguns: stdlib-only/no-CDN; a 200 is not a render (render-smoke + both-pane screenshot); footgun
  11 — flat selectors `'pre' '.hljs' '.hljs-keyword'`, never `'#article pre code'` (exit 2); footgun
  10 — GET header-dump for MIME; live instance :8139 — throwaway :8138, never compose; footgun 9 — no
  Dockerfile change (`COPY static/` covers it).

## Work log

- `2026-06-18` — Vendored into `static/`: `highlight.min.js` (highlight.js **v11.11.1 common** build
  from `@highlightjs/cdn-assets`, 127496 B, ~34 langs, no mermaid grammar), `marked-highlight.umd.js`
  (`marked-highlight@2.1.4` `lib/index.umd.js`, 3131 B), and a curated `hljs-github.css` (2837 B).
  Verified the browser-global path in headless Chrome against the real `static/marked.min.js`:
  `window.markedHighlight` is a namespace object, `.markedHighlight` is the factory, `window.hljs`
  is the engine; `marked.use(mh({…}))` composes, `marked.parse` returns a **string** (sync), emits
  `.hljs`/`.hljs-keyword`.
- `2026-06-18` — **Curated theme:** stripped **all** `.hljs{…}` base rules (background/color/layout)
  from upstream `github.min.css` + `github-dark.min.css` so the viewer's pane-adaptive `#article pre`
  background/text show through (no box on either pane); github-light at top level, github-dark wrapped
  in `@media (prefers-color-scheme: dark)`. Only `.hljs-*` token colors remain.
- `2026-06-18` — **viewer.html:** added the `<link>` (after katex.css) + two `<script>`s (after
  marked-footnote); registered highlight in `setupMarked()` after footnotes with the exact global
  `window.markedHighlight.markedHighlight`, a **sync** callback, `lang==='mermaid' → return code`
  (so `renderMermaid()` still makes the diagram), and a guard wrapping the call (default-safe).
- **Peer-dep deviation (recorded):** `marked-highlight@2.1.4` declares `peerDependencies: marked
  ">=4 <15"`; vendored marked is **v18.0.4** — out of range but **verified working** in the browser
  path. **Re-probe trigger:** if `static/marked.min.js` is bumped, re-run the browser-global
  coexistence probe. (`marked-footnote@1.4.0` peer `>=7.0.0` is in range.)
- Files: `viewer.html`, `static/highlight.min.js`, `static/marked-highlight.umd.js`,
  `static/hljs-github.css`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py` OK; `docker build` OK; rebuilt throwaway on :8138.
- `2026-06-18` — MIME (GET header-dump): `highlight.min.js`/`marked-highlight.umd.js` →
  `text/javascript`, `hljs-github.css` → `text/css`; `highlight.min.js` body 127496 B (`> 100000`).
- `2026-06-18` — `render-smoke.sh '<id>' 'pre' '.hljs' '.hljs-keyword' '#article'` → all ok
  (.hljs-keyword 2); `render-smoke.sh '<id>' '.katex' '.mermaid' 'table' 'sup'` → all ok (no
  regression). DOM truth: mermaid renders as a `.mermaid` diagram with **no hljs tokens inside it**
  (skip works); footnote/math present.
- `2026-06-18` — **Both-pane screenshots** (`--blink-settings=preferredColorScheme=1/0`) under
  `reviews/sprint-08-render-evidence-2026-06-18/`: dark (`review-dark.png`) — python tokens legible
  on the dark `pre` background, **no white box**; light (`review-light.png`) — github-light tokens on
  the light pre; mermaid themed per pane; footnotes section + back-ref, no banner.
- **Default-safe:** a no-code doc emits no `.hljs` (highlight only touches fenced code); `marked.parse`
  stays synchronous with all three extensions (math + footnote + highlight) registered.

## Follow-ups

- A different dual theme is a drop-in `hljs-github.css` swap if github isn't preferred.
