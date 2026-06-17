---
id: MR-022
title: Binary-safe _read_bytes + static-route swap; vendor KaTeX; widen /static/ content-types; render math in viewer
status: done
layer: ui              # ui+infra: touches viewer.html + static/ (ui) and the app.py /static/ route + docker build (infra)
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: []
branch: dev            # solo cycle — committed straight to dev per README dev-flow
created: 2026-06-18
updated: 2026-06-18
---

## Goal

A reviewer opening `/review/{id}` for a draft containing LaTeX sees the math **rendered** the way
the Jekyll/MathJax-published site renders it — inline `$...$` / `\(...\)`, display `$$...$$` /
`\[...\]` — with no false positives on a lone `$` in prose. This is P0a. Self-contained: a draft
with no math renders exactly as today. KaTeX is vendored into `static/` (no CDN, no pip), which
forces the prerequisite fix that the static route can serve **binary** assets at all.

## Acceptance criteria

- [x] **Binary-safe read (B1).** A `_read_bytes(path, default=b"")` helper (`open(path, "rb")`) is
      added to `app.py`, and the `/static/` route serves through it into the already-byte-accepting
      `_send` (`app.py:151–153`). The UTF-8 `_read` (`app.py:49`) is **not** used for static assets.
      Text files (source/feedback/notes/meta) keep `_read`/`_read_json`.
- [x] **Content-type map widened.** The `/static/` handler (`app.py:~333–340`) returns
      `text/css` for `.css`, `font/woff2` for `.woff2`, `font/woff` for `.woff`, `font/ttf` for
      `.ttf`, `text/javascript` for `.js`, else `application/octet-stream`.
- [x] **KaTeX vendored + fonts flat.** `katex.min.js`, `katex.min.css`, and the 20 woff2 fonts the
      CSS references are in `static/`; the CSS `url()` font references are **flattened to bare
      filenames** (no `fonts/` subdir) so the existing flat `/static/([A-Za-z0-9._-]+)` regex
      (`app.py:333`, no `/`) serves them unchanged. (`auto-render.min.js` was vendored then dropped —
      the marked extension uses `katex.renderToString`, not the auto-render pass.) Exact file list +
      size in the Work log.
- [x] **Math rendered for all four Jekyll/MathJax delimiters** — inline `$...$` and `\(...\)`,
      display `$$...$$` and `\[...\]` — matching the published site. (Mechanism changed from the
      plan's `renderMathInElement` post-pass to a **marked extension**; see Work log for why the
      post-pass cannot meet this AC.) `<link>` + `<script>` for KaTeX added by the `marked`/`mermaid`
      includes; `setupKatex()` registers the extension once in `boot()` before any `marked.parse`.
- [x] **GATING proof (S1) — fonts actually served as binary, from the rebuilt container:**
      `curl -sI .../static/katex.min.css` → `200` + `content-type: text/css`;
      `curl -sI .../static/KaTeX_Main-Regular.woff2` → `200` + `content-type: font/woff2`;
      `curl -s .../static/KaTeX_Main-Regular.woff2 -o /tmp/k.woff2 && file /tmp/k.woff2` →
      identifies as **WOFF2** (non-empty body — a UTF-8-read handler would 500/empty here; a HEAD
      alone would not catch it).
- [x] **Render wiring smoke (non-gating, S1):** `scripts/render-smoke.sh "/review/$id" '.katex' '#article'`
      reports ≥1 `.katex` node for a fixture with `$E=mc^2$` and `$$\int_0^1 x\,dx$$`. (Proves the
      math extension fired — NOT that fonts loaded; the woff2 body check above is the gate.)
- [x] **Prose-`$` safety:** the fixture line `Prices: $5 and $10 in prose.` shows literal dollars —
      no `.katex` node spanning them — while real math renders.
- [x] **Note-anchor non-regression (N2):** a math-quoting note renders its card **exactly once**
      (no duplicates from `renderComments()`'s 250/800/1600ms `setTimeout` re-walks,
      `viewer.html:402`); a prose note in a block that also contains math still anchors (the
      `reconcile` substring test at `viewer.html:232` only sees the math substring change).
- [x] **No redundant Dockerfile change.** No per-file `COPY` is added — `Dockerfile:9`
      (`COPY static/ ./static/`) already copies new `static/` files.
- [x] Local validation passes: `python3 -m py_compile app.py`; `docker build` succeeds (vendored
      assets + static-route change); the render-smoke + curl checks above run from the rebuilt
      container.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — Service (Math) section, the "Binary-safe read" Key
  constraint, Risks (KaTeX fonts), Verification (MR-022 block). B1 is the epic's highest-priority
  code change; **extending the content-type map alone leaves the route 500ing on `.woff2`** — the
  `_read_bytes` swap is mandatory.
- Render order is load-bearing: KaTeX runs *after* `numberBlocks()` (`viewer.html:210`) so `.katex`
  nodes survive the `.blk` reparenting, and *after* `renderMermaid()` (`viewer.html:155`).
- Engine = **KaTeX** (brief's preference; its auto-render same-run scanner is the prose-`$`-safe
  matcher). If font bundling proves unworkable, **MathJax 3 is the documented fallback** — re-open
  at G4, do not silently swap.
