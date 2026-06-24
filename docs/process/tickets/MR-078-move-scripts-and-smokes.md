---
id: MR-078
title: Move mcp_server.py/watch.py→src/, smokes+render-smoke→tests/, fix SERVER path, Dockerfile.watcher COPY
status: ready
layer: infra
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-076]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Get the remaining loose Python off the root: the two standalone scripts to `src/`, the smokes and the
render-smoke to `tests/`. Container destinations are held stable (`/app/...`) so `agent-mcp.json` and
`docker-compose.yml` need no edit — the only code consequence is the smokes' `SERVER` path and the
watcher Dockerfile's COPY sources.

## Acceptance criteria

- [ ] `git mv mcp_server.py watch.py src/`; `git mv mcp_smoke.py agent_smoke.py tests/`;
      `git mv scripts/render-smoke.sh tests/` (history preserved).
- [ ] `tests/mcp_smoke.py` and `tests/agent_smoke.py`: `SERVER = os.path.join(HERE, "..", "src",
      "mcp_server.py")` (was the bare-sibling `os.path.join(HERE, "mcp_server.py")`).
- [ ] `Dockerfile.watcher`: `COPY watch.py mcp_server.py ./` → `COPY src/watch.py src/mcp_server.py
      ./` (destinations stay `/app/watch.py`, `/app/mcp_server.py`); `CMD ["python3", "watch.py"]` and
      `COPY watcher/ ./watcher/` unchanged.
- [ ] `python3 -m py_compile src/mcp_server.py src/watch.py`; run `tests/mcp_smoke.py` green; `docker
      build -f Dockerfile.watcher .` succeeds; `docker run --rm <watcher-img> ls /app` shows
      `watch.py`, `mcp_server.py`, and `watcher/` at `/app`.
- [ ] **Confirm unchanged + still valid:** `watcher/agent-mcp.json` (`"/app/mcp_server.py"`) and
      `docker-compose.yml` (`/app/watcher/launch.sh`) need no edit (grep both, assert no path drift).

## Notes / context

- `mcp_smoke.py:19`, `agent_smoke.py:34` (the `SERVER` lines); `Dockerfile.watcher:19` (the COPY).
- Verified in planning: `mcp_server.py`/`watch.py` do not `import app` and do not read web assets via
  `__file__`, so they are genuinely move-as-is.
- Epic: "Infra" — the watcher-Dockerfile + smokes bullets; "Container destinations are stable".

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
