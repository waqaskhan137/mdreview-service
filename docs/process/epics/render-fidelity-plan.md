---
epic: render-fidelity
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-18
source: requirements/render-fidelity.md
gate: passed 2026-06-18  # G1 (Plan Gate): passed (round 2, staff-critic PASS) — tickets unblocked
review: reviews/render-fidelity-plan-review-2026-06-18.md, reviews/render-fidelity-plan-review-2026-06-18-r2.md
related_sprints: []    # sprint-08 once the sprint opens
related_tickets: []    # empty until G1 passes and tickets are created
---

# Render fidelity — footnotes + syntax highlighting

This epic closes the last two P2 gaps between what a Jekyll/MathJax-published post shows and what
the mdreview viewer renders: **GFM footnotes** (`[^id]` refs → superscript links to an ordered
footnotes section with back-refs) and **syntax highlighting** of fenced code blocks. Both render as
raw/plain text today because marked core has neither and no highlighter is bundled. With the
marked-extension and stdlib-vendoring patterns already established (sprint-06, KaTeX/`setupKatex`),
this is a small, additive, viewer-only epic that vendors two tiny `marked` adapters plus one
highlighter into `static/` and registers them in the existing `setupKatex()`/`boot()` path.

**Source requirement:** [`requirements/render-fidelity.md`](../requirements/render-fidelity.md) — the
original brief, kept verbatim.

## Product goal

A reviewer opening a draft sees it **as it will publish**:

- A `[^id]` reference renders as a superscript link; its `[^id]: …` definition renders in an ordered
  footnotes section at the end of the article, with a back-reference link to the citation.
