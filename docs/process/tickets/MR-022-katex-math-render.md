---
id: MR-022
title: Binary-safe _read_bytes + static-route swap; vendor KaTeX; widen /static/ content-types; render math in viewer
status: ready
layer: ui              # ui+infra: touches viewer.html + static/ (ui) and the app.py /static/ route + docker build (infra)
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: []
branch:
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

- [ ] **Binary-safe read (B1).** A `_read_bytes(path, default=b"")` helper (`open(path, "rb")`) is
      added to `app.py`, and the `/static/` route serves through it into the already-byte-accepting
      `_send` (`app.py:151–153`). The UTF-8 `_read` (`app.py:49`) is **not** used for static assets.
      Text files (source/feedback/notes/meta) keep `_read`/`_read_json`.
- [ ] **Content-type map widened.** The `/static/` handler (`app.py:~333–340`) returns
      `text/css` for `.css`, `font/woff2` for `.woff2`, `font/woff` for `.woff`, `font/ttf` for
      `.ttf`, `text/javascript` for `.js`, else `application/octet-stream`.
- [ ] **KaTeX vendored + fonts flat.** `katex.min.js`, the contrib `auto-render.min.js`,
      `katex.min.css`, and the woff2 fonts the CSS references are in `static/`; the CSS `url()` font
      references are **flattened to bare filenames** (no `fonts/` subdir) so the existing flat
      `/static/([A-Za-z0-9._-]+)` regex (`app.py:333`, no `/`) serves them unchanged. The exact
      bundled file list + total size is recorded in this ticket's Work log.
- [ ] **Math wired into the render sequence.** `<link>`/`<script>` tags added alongside the
      `marked`/`mermaid` includes (`viewer.html:136–137`); in `load()`, **after** `art.innerHTML`,
      `numberBlocks()` and `await renderMermaid()` (i.e. between `viewer.html:205` and `:206` per the
      plan), `renderMathInElement(document.getElementById('article'), {...})` runs with delimiters
      ordered `$$`,`\[`,`\(`,`$` (display rules before the lone-`$` rule), `throwOnError:false`,
      `ignoredTags:['script','noscript','style','textarea','pre','code']`.
- [ ] **GATING proof (S1) — fonts actually served as binary, from the rebuilt container:**
      `curl -sI .../static/katex.min.css` → `200` + `content-type: text/css`;
      `curl -sI .../static/KaTeX_Main-Regular.woff2` → `200` + `content-type: font/woff2`;
      `curl -s .../static/KaTeX_Main-Regular.woff2 -o /tmp/k.woff2 && file /tmp/k.woff2` →
      identifies as **WOFF2** (non-empty body — a UTF-8-read handler would 500/empty here; a HEAD
      alone would not catch it).
- [ ] **Render wiring smoke (non-gating, S1):** `scripts/render-smoke.sh "/review/$id" '.katex' '#article'`
      reports ≥1 `.katex` node for a fixture with `$E=mc^2$` and `$$\int_0^1 x\,dx$$`. (Proves
      `renderMathInElement` fired — NOT that fonts loaded; the woff2 body check above is the gate.)
- [ ] **Prose-`$` safety:** the fixture line `Prices: $5 and $10 in prose.` shows literal dollars —
      no `.katex` node spanning them — while real math renders.
- [ ] **Note-anchor non-regression (N2):** a math-quoting note renders its card **exactly once**
      (no duplicates from `renderComments()`'s 250/800/1600ms `setTimeout` re-walks,
      `viewer.html:402`); a prose note in a block that also contains math still anchors (the
      `reconcile` substring test at `viewer.html:232` only sees the math substring change).
- [ ] **No redundant Dockerfile change.** No per-file `COPY` is added — `Dockerfile:9`
      (`COPY static/ ./static/`) already copies new `static/` files.
- [ ] Local validation passes: `python3 -m py_compile app.py`; `docker build` succeeds (vendored
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- MathJax-3 fallback (only if KaTeX font bundling fails at G4).
