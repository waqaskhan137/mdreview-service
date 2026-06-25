---
id: MR-083
title: Extract assets.py + AssetService (content-hash storage + manifest)
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-082]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move content-hash asset storage + the manifest behind a service. The router's asset-GET stops
path-joining `/data` directly and resolves through the service. (Class vs plain-function module is
implementer's discretion per the epic; the only hard rule is no self-built dependencies.)

## Acceptance criteria

- [x] `src/mdreview/assets.py` provides `attach_asset(rid, name, data)`, `list_assets(rid)`,
      `find(rid, stored)`, `_stored_name(name, data)`, and the `_EXT_RE` + assets-dir/manifest paths,
      over the injected `store`. Content-hash naming (`sha1(bytes)[:16] + ext`) and **manifest-only
      resolution** (path-traversal-proof by construction) preserved.
- [x] The asset-GET arm (`app.py:793-805`) resolves via the service (`find`) then reads bytes through
      `store.read_bytes` — **no `_assets_dir` / manifest path-join left in the handler.**
- [x] POST asset → `GET /asset/<stored>` returns bytes whose **sha matches the golden**; `ctype` from
      the manifest is unchanged. `tests/agent_smoke.py` (the asset-embed loop: create →
      `attach_asset(path=…)` → `<img>` renders `naturalWidth>0`) is green.
- [x] `python3 -m py_compile src/app.py src/mdreview/assets.py`.

## Notes / context

- `app.py:225-265` (asset helpers), `app.py:793-805` (the asset-GET arm), `app.py:230-231` /
  `app.py:798` (traversal-proof rationale).
- Epic: `assets.py` row ("may stay function-shaped if it reads cleaner").

## Work log

- `2026-06-25` — Created `src/mdreview/assets.py` with `AssetService(store)`: `list`, `attach`,
  `find` (manifest-only resolution), `path`, plus `_dir`/`_manifest`/`_stored_name` and the
  `_EXT_RE`. Logic moved verbatim (content-hash naming, manifest upsert, traversal-proof). In
  `src/app.py`: `_assets = AssetService(_store)`; the asset function block is gone; the 3 asset arms
  (GET/POST `/assets`, GET `/asset/{stored}`) call `_assets.*`; dropped the now-unused `hashlib`
  import. Files: `src/mdreview/assets.py`, `src/app.py`.
- Folded a pre-existing fix into `tests/agent_smoke.py`: its `server_info` assertion expected **18**
  tools, but the MCP surface has been **20** since MR-053 (mcp_smoke already asserts 20). Stale
  literal, unrelated to this refactor; corrected 18 -> 20 so the test I now own (moved in MR-078)
  passes.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/assets.py` → OK. Golden sweep →
  **byte-identical** (41/41), covering asset POST (entry: stored/bytes/ctype), GET `/assets` list,
  GET `/asset/{stored}` bytes SHA, and the bad-stored 404. `grep` finds no inline
  `_assets_dir(`/`attach_asset(`/`list_assets(` in `src/app.py`. **agent_smoke.py PASS** (Node 22 +
  Chrome CDP): `server_info` 20 tools, `attach_asset(path=)` -> stored+url, asset served 200
  image/png, viewer repoints `<img>`, render proof `#article img naturalWidth>0 AND src==asset`
  (nw=1).

## Follow-ups

Anything deliberately deferred.
