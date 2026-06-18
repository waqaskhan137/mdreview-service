---
id: MR-028
title: Vendor marked-footnote + render GFM footnotes in the viewer (refs + ordered back-ref section)
status: ready
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

- [ ] **Vendored.** `static/marked-footnote.umd.js` (pinned `marked-footnote@1.4.0`, ~3.3 KB UMD)
      committed; a `<script src="/static/marked-footnote.umd.js">` added **after** `marked.min.js` in
      the viewer head/script region (`viewer.html:~144-146`).
- [ ] **Registered (default-safe).** `setupKatex()` is renamed/extended to `setupMarked()` (still
      called once in `boot()` before any `marked.parse`, still `_katexReady`-guarded). After the
      existing math `marked.use({…})`, register footnotes — the global **is the factory**:
      `const mf = window.markedFootnote; if (typeof mf === 'function') marked.use(mf());`. The guard
      wraps the actual call so a missing asset degrades to today's behavior, never throws (footgun 8).
- [ ] **`.sr-only` clip rule (load-bearing — would otherwise render a banner).** `marked-footnote`
      emits `<h2 id="footnote-label" class="sr-only">Footnotes</h2>`; the viewer has **no `.sr-only`
      rule today** (grep-confirmed), so without one it renders as a full-size accent "FOOTNOTES"
      banner. Add the standard clip rule to the viewer `<style>`:
      `position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;padding:0;margin:-1px;`.
- [ ] **`.footnotes` styling** to match the article (`.footnotes`/`[data-footnotes]`: small
      superscript refs, muted `<hr>` + ordered list using the existing `--rule`/`--muted` tokens).
- [ ] **Section is numbered/commentable** (A4): the footnotes `<section>` is appended before
      `numberBlocks()` runs, so it becomes a `.blk` like any block; confirm it doesn't break
      `numberBlocks` heading logic (it's a `<section>`, not an `H1-3`).
- [ ] **No regression** (verified): math (`.katex`) renders next to footnotes; currency `$5 and $10`
      stays literal; a caret inside math `$a[^2]$` is consumed by math; GFM tables + mermaid still
      render; `marked.parse` still returns a **string** (synchronous — the viewer calls it sync).
- [ ] **History modal:** because registration is global on `marked`, `.histdoc` drafts get footnotes
      for free (id-duplication across the open modal + article is accepted cosmetic, not fixed here).
- [ ] **GATING render evidence (rebuilt throwaway container :8138):**
      `scripts/render-smoke.sh "$BASE/review/$ID" 'sup' '.footnotes' '#article'` → all ok (≥1);
      MIME via GET header-dump `curl -sD - -o /dev/null .../static/marked-footnote.umd.js` →
      `text/javascript`; a screenshot showing superscript refs + the bottom footnotes section with a
      back-ref `↩` and **no visible "Footnotes" banner**. Default-safe: a no-footnote doc shows no
      `.footnotes`.
- [ ] Local validation: `python3 -m py_compile app.py` (sanity); `docker build`; the above.

## Notes / context

- Epic plan: `epics/render-fidelity-plan.md` — UI step 3 (exact `window.markedFootnote` global +
  snippet), M1 (why vendor not hand-roll: the hand-roll silently dropped a 2nd consecutive
  definition), M2 (footnote↔math coexistence), step 4 (`.sr-only`).
- Footguns: stdlib-only/no-CDN (vendor the file); a 200 is not a render (render-smoke + screenshot);
  footgun 11 — flat selectors `'sup' '.footnotes' '#article'`, never `'#article sup'`; footgun 10 —
  GET header-dump for MIME, not `curl -sI`; live instance :8139 — throwaway on :8138, never compose.
- No `app.py` / `Dockerfile` change (the `/static/` route + `COPY static/` already cover it).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Optional: exclude `section.footnotes` from `numberBlocks` if a non-commentable footnotes section is
  preferred (one-line; A4 default is commentable).
- Optional: per-render footnote id-prefixing for the history modal (cosmetic id-dup) — not this epic.
