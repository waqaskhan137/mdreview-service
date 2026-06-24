---
id: MR-086
title: Rename src/app.py→src/mdreview/server.py, add __main__.py, flip entrypoint to python -m mdreview
status: ready
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-085]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

The final step. With every concern extracted, the monolith becomes the thin HTTP layer:
`server.py` holds framing + the router + the composition root, and the container ships from
`python -m mdreview`. This is where the no-store-helper contract proves the IoC is real, not a rename.

## Acceptance criteria

- [ ] `git mv src/app.py src/mdreview/server.py`. `server.py` holds `H` (framing
      `_send`/`_json`/`_body_json`/`_base`, `_wait`, `route`), a `MdreviewServer(ThreadingHTTPServer)`
      subclass carrying `.app`, and `main()` — the **composition root** building `Store` → each
      service (store injected) → the `Services` bundle → `server.app = services`. `H` reads
      `self.server.app.<service>` per request (no constructor args).
- [ ] `src/mdreview/__main__.py` (`from .server import main; main()`). `python -m mdreview` boots with
      `PYTHONPATH=src`.
- [ ] **No-store-helper contract (the G1 blocker's enforcement):** grep `server.py` for
      `_comments_path(`, `_assets_dir(`, `_dir(`, `_read_json(`, **`_read(`**, **`_read_bytes(`**,
      `_write(`, `_write_comments(`, `_find_comment(`, and `os.path.join(.*DATA_DIR` → **zero hits**.
      The only file reads `server.py` keeps are the `WEB_DIR` static/viewer/dashboard reads via the
      public `store.read_text`/`read_bytes`/`ctype_for`. (The `_read(`/`_read_bytes(` tokens are the
      folded G1 r2 SHOULD, closing the completeness hole.)
- [ ] `Dockerfile` `CMD` → `["python", "-m", "mdreview"]`. A **rebuilt throwaway container** runs
      `python -m mdreview` on a scratch port and serves a rendered viewer.
- [ ] Full green on the rebuilt image: `tests/mcp_smoke.py`, `tests/agent_smoke.py`, render-smoke
      (`#article`/`h1`, `#list`/`.card`), `curl /healthz` + `/api/reviews`, golden-transcript
      byte-identical, and the **`mdreview-qc`** end-to-end PASS.
- [ ] Gate: `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`.

## Notes / context

- `app.py:385-419` (framing), `app.py:421-460` (`_wait`), `app.py:482-824` (`route`), `app.py:827-829`
  (`main`); the IoC seam (`self.server.app`) verified in planning (`socketserver` sets `self.server`).
- Epic: `server.py` row, "The IoC seam (verified feasible)", "The router must call services, not
  store primitives", and the no-store-helper contract (BLOCKER fix + the `_read(`/`_read_bytes(`
  fold).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
