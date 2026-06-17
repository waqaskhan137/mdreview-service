---
id: MR-025
title: Viewer rewrites local/relative/site-root <img src> to served asset URLs
status: ready
layer: ui
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: [MR-023]
branch:
created: 2026-06-18
updated: 2026-06-18
---

## Goal

The viewer makes attached images **visibly render**: it fetches the review's asset manifest and
rewrites local/relative/site-root `<img src>` to the served (stored-name) URLs, so a draft using
`/assets/x.png` or `../img/y.svg` renders without the agent mutating `source.md`. This is the UI
half of P0b and the phase that turns "bytes are served" into "the image painted."

## Acceptance criteria

- [ ] **Manifest fetch.** On `load()`, fetch `GET {API}/assets` → `{assets:[{name, stored, url}]}`
      once per render.
- [ ] **Rewrite rule.** For each `<img>` in `#article` whose `src` is **not** absolute/`http(s):`/
      `data:`, match against the manifest by `name` — **full draft `src` first, then `basename`
      fallback** — and on a match set `img.src = matched.url`. The `url` is the **stored-name
      (`%2F`-free) served URL** (S4), decoupled from the human match key. Site-root (`/assets/foo.png`)
      and source-relative (`../img/foo.svg`) both reduce to a `name` the agent attached.
- [ ] **No regression.** Unmatched local `<img>` keep their original `src` (they 404 as before —
      today's behavior); absolute and `data:` images are untouched. A draft with no images / no
      manifest renders exactly as today (`{"assets":[]}` → no rewrites).
- [ ] **No source mutation.** `source.md` is never rewritten; the rewrite is render-time only on the
      DOM. The draft stays byte-identical to the real one.
- [ ] **GATING proof (S2), render-smoke from rebuilt container:** for a review whose source
      references `<img src="/assets/pixel.png">` with `pixel.png` attached (MR-023):
      `scripts/render-smoke.sh "/review/$id" '#article img'` passes **and** the rewritten
      `img.src` equals the served `/api/reviews/{id}/asset/<sha1hex>.png` URL (assert the value, not
      just presence) **and** a `curl` of that exact URL returns image bytes (`file(1)` → image).
      Element presence alone is **insufficient**.
- [ ] Local validation passes: `python3 -m py_compile app.py`; render-smoke + the `img.src` value
      assertion + asset-URL curl above.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — UI (Assets) section, the match-key vs served-key
  decoupling (S4), Verification (MR-025 block). Match key = the `name` the agent attached; served
  key = the `%2F`-free stored name.
- Wire near the existing render path in `viewer.html` `load()` — after `marked.parse(md)` produces
  `html`, operate on the `#article` DOM (interplays with `numberBlocks()` at `viewer.html:210` —
  rewrite `<img src>` so the served image survives reparenting). The live-reload `poll()→load()`
  path re-runs it for free.
- Known edge (assumption 3): two images sharing a basename across different attached dirs — the
  full-path match disambiguates; a pure basename collision is the one ambiguous case (agent should
  attach under distinct `name`s). Documented, not blocking.
- Depends on MR-023's `GET /assets`.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- "Missing asset" hint on unmatched local `<img>` — optional P2 nicety, not required here.
