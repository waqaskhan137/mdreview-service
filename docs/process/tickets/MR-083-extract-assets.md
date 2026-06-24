---
id: MR-083
title: Extract assets.py + AssetService (content-hash storage + manifest)
status: ready
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-082]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move content-hash asset storage + the manifest behind a service. The router's asset-GET stops
path-joining `/data` directly and resolves through the service. (Class vs plain-function module is
implementer's discretion per the epic; the only hard rule is no self-built dependencies.)

## Acceptance criteria

- [ ] `src/mdreview/assets.py` provides `attach_asset(rid, name, data)`, `list_assets(rid)`,
      `find(rid, stored)`, `_stored_name(name, data)`, and the `_EXT_RE` + assets-dir/manifest paths,
      over the injected `store`. Content-hash naming (`sha1(bytes)[:16] + ext`) and **manifest-only
      resolution** (path-traversal-proof by construction) preserved.
- [ ] The asset-GET arm (`app.py:793-805`) resolves via the service (`find`) then reads bytes through
      `store.read_bytes` — **no `_assets_dir` / manifest path-join left in the handler.**
- [ ] POST asset → `GET /asset/<stored>` returns bytes whose **sha matches the golden**; `ctype` from
      the manifest is unchanged. `tests/agent_smoke.py` (the asset-embed loop: create →
      `attach_asset(path=…)` → `<img>` renders `naturalWidth>0`) is green.
- [ ] `python3 -m py_compile src/app.py src/mdreview/assets.py`.

## Notes / context

- `app.py:225-265` (asset helpers), `app.py:793-805` (the asset-GET arm), `app.py:230-231` /
  `app.py:798` (traversal-proof rationale).
- Epic: `assets.py` row ("may stay function-shaped if it reads cleaner").

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
