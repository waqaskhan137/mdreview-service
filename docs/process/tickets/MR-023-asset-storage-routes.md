---
id: MR-023
title: Per-review asset storage + manifest + POST/GET /assets, GET /asset/{stored} (base64, binary read, stored-name URL)
status: done
layer: svc
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: []
branch: dev
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

- [x] **Storage.** Per review, a sibling `assets/` dir (`_dir(rid)/assets/`) holds raw bytes plus
      `assets.json` — a manifest of `[{name, stored, bytes, ctype, ts}]`. `assets/` sits beside
      `history/`; `snapshot_round` (`app.py:105`) and the source/feedback writers never touch it, so
      assets survive every `PUT /source`. Removed by the existing `DELETE` rmtree.
- [x] **Stored-name safety.** The on-disk/served name is `sha1(bytes)[:16]` + a sanitized original
      extension (e.g. `<sha1hex>.png`). The client `name` is kept **only** as a manifest match
      field. Identical bytes dedupe. No `/`, `..`, or NUL can appear in a stored name by construction.
- [x] **Routes** (new `re.fullmatch` rows in `route()`, `RID` from `app.py:38` reused unchanged):
      - `POST /api/reviews/{id}/assets` body `{name, content_b64}` → `{name, stored, url, bytes, ctype}`.
      - `GET  /api/reviews/{id}/assets` → `{assets:[{name, stored, url, bytes, ctype, ts}]}`.
      - `GET  /api/reviews/{id}/asset/{stored}` → raw bytes, served via **`_read_bytes`** (B1) with
        the stored `ctype`. The trailing segment is resolved **against the manifest only** (`stored`
        lookup); an unknown `stored` is `404` — the handler never path-joins the request segment.
- [x] **Served URL keys on the stored name (S4).** The returned `url` is
      `{self._base()}/api/reviews/{id}/asset/{stored}` (`_base()` is PUBLIC_BASE-aware, `app.py:176`)
      — it contains **no `%2F`**, so a reverse proxy can't mangle it. The human `name` is never in
      the URL path.
- [x] **Binary read (B1).** `GET /asset/{stored}` reads via `_read_bytes` (added in MR-022, or here
      if this lands first), never the UTF-8 `_read` (`app.py:49`).
- [x] **Locking.** The manifest read-modify-write on attach holds the module `_lock`, mirroring the
      source/feedback/snapshot writers.
- [x] **Back-compat.** Existing reviews have no `assets.json`; readers default to `[]`
      (`_read_json(..., [])`). `GET /assets` on a pre-existing review returns `{"assets":[]}`.
- [x] **GATING curl round-trip (from rebuilt container):** attach a 1×1 png by base64 under
      `name:"/assets/pixel.png"` → response has `stored:"<sha1hex>.png"`, `url` with **no `%2F`**,
      `bytes` + `ctype:"image/png"`; `GET /assets` lists it; `GET /asset/<sha1hex>.png -o /tmp/p.png
      && file /tmp/p.png` → **PNG image data** (proves `_read_bytes` ran — a UTF-8 read 500s here).
- [x] **Negative / traversal:** `GET /asset/..%2f..%2fmeta.json` → `404` (unknown stored name; no
      path join).
- [x] Local validation passes: `python3 -m py_compile app.py`; curl round-trip + negative above.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — Service (Assets) section, Storage/Stored-name-safety/
  Routes bullets, Verification (MR-023 block), Risks (path traversal). The served URL **must** key on
  the `%2F`-free `sha1+ext` stored name (S4); base64 is the sole transport (S5).
- Existing storage patterns to mirror: `_dir(rid)`, `_read_json(path, default)`, `snapshot_round`
  (`app.py:105`), the `_lock`-guarded writers, `_base()` (`app.py:176`), `_body_json` (`app.py:168`).
- History interaction is **out of scope** (Non-goals): assets are review-scoped, not snapshotted
  per round.

## Work log

- `2026-06-18` — **app.py:** added `base64`, `hashlib` imports; extended `_CTYPES` with image
  types (png/jpg/jpeg/gif/svg/webp/avif/bmp/ico). New asset helpers: `_assets_dir(rid)`,
  `_assets_manifest(rid)`, `list_assets(rid)`, `_stored_name(name, data)` (= `sha1(bytes)[:16]` +
  sanitized ext via `_EXT_RE`), `attach_asset(rid, name, data)` (writes bytes, upserts the manifest
  by `name`; caller holds `_lock`).
- `2026-06-18` — **Routes** (inserted before `/review/{id}`): `POST /api/reviews/{id}/assets`
  `{name, content_b64}` → `{name, stored, url, bytes, ctype}` (201); `GET …/assets` →
  `{assets:[…]}` with per-entry `url`; `GET …/asset/{stored}` → raw bytes via `_read_bytes` (B1)
  with the stored `ctype`, resolved **through the manifest only** (never path-joins the request
  segment). The asset-GET regex `[A-Za-z0-9._-]+` excludes `%`/`/`, so an encoded-traversal segment
  fails to match → 404 before any lookup; the manifest check is defense-in-depth.
- `2026-06-18` — base64 is the **only** transport (S5: no `{name,path}` host-read form). Served URL
  keys on the `%2F`-free `sha1+ext` **stored** name (S4); the human `name` stays a manifest field.
  `assets/` + `assets.json` are siblings of `source.md`/`history/`; `snapshot_round` never touches
  them, so they survive every `PUT /source`. POST validates `name` + `content_b64` (400 if missing
  or not valid base64). Re-attaching a `name` upserts (old stored bytes orphaned until `DELETE`
  rmtrees the review — accepted minor debt).
- Files: `app.py`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py` OK; `docker build` OK; validated from the rebuilt
  throwaway container (`:8138`).
- `2026-06-18` — **curl round-trip:** attach a 1×1 PNG under `name:"/assets/pixel.png"` → response
  `stored:"490e9f0db52061ac.png"`, `url` with **no `%2F`**, `bytes:70`, `ctype:"image/png"`;
  `GET /assets` lists it; `GET /asset/490e9f0db52061ac.png` → `content-type: image/png` + body
  `file`-identified as **PNG image data, 1x1** (proves `_read_bytes`/B1 — a UTF-8 read would 500).
- `2026-06-18` — **survives revision (brief's core ask):** asset count 1 before and after a
  `PUT /source` (which snapshotted `history/round-0`); refetch still returns the PNG. On-disk
  `_dir(id)/` shows `assets/` + `assets.json` as siblings of `history/` (not under it).
- `2026-06-18` — **back-compat:** `GET /assets` on a review with none attached → `{"assets":[]}`.
- `2026-06-18` — **negatives:** unknown stored → 404; `GET /asset/..%2f..%2fmeta.json` → 404
  (regex non-match); POST missing `content_b64` → 400; POST invalid base64 → 400.

## Follow-ups

- Server-side local-dir `{name,path}` attach behind `MDREVIEW_ASSET_ROOTS` — **cut to backlog (S5)**;
  if revived, must ship the `os.path.realpath(root)+os.sep` boundary check (S3) + negative-path ACs.
- Re-attaching a `name` with new bytes orphans the old stored file (cleaned only at review delete).
  Trivial leak; a manifest-driven sweep could reclaim it if it ever matters.