- `re.fullmatch` means route ordering does **not** prevent shadowing here (N1) — do not add an
  ordering "constraint"; it's false for this router.

## Work log

- `2026-06-18` — **app.py:** added `_read_bytes(path, default=b"")` (binary `open(..,"rb")`, B1) +
  a `_CTYPES` map and `_ctype_for(name)`; the `/static/` route now serves `_read_bytes(p)` with
  `_ctype_for(fn)` (`.js/.css/.woff2/.woff/.ttf`, else octet-stream). Text files keep `_read`.
- `2026-06-18` — **Vendored KaTeX 0.17.0** into `static/` via `npm pack katex@0.17.0`:
  `katex.min.js` (271 KB), `katex.min.css` (flattened, 24 KB), and **20 `KaTeX_*.woff2`** fonts
  (woff2 only; legacy `.woff`/`.ttf` dropped — modern browsers fetch woff2 first and stop). CSS
  transformed: stripped the `,url(fonts/X.woff)/.ttf` fallback entries and rewrote
  `url(fonts/X.woff2)` → `url(X.woff2)` so the flat `/static/` regex serves them with no `/`. Total
  `static/` 3.8 MB (KaTeX added ~0.45 MB; KaTeX font payload << the already-vendored 3.3 MB mermaid).
- `2026-06-18` — **viewer.html:** `<link rel="stylesheet" href="/static/katex.min.css">` in head;
  `<script src="/static/katex.min.js">` after mermaid; new `setupKatex()` registers a **marked
  extension** (`blockMath` + `inlineMath` tokenizers → `katex.renderToString`), called once in
  `boot()` before any parse. No post-render pass; the `renderMath()` call was removed from `load()`.
- **DEVIATION FROM PLAN (mechanism, not engine/scope):** the plan specified KaTeX **auto-render**
  (`renderMathInElement`) as a post-markdown pass. G4 validation proved that approach **cannot meet
  this ticket's AC**, for two independent reasons I verified against the vendored `marked.min.js`:
  (1) marked **strips the backslashes** from `\(...\)` and `\[...\]` (→ literal `(…)`/`[…]`) before
  any post-pass runs, so those two required delimiters never reach KaTeX; (2) auto-render's bare-`$`
  scanner **pairs prose dollars** — `"$5 and $10"` renders "5 and " as math, and `\$`-escaping does
  not stop it. Both are fatal to the brief ("inline `$...$` and `\(...\)` … don't trip on a lone `$`
  in prose"). The marked-extension approach tokenizes math **during** the parse: backslash
  delimiters survive, code spans/blocks are auto-skipped by marked, and a no-whitespace-hugging rule
  on `$...$` (`/^\$([^\s$](?:[^$\n]*[^\s$])?)\$/`) distinguishes real math from currency/lone `$`.
  Engine is still **KaTeX** (only the integration changed); `auto-render.min.js` was therefore not
  shipped. The plan anticipated a G4 re-open on the math integration — this is that, resolved up.
- Files: `app.py`, `viewer.html`, `static/katex.min.js`, `static/katex.min.css`, `static/KaTeX_*.woff2` (20).

## Validation

- `2026-06-18` — `python3 -m py_compile app.py` OK; `docker build -t mdreview-service:rr .` OK.
- `2026-06-18` — **Marked-extension logic** proven in node against the vendored `marked.min.js` +
  `katex.min.js` across 10 boundary cases before wiring: all 4 delimiters render; currency/escaped/
  lone-`$`/code stay literal; subscript/star math survive markdown.
- `2026-06-18` — **Rendered-DOM truth table** from the rebuilt throwaway container (`:8138`, headless
  Chrome `--dump-dom`), clean Python-authored fixture (single backslashes): **ALL PASS** — `$...$`,
  `\(...\)`, `$$...$$`, `\[...\]` all render (6 inline + 2 display katex nodes); `$5 and $10`,
  `\$5`→`$5`, lone `$`, and `` `$x$` `` in code all stay **literal**.
- `2026-06-18` — **GATING font/CSS (S1), GET header dump** (HEAD is 501 on this server — no
  `do_HEAD` — so `curl -sI` from the plan returns a text/html error page; verified via `curl -sD -`
  GET, which is the path browsers actually use): `katex.min.css` → 200 `text/css`; `katex.min.js` →
  200 `text/javascript`; `KaTeX_Main-Regular.woff2` & `KaTeX_Size4-Regular.woff2` → 200 `font/woff2`;
  `file` identifies the fetched body as a valid **WOFF2** (26272 B) — proves `_read_bytes` ran (a
  UTF-8 `_read` would have 500'd). Unknown `/static/nope.woff2` → 404.
- `2026-06-18` — `render-smoke.sh '.katex' '#article'` → ok (4 nodes / 1) — wiring fired.

## Follow-ups

- `do_HEAD` is unimplemented (HEAD → 501 text/html); the plan's `curl -sI` MIME checks must use a
  GET header-dump instead. Not introduced by this epic (pre-existing); noted for the docs/verify
  commands and as a possible backlog hygiene item.
- MathJax-3 fallback is now moot — the marked-extension integration resolved the math-integration
  risk without changing engines.
