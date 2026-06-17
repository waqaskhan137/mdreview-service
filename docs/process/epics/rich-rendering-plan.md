---
epic: rich-rendering
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-18
source: requirements/rich-rendering.md
gate: passed 2026-06-18  # G1 (Plan Gate): passed (round 2, staff-critic PASS) — tickets unblocked
review: reviews/rich-rendering-plan-review-2026-06-18.md, reviews/rich-rendering-plan-review-2026-06-18-r2.md
related_sprints: [sprint-06]
related_tickets: [MR-022, MR-023, MR-024, MR-025, MR-026]
---

# Rich Rendering Plan

An agent drove a long, image- and math-heavy research post through mdreview over the MCP and hit
two hard walls that broke a clean review loop: **LaTeX rendered as raw text** (so equations could
not be reviewed visually), and **`<img>` tags referencing site paths (`/assets/...`) or paths
relative to the source file 404'd**, because the service serves only the document and the bundled
renderers — never the draft's asset directory. The agent's workaround (stand up a separate static
server and rewrite every `src`) makes the reviewed draft diverge from the real one, defeating the
point of review. This epic closes both gaps so a math- and image-heavy draft renders in the viewer
the way it renders on the published site — with no CDN, no pip, and no second server.

**Source requirement:** [`requirements/rich-rendering.md`](../requirements/rich-rendering.md) —
the original brief, kept verbatim. Scoped by the user (2026-06-18) to the **two P0s only**; P1/P2
items (theme awareness, SVG/animation doc line, footnotes, syntax highlighting) are deferred to
backlog and are **non-goals** here. Mermaid fenced blocks and YAML front-matter parsing are
**already shipped in `dev`** (`viewer.html` `renderMermaid()` at viewer.html:155 and the
front-matter strip in `load()` at viewer.html:188) — this epic does not rebuild them.

## Product goal

A reviewer opening `/review/{id}` for a draft that contains LaTeX and local/relative/site-root
images sees:

- **Math rendered**, matching the Jekyll/MathJax-published site: inline `$...$` and `\(...\)`,
  display `$$...$$` and `\[...\]`, with no false positives on a lone `$` in prose (e.g. "$5").
- **Images that resolve**, because the agent attached the draft's assets to the review once (a
  small MCP/HTTP call, not a base64 blob shoved through `update_source`), and the service serves
  them at a stable per-review URL that the viewer rewrites `<img src>` to.

Both surfaces (HTTP API in `app.py`, MCP tools in `mcp_server.py`) carry the asset capability, so
an agent driving over MCP never has to leave the protocol or rewrite the draft.

## Core design principle

**Render the draft as the published site would, without leaving the box.** Everything is vendored
into `static/` (math engine) or stored under the review's own directory (assets) and served by the
existing stdlib router. No CDN, no pip, no second server, and — critically — **no change to the
default behavior of a review that has no math and no attached assets**: a draft with neither must
render exactly as it does today. Both features are *additive and default-safe*: a missing asset
manifest, a missing `source_path`, or prose with no `$$` leaves today's render path untouched.

## Recommended approach

Two independent vertical features. Math (P0a) is UI-only plus one infra widening of the static
route. Assets (P0b) is service + MCP + a small viewer `<img>` rewrite. They share no code and can
ship in either order; math is the smaller, lower-risk slice and goes first.

### Service (`app.py`)

**Math (P0a):** the service-side change is the `/static/` route, and it has **two listed code
changes**, not one. Three problems with KaTeX assets must be solved at app.py:333–340:

0. **(BLOCKER — binary-safe read.)** `_read(path)` (app.py:49) opens with `encoding="utf-8"` and
   returns `str`; the static handler currently serves via `self._send(200, _read(p), ctype)`
   (app.py:339). Every file vendored so far (`marked.min.js`, `mermaid.min.js`) is UTF-8 text, so
   this path has never touched binary. KaTeX adds `.woff2` fonts — **the first font byte raises an
   uncaught `UnicodeDecodeError` inside the handler, not a served file.** Extending the
   content-type map is necessary but **not sufficient**; the read itself must change. **Listed code
   change:** add a `_read_bytes(path, default=b"")` helper that mirrors `_read` but does
   `open(path, "rb").read()` (catching `FileNotFoundError`), and serve the static route through it
   — `self._send(200, _read_bytes(p), ctype)`. `_send()` already byte-accepts (app.py:151–153), so
   this is a one-line helper plus a one-call swap. **Route → read mapping:** the `/static/` route
   (fonts/css/js — all of it, since the helper is byte-safe for the existing text files too) uses
   `_read_bytes`; `source.md`/`feedback.md`/`notes.json`/`meta.json` keep `_read`/`_read_json`
   (they are and remain UTF-8 text). The new `GET /asset/{stored}` route (MR-023) also uses
   `_read_bytes` — see the Assets section. **This is the highest-priority change in the epic: omit
   it and the rebuilt container 500s on the first `.woff2` request.**
1. The content-type map only knows `.js` (`text/javascript`) and falls back to
   `application/octet-stream`. KaTeX ships a **stylesheet** (`katex.min.css`) and **web fonts**
   (`.woff2`). A `<link>` served as `application/octet-stream` is ignored by browsers, and fonts
   need a font MIME. Extend the map: `.js`→`text/javascript`, `.css`→`text/css`,
   `.woff2`→`font/woff2`, `.woff`→`font/woff`, `.ttf`→`font/ttf`, else `application/octet-stream`.
   (This is the *second* code change, paired with change 0 — neither alone suffices.)
