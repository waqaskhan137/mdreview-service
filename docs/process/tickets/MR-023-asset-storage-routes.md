---
id: MR-023
title: Per-review asset storage + manifest + POST/GET /assets, GET /asset/{stored} (base64, binary read, stored-name URL)
status: ready
layer: svc
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: []
branch:
created: 2026-06-18
updated: 2026-06-18
---

## Goal

An agent can **attach a draft's images to a review once** (a small base64 call, not a blob shoved
through `update_source`) and the service serves them at a stable per-review URL — so a math-/image-
heavy draft no longer needs a second static server or `src` rewrites. This is the service half of
P0b. Assets live under the review's own directory, survive every `PUT /source` revision, and are
served binary-safely with a declared MIME. base64 is the **only** transport (the `{name,path}`
server-side local-read form is cut — see epic Non-goals / S5).

## Acceptance criteria

- [ ] **Storage.** Per review, a sibling `assets/` dir (`_dir(rid)/assets/`) holds raw bytes plus
      `assets.json` — a manifest of `[{name, stored, bytes, ctype, ts}]`. `assets/` sits beside
      `history/`; `snapshot_round` (`app.py:105`) and the source/feedback writers never touch it, so
      assets survive every `PUT /source`. Removed by the existing `DELETE` rmtree.
- [ ] **Stored-name safety.** The on-disk/served name is `sha1(bytes)[:16]` + a sanitized original
      extension (e.g. `<sha1hex>.png`). The client `name` is kept **only** as a manifest match
      field. Identical bytes dedupe. No `/`, `..`, or NUL can appear in a stored name by construction.
- [ ] **Routes** (new `re.fullmatch` rows in `route()`, `RID` from `app.py:38` reused unchanged):
      - `POST /api/reviews/{id}/assets` body `{name, content_b64}` → `{name, stored, url, bytes, ctype}`.
      - `GET  /api/reviews/{id}/assets` → `{assets:[{name, stored, url, bytes, ctype, ts}]}`.
      - `GET  /api/reviews/{id}/asset/{stored}` → raw bytes, served via **`_read_bytes`** (B1) with
        the stored `ctype`. The trailing segment is resolved **against the manifest only** (`stored`
        lookup); an unknown `stored` is `404` — the handler never path-joins the request segment.
- [ ] **Served URL keys on the stored name (S4).** The returned `url` is
      `{self._base()}/api/reviews/{id}/asset/{stored}` (`_base()` is PUBLIC_BASE-aware, `app.py:176`)
      — it contains **no `%2F`**, so a reverse proxy can't mangle it. The human `name` is never in
      the URL path.
- [ ] **Binary read (B1).** `GET /asset/{stored}` reads via `_read_bytes` (added in MR-022, or here
      if this lands first), never the UTF-8 `_read` (`app.py:49`).
- [ ] **Locking.** The manifest read-modify-write on attach holds the module `_lock`, mirroring the
      source/feedback/snapshot writers.
- [ ] **Back-compat.** Existing reviews have no `assets.json`; readers default to `[]`
      (`_read_json(..., [])`). `GET /assets` on a pre-existing review returns `{"assets":[]}`.
- [ ] **GATING curl round-trip (from rebuilt container):** attach a 1×1 png by base64 under
      `name:"/assets/pixel.png"` → response has `stored:"<sha1hex>.png"`, `url` with **no `%2F`**,
      `bytes` + `ctype:"image/png"`; `GET /assets` lists it; `GET /asset/<sha1hex>.png -o /tmp/p.png
      && file /tmp/p.png` → **PNG image data** (proves `_read_bytes` ran — a UTF-8 read 500s here).
- [ ] **Negative / traversal:** `GET /asset/..%2f..%2fmeta.json` → `404` (unknown stored name; no
      path join).
- [ ] Local validation passes: `python3 -m py_compile app.py`; curl round-trip + negative above.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — Service (Assets) section, Storage/Stored-name-safety/
  Routes bullets, Verification (MR-023 block), Risks (path traversal). The served URL **must** key on
  the `%2F`-free `sha1+ext` stored name (S4); base64 is the sole transport (S5).
- Existing storage patterns to mirror: `_dir(rid)`, `_read_json(path, default)`, `snapshot_round`
  (`app.py:105`), the `_lock`-guarded writers, `_base()` (`app.py:176`), `_body_json` (`app.py:168`).
- History interaction is **out of scope** (Non-goals): assets are review-scoped, not snapshotted
  per round.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Server-side local-dir `{name,path}` attach behind `MDREVIEW_ASSET_ROOTS` — **cut to backlog (S5)**;
  if revived, must ship the `os.path.realpath(root)+os.sep` boundary check (S3) + negative-path ACs.