- A fenced code block (```` ```python ````) renders with token colors, not flat monospace, in a
  theme that reads on **both** the light and dark panes.

And nothing already shipped regresses: math (KaTeX), mermaid diagrams, the image mat, block
numbering, note reconciliation, and GFM tables. A document with **no** footnotes and **no** fenced
code renders byte-identical to today.

## Core design principle

**Register, don't rewrite.** Footnotes and highlighting both hook into the *one* place markdown
becomes HTML — `marked.parse(md)` at `viewer.html:270`, fed by extensions registered once in
`setupKatex()` (rename/extend to `setupMarked()`). Doing the work *inside* `marked.parse` (not as a
DOM post-pass) means it runs **before** `numberBlocks()` reparents `#article` children and **before**
`renderMermaid()` replaces `code.language-mermaid`, so there is zero ordering fight with the existing
render sequence. Vendoring is curated, like KaTeX: small, battle-tested adapters committed to
`static/`, served by the existing `/static/` route, copied by the existing `Dockerfile COPY static/`
— no `app.py` change, no `Dockerfile` change, no runtime fetch.

## Measurements that settled the design

Every render-observable fork below was probed against the real vendored `static/marked.min.js`
(marked **v18.0.4**) in `node v22`, with the live math extensions copied verbatim from `setupKatex()`
(`viewer.html:190-209`), and theme colors checked with headless-Chrome screenshots. Results:

### M1 — Footnotes: hand-roll vs vendor `marked-footnote`

| Probe (md input) | Hand-rolled extension | Vendored `marked-footnote@1.4.0` |
|---|---|---|
| Ordered section + back-refs | works for 1 def | works |
| **Two consecutive `[^a]:`/`[^b]:` defs** | **dropped `[^b]` with an over-greedy continuation regex** (silent) | both collected correctly |
| A reference reused twice (`[^a]` … `[^a]`) | not handled | multiple back-refs (`↩` `↩²`) — correct |
| Definition order vs reference order | fragile | numbered by reference order (GitHub semantics) |
| Accessibility (`aria-describedby`, `sr-only` label) | none | emitted for free |
| GitHub-compatible ids (`footnote-ref-a`/`footnote-a`) | by hand | by default |

**Decision: vendor `marked-footnote@1.4.0`** (UMD, **3.3 KB** minified). The hard part of footnotes —
document-wide definition collection, de-dup, reference-order numbering, multi-back-ref reuse — is
exactly where a hand-roll silently drops content (a one-character regex mistake dropped `[^b]` in the
probe). A 3.3 KB curated dependency is correct-by-default and matches the KaTeX-vendoring precedent.
Trade-off accepted: undefined refs (`[^z]` with no definition) render as **literal `[^z]` text** and
emit no footnotes section — acceptable (better than a dangling link), captured as a verification
fixture.

### M2 — Extension coexistence (footnote ↔ math, the brief's load-bearing risk)

Registered math first (as the viewer does), then `marked.use(markedFootnote())`, then highlight:

| md input | Result | Correct? |
|---|---|---|
| `Energy $E=mc^2$ is famous[^e].` | math token + footnote sup, side by side | yes |
| `See[^x].` then `\[ a^2+b^2=c^2 \]` | inline footnote + display math | yes |
| `Costs $5 and $10[^p].` (currency) | `$5`/`$10` stay literal; only `[^p]` is a footnote | yes |
| `value $a[^2]$ end[^r].` (caret inside math) | **math wins** `$a[^2]$`; `[^r]` is the only footnote | yes |
| `| a | b |` GFM table | renders unchanged | yes |
| ```` ```python … arr[^1] ```` | fenced code untouched (no footnote/math) | yes |

The inline tokenizers do **not** eat each other's delimiters: marked tokenizes left-to-right and
`$…$`'s `start` fires before `[^…]` inside a math span, so a caret inside math is consumed by math.
`marked.parse(md)` **returns a string, not a Promise**, with all three extensions registered — the
viewer calls it synchronously at `viewer.html:270`, so this must hold, and it does.

### M3 — Highlighter engine, integration point, and mermaid exclusion

| Option | Finding |
|---|---|
| **Engine** highlight.js "common" build | ~34 grammars incl. python, js, ts, bash, json, yaml, go, rust, c/cpp, java, sql, ruby, php, swift, kotlin, css/scss, xml, markdown, diff. **`mermaid` is not a language** in it. **~127 KB** min on disk (`@highlightjs/cdn-assets@11.11.1/highlight.min.js`, confirmed by the G1 reproduction). |
| highlight.js "all" / Prism | "all" is ~1 MB (rejected, bloat); Prism is lighter but needs per-language registration and a different token-class scheme. Common build covers every language a dev/Jekyll post uses. |
| **Integration** `marked-highlight@2.1.4` (UMD, **3.1 KB**) at parse time | highlights `code` tokens during `marked.parse`, emitting `<code class="hljs language-X">` with `.hljs-*` token spans — **before** `numberBlocks`/`renderMermaid`. Cleaner than a DOM post-pass (which would run after reparenting and need a careful exclude selector). |
| **Mermaid exclusion** | the highlight callback returns `code` unchanged when `lang === 'mermaid'`, leaving the `<code class="hljs language-mermaid">` raw. `renderMermaid()` selects `#article code.language-mermaid` (`viewer.html:165`) — still matches (the extra `hljs` class is harmless; the whole `<pre>` is replaced by the diagram div anyway). **No double-processing.** |

Combined probe (math + footnote + highlight registered together): python block →
`.hljs-keyword`/`.hljs-number` spans; mermaid block → stays raw `language-mermaid`; footnote section
emitted; `parse` returns a string. All correct.

### M4 — Theme on both panes (the brief's theme-sensitivity risk)

The viewer is light **or** dark by `prefers-color-scheme` (`:root` tokens, `viewer.html:9-10`); a
single hljs theme looks wrong on one pane. Probe: built the github (light) + github-dark token CSS,
**stripped each theme's `.hljs{background;color}` base rule** so the existing
`#article pre{background:rgba(127,127,127,.1)}` (`viewer.html:26`, already pane-adaptive) shows
through, put light at top level and dark inside `@media (prefers-color-scheme: dark)`, and
screenshotted a python sample on the real pre background in both schemes.

| Scheme | Result |
|---|---|
| Light pane | github-light colors (red keywords, purple titles, dark-blue literals, grey comments) read clearly on the light pre mat |
| Dark pane | github-dark colors read clearly on the dark pre mat; no white box, no smear |

**Decision: ship one hand-curated `hljs-github.css`** = github light rules (top level) + github-dark
rules wrapped in `@media (prefers-color-scheme: dark)`, with the `.hljs` `background`/base `color`
stripped so the pane's existing pre background is preserved. Two upstream theme files (github,
github-dark), ~1.3 KB each, concatenated and trimmed into one **~2.5 KB** vendored file.

