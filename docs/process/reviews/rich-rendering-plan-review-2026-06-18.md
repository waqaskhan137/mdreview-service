---
review_of: epics/rich-rendering-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS-WITH-CONDITIONS
status: resolved
---

## Verdict

The plan is directionally sound and unusually well-reasoned on the parts it chose to examine: the
KaTeX flatten-and-rewrite path, the `sha1+ext` stored name, the manifest-only GET, and the
`MDREVIEW_ASSET_ROOTS` default-off posture are all correct, and I verified the load-bearing code
claims (the no-`/` static regex, the JSON-only body, the `COPY static/` Dockerfile line, route
non-shadowing) against the source — they hold. But it has **one true blocker**: the plan describes
the only service-side math change as "extend the content-type map," and that is not enough — the
existing reader is UTF-8-only and will *crash* on every font and every stored image byte. That gap
plus a small cluster of evidence-sufficiency and security-precision conditions must be closed
before tickets are spawned, or the implementer will follow the plan literally and ship a static
route that 500s on `.woff2`.

## Findings

### [BLOCKER] B1 — The static/asset read path is UTF-8-only; it will crash on fonts and image bytes. The plan never names a binary read.

The plan's Service/Math section says "the *only* service-side change is the `/static/` route" and
scopes that change to *extending the content-type map*. That is incomplete to the point of being
wrong. `_read()` (`app.py:49`) opens with `encoding="utf-8"` and returns `str`; the `/static/`
handler serves via `self._send(200, _read(p), ctype)` (`app.py:339`). Every existing static file
(`marked.min.js`, `mermaid.min.js`) is UTF-8 text, so this has never been exercised on binary. I
verified the failure directly: reading real `.woff2` bytes through that helper raises
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0x80` — an *uncaught* exception in the
request handler, not a served file. The same defect lands on the new `GET /asset/{name}` route the
moment it serves a PNG/JPEG/SVG-binary via `_read()`.

`_send()` already accepts `bytes` (`app.py:151–153`), so the fix is small but it is a *code change
the plan does not list*: introduce a binary read (`open(p, "rb").read()`) for the font/asset
branches (and likely a `_read_bytes()` helper mirroring `_read()`). **Required before G1:** the
plan's app.py change list for MR-022 (static fonts/css) and MR-023 (asset bytes) must explicitly
include the binary read; "extend the content-type map" alone produces a route that crashes on the
first font request. Verify with `curl -sI .../static/KaTeX_Main-Regular.woff2` returning 200 +
`content-type: font/woff2` *and a non-empty body that `file(1)` identifies as WOFF2* — a HEAD/MIME
check alone will not catch a body that the handler failed to write.

### [SHOULD] S1 — Render-smoke asserting a `.katex` node is false confidence for "fonts loaded"; the plan's own Verification contradicts its Risks.

The Risks section correctly says the AC must "assert a `.katex` node *with glyphs* (font actually
loaded), not just the element present." But the Verification section's actual command is
`scripts/render-smoke.sh "...review/$id" '.katex' '#article'`, which (per `scripts/render-smoke.sh`,
verified — it counts elements matching a selector in the dumped DOM) only proves the `.katex`
element *exists*. `renderMathInElement` creates `.katex` subtrees from the JS alone with zero fonts
loaded; the element count is identical whether the woff2 served or 404'd. So the smoke as written
cannot fail on the exact regression B1 describes. render-smoke has no way to assert glyph metrics
via a CSS selector. **Resolve by** making the font-load proof the two `curl -sI .../static/*.woff2`
MIME+body checks already in the MR-022 block (promote them from afterthought to the gating
assertion, and add the `file(1)` body check from B1), and downgrade the `.katex` selector to "math
wiring fired," not "fonts loaded." State this split in the MR-022 AC so the implementer doesn't
treat a green `.katex` smoke as sufficient.

### [SHOULD] S2 — Same false-confidence pattern on MR-026's image smoke: `'#article img'` proves an element, not a load or a rewritten src.

MR-026's smoke is `scripts/render-smoke.sh ".../review/$id" '#article img'`. A broken `<img>` whose
`src` still 404s is present in the dumped DOM as an element, so this passes even if the rewrite
logic never fired or the asset URL is wrong. The G7 row promises "a loaded `<img>` (with the
rewritten served `src`)" — render-smoke cannot assert "loaded" or the `src` value. **Resolve by**
pinning the AC to: (a) the `<img>` element exists, (b) a DOM check that its `src` equals the served
`{base}/.../asset/...` URL (render-smoke would need a src-asserting selector or a small companion
check), and (c) a `curl` of that exact URL returns 200 + image bytes. The plan gestures at (c) but
doesn't make (b) gating; without (b) the "rewrite happened" claim is unproven by the evidence.

### [SHOULD] S3 — The `MDREVIEW_ASSET_ROOTS` confinement is described as "realpath must start with a root" — the naive `startswith` is the classic prefix-confusion bug.

The plan says the resolved `os.path.realpath` "must start with one of those roots or it's a 400."
A literal `realpath.startswith(root)` admits `/srv/site-secrets/passwd` when the root is
`/srv/site` (verified: it shares the string prefix but is not under the dir). The correct check is
`startswith(root + os.sep)` (or `os.path.commonpath([realpath, root]) == root`), plus realpath on
*both* sides so a symlink inside an allowed root that points out is also rejected. The feature is
off by default so this is not a blocker, **but if MR-024 ships, this exact separator-boundary check
must be written into its AC** — a plan-gate review exists to stop precisely this footgun reaching
the implementer as "start with."

### [SHOULD] S4 — The attach-key-as-full-`src` convention yields URLs with encoded slashes (`%2F`) that the documented production proxy may mangle.

The convention stores `name` as the exact draft `src` (e.g. `/assets/x.png`), and the plan's own
example serves it at `.../asset/%2Fassets%2Fpixel.png`. `urlparse` keeps `%2F` encoded (verified —
`route()` uses `urlparse(self.path).path` at `app.py:203`, no decode), so the app itself is fine.
But this service is deployed behind a reverse proxy (the live landing-page stack at
mdreview.waqasrana.space); many proxies (nginx default, several CDNs) reject or normalize `%2F` in
a path segment and will 404 the asset before it reaches the app — invisible in a localhost smoke,
broken in the relayed/PUBLIC_BASE path that is the feature's whole reason for `_base()`. Since the
viewer's match already has a *basename* fallback, the slash in the stored `name` buys little. **At
minimum** call this out as a known risk with the localhost-vs-proxy asymmetry, add a smoke against
the PUBLIC_BASE form, and consider storing/serving under a `%2F`-free key (e.g. the basename, or a
hash) while keeping the full path only as a manifest match field. This is the one place the
author's self-identified "least-sure decision" (the attach key) actually bites, and it bites in
production, not in the unit.

### [SHOULD] S5 — Consider cutting the `path`/local-read form (MR-024) from this epic, not just gating it.

The plan defends shipping `{name, path}` behind the env allow-list, and the reasoning is sound: it
is off unless an operator opts in, realpath-confined, and the brief asked for `register_asset_dir`.
But the base64 path (MR-023) fully delivers both P0s; `{name, path}` adds host-filesystem-read code
and attack surface (see S3) to a no-auth service for a convenience the brief lists as one of
several "best first" options, not a hard requirement. The plan already makes MR-024 optional and
foldable — I'd go further and **defer it to backlog for this epic**, shipping only base64. If kept,
S3 is mandatory and the negative-path AC (`path` outside roots → 400, symlink-escape → 400) must be
explicit. This is a preference with a real trade-off, your call — but a no-auth service should lean
toward not having an arbitrary-host-read code path at all until something needs it.

### [NIT] N1 — Route-ordering rationale is slightly wrong (harmless).

The plan inserts the asset routes "before `/review/{id}` and `/static/...` so the `{id}` pattern
can't shadow them." Verified: every route uses `re.fullmatch`, so `/api/reviews/{id}` does **not**
match `/api/reviews/{id}/assets` or `/asset/{name}` regardless of order (checked all four
combinations). The ordering is fine to keep, but the stated reason (shadowing) doesn't apply with
`fullmatch`; don't let it propagate into the ticket as a load-bearing constraint.

### [NIT] N2 — KaTeX/note-anchoring degradation is acceptable, but the stated insertion point is imprecise.

The plan says run KaTeX "after `numberBlocks()` + `await renderMermaid()`," which places it before
`reconcile()` (`viewer.html:206`) and `render()` (`:207`). `reconcile()` re-anchors notes by
`blk.innerText.includes(nt.quote)` (`:232`); a prose note in a block that also contains math still
matches because only the math substring changes. `highlightNote()` (`:334`) already returns `null`
and falls back to the block anchor when a range can't be surrounded (`:346,:349`), so a note
quoting raw LaTeX degrades to a block card rather than vanishing — acceptable, and the plan is right
that prose notes (the dominant case) are unaffected. Two precisions for the AC: (1) state the exact
line KaTeX is inserted at relative to `reconcile`/`render`, since "after renderMermaid" is
ambiguous about the reconcile boundary; (2) `renderComments()` re-runs on the 250/800/1600ms
`setTimeout` fallbacks (`viewer.html:402`) and re-walks the KaTeX-modified DOM each time — confirm
in the smoke that a math-quoting note renders its card exactly once, not that this is silently fine.

### [NIT] N3 — MR-027 (docs sweep) carry-over treatment is correct.

Verified against the G7 pass-condition row and the Definition of Done: a docs-sweep ticket is "NOT
eligible for carry-over" and deferred docs are force-closed at sprint close. MR-027 is correctly
flagged non-carry-over-eligible. No change needed; noted because the prompt asked.

## What I verified (so the author can trust the blocker list)

- `app.py:49` `_read()` is `encoding="utf-8"` → `UnicodeDecodeError` on binary (reproduced). B1.
- `app.py:333` static regex `[A-Za-z0-9._-]+` with `re.fullmatch` excludes `/` → subdirs 404. True.
- KaTeX font filenames (`KaTeX_Main-Regular.woff2` …) are `[A-Za-z0-9._-]` only → flatten serves
  them; CSS `url()` refs all use the `fonts/` prefix → the rewrite the plan describes is required
  and sufficient. True.
- `app.py:168` `_body_json` is JSON-only → base64-in-JSON is the right transport. True.
- `Dockerfile:9` `COPY static/ ./static/` → new static files need no Dockerfile change. True.
- `urlparse(self.path).path` (`app.py:203`) does not decode `%2f` → manifest-only lookup makes
  `/asset/..%2f..%2fmeta.json` a 404. True (the traversal model is sound).
- Asset route regexes do not shadow / get shadowed by existing routes under `fullmatch`. True.
- `MR-021` is the highest existing ticket → `MR-022` is the correct next ID. True.
- `scripts/render-smoke.sh` counts matching DOM elements (cannot assert load/attribute value). True
  — basis for S1/S2.

## Resolution log

_Author (mdreview-planner) applied 2026-06-18 (Europe/London). Verdict/frontmatter unchanged —
re-review sets them. Full detail in the plan's "Review resolutions" section._

- **B1 (BLOCKER) — fixed.** Added a listed code change: `_read_bytes(path, default=b"")`
  (`open(path,"rb").read()`) with the `/static/` route swapped onto it; `GET /asset/{stored}` also
  serves via `_read_bytes`. Route→read mapping stated (binary routes vs. text source/feedback/meta).
  In MR-022 + MR-023 scope. Verification gates the woff2 body with `file(1)`.
- **S1 — fixed.** MR-022 gating proof is now the woff2 MIME + `file(1)` body check; `.katex`
  render-smoke downgraded to "wiring fired, not fonts loaded." Reconciled Verification with Risks.
- **S2 — fixed.** MR-025 (was MR-026) image proof pinned to: element exists + `img.src` == served
  stored-name URL + `curl` of that URL returns image bytes. Element presence alone marked insufficient.
- **S3 — addressed.** MR-024 cut (see S5), so `startswith` cannot ship. The correct
  `realpath(root)+os.sep` / `commonpath` (realpath both sides) boundary check + negative-path ACs
  recorded as a hard precondition of any future revival, in Risks + Non-goals.
- **S4 — fixed by design.** Served URL keys on the `%2F`-free `sha1+ext` stored name
  (`/asset/{stored}`); human `name` is a manifest match field only. No encoded slash reaches the
  proxy. Added a PUBLIC_BASE `%2F`-free smoke.
- **S5 — decided: CUT.** Dropped the `{name, path}` local-read form to backlog; base64-only.
  `path` arg removed from `attach_asset`; ticket renumbered. **Ticket count now five.**
- **N1 — fixed.** Removed the false "ordering prevents shadowing" rationale (`re.fullmatch`); kept
  ordering as convention, flagged "not a constraint."
- **N2 — fixed.** KaTeX insertion pinned between viewer.html:205 and :206 (before `reconcile`);
  render-once AC added against the `renderComments()` setTimeout re-walks (viewer.html:402).
- **N3 — no change.** MR-026 docs sweep already non-carry-over-eligible.
