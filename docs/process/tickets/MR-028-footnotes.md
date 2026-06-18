---
id: MR-028
title: Vendor marked-footnote + render GFM footnotes in the viewer (refs + ordered back-ref section)
status: done
layer: ui
priority: P2
sprint: sprint-08
epic: render-fidelity
depends_on: []
branch: dev
created: 2026-06-18
updated: 2026-06-18
---

## Goal

GFM footnotes (`[^id]` refs + `[^id]: …` definitions) render as superscript links to an ordered
footnotes section with back-references — the way a Jekyll-published post shows them — instead of raw
`[^id]` text. Reuses the established marked-extension pattern (`setupKatex`→`setupMarked`). Phase 1
of render-fidelity; ships on its own.

## Acceptance criteria

- [x] **Vendored.** `static/marked-footnote.umd.js` (pinned `marked-footnote@1.4.0`, ~3.3 KB UMD)
      committed; a `<script src="/static/marked-footnote.umd.js">` added **after** `marked.min.js` in
      the viewer head/script region (`viewer.html:~144-146`).
- [x] **Registered (default-safe).** `setupKatex()` is renamed/extended to `setupMarked()` (still
      called once in `boot()` before any `marked.parse`, still `_katexReady`-guarded). After the
      existing math `marked.use({…})`, register footnotes — the global **is the factory**:
      `const mf = window.markedFootnote; if (typeof mf === 'function') marked.use(mf());`. The guard
      wraps the actual call so a missing asset degrades to today's behavior, never throws (footgun 8).
- [x] **`.sr-only` clip rule (load-bearing — would otherwise render a banner).** `marked-footnote`
      emits `<h2 id="footnote-label" class="sr-only">Footnotes</h2>`; the viewer has **no `.sr-only`
      rule today** (grep-confirmed), so without one it renders as a full-size accent "FOOTNOTES"
      banner. Add the standard clip rule to the viewer `<style>`:
      `position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;padding:0;margin:-1px;`.
- [x] **`.footnotes` styling** to match the article (`.footnotes`/`[data-footnotes]`: small
      superscript refs, muted `<hr>` + ordered list using the existing `--rule`/`--muted` tokens).
- [x] **Section is numbered/commentable** (A4): the footnotes `<section>` is appended before
      `numberBlocks()` runs, so it becomes a `.blk` like any block; confirm it doesn't break
      `numberBlocks` heading logic (it's a `<section>`, not an `H1-3`).
- [x] **No regression** (verified): math (`.katex`) renders next to footnotes; currency `$5 and $10`
      stays literal; a caret inside math `$a[^2]$` is consumed by math; GFM tables + mermaid still
      render; `marked.parse` still returns a **string** (synchronous — the viewer calls it sync).
- [x] **History modal:** because registration is global on `marked`, `.histdoc` drafts get footnotes
      for free (id-duplication across the open modal + article is accepted cosmetic, not fixed here).
- [x] **GATING render evidence (rebuilt throwaway container :8138):**
      `scripts/render-smoke.sh "$BASE/review/$ID" 'sup' '.footnotes' '#article'` → all ok (≥1);
      MIME via GET header-dump `curl -sD - -o /dev/null .../static/marked-footnote.umd.js` →
      `text/javascript`; a screenshot showing superscript refs + the bottom footnotes section with a
      back-ref `↩` and **no visible "Footnotes" banner**. Default-safe: a no-footnote doc shows no
      `.footnotes`.
- [x] Local validation: `python3 -m py_compile app.py` (sanity); `docker build`; the above.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — UI step 3 (exact `window.markedFootnote` global +
  snippet), M1 (why vendor not hand-roll: the hand-roll silently dropped a 2nd consecutive
  definition), M2 (footnote↔math coexistence), step 4 (`.sr-only`).
- Footguns: stdlib-only/no-CDN (vendor the file); a 200 is not a render (render-smoke + screenshot);
  footgun 11 — flat selectors `'sup' '.footnotes' '#article'`, never `'#article sup'`; footgun 10 —
  GET header-dump for MIME, not `curl -sI`; live instance :8139 — throwaway on :8138, never compose.
- No `app.py` / `Dockerfile` change (the `/static/` route + `COPY static/` already cover it).

## Work log

- `2026-06-18` — Vendored `marked-footnote@1.4.0` `dist/index.umd.js` → `static/marked-footnote.umd.js`
  (2982 bytes; peerDep marked `>=7.0.0`, clean for vendored v18). Verified its browser-global shape
  before wiring: in headless Chrome against the real `static/marked.min.js`, `window.markedFootnote`
  is the factory, `marked.use(markedFootnote())` composes, `marked.parse` returns a string, emits
  `<sup>` + `<section data-footnotes class="footnotes">` + `<h2 class="sr-only">Footnotes</h2>`.
- `2026-06-18` — **viewer.html:** added the `<script>` after the katex include; renamed
  `setupKatex()`→`setupMarked()` (and the `boot()` call + `_katexReady`→`_markedReady`), guarded the
  math `marked.use` on `window.katex` and appended footnotes
  (`var mf=window.markedFootnote; if(typeof mf==='function') marked.use(mf());`) — each feature
  guards its own global (default-safe). Added `.footnotes` styling + a real `.sr-only` clip rule
  (the heading would otherwise render as a banner — SHOULD-3). The footnotes `<section>` is part of
  marked's output, so it's the last `#article` child before `numberBlocks()` → numbered like any
  block (A4).
- Files: `viewer.html`, `static/marked-footnote.umd.js`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py` OK; `docker build` OK; validated from a rebuilt
  throwaway container on :8138 (never compose/:8139).
- `2026-06-18` — MIME (GET header-dump): `/static/marked-footnote.umd.js` → `text/javascript`.
- `2026-06-18` — `render-smoke.sh '<id>' 'sup' '.footnotes' '#article'` → all ok (sup 3 / .footnotes
  1 / #article 1); `render-smoke.sh '<id>' '.katex' '.mermaid' 'table'` → all ok (no regression).
- `2026-06-18` — **DOM truth + screenshot** (fixture = footnote + reused ref + math + mermaid +
  table + currency): `<sup>` refs render; ordered footnotes section with back-ref `↩` **and `↩²`**
  for the reused ref; the `sr-only` heading is present but **hidden** (no "Footnotes" banner —
  screenshot-confirmed); `$E=mc^2$` renders; `$5 and $10` stays literal; mermaid is a diagram; table
  renders. **Default-safe:** a no-footnote doc emits no real footnotes section (`data-footnotes`
  absent — the only `class="footnotes"` string is in a CSS comment, since reworded).
- `2026-06-18` — `marked.parse` stays synchronous with the footnote extension registered (string
  return), as the viewer requires.

## Follow-ups

- Optional: exclude `section.footnotes` from `numberBlocks` if a non-commentable footnotes section is
  preferred (one-line; A4 default is commentable).
- Optional: per-render footnote id-prefixing for the history modal (cosmetic id-dup) — not this epic.