### Bundle size summary (all vendored into `static/`, committed, no runtime fetch)

| File | Size (min) |
|---|---|
| `marked-footnote.umd.js` | 3.3 KB |
| `marked-highlight.umd.js` | 3.1 KB |
| `highlight.min.js` (common build) | ~127 KB |
| `hljs-github.css` (curated dual-scheme) | ~2.5 KB |
| **Total added** | **~136 KB** |

For scale: `mermaid.min.js` is already 3.3 MB and `katex.min.js` 265 KB vendored. ~136 KB is lean
and well within the brief's budget.

## Recommended approach

### Service (`app.py`)

**No change.** The `/static/{file}` route (`app.py:461`, regex `/static/([A-Za-z0-9._-]+)`) already
serves any new `.js`/`.css` file, and `_ctype_for` (`app.py:74-93`) already maps `.js →
text/javascript` and `.css → text/css`. The `Dockerfile`'s `COPY static/ ./static/` (`Dockerfile:9`)
already copies every `static/` file — **footgun 9 is satisfied without a Dockerfile edit** (unlike a
new *root-level* served file, which would need one). This epic touches **zero** service/infra code.

### UI (`viewer.html` + `static/`)

1. **Vendor four files into `static/`** (download the exact pinned versions, commit them):
   `marked-footnote.umd.js`, `marked-highlight.umd.js`, `highlight.min.js` (highlight.js v11.x
   *common* build), and a hand-curated `hljs-github.css` (per M4).
2. **Add four tags to the viewer `<head>`/script region**, alongside the existing
   marked/mermaid/katex includes (`viewer.html:144-146`) and the katex `<link>` (`viewer.html:7`):
   `<link rel="stylesheet" href="/static/hljs-github.css">` and three `<script src="/static/…">`
   for `highlight.min.js`, `marked-footnote.umd.js`, `marked-highlight.umd.js`. **Load order:**
   the adapters must load after `marked.min.js` (they extend it) and `highlight.min.js` must load
   before it is referenced in the highlight callback.