2. The route regex is `r"/static/([A-Za-z0-9._-]+)"` — **the character class has no `/`**, so KaTeX
   CSS's relative font references (`fonts/KaTeX_*.woff2`) would 404. Either (preferred) **flatten
   the fonts into `static/` and rewrite the CSS `url()` paths to bare filenames** so the existing
   flat regex still serves them, **or** widen the regex to one optional `fonts/` subdir
   (`r"/static/(?:fonts/)?([A-Za-z0-9._-]+)"`) with the file lookup pinned under `HERE/static`.
   Pick flatten-and-rewrite: it keeps the router regex unchanged (less attack surface, no traversal
   question) and is a one-time `sed` on the vendored CSS. Document the rewrite in the ticket so a
   future KaTeX bump repeats it.

**Assets (P0b):** new storage + routes, all under the review's existing directory so they ride the
`DELETE` rmtree and never collide with `source.md`/`feedback.md`/`notes.json`/`history/`.

- **Storage.** Per review: a sibling `assets/` directory (`_dir(rid)/assets/`) holding the raw
  bytes, plus `assets.json` (a manifest: `[{name, stored, bytes, ctype, ts}]`). `assets/` sits
  beside `history/`; neither the snapshot path (`snapshot_round`, app.py:105) nor the source/
  feedback writers touch it, so it survives every `PUT /source` revision unchanged — which is the
  whole point (attach once, reuse across revisions; never resend blobs through `update_source`).
