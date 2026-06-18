---
review_of: sprints/sprint-06.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS
status: resolved
---

# Sprint-06 (rich-rendering) — G7 close review

**Verdict: PASS.** All five committed tickets (MR-022..026) are implemented and their acceptance
criteria hold against the shipped code, reproduced independently from the rebuilt container on
`:8138` (rebuild already in place) — math renders for all four delimiters with prose/currency `$`
literal, assets attach/serve/survive `PUT /source`, the viewer rewrites `<img src>`, the MCP tools
round-trip, and docs match the surface. The MR-022 mechanism deviation (marked extension instead of
the plan's auto-render post-pass) is justified: I reproduced both blocking reasons. No blockers; two
NITs.

## Per-ticket AC check

### MR-022 — KaTeX math (marked extension) + binary-safe static route — MET
- **B1 binary read / S1 gating (woff2 body):** `_read_bytes` (`app.py:59`) added; `/static/` serves
  through it (`app.py:466`). Reproduced via GET header-dump (HEAD is 501 — no `do_HEAD`):
  `KaTeX_Main-Regular.woff2` → 200 `font/woff2`, `Content-Length: 26272`, body `file(1)` = "Web Open
  Font Format (Version 2)". `katex.min.css` → 200 `text/css` (21572 B); `katex.min.js` → 200
  `text/javascript`; unknown `/static/nope.woff2` → 404. A UTF-8 read would have 500'd here — it did not.
- **Content-type map:** `_CTYPES`/`_ctype_for` (`app.py:74-93`) cover css/woff2/woff/ttf/js + image types.
- **KaTeX vendored + fonts flat:** 20 `KaTeX_*.woff2` in `static/`; CSS has zero `fonts/` subdir refs,
  20 distinct woff2 referenced = 20 present, no legacy `.woff`/`.ttf` fallbacks. Flat `/static/` regex
  serves them unchanged.
- **All four delimiters render; prose/currency/code/escaped literal:** reproduced via headless-Chrome
  `--dump-dom`. KaTeX `<annotation>` (TeX-source) list is exactly `E=mc^2` (`$…$`), `a+b=c` (`\(…\)`),
  `\int_0^1 x\,dx` (`$$…$$`), `\sum_{i=1}^n i` (`\[…\]`), plus `a_i`, `x^*`. `$5 and $10`, `\$5`, lone
  `$`, and `` `$x$` `` are absent from the annotations and present as literal text in the rendered DOM.
  2 `katex-display` nodes confirm both display delimiters render as display. The deviation screenshot
  (`review-math-image.png`) shows the same visually.
- **Deviation verified (not waved through):** ran the vendored `marked.min.js` on single-backslash
  source. Vanilla `marked.parse` turns `\(a+b=c\)`→`(a+b=c)`, `\[x\]`→`[x]`, `\$5`→`$5` — i.e. marked
  consumes the backslash delimiters before any post-pass could see them. Claim (a) is real; the
  marked-extension (tokenize-during-parse) is the correct fix. Claim (b) (auto-render pairs prose `$5
  and $10`) is consistent with KaTeX auto-render's bare-`$` scanner; not separately reproduced because
  the chosen mechanism sidesteps it and (a) alone is dispositive. Engine is still KaTeX.
- **Inline-`$` regex soundness:** probed `/^\$([^\s$](?:[^$\n]*[^\s$])?)\$/` against real math and
  currency. Real math (`$x$`, `$a + b$`, `$f(x)=x^2$`, `$\frac{1}{2}$`, `$\{1,2\}$`) renders;
  leading/trailing-space (`$ x$`, `$x $`), `$5 for $10`, `a $5 bill` stay literal. The only math
  matches on `$100$200`/`$a$b$c$` are inherently-ambiguous adjacent-pair inputs, not realistic prose —
  defensible. No false-negative on real math surfaced.
- **Default-safe:** a no-math/no-asset draft renders 0 katex nodes, prose `$20`/`$30` literal, code
  literal, list intact.
- **N2 render-once:** card rendering rebuilds from the notes array each `renderComments` pass (not
  append), so the `setTimeout` re-walks can't duplicate; math-quoting notes fall back to the block
  card (documented). Structurally sound.
- **No redundant Dockerfile change; py_compile + docker build OK** (rebuild is the running `:rr` image).

### MR-023 — Asset storage + routes (base64, binary read, stored-name URL) — MET
- **Storage / survives `PUT /source`:** reproduced. Attach → asset count 1 → `PUT /source` (revision
  →1, `history/round-0` snapshotted) → count still 1, bytes still fetchable. On-disk `assets/` +
  `assets.json` are siblings of `history/` (not under it). This is the brief's core ask.
- **Stored-name safety:** `_stored_name` (`app.py:208`) = `sha1(bytes)[:16]` + sanitized ext.
  Stress-tested 13 hostile names (`../../../etc/passwd`, NUL, `%2e%2e%2f`, `evil.png/../`) — every
  result is `/`-, `..`-, NUL-, `%`-free by construction.
- **Routes + served URL (S4):** attach → `{stored:"490e9f0db52061ac.png", url:.../asset/490e…png,
  bytes:70, ctype:"image/png"}` — no `%2F` in the URL. `GET /assets` lists it; `GET /asset/<stored>` →
  200 `image/png`, `file(1)` = "PNG image data, 1x1" (proves `_read_bytes`/B1).
- **Negatives:** `GET /asset/..%2f..%2fmeta.json` → 404; unknown stored → 404; POST missing
  `content_b64` → 400; POST invalid base64 → 400 (`b64decode(validate=True)`, `app.py:427`).
- **Back-compat:** fresh review `GET /assets` → `{"assets":[]}`.
- **Locking:** attach POST takes `_lock` around `attach_asset` (`app.py:430`).

### MR-024 — MCP attach_asset + list_assets — MET
- `mcp_smoke.py` against `:8138`: all assertions PASS, including "tools/list returns exactly the 10
  tools", "attach_asset → stored sha1+ext, isError false", "list_assets → includes the attached asset".
- Schema: `attach_asset {id,name,content_b64}` (no `path` — S5), `list_assets {id}`
  (`mcp_server.py:90-110`); dispatch maps 1:1 to the HTTP routes (`mcp_server.py:187-190`); docstring
  and `# The 10 tools` comment updated. `py_compile` of all three modules OK.

### MR-025 — Viewer `<img src>` rewrite — MET
- `rewriteAssetImages` (`viewer.html:213`) reads `getAttribute('src')` (authored value), fetches
  `/assets` once (only if imgs present), builds full-name + basename maps, repoints `img.src` to the
  served `%2F`-free URL. Reproduced in headless Chrome: `/assets/pixel.png` and `../img/pixel.png`
  (basename match) both repoint to `.../asset/490e9f0db52061ac.png`; `/assets/missing.png` stays
  literal; `data:` and `https://example.com/...` untouched.
- **S2 served-bytes gate:** curl of the exact rewritten URL → `file(1)` = "PNG image data, 1x1".
- `render-smoke.sh` on a clean math+image fixture: `.katex` 2, `img` 1, `#article` 1, exit 0.
- No `source.md` mutation (DOM-only).

### MR-026 — Docs sweep — MET
- **README:** three asset rows + base64 body + stored-name URL (`README.md:54-56`), KaTeX/math line,
  Assets paragraph (base64-only, attach-once, survives revisions), MCP tools list. No `path`/local-dir
  overclaim.
- **CLAUDE.md:** "Rich content: math and images" section — math delimiters + prose-`$` literal, the
  attach_asset curl flow, the SVG/animation one-line note (line 63, per the brief), and the
  Mermaid/front-matter "already works" correction (line 44).
- **AGENTS.md:** MCP tool list + math/image note cross-linking CLAUDE.md.
- **mcp_server.py docstring:** "10 schemas"/"10 tools" consistent.
- Docs ↔ implementation cross-check: no documented-but-missing endpoint/tool; no overclaim.

## Findings

- **[NIT]** Asset `ctype` is derived from the attacker-controllable `name` extension
  (`_ctype_for(name)`, `app.py:222`), so attaching `name:"x.html"` (or `.svg`) makes the service
  serve attacker bytes as `text/html`/`image/svg+xml` from its own origin — a stored-XSS shape.
  Blast radius is bounded to whoever already holds the (unguessable, no-auth) review id, and the same
  actor can already inject script-bearing markdown via `update_source`, so this adds no new trust
  boundary. Worth a one-line note in the asset code/docs that attached bytes are served with a
  name-derived MIME and the service is single-tenant-by-id; consider clamping non-image extensions to
  `application/octet-stream` if assets are ever exposed multi-tenant. Not blocking.
- **[NIT]** `render-smoke.sh`'s documented `#article img` selector has no descendant combinator, so the
  evidence and AC use the `img` tag selector instead (already called out in MR-025 follow-ups). The
  stronger `img.src == served URL` + served-bytes checks are the real gate; the harness limitation is
  pre-existing, not introduced here. Backlog hygiene at most.

## What's good
The B1/S1 binary-read fix is correct and is the right gating proof (woff2 `file(1)` body, not element
count). The match-key/served-key decoupling (human `name` for matching, `sha1+ext` for the URL)
genuinely removes the `%2F`-through-proxy class at the design level. The MR-022 deviation was
diagnosed correctly and resolved at G4 rather than silently swapped — exactly the documented process.

## Resolution log

- **2026-06-18 — NIT 1 (asset content-type from attacker-controllable `name`): addressed.** Added
  `X-Content-Type-Options: nosniff` to all responses (`app.py` `_send`) and a README note that asset
  serving inherits the no-auth/id-only posture — treat an attached asset like the draft's own HTML
  (commit "harden(svc): nosniff + asset-serving no-auth doc note"). Multi-tenant ctype clamping
  remains a documented backlog item, not needed for the current single-tenant-by-id posture. Math/
  fonts/assets re-validated intact after the change.
- **2026-06-18 — NIT 2 (render-smoke `#article img` selector): accepted.** Pre-existing harness
  limitation (no descendant combinator); the `img` tag selector + the stronger `img.src == served
  URL` and served-bytes checks are the real gate. Recorded in MR-025 follow-ups; no change.
- **2026-06-18 — Verdict PASS, no blockers/shoulds. Sprint-06 closed at G7.**