3. **Extend `setupKatex()` → `setupMarked()`** (the once-only, idempotent registrar called in
   `boot()` at `viewer.html:238`, before any `marked.parse`). Keep the existing math `marked.use({…})`
   first, then append the two registrations below. **The exact browser-global shapes (pinned by the
   G1 critic's headless-Chrome reproduction)** are:
   - `window.markedFootnote` — **the factory itself** (`typeof === 'function'`); call it.
   - `window.markedHighlight` — a UMD **namespace object** (`typeof === 'object'`); the factory is the
     property `window.markedHighlight.markedHighlight`. **Bare `markedHighlight(...)` throws
     `TypeError: markedHighlight is not a function`** — that is the trap this snippet exists to avoid.
   - `window.hljs` — the highlight.js engine object (`typeof === 'object'`).

   Use these snippets verbatim (the `window.*` guard must wrap the **actual call**, so a missing or
   odd-shaped global degrades silently to today's behavior instead of passing the guard then throwing
   — default-safe, footgun 8):
   ```js
   // footnotes: global IS the factory
   const mf = window.markedFootnote;
   if (typeof mf === 'function') marked.use(mf());

   // highlight: global is a NAMESPACE OBJECT; factory is .markedHighlight
   const mh = window.markedHighlight && window.markedHighlight.markedHighlight;
   if (mh && window.hljs) marked.use(mh({
     langPrefix: 'hljs language-',
     highlight(code, lang){
       if (lang === 'mermaid') return code;                       // leave mermaid raw for renderMermaid()
       if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, {language: lang}).value;
       return hljs.highlightAuto(code).value;                     // unlabelled/unknown → best-effort
     }
   }));
   ```
   Note the highlight guard tests `mh` (the resolved factory) **and** `window.hljs` before the call, so
   either a missing `marked-highlight` asset (no `window.markedHighlight`) or a missing
   `highlight.min.js` (no `window.hljs`) silently skips registration rather than throwing. Keep the
   `_katexReady`-style once-only flag so re-entry is a no-op.
4. **Footnotes CSS** in the viewer `<style>`: style `.footnotes`/`[data-footnotes]` (a top rule,
   small superscript refs, a muted `<hr>` + ordered list using existing `--rule`/`--muted` tokens)
   so the section matches the article. **Plus a real `.sr-only` clip rule** — `marked-footnote` leads
   the section with `<h2 id="footnote-label" class="sr-only">Footnotes</h2>` (verbatim from the G1
   reproduction), but `viewer.html` has **zero `.sr-only` rules today** (grep-confirmed). Without one,
   that `<h2>` renders as a full-size, accent-colored "FOOTNOTES" banner via the existing
   `#article h2` rule (`viewer.html:20`, uppercase + accent). Add the standard visually-hidden clip
   rule to the viewer `<style>` so the screen-reader label stays in the DOM (a11y) but is hidden
   visually:
   ```css
   .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;padding:0;margin:-1px;}
   ```
   (Chosen over re-styling `.footnotes h2` to a small visible label: the upstream markup intends a
   visually-hidden heading, and `.sr-only` is the conventional, reusable rule.) The footnote section is
   appended as the **last child** of `#article` *before* `numberBlocks()` runs, so it becomes its own
   `.blk` and is numbered/commentable like any block — acceptable and consistent (the nested `<h2>` is
   inside the `<section>`, never iterated by `numberBlocks`, so `heading` tracking is undisturbed — A4
   holds, confirmed by the G1 review).
5. **History modal (`.histdoc`)** also renders draft markdown via `marked.parse`
   (`viewer.html:489`). Because footnotes/highlighting register **globally** on `marked` in
   `setupMarked()`, the history modal gets both **for free** — no extra wiring. This is the *consistent*
   choice (the brief flagged the math/image work treated `.histdoc` inconsistently). One caveat:
   `marked-footnote`'s ids are document-global (`footnote-a`), so a history draft rendered while the
   main article is also in the DOM could duplicate an id; since the history modal is a transient
   overlay and its links are same-page anchors, this is cosmetic. **In scope, called out, accepted as
   cosmetic** — do not add per-render id-prefixing this epic.

## Rollout phases

Two independently shippable UI slices. Footnotes first (pure viewer + one tiny vendored file, lowest
risk); highlighting second (one larger vendored file + theme CSS). Either could ship alone.

### Phase 1 — GFM footnotes
Vendor `marked-footnote.umd.js`; add the `<script>` tag; register it in `setupMarked()`; add
`.footnotes` styling. Ships footnote refs + ordered back-ref section in the viewer and history modal.

### Phase 2 — Syntax highlighting
Vendor `highlight.min.js` (common) + `marked-highlight.umd.js` + curated `hljs-github.css`; add the
tags; register the highlight hook with the mermaid skip in `setupMarked()`. Ships token-colored
fenced code on both panes, mermaid untouched.

(Optional Phase 3 — a docs line in `README.md`/`AGENTS.md` noting footnotes + highlighting are now
rendered. Small; fold into the Phase-2 ticket's docs requirement or a same-sprint docs-sweep ticket
per the Definition of Done.)

## Non-goals

- **Any service / API / MCP change.** Viewer + `static/` only (per the brief).
- **A user-facing theme or language picker.** One curated dual-scheme theme; auto-detect for
  unlabelled code.
- **The "all languages" highlight.js build.** Common build only; an exotic language degrades to
  `highlightAuto` (best-effort) or plain, never a 1 MB payload.
- **GFM tables work** — already shipped (marked default); this epic only must-not-regress them.
- **Mermaid + YAML front-matter** — already shipped, out of scope.
- **Per-render footnote id-prefixing** for the history modal (cosmetic id-duplication accepted).
- The animated-GIF landing demo (MR-021), the cut local-dir asset read, and the infra backlog items
  (per the brief's Out of scope).

## Key constraints

- **Stdlib-only, no pip, no CDN, no runtime fetch.** All four assets are downloaded at pinned
  versions and committed into `static/`, exactly like KaTeX/marked/mermaid. No `<script src>` to a CDN.
- **A 200 is not a render** (footgun 6). G4/G7 verification renders the page from the **rebuilt
  container** with `scripts/render-smoke.sh` asserting real DOM nodes — a footnote node **and** a
  highlighted-token node — plus a both-pane screenshot. See Verification.
- **`render-smoke.sh` is a flat matcher** (footgun 11): assert each node with a standalone selector
  (`'sup'`, `'.footnotes'`, `'.hljs'`, `'.hljs-keyword'`, `'pre'`, `'#article'`) — **never** a
  descendant selector like `'#article pre code'` (rejected as bad usage, exit 2).
- **MIME checks use a GET header-dump** (footgun 10): `curl -sD - -o /dev/null .../static/highlight.min.js`
  to confirm `text/javascript` and `.../static/hljs-github.css` → `text/css`. **Never `curl -sI`**
  (HEAD → 501, the wrong page).
- **Additive / default-safe** (footgun 8): a doc with no footnotes and no fenced code renders
  byte-identical to today; every adapter registration is `window.*`-guarded so a missing asset
  degrades silently to current behavior.
- **No regression**: math extension (register math first, footnote/highlight after — M2),
  mermaid (`lang==='mermaid'` returns raw; `code.language-mermaid` still matched by `renderMermaid` —
  M3), the image mat, `numberBlocks`, note reconciliation, GFM tables.
- **`marked.parse` must stay synchronous** — registered with `markedHighlight`'s **sync** highlight
  callback (not `async:true`); the viewer calls `marked.parse(md)` synchronously at `viewer.html:270`.
  Confirmed string return in M2/M3.
- **No `app.py` / `Dockerfile` change.** The `/static/` route and `COPY static/` already cover new
  `static/` files (footgun 9 satisfied; this is *not* a new root-level served file).
- **No auth / id-only tenancy unchanged** — this epic neither lists nor aggregates across reviews, so
  it does not widen exposure (footgun 5 not engaged).
- **Live instance is on :8139; never `docker compose up`** (compose binds :8137). Verification uses a
  **throwaway container on :8138**.

## Preferred execution order

1. **MR-028** (Phase 1, footnotes) — smallest, lowest-risk, no theme decision; ships and verifies first.
2. **MR-029** (Phase 2, highlighting) — independent of MR-028; the larger payload + theme CSS.
3. **MR-030** (docs) — only after both render; or fold docs into MR-029 and drop this ticket.

MR-028 and MR-029 are technically independent (different vendored files, both only extend
`setupMarked()`); ordering is by risk, not dependency. Both edit `setupMarked()` and the viewer
`<head>`, so run them sequentially to avoid a trivial merge conflict.

## Ticket breakdown

IDs are placeholders; the orchestrator allocates real IDs after G1. Next free ID is **MR-028**
(highest existing is MR-027); the sprint is **sprint-08** (highest is sprint-07).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-028 | Vendor `marked-footnote` and render GFM footnotes in the viewer (refs + ordered back-ref section), styled to match | ui | 1 |
| MR-029 | Vendor highlight.js (common) + `marked-highlight` + dual-scheme `hljs-github.css`; highlight fenced code at parse time, skipping mermaid | ui | 2 |
| MR-030 | Docs: note footnotes + syntax highlighting in `README.md`/`AGENTS.md` (may fold into MR-029's docs requirement) | docs | 3 |

Proposed count: **2 feature tickets + 1 small docs ticket** (the docs ticket may collapse into
MR-029 per the Definition of Done's same-change-or-same-sprint-sweep rule). Count unchanged by the
G1 review — all three conditions land inside the existing MR-028/MR-029 scope, no new ticket.

**Per-ticket scope / acceptance-criteria notes (G1 conditions baked in):**

- **MR-028 (footnotes) — AC must include a `.sr-only` clip rule.** `marked-footnote` emits
  `<h2 id="footnote-label" class="sr-only">Footnotes</h2>`; `viewer.html` has **no `.sr-only` rule
  today**, so without one the heading renders as a visible accent-colored "FOOTNOTES" banner via
  `#article h2` (`viewer.html:20`). MR-028's CSS scope **must add** the standard clip rule (see step 4):
  `.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;padding:0;margin:-1px;}`.
  **AC:** a screen-reader-only "Footnotes" label is in the DOM but not visible in the both-pane
  screenshot (no banner heading above the ordered list).
- **MR-029 (highlighting) — AC must pin the real highlight call and record the peer-range deviation.**
  (1) The registration **must** resolve the factory off the namespace object —
  `const mh = window.markedHighlight && window.markedHighlight.markedHighlight; if (mh && window.hljs) marked.use(mh({…}))`
  — **not** bare `markedHighlight(...)`, which throws `TypeError` (see step 3). AC: the highlight hook
  registers without a console error and `.hljs-keyword` tokens render. (2) The Work-log **must note**
  the **verified-but-out-of-range** pin: `marked-highlight@2.1.4` peer-declares `marked ">=4 <15"`
  but the vendored marked is **v18.0.4** (reproduced working in headless Chrome at G1). Record the
  **re-probe trigger**: any future `static/marked.min.js` bump requires re-running the headless-Chrome
  browser-global coexistence probe before trusting the highlighter. (`marked-footnote@1.4.0` is in
  range — `marked ">=7.0.0"` — and needs no such note.)

## Risks and mitigations

| Risk | Likelihood | Mitigation (measured where possible) |
|---|---|---|
| Footnote inline tokenizer eats math `$…$` (or vice-versa) | low | **M2** probed all adjacency cases against the real math extensions — no delimiter conflict; math wins a caret inside math; currency stays literal. |
| `marked-highlight` makes `marked.parse` async (returns a Promise) and breaks the sync call at `viewer.html:270` | low | Register with the **sync** callback (no `async:true`); **M2/M3** confirmed a string return. |
| Highlighter highlights mermaid blocks / double-processes with `renderMermaid` | low | The callback returns raw `code` for `lang==='mermaid'`; `code.language-mermaid` still matched by `renderMermaid` (**M3**). The common build doesn't even include a mermaid grammar. |
| hljs theme looks wrong / has a white box on the dark pane | medium | **M4** screenshotted both panes; ship a dual-scheme `@media`-scoped theme with `.hljs` background stripped so the pane's pre background shows through. **Both-pane screenshot is a G7 requirement.** |
| A hand-rolled footnote impl silently drops a definition | n/a (avoided) | Chose the vendored adapter precisely because the hand-roll dropped `[^b]` in M1. |
| Payload bloat | low | ~127 KB total (M3 summary), vs 3.3 MB mermaid already shipped. Common build, not "all". |
| New `static/` file not served in the rebuilt container | very low | `/static/` route + `COPY static/` already cover it (footgun 9); the GET header-dump MIME check (footgun 10) catches a missing/empty asset. |
| **`marked-highlight@2.1.4` is out of its declared peer range** (`peerDependencies: marked ">=4 <15"`; vendored `marked.min.js` is **v18.0.4**) | low (verified) | **Verified-but-out-of-range pin.** The G1 critic reproduced the exact `<script src>` + browser-global path in headless Chrome: v18 composes, `marked.parse` returns a string, `.hljs-keyword` tokens emit — it works **today**. Recorded as an accepted deviation in MR-029. **Re-probe trigger:** if `static/marked.min.js` is ever bumped, re-run the headless-Chrome browser-global coexistence probe (the canonical check) before trusting the highlighter. (`marked-footnote@1.4.0` peer-declares `marked ">=7.0.0"` — open-ended, **in range, clean**.) |
| History modal footnote id-duplication | low/cosmetic | Accepted as cosmetic non-goal; called out, not fixed this epic. |

## Assumptions and open questions

No BLOCKER-FOR-HUMAN. Proceeding on the assumptions below (autonomous invocation, no `--ask`).

**Load-bearing (changes the design) — 1:**

- **A1 (load-bearing): the highlighter runs at parse time via `marked-highlight`, not as a DOM
  post-pass.** Justification: M3 showed the parse-time hook runs before `numberBlocks`/`renderMermaid`
  with no ordering fight and a clean mermaid skip; a post-pass would run after reparenting and need a
  careful exclude selector. If a reviewer prefers a post-pass (e.g. to avoid `marked-highlight`
  entirely), that's a one-ticket swap, but the parse-time approach is recommended and measured.

**Minor (best-effort assumption stated) — 4:**

- **A2 (minor): vendor github/github-dark as the theme pair.** Justification: GitHub's themes are the
  reference for "renders like the published post," are pure `.hljs*` selectors (trivially
  `@media`-scopable, M4), and read on both panes. Any other dual theme is a drop-in swap.
- **A3 (minor): highlight.js common build (~34 grammars), not a custom subset.** Justification: it
  covers every language a dev/Jekyll post uses at ~127 KB; pruning further saves little and risks a
  missing language. Unlabelled blocks use `highlightAuto`.
- **A4 (minor): the footnotes section is numbered as a normal `.blk` and is commentable.** Justification:
  it is appended before `numberBlocks` runs, consistent with every other block; no special-casing.
  If undesirable, exclude `section.footnotes` in `numberBlocks` — a one-line follow-up.
- **A5 (minor): history-modal footnote id-duplication is cosmetic and not fixed.** Justification: the
  modal is a transient overlay with same-page anchors; per-render id-prefixing is out of scope.

## Verification

All commands use a **throwaway container on host port 8138** (never `docker compose`; the live
instance is :8139, compose is :8137). Run from the repo root on `dev`.

### Build + boot a throwaway container
```bash
docker build -t mdreview-rf .
docker rm -f mdreview-rf 2>/dev/null || true
docker run -d --name mdreview-rf -p 8138:8080 mdreview-rf
sleep 1
BASE=http://localhost:8138
curl -s "$BASE/healthz"            # expect ok
```

### Service gate (no app.py change, but keep the gate honest)
```bash
python3 -m py_compile app.py       # must pass (unchanged file still compiles)
```

### Vendored assets are served with the right MIME (GET header-dump — footgun 10, NOT curl -sI)
```bash
curl -sD - -o /dev/null "$BASE/static/highlight.min.js"      | grep -i '^content-type'   # text/javascript
curl -sD - -o /dev/null "$BASE/static/marked-footnote.umd.js" | grep -i '^content-type'  # text/javascript
curl -sD - -o /dev/null "$BASE/static/marked-highlight.umd.js"| grep -i '^content-type'  # text/javascript
curl -sD - -o /dev/null "$BASE/static/hljs-github.css"       | grep -i '^content-type'   # text/css
# also assert non-empty (catches an uncopied/empty asset — assert a floor, not an exact byte count):
test "$(curl -s "$BASE/static/highlight.min.js" | wc -c)" -gt 100000 && echo ok  # ~127 KB, must be > 100000
```

### Seed a review exercising footnotes + highlighting + the must-not-regress paths
```bash
ID=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' -d '{
 "title":"render-fidelity smoke",
 "markdown":"# Render fidelity\n\nA claim with a footnote[^a] and energy $E=mc^2$ inline.\n\nReuse[^a] the same ref.\n\n```python\ndef greet(name=\"x\"):\n    return f\"hi {name}\"\n```\n\n```mermaid\ngraph TD; A-->B;\n```\n\n| col | val |\n|-----|-----|\n| a | 1 |\n\nCosts $5 and $10 (currency, not math).\n\n[^a]: The footnote definition with *emphasis*.\n"
}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
echo "review id: $ID  ->  $BASE/review/$ID"
```

### Render-smoke from the rebuilt container — flat selectors only (footgun 11)
```bash
# Phase 1 (footnotes): a superscript ref AND the ordered footnotes section render.
scripts/render-smoke.sh "$BASE/review/$ID" 'sup' '.footnotes' '#article'

# Phase 2 (highlighting): a highlighted <code> block AND a keyword token render.
scripts/render-smoke.sh "$BASE/review/$ID" 'pre' '.hljs' '.hljs-keyword' '#article'

# Must-not-regress: math, mermaid diagram, table still render.
scripts/render-smoke.sh "$BASE/review/$ID" '.katex' '.mermaid' 'table'
```
Each selector must report `ok` (>=1 node). **Never** pass `'#article pre code'` or any
space-containing selector — the matcher rejects it as bad usage (exit 2), which is not a render miss.

### Both-pane screenshot (the theme is theme-sensitive — M4 / G7 requirement)
```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# default (dark) pane:
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars --force-color-profile=srgb \
  --window-size=900,1100 --virtual-time-budget=2500 \
  --screenshot=/tmp/rf-dark.png "$BASE/review/$ID"
```
Inspect `/tmp/rf-dark.png`: footnote refs are superscripts, the footnotes section renders at the
bottom with a back-ref `↩`, the python block is token-colored and **legible on the dark pre
background** (no white box), the mermaid block is a diagram (not code), the table renders. For the
light pane, capture a light-scheme screenshot (emulate light, or capture on a light-default host) and
confirm github-light colors read on the light pre background. Save both under
`reviews/sprint-08-render-evidence-*` at G7.

### Default-safe regression (no footnotes, no code → byte-identical today)
```bash
ID2=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"plain","markdown":"# Plain\n\nJust a paragraph, no footnotes, no code.\n"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
scripts/render-smoke.sh "$BASE/review/$ID2" '#article' 'h1' 'p'   # renders; no .footnotes/.hljs present is expected
```
A plain doc must show no `.footnotes` and no `.hljs` (nothing to highlight) and render exactly as
before the epic.

### Teardown
```bash
docker rm -f mdreview-rf
```

## Review resolutions

**2026-06-18 — G1 staff-critic review** (`reviews/render-fidelity-plan-review-2026-06-18.md`),
verdict **PASS-WITH-CONDITIONS** (0 BLOCKER, 4 SHOULD, 1 NIT). The critic reproduced the
browser-global `<script src>` path in headless Chrome (the load-bearing risk works), so no redesign —
all fixes are ticket-level and applied in this revision:

- **SHOULD-1 (wrong verification URL).** Every Verification command used `$BASE/r/$ID`, but the viewer
  route is `/review/{id}` (`app.py:453`; `review_url` at `app.py:317`) — `/r/` 404s. Replaced
  `/r/$ID` → `/review/$ID` in all four spots: the seed `echo`, the three render-smoke blocks, the
  Chrome screenshot command, and the default-safe-regression smoke. Grep-confirmed zero `/r/` left.
- **SHOULD-2 (highlight snippet throws as written).** Rewrote step 3 (`setupMarked()`) to state the
  exact globals — `window.markedFootnote` is the factory; `window.markedHighlight` is a **namespace
  object** whose `.markedHighlight` is the factory (bare call throws `TypeError`); `window.hljs` is the
  engine — and replaced the loose "destructure or reference accordingly" with a verbatim snippet whose
  guard wraps the **actual call**: `const mh = window.markedHighlight && window.markedHighlight.markedHighlight; if (mh && window.hljs) marked.use(mh({…}))`. A missing/odd-shaped global now degrades
  silently (footgun 8) instead of passing the guard then throwing. Mirrored into MR-029's AC note.
- **SHOULD-3 (stray visible "Footnotes" heading).** `marked-footnote` emits
  `<h2 class="sr-only">Footnotes</h2>` and `viewer.html` has **no `.sr-only` rule** (grep-confirmed),
  so it renders as an accent banner via `#article h2`. Extended step 4 to add the standard clip rule
  (`.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0;padding:0;margin:-1px;}`)
  to the viewer `<style>`, hiding the label visually while keeping it for screen readers. Added to
  MR-028's CSS scope + AC.
- **SHOULD-4 (peer-range deviation).** Added a Risks row recording `marked-highlight@2.1.4`
  (`peerDependencies: marked ">=4 <15"`) against the vendored **v18.0.4** as a **verified-but-out-of-range**
  pin, with the **re-probe trigger** (re-run the headless-Chrome coexistence probe on any
  `static/marked.min.js` bump). Noted `marked-footnote@1.4.0` is in range (`>=7.0.0`, clean). Added to
  MR-029's scope/Work-log note.
- **NIT (payload numbers).** Corrected the bundle-size table and prose: `highlight.min.js` ~127 KB
  (not ~119 KB), total ~136 KB; common build ~34 grammars (not 36) in M3 and A3. Loosened the
  Verification non-empty assert from "~119000" to a `> 100000` floor test.
