---
id: MR-078
title: Move mcp_server.py/watch.py→src/, smokes+render-smoke→tests/, fix SERVER path, Dockerfile.watcher COPY
status: done
layer: infra
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-076]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Get the remaining loose Python off the root: the two standalone scripts to `src/`, the smokes and the
render-smoke to `tests/`. Container destinations are held stable (`/app/...`) so `agent-mcp.json` and
`docker-compose.yml` need no edit — the only code consequence is the smokes' `SERVER` path and the
watcher Dockerfile's COPY sources.

## Acceptance criteria

- [x] `git mv mcp_server.py watch.py src/`; `git mv mcp_smoke.py agent_smoke.py tests/`;
      `git mv scripts/render-smoke.sh tests/` (history preserved).
- [x] `tests/mcp_smoke.py` and `tests/agent_smoke.py`: `SERVER = os.path.join(HERE, "..", "src",
      "mcp_server.py")` (was the bare-sibling `os.path.join(HERE, "mcp_server.py")`).
- [x] `Dockerfile.watcher`: `COPY watch.py mcp_server.py ./` → `COPY src/watch.py src/mcp_server.py
      ./` (destinations stay `/app/watch.py`, `/app/mcp_server.py`); `CMD ["python3", "watch.py"]` and
      `COPY watcher/ ./watcher/` unchanged.
- [x] `python3 -m py_compile src/mcp_server.py src/watch.py`; run `tests/mcp_smoke.py` green; `docker
      build -f Dockerfile.watcher .` succeeds; `docker run --rm <watcher-img> ls /app` shows
      `watch.py`, `mcp_server.py`, and `watcher/` at `/app`.
- [x] **Confirm unchanged + still valid:** `watcher/agent-mcp.json` (`"/app/mcp_server.py"`) and
      `docker-compose.yml` (`/app/watcher/launch.sh`) need no edit (grep both, assert no path drift).

## Notes / context

- `mcp_smoke.py:19`, `agent_smoke.py:34` (the `SERVER` lines); `Dockerfile.watcher:19` (the COPY).
- Verified in planning: `mcp_server.py`/`watch.py` do not `import app` and do not read web assets via
  `__file__`, so they are genuinely move-as-is.
- Epic: "Infra" — the watcher-Dockerfile + smokes bullets; "Container destinations are stable".

## Work log

- `2026-06-25` — `git mv mcp_server.py watch.py src/`; `git mv mcp_smoke.py agent_smoke.py tests/`;
  `git mv scripts/render-smoke.sh tests/` (`scripts/` emptied out and is gone — one fewer root dir).
  Fixed `SERVER = os.path.join(HERE, "..", "src", "mcp_server.py")` in `tests/mcp_smoke.py:19` and
  `tests/agent_smoke.py:34`. `Dockerfile.watcher`: `COPY watch.py mcp_server.py ./` → `COPY
  src/watch.py src/mcp_server.py ./` (destinations stay `/app/...`). Files: moves + 3 edits.
- The README/CLAUDE refs to `scripts/render-smoke.sh` are repointed to `tests/render-smoke.sh` in
  MR-079 (the docs-repointing ticket, next commit) alongside the `py_compile` gate refs.

## Validation

- `2026-06-25` — `python3 -m py_compile src/mcp_server.py src/watch.py` → OK. Booted `src/app.py` on
  scratch `:8155`; `MDREVIEW_BASE=http://localhost:8155 python3 tests/mcp_smoke.py` → **PASS** (all
  44 assertions: protocol surface, 20 tools, create→update round-trip, attach-by-path, comment
  lifecycle, lease/hand_back). `docker build -f Dockerfile.watcher .` → OK; `docker run --rm <img> ls
  /app` → `mcp_server.py`, `watch.py`, `watcher/` (destinations stable). `watcher/agent-mcp.json`
  (`/app/mcp_server.py`) and `docker-compose.yml` (`/app/watcher/launch.sh`) are **unmodified** and
  still resolve to the COPY destinations (`git status` clean for both).

## Follow-ups

Anything deliberately deferred.