- **Stored-name safety.** Never write under the client-supplied `name` directly. Derive a stored
  filename = `sha1(bytes)[:16]` + the *sanitized* original extension; keep the human `name` only as
  a manifest field for matching. This makes the on-disk name traversal-proof by construction
  (`/`, `..`, NUL can't appear in a hex+ext name) and dedupes identical bytes.
- **Served URL keys on the stored name, not the human `name` (S4).** The asset's public URL is
  built from the **`sha1+ext` stored name** — `{base}/api/reviews/{id}/asset/{stored}` — which by
  construction contains **no `/`** and therefore **no `%2F`** when placed in a path segment. The
  human `name` (the exact draft `src`, possibly `/assets/x.png`) is kept **only** as a manifest
  match field; it never appears in the served path. This kills the encoded-slash-through-proxy
  failure (S4) at the design level: a reverse proxy (the live `mdreview.waqasrana.space` stack)
  never sees a `%2F` to reject. The viewer (MR-026) matches a draft `<img src>` to a manifest
  `name`, then sets `img.src` to that manifest entry's **`url`** (the `%2F`-free stored-name URL) —
  the match key and the served key are decoupled on purpose.
- **Routes** (new regex rows in `route()`; placed *after* the `/feedback` and `/status` rows and
  *before* the `/review/{id}` row by convention — note under `re.fullmatch` ordering does **not**
  affect correctness here, see N1):

  | Method | Path | Body | Returns |
  |--------|------|------|---------|
  | `POST` | `/api/reviews/{id}/assets` | `{name, content_b64}` | `{name, stored, url, bytes, ctype}` |
  | `GET`  | `/api/reviews/{id}/assets` | | `{assets:[{name, stored, url, bytes, ctype, ts}]}` |
  | `GET`  | `/api/reviews/{id}/asset/{stored}` | | raw bytes (the served asset) |
  | `DELETE` | `/api/reviews/{id}/asset/{stored}` | | `{deleted}` *(optional, P-2 nicety)* |

  Route regex shapes (id pattern reused verbatim from `RID`):
  `r"/api/reviews/" + RID + r"/assets"` and
  `r"/api/reviews/" + RID + r"/asset/([A-Za-z0-9._-]+)"`. The trailing segment is the **stored
  name** (`sha1+ext`, `[A-Za-z0-9._-]` only — no `%`/`/` ever needed in the class). The lookup
  resolves it **against the manifest only** (`stored` must be a known manifest entry); an unknown
  segment is a 404. The handler never joins the request segment onto a filesystem path, so there is
  no traversal vector even before the stored-name guard — defense in depth.

  **Binary read on the asset GET (B1).** The asset GET serves PNG/JPEG/SVG-binary/etc., so it
  **must** use `_read_bytes(p)` (the helper added in MR-022), **not** `_read(p)` — `_read`'s
  `encoding="utf-8"` raises `UnicodeDecodeError` on the first non-text image byte exactly as it
  would on a font. The handler reads the stored file under `assets/{stored}` with `_read_bytes` and
  `self._send(200, bytes, ctype)` using the manifest's recorded `ctype`. This is a **listed code
  change in MR-023's scope**, paired with the route — serving via `_read` would 500 on any binary
  image. (MR-022 introduces `_read_bytes`; MR-023 reuses it. If MR-023 lands first, it introduces
  the helper instead — either way the helper is a hard prerequisite of any binary-serving route.)

  The `{name, path}` server-side local-read form is **cut from this epic** — base64 (`content_b64`)
  is the sole transport. See the MR-024 decision in Non-goals and the Risks/Resolution log.

- **Write discipline.** All asset writes go through the module `_lock` (mirroring the source/
  feedback/snapshot writers); the manifest is read-modify-write under the lock.

- **Back-compat.** `assets.json` is absent on every existing review. Readers default to `[]`
  (`_read_json(..., [])`, the established pattern). `GET /assets` on a pre-existing review returns
  `{"assets": []}`; nothing in the viewer or meta assumes the key exists. New POST field
  `content_b64` is optional (existing endpoints unchanged); a pre-`assets.json` manifest entry that
  lacks `stored` cannot occur (the manifest is only ever written by the new writer with `stored`
  present).

- **URL form.** The returned `url` uses `self._base()` (PUBLIC_BASE-aware, app.py:176) so a relayed
  URL is reachable, identical to how `review_url` is built — i.e. an absolute
  `{base}/api/reviews/{id}/asset/{stored}`, where `{stored}` is the `%2F`-free `sha1+ext` name
  (S4). Because the served path has no encoded slash, the relayed/PUBLIC_BASE deployment behind a
  reverse proxy resolves it identically to localhost.

### MCP (`mcp_server.py`)

Add tools 1:1 with the new HTTP endpoints, in the existing thin-wrapper style (a `TOOLS` schema
entry + a `route()` branch mapping name→(method, path, body); no new state):

- **`attach_asset`** — args `{id (req), name (req), content_b64 (req)}`. Maps to
  `POST /api/reviews/{id}/assets`. base64 is the sole transport (the `path`/local-read form is cut
  this epic — see MR-024 decision). Mirrors the brief's `attach_asset(review_id, bytes, name)`.
- **`list_assets`** — args `{id (req)}`. Maps to `GET /api/reviews/{id}/assets`.

Two tools (not a `register_asset_dir`): a per-file base64 attach is the safe, traversal-free
default and fully delivers both P0s. Bulk-dir / server-side-path registration is **deferred to
backlog** (S5) — a no-auth, id-only service does not carry an arbitrary-host-read code path until a
concrete need exists. Keep the tool count minimal and consistent. Update the docstring's tool list
and `mcp_smoke.py` (if it enumerates tools) accordingly.

### UI (`viewer.html`)

**Math (P0a):** vendor `katex.min.js` + the contrib auto-render `auto-render.min.js` +
`katex.min.css` (+ flattened fonts) into `static/`. Add two `<link>/<script>` tags alongside the
existing `marked`/`mermaid` includes (viewer.html:136–137). In `load()`, the sequence is `art.innerHTML=html` (viewer.html:203) → `numberBlocks()` (:204) →
`await renderMermaid()` (:205) → `reconcile()` (:206) → `render()` (:207). **Insert
`renderMathInElement(...)` between line 205 and `reconcile()` (:206)** — i.e. after the DOM is
reparented into `.blk` wrappers and mermaid has run, but **before** `reconcile()` re-anchors notes,
so notes match against the already-typeset DOM and a math-quoting note degrades to a block card
deterministically (N2). Call `renderMathInElement(document.getElementById('article'), {...})` with
the delimiter set:

```
delimiters: [
  {left:'$$',  right:'$$',  display:true},
  {left:'\\[', right:'\\]', display:true},
  {left:'\\(', right:'\\)', display:false},
  {left:'$',   right:'$',   display:false},
],
throwOnError:false, ignoredTags:['script','noscript','style','textarea','pre','code'],
```

The `$$`/`\[` rules **must precede** the single-`$` rule so display math isn't mis-split, and
auto-render's own scanner requires a matching closing `$` on the same logical text run — a lone `$`
in prose has no partner and is left as text (this is how KaTeX avoids the prose-`$` false positive;
verify it in the render-smoke with a `$5 and $10` paragraph). `ignoredTags` keeps math syntax
inside code blocks literal.

**Interaction with existing layers — the load-bearing UI risk:**

- `numberBlocks()` (viewer.html:210) rebuilds `#article` children into `.blk` wrappers. Run KaTeX
  *after* it so `.katex` nodes live inside the final `.blk` structure and aren't discarded.
- `reconcile()` (viewer.html:228) and `highlightNote()` (viewer.html:334) match notes by
  `innerText`/exact-substring inside text nodes. KaTeX replaces `$x$` with a `.katex` element tree
  whose `innerText` is the rendered math, **not** the source `$x$`. A note quoting raw LaTeX won't
  re-anchor after math renders. Acceptable and in-scope-bounded: notes anchor to *rendered* text;
  a quote that lands on math falls back to the block anchor (the existing `highlightNote` returns
  `null` → block-level card, viewer.html:349). A prose note in a block that *also* contains math
  still matches, because `reconcile` tests `blk.innerText.includes(nt.quote)` (viewer.html:232) and
  only the math substring changed — so prose notes (the dominant case) are unaffected. Call this out
  in the ticket AC as expected behavior, not a bug. Do **not** try to make highlight ranges span
  `.katex` subtrees this epic.
- The live-reload `poll()`→`load()` path re-runs the whole sequence, so re-renders re-typeset math
  for free. No extra wiring. **N2 AC:** `renderComments()` re-runs on the 250/800/1600ms
  `setTimeout` fallbacks (viewer.html:402) and re-walks the KaTeX-modified DOM each time — the
  render-smoke must confirm a math-quoting note renders its card **exactly once** (no duplicate
  cards from the repeated walks), not assume it silently.

**Assets (P0b):** before render, rewrite `<img>` sources that the service now hosts. After
`marked.parse(md)` produces `html` and before/just-after setting `#article` innerHTML, resolve each
`<img>`'s `src`:

1. Fetch the manifest once per load: `GET {API}/assets` → `{assets:[{name, stored, url}]}`.
2. For each `<img>` in `#article`, if its `src` is **not** absolute/`data:`, match against the
   manifest by manifest `name` (full draft `src` first, then `basename` fallback), and on a match
   set `img.src = matched.url`. The `url` is the **stored-name** (`%2F`-free) served URL, **not**
   the human `name` (S4) — the match key and the served key are decoupled. Site-root paths
   (`/assets/foo.png`) and source-relative paths (`../img/foo.svg`) both reduce to a `name` the
   agent attached.
3. Unmatched `<img>` keep their original `src` (today's behavior — they 404 as before; no
   regression). Optionally tag unmatched-local images so the reviewer sees a "missing asset" hint
   (P-2 nicety, not required for P0b done).

This makes the **match key = the `name` the agent passes**, while the **served key = the stored
`sha1+ext`** (S4: the served URL never contains `%2F`, so a reverse proxy can't mangle it).
Convention (document it): the agent attaches each image under the *exact `src` string used in the
draft* (e.g. `name:"/assets/x.png"` or `name:"fig/x.svg"`), so the viewer's match is a direct
lookup with a basename fallback. No markdown rewrite, no `source.md` mutation — the draft stays
byte-identical to the real one.

## Rollout phases

Each phase is independently shippable and leaves the service correct if the next never lands.

### Phase 1 — Math rendering (P0a)
Vendor KaTeX into `static/`; widen the `/static/` content-type map (and serve the flattened
fonts); wire `renderMathInElement` into the viewer render sequence with the Jekyll-matching
delimiters. Ship-on-its-own: a math-heavy draft now renders; an asset-heavy draft is unaffected.

### Phase 2 — Asset attach + serve (P0b, service + MCP)
Add `assets/` storage + manifest, the `POST/GET /assets` and `GET /asset/{stored}` routes (binary
read via `_read_bytes`), the stored-name + manifest-lookup traversal guards, and the
`attach_asset`/`list_assets` MCP tools. base64 is the sole transport (the `path` form is cut — S5).
Ship-on-its-own: an agent can attach and fetch assets over HTTP/MCP even before the viewer rewrites
`<img>` (verifiable by curling the asset URL).

### Phase 3 — Viewer image rewrite (P0b, UI)
The viewer fetches the manifest and rewrites local/relative/site-root `<img src>` to served asset
URLs. Depends on Phase 2's `GET /assets`. This is the phase that makes images visibly render.

### Phase 4 — Docs sweep
Update `README.md` API table (new asset rows + the static content-type note), `CLAUDE.md` contract
(attach-asset step in the agent loop; note math now renders), and `mcp_server.py` docstring tool
list. Per the Definition of Done, durable behavior changes are documented in the same change or a
named same-sprint docs-sweep ticket — this is that ticket, and (per G7) it is **not** carry-over
eligible.

## Non-goals

- **Theme awareness (P1).** Backlog. No host `color-scheme` work, no neutral-card rendering.
- **SVG/animation doc line (P1).** Backlog. Animated/filtered SVGs already work once reachable;
  nothing to build (P0b makes them reachable as a side effect).
- **Footnotes + syntax highlighting (P2).** Backlog. Footnotes need a marked extension; no
  highlighter is bundled.
- **Mermaid fenced blocks & YAML front-matter parsing.** **Already shipped in `dev`** — not rebuilt.
- **Markdown rewriting on the server.** The draft is never mutated to fix images; the viewer
  rewrites `<img src>` at render time only.
- **History-aware assets.** Assets are review-scoped, not per-revision-snapshotted; a past
  `history/round-N` draft is rendered with the *current* asset set. Acceptable; noted as debt.
- **Auth / per-asset access control.** Assets inherit the review's id-only tenancy. Out of scope.
- **Server-side local-dir / `{name, path}` asset read (was MR-024).** **Cut from this epic (S5).**
  base64 (`content_b64`) fully delivers both P0s; a no-auth, id-only service should not carry an
  arbitrary-host-filesystem-read code path (even env-gated and realpath-confined) until a concrete
  need exists. Deferred to backlog. If revived, it **must** ship with the `os.path.realpath(root) +
  os.sep` separator-boundary check (S3, recorded in the Risks/Resolution log) and a negative-path
  AC (path outside roots → 400, symlink-escape → 400). The `path` arg is dropped from
  `attach_asset` for now.

## Key constraints

The project footguns this epic hits head-on — each must hold:

- **Stdlib-only, zero pip, no CDN.** The math engine is vendored into `static/` exactly like
  `marked.min.js`/`mermaid.min.js`; the asset server is pure `http.server`/the existing router with
  no Flask/Pillow. No image processing — bytes are stored and served verbatim with a declared MIME.
- **Overwrite-based persistence — no collisions.** Per-review `assets/` + `assets.json` are new
  siblings of `source.md`/`feedback.md`/`notes.json`/`history/`. The source/feedback writers and
  `snapshot_round` (app.py:105) never touch them, so assets survive every `PUT /source`. This is
  the brief's core requirement: attach once, reuse across revisions, never resend blobs.
- **Back-compat of `meta.json` / new files.** Existing reviews lack `assets.json`; every reader
  defaults it to `[]` and never assumes presence. New POST fields (`content_b64`/`path`/`name`) are
  optional additions; existing endpoints are unchanged.
- **Single-file regex router, ordered match.** New asset routes are regex rows inserted *after*
  `/status`/`/feedback` and *before* `/review/{id}` and `/static/...` by convention. Under
  `re.fullmatch` (every route uses it), `/api/reviews/{id}` does **not** match
  `/api/reviews/{id}/assets` or `/asset/{stored}` regardless of order — so ordering is *not* a
  correctness constraint here (N1); it's kept tidy, not load-bearing. The `{id}` regex `RID`
  (`app.py:38`) is reused unchanged. **Do not propagate "ordering prevents shadowing" into the
  ticket as a constraint — it's false under `fullmatch`.**
- **Binary-safe read — the static and asset routes must not use the UTF-8 `_read`.** `_read`
  (app.py:49) is `encoding="utf-8"` and crashes on the first font/image byte. Both binary-serving
  routes (`/static/*` fonts/css, `GET /asset/{stored}`) read via the new `_read_bytes` helper into
  the already-byte-accepting `_send` (app.py:151–153). Text files (source/feedback/notes/meta) keep
  `_read`/`_read_json`. This is the epic's highest-priority code change (B1).
- **No auth, id-only tenancy — no traversal, no arbitrary host reads.** The asset GET resolves the
  trailing segment through the manifest only (never joined onto a path); stored names are
  `sha1+ext` (no `/`/`..`/NUL by construction). base64 is the sole transport — **the `{name, path}`
  server-side local-read form is cut this epic (S5)**, so the service reads no arbitrary host file
  at all. A feature that serves attached bytes does **not** widen cross-review exposure (it's
  id-scoped). The served URL keys on the `%2F`-free stored name (S4), so no proxy-side encoded-slash
  exposure either.
- **JS-rendered viewer — a 200 is not a render.** G4 (ui tickets) and G7 require
  `scripts/render-smoke.sh` from the **rebuilt container** asserting real DOM nodes: a `.katex` node
  for math, a loaded `<img>` (with the rewritten served `src`) for assets. A 200 on the asset route
  proves bytes are served, not that the image painted.
- **Packaging.** `Dockerfile:9` already does `COPY static/ ./static/`, so **new files dropped into
  `static/` (KaTeX js/css/fonts) need no Dockerfile change** — they're copied by the directory copy.
  (The sprint-01 `dashboard.html` footgun applies only to *new root-level served files*, of which
  this epic adds none.) The asset feature stores under `DATA_DIR` (a volume), not the image, so it
  needs no `COPY` either. State this explicitly in the math ticket so the implementer doesn't add a
  redundant per-file `COPY` and doesn't wrongly assume one is missing.
- **Conventions.** Dates `Europe/London`; commits carry the `Co-Authored-By: Claude` trailer and the
  ticket ID; validation is `python3 -m py_compile app.py` (+ `docker build` for the infra-touching
  math ticket, render-smoke for ui). No test framework.

## Preferred execution order

1. **MR-022 (ui+infra) — Math.** Smallest, lowest-risk, no service-storage surface. Add the
   `_read_bytes` binary-read helper + swap the static route onto it (B1), vendor KaTeX, widen the
   static content-type map, wire `renderMathInElement`. Ship and prove with the woff2 MIME+body
   curl checks (gating) plus a `.katex` wiring smoke. (Carries the static-route infra change per
   footgun-9 reasoning above.)
2. **MR-023 (svc) — Asset storage + HTTP routes.** Storage, manifest, `POST/GET /assets` +
   `GET /asset/{stored}` (binary read via `_read_bytes`), traversal guards, stored-name URL keying.
   base64 only. Depends on nothing (introduces `_read_bytes` itself if it lands before MR-022);
   proven by curl (attach base64 → GET asset → bytes round-trip via `file(1)`).
3. **MR-024 (svc) — MCP `attach_asset` + `list_assets`.** Depends on MR-023. Proven with
   `mcp_smoke.py`.
4. **MR-025 (ui) — Viewer `<img>` rewrite.** Depends on MR-023's `GET /assets`. Proven by a DOM
   check that `img.src` equals the served `%2F`-free asset URL **plus** a `curl` of that exact URL
   returning image bytes (`file(1)`), not just element presence.
5. **MR-026 (docs) — Docs sweep.** README API table, CLAUDE.md contract, MCP docstring. Same-sprint,
   not carry-over eligible (G7).

Service-before-UI is honored: assets storage (MR-023) precedes the viewer rewrite (MR-025); KaTeX
is self-contained ui+infra and can run first or in parallel. The former MR-024 (`path`/local-dir
attach) is **cut** (S5); the slot is reused, so the epic is **five tickets**.

## Ticket breakdown

Create in `tickets/` only after G1. IDs are placeholders (next free is MR-022; orchestrator
allocates). Each ticket is one vertical slice with its own AC and render-smoke/curl evidence.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-022 | Binary-safe `_read_bytes` + static route swap; vendor KaTeX; widen `/static/` content-types; render math in viewer | ui | 1 |
| MR-023 | Per-review asset storage + manifest + `POST/GET /assets`, `GET /asset/{stored}` (base64, binary read, stored-name URL) | svc | 2 |
| MR-024 | MCP `attach_asset` + `list_assets` tools | svc | 2 |
| MR-025 | Viewer rewrites local/relative/site-root `<img src>` to served asset URLs | ui | 3 |
| MR-026 | Docs sweep: README API table, CLAUDE.md contract, MCP docstring | docs | 4 |

Per-ticket scope notes for the implementer:
- **MR-022** *must* add `_read_bytes(path, default=b"")` and serve the `/static/` route through it
  (B1) — extending the content-type map alone leaves the route 500ing on `.woff2`. Gating proof is
  the woff2 MIME+`file(1)` body check (S1), not the `.katex` element count.
- **MR-023** *must* serve `GET /asset/{stored}` via `_read_bytes` (B1) and key the served URL on the
  `%2F`-free `sha1+ext` stored name (S4). base64 is the only transport (S5).
- **MR-025** AC pins the rewrite proof to `img.src == served url` **and** a `curl` of that URL
  returning image bytes (S2), not just `#article img` presence.

`depends_on`: MR-024←MR-023; MR-025←MR-023 (`GET /assets`); MR-026←all. MR-022 is independent (and
introduces `_read_bytes` that MR-023 reuses — if scheduled after MR-023, MR-023 introduces it). The
former local-dir `path` form is **cut** (S5), so this is **five tickets**, firmly — not "six, maybe
five."

## Risks & mitigations

- **KaTeX fonts crash the UTF-8 reader, are served with the wrong MIME, or 404'd by the flat
  `/static/` regex.** *Highest-certainty implementation trap — three failure modes, three fixes.*
  (1) `_read` is `encoding="utf-8"` (app.py:49) and **crashes** on the first font byte
  (`UnicodeDecodeError`, uncaught) — fix: `_read_bytes` binary helper, static route served through
  it (B1). (2) The route only knows `.js` (app.py:338) — fix: extend the content-type map
  (`.css`/`.woff2`/`.woff`/`.ttf`). (3) The regex excludes `/` (app.py:333) — fix: flatten KaTeX
  fonts into `static/` with the CSS `url()` references rewritten to bare filenames so the existing
  regex serves them unchanged. **Gating AC** is the `curl -sI .../static/*.woff2` returning 200 +
  `content-type: font/woff2` **and a non-empty body `file(1)` identifies as WOFF2** (S1) — a HEAD
  alone passes even if the handler wrote nothing. The `.katex` render-smoke proves *math wiring
  fired*, not that fonts loaded (render-smoke counts elements; KaTeX builds `.katex` subtrees from
  JS with zero fonts — see S1).
- **KaTeX font payload size.** KaTeX ships ~60 font files (woff2 ≈ several hundred KB total) plus
  ~0.3 MB js + ~0.5 MB css(unminified). Far smaller than the already-vendored 3.3 MB
  `mermaid.min.js`, so the "small image" constraint holds; still, prune to the woff2 set the CSS
  actually references (drop legacy `.woff`/`.ttf` if the CSS's `format()` fallbacks aren't needed)
  to keep it tight. Note exact bundled file list + total size in MR-022's Work log.
- **MathJax-vs-KaTeX fork.** *Decision: KaTeX*, per the brief's preference (lighter/faster) and
  because its auto-render delimiter pass is exactly the prose-`$`-safe scanner we need. MathJax 3
  would avoid the fonts-as-static-files problem (it can use its own font CSS), but is heavier and
  slower to typeset a long post. If KaTeX's font bundling proves unworkable in MR-022, MathJax 3 is
  the documented fallback (same render-sequence wiring; different vendored payload) — re-open at
  G4, don't silently swap.
- **Prose-`$` false positives.** Mitigated by KaTeX auto-render's same-run matching + delimiter
  ordering ($$ before $). AC: a render-smoke fixture with `$5 and $10` in prose must show those as
  literal text (no `.katex` node spanning them) while a real `$E=mc^2$` renders.
- **Math breaks note anchoring on equations.** `reconcile`/`highlightNote` match source text;
  rendered math no longer contains the raw `$...$`. Mitigation: documented expected behavior —
  math-quoting notes fall back to the block anchor (existing path). Not a regression for prose
  notes, which dominate. No code change attempted this epic.
- **Path traversal / arbitrary host read via the asset feature.** *Real security consideration.*
  Mitigations layered: stored names are `sha1+ext` (no separators); the GET resolves the trailing
  segment via the manifest, never path-joining the request segment; the served URL is keyed on the
  `%2F`-free stored name (S4). **The server-side local-read `{name, path}` form is cut this epic
  (S5)** — the service reads no arbitrary host file at all, removing the whole class. AC for MR-023
  must include a negative curl: `GET /asset/..%2f..%2fmeta.json` → 404 (unknown stored name).
  *If the `path` form is ever revived from backlog,* its confinement **must** use a path-boundary
  check that rejects prefix confusion — `os.path.realpath(root) + os.sep` (or
  `os.path.commonpath([realpath(p), realpath(root)]) == realpath(root)`), realpath on **both** sides
  so a symlink inside an allowed root pointing out is rejected — **not** a naive
  `realpath.startswith(root)`, which admits `/srv/site-secrets` for root `/srv/site` (S3). That
  exact check, plus negative-path ACs (`path` outside roots → 400, symlink-escape → 400), is a hard
  precondition of reviving the feature. Recorded here so the backlog ticket inherits it.
- **Asset/history interaction.** Assets are review-scoped, not snapshotted per round; a replayed
  `history/round-N` draft renders against the *current* assets. Accepted as debt (Non-goals);
  cheaper than versioning blobs and matches "attach once, reuse across revisions."
- **Manifest race under concurrent attaches.** Read-modify-write of `assets.json` must hold `_lock`
  (as the source/feedback writers do). AC: writes go through `_lock`.

## Verification

Per-ticket gates: `python3 -m py_compile app.py` for every svc/ui change; `docker build` for the
math ticket (it touches the static route + adds vendored assets) and any infra-affecting slice;
`scripts/render-smoke.sh` from the **rebuilt container** for ui tickets. No test framework — curl +
render-smoke are the evidence.

**MR-022 (math), from the rebuilt container. The GATING proof is the woff2 body check, NOT the
`.katex` count (S1):**
```
docker build -t mdreview-service:rr . && \
docker run -d --rm -p 8138:8080 --name rr mdreview-service:rr
# --- GATING: fonts actually served as binary (catches the B1 crash + wrong MIME) ---
curl -sI localhost:8138/static/katex.min.css | grep -i 'content-type: text/css'        # 200 + text/css
curl -sI localhost:8138/static/KaTeX_Main-Regular.woff2 | grep -i 'content-type: font/woff2'  # 200 + font/woff2
curl -s localhost:8138/static/KaTeX_Main-Regular.woff2 -o /tmp/k.woff2 && file /tmp/k.woff2   # -> Web Open Font Format 2
#   ^ the file(1) check is the real gate: a UTF-8-read handler (B1) returns a 500 / empty body here,
#     which a HEAD/MIME check alone would NOT catch. A non-empty WOFF2 body proves _read_bytes ran.
# --- non-gating: math WIRING fired (element exists; does NOT prove fonts loaded) ---
id=$(curl -s -X POST localhost:8138/api/reviews -H 'Content-Type: application/json' \
  -d '{"title":"math","markdown":"# m\n\nInline $E=mc^2$ and display $$\\int_0^1 x\\,dx$$.\n\nPrices: $5 and $10 in prose.\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
scripts/render-smoke.sh "http://localhost:8138/review/$id" '.katex' '#article'
# expect: ok .katex (>=1 node) — proves renderMathInElement fired. NOT proof fonts loaded (S1).
# manual/visual: the "$5 and $10" line shows literal dollars, no .katex spanning them.
```

**MR-023 (asset storage), curl round-trip with expected JSON. URL keys on the `%2F`-free stored
name (S4); the GET reads binary (B1):**
```
id=...   # an existing review id
# attach a 1x1 png by base64 under its draft src name:
curl -s -X POST localhost:8138/api/reviews/$id/assets -H 'Content-Type: application/json' \
  -d '{"name":"/assets/pixel.png","content_b64":"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="}'
# expect: {"name":"/assets/pixel.png","stored":"<sha1hex>.png",
#          "url":"http://localhost:8138/api/reviews/<id>/asset/<sha1hex>.png","bytes":68,"ctype":"image/png"}
#   ^ note: NO %2F in the url — it keys on `stored`, not the human `name` (S4).
curl -s localhost:8138/api/reviews/$id/assets
# expect: {"assets":[{"name":"/assets/pixel.png","stored":"<sha1hex>.png","url":"...","bytes":68,"ctype":"image/png","ts":...}]}
# fetch by stored name -> binary bytes (proves the GET used _read_bytes, B1):
curl -s "localhost:8138/api/reviews/$id/asset/<sha1hex>.png" -o /tmp/p.png && file /tmp/p.png  # -> PNG image data
# back-compat: a review created before assets existed:
curl -s localhost:8138/api/reviews/$id/assets   # -> {"assets":[]} when none attached
# traversal / unknown-stored-name negative:
curl -s -o /dev/null -w '%{http_code}\n' "localhost:8138/api/reviews/$id/asset/..%2f..%2fmeta.json"  # -> 404
```

**MR-024 (MCP):** extend/run `mcp_smoke.py` — `tools/list` includes `attach_asset` + `list_assets`;
`tools/call attach_asset {id,name,content_b64}` returns the asset JSON (with `stored`+`url`);
`list_assets` lists it. (No `path` arg — that form is cut, S5.)

**MR-025 (viewer `<img>` rewrite), render-smoke from rebuilt container. The GATING proof is the
rewritten `src` value + a byte fetch, NOT element presence (S2):**
```
# review whose source references ![](/assets/pixel.png) with pixel.png attached (MR-023):
# (a) element exists:
scripts/render-smoke.sh "http://localhost:8138/review/$id" '#article img'
# (b) GATING: the <img src> was actually rewritten to the served stored-name URL. render-smoke
#     counts elements only, so assert the attribute via a small companion check on the dumped DOM
#     (e.g. grep the served /api/reviews/$id/asset/<sha1hex>.png URL out of the #article img src),
#     OR extend render-smoke with a src-asserting selector. A present-but-unrewritten <img>
#     (src still "/assets/pixel.png", 404ing) MUST fail this step.
# (c) GATING: that exact rewritten URL returns image bytes:
curl -s "localhost:8138/api/reviews/$id/asset/<sha1hex>.png" -o /tmp/img.png && file /tmp/img.png  # -> PNG image data
# Together (b)+(c) prove "rewrite fired AND resolves" — element presence (a) alone does not (S2).
# (d) PUBLIC_BASE smoke (S4): with MDREVIEW_PUBLIC_BASE set, the url has no %2F, so a path-segment
#     reverse proxy resolves it identically — confirm the served url contains no '%2F'.
```

**G7 (sprint close):** since product pages (`viewer.html`, `static/**`) are touched, the close
review must rebuild the container, run `curl /healthz` + `/api/reviews`, **and** run
`scripts/render-smoke.sh` against `/review/{id}` asserting both `.katex` (math wiring) and
`#article img` — but the **gating** image/font proofs are the binary-body checks above: the woff2
`file(1)` check (S1) and the rewritten-`src` + asset-byte fetch (S2), not the element counts. Save a
screenshot under `reviews/sprint-NN-render-evidence-*`. A green `.katex`/`#article img` count alone
is **not** sufficient evidence at G7 — record the woff2 and rewritten-`src` body checks too.

## Assumptions & open questions

Surface first; proceeding on the stated assumptions (invoked autonomously, no `--ask` this run).
None rise to BLOCKER-FOR-HUMAN — both forks have a safe, reversible default.

1. **(load-bearing) Math engine = KaTeX.** *Assumption:* vendor KaTeX (`katex.min.js` +
   `contrib/auto-render.min.js` + `katex.min.css` + flattened woff2 fonts). *Justification:* the
   brief prefers it (lighter/faster) and its auto-render delimiter scanner is precisely the
   prose-`$`-safe matcher required. *If wrong:* MathJax 3 is the documented fallback, same wiring
   point; re-open at MR-022 G4 rather than swap silently.
2. **(load-bearing) Asset model = (a) attach-asset, base64 only (the `path`/local-read variant is
   cut, S5); (b) not built; (c) folded into the viewer's basename match.** *Assumption:* build the
   attach-asset capability (the brief's "real fix"); store per-review under `assets/`; serve at a
   stable manifest-keyed URL keyed on the `%2F`-free stored name (S4); the viewer rewrites
   `<img src>` by matching the attached `name`. Option (b) "resolve relative to `source_path`" is
   **subsumed**: the viewer's basename/relative-path match against attached names covers
   source-relative `src` without a separate server resolver — and crucially the service can't read
   the agent's filesystem anyway (it's remote), so (b) only works if the bytes are attached, which
   is exactly (a). Option (c) site-root mapping (the former `MDREVIEW_ASSET_ROOTS` env form) is
   **deferred to backlog** (S5) — base64 delivers both P0s without a host-read code path.
   *Justification:* (a) is the only option that works for a remote agent over MCP and kills the
   base64-through-`update_source` problem. *If wrong:* the storage + URL scheme is reusable
   regardless of which resolver the viewer prefers.
3. **(load-bearing) Attach key convention = the agent attaches each image under the exact `src`
   string used in the draft, and the viewer matches by full path then basename.** *Assumption:* this
   keeps the match a direct lookup with no markdown rewrite and no `source.md` mutation.
   *Justification:* avoids divergence from the real draft (the brief's central complaint).
   *If wrong (e.g. two images share a basename across dirs):* the full-path match disambiguates;
   only a basename collision across different attached dirs is ambiguous — documented as a known
   edge, agent should attach under distinct names.
4. **(minor) Bytes transport = base64 in the JSON body**, not multipart. *Justification:* the
   existing handler is JSON-only (`_body_json`, app.py:168); multipart parsing is extra stdlib
   surface for no benefit when the MCP transport is JSON anyway. base64 inflates ~33% but is
   attach-once (not per-revision like the brief's rejected `update_source` blob), so the cost is
   bounded. *If a very large asset matters:* the deferred `path` form (backlog, S5) would avoid
   base64 — revive it then, with the S3 boundary check mandatory.
5. **(minor) MCP tool count = two** (`attach_asset`, `list_assets`), no `register_asset_dir`.
   *Justification:* dir registration is the host-read `path` form, cut this epic (S5); keeps the
   surface minimal and traversal-safe by default. `attach_asset` takes `content_b64` only.
6. **(minor) Static-font subdir handling = flatten + rewrite CSS**, not widen the route regex.
   *Justification:* keeps the router regex (and its no-`/` traversal property) unchanged. *If
   flattening proves brittle on a KaTeX bump:* the one-optional-`fonts/`-segment regex is the
   documented alternative.

## Review resolutions

Responding to `reviews/rich-rendering-plan-review-2026-06-18.md` (staff-critic, G1,
PASS-WITH-CONDITIONS: 1 BLOCKER + 5 SHOULD + 3 NIT). Author-applied 2026-06-18 (Europe/London).
The reviewer's verdict/frontmatter is left untouched — re-review sets it.

- **B1 (BLOCKER — fixed).** Verified `_read()` (app.py:49) is `encoding="utf-8"` and `_send()`
  (app.py:151–153) already byte-accepts. Added a **listed code change** for a binary-safe read: a
  `_read_bytes(path, default=b"")` helper (`open(path, "rb").read()`, catching `FileNotFoundError`),
  with the `/static/` route swapped onto it. Stated the route→read mapping explicitly: `/static/*`
  (fonts/css/js) and `GET /asset/{stored}` use `_read_bytes`; source/feedback/notes/meta keep
  `_read`/`_read_json`. Put this in the Service/Math section (new change "0"), the Assets section
  (asset GET binary-read paragraph), Key constraints (new "Binary-safe read" bullet), the Risks
  section (failure-mode 1 of 3), and the scope of both MR-022 and MR-023 in the ticket table.
  Verification gates the woff2 body with `file(1)`, which a HEAD/MIME check would miss.
- **S1 (fixed).** Reconciled Verification with Risks: the MR-022 gating proof is now the
  `curl -sI .../static/*.woff2` MIME check **plus** a `file(1)` body check (promoted from afterthought
  to the gate); the `.katex` render-smoke is explicitly downgraded to "math wiring fired, NOT fonts
  loaded." Stated in the MR-022 Verification block, the ticket-table scope note, and the G7 block.
- **S2 (fixed).** MR-026→MR-025's image smoke gating is now (a) element exists, (b) a DOM assertion
  that `img.src` equals the served stored-name URL (a present-but-unrewritten 404ing `<img>` must
  fail this), and (c) a `curl` of that exact URL returning image bytes via `file(1)`. Element
  presence alone is explicitly marked insufficient. In the MR-025 Verification block, the
  execution-order note, the ticket-table scope note, and the G7 block.
- **S3 (addressed — feature cut, check recorded for revival).** Since MR-024 is cut (S5), the
  `startswith` prefix-confusion bug cannot ship in this epic. The correct boundary check —
  `os.path.realpath(root) + os.sep` (or `os.path.commonpath` with realpath on **both** sides so a
  symlink inside an allowed root pointing out is rejected), **never** naive
  `realpath.startswith(root)` (which admits `/srv/site-secrets` for root `/srv/site`) — is recorded
  in the Risks section and the Non-goals MR-024 entry as a **hard precondition of reviving** the
  feature, with the negative-path ACs.
- **S4 (fixed by design).** Decoupled the match key from the served key: the served asset URL is
  built from the `%2F`-free `sha1+ext` **stored name** (`/asset/{stored}`), not the human `name`.
  The human `name` (possibly `/assets/x.png`) stays only as a manifest match field. The served path
  therefore never contains an encoded slash, so the documented reverse-proxy / PUBLIC_BASE
  deployment can't 404 it. Updated the Storage section (new "Served URL keys on the stored name"
  bullet), the route table (`/asset/{stored}`, regex `[A-Za-z0-9._-]+`), the URL-form bullet, the
  viewer rewrite step, Key constraints, and added a PUBLIC_BASE `%2F`-free smoke to MR-025
  Verification.
- **S5 (decided — CUT MR-024).** Took the reviewer's recommended (and lower-risk) default: **dropped
  the `{name, path}` server-side local-read form from this epic.** base64 delivers both P0s; a
  no-auth, id-only service should not carry an arbitrary-host-read code path until something needs
  it. Moved it to Non-goals (with the S3 revival precondition), dropped the `path` arg from
  `attach_asset`, removed the MR-024 ticket, and renumbered. **Ticket count is now five.**
- **N1 (fixed — cheap).** Removed the false "ordering prevents shadowing" rationale: under
  `re.fullmatch` (verified) `/api/reviews/{id}` cannot match `/assets` or `/asset/{stored}`
  regardless of order. Kept the insertion location as convention only, and explicitly flagged
  "do not propagate as a constraint" in Key constraints and the route table.
- **N2 (fixed — cheap).** Made the KaTeX insertion point precise: between viewer.html:205
  (`await renderMermaid()`) and :206 (`reconcile()`), with the line sequence cited. Added the
  render-once AC: `renderComments()` re-runs on the 250/800/1600ms `setTimeout` fallbacks
  (viewer.html:402) and re-walks the KaTeX-modified DOM, so the smoke must confirm a math-quoting
  note's card renders exactly once.
- **N3 (no change needed).** MR-027→MR-026 docs-sweep is already correctly flagged
  non-carry-over-eligible per the G7 pass-condition row + Definition of Done. Reviewer confirmed.
