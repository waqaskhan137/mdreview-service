---
slug: oop-refactor-src-layout
captured: 2026-06-25            # Europe/London
source: this session (plan-mode plan, approved by the product owner)
related_epic: epics/oop-refactor-src-layout-plan.md
---

# OOP Refactor + `src/` Restructure — mdreview-service

> Verbatim capture of the approved plan-mode plan. Grooming, scope cuts, and design
> decisions happen in the epic plan + tickets, not by editing this brief. Later changes
> go under **Amendments** only.

## Context

`app.py` (834 lines) is a single-file monolith: one god `route()` method (40+ regex
branches) plus ~25 free functions operating on module globals, mixing ~10 concerns
(config, persistence/locking, review lifecycle, comment state machine, assets, turn
baton/lease, long-poll, HTTP framing, history, static serving). The repo root also
holds loose Python (`app.py`, `mcp_server.py`, `watch.py`, two smokes) and frontend
(`viewer.html`, `dashboard.html`, `static/`).

Goal: code strictly under `src/`, a clean root, and clear single-responsibility
modules wired by **inversion of control** (constructor injection — nothing builds its
own dependencies; a composition root wires everything). This is a **pure internal
refactor**: the HTTP API, on-disk `/data` format, and viewer behaviour stay identical,
so rollback is just redeploying the prior image.

Decisions (confirmed): **Tier B** (restructure + decompose `app.py`; `mcp_server.py`
and `watch.py` move as-is). Execute **through the gated `/feature-cycle`** — this file
is the technical brief its `mdreview-planner` consumes. Infra **stays at root** (root's
"no dangling" rule reads as "no loose source/frontend"; Dockerfiles + compose are
conventional root residents).

## Target layout

```text
mdreview-service/
├── README.md  LICENSE  CLAUDE.md  AGENTS.md      # stay (convention)
├── Dockerfile  Dockerfile.watcher  docker-compose.yml  .env.example   # stay (infra at root)
├── watcher/                                       # stays (container path /app/watcher, self-locating)
├── docs/  site/  reviews/  .claude/  .github/     # unchanged
├── web/                                           # NEW — frontend (not "code")
│   ├── viewer.html  dashboard.html
│   └── static/...
├── tests/                                         # NEW — moved smokes
│   ├── mcp_smoke.py  agent_smoke.py  render-smoke.sh
└── src/
    ├── mdreview/                                  # the HTTP service package — python -m mdreview
    │   ├── __init__.py  __main__.py
    │   ├── config.py  store.py  reviews.py
    │   ├── comments.py  assets.py  handoff.py
    │   └── server.py
    ├── mcp_server.py                              # standalone script (does NOT import the package)
    └── watch.py                                   # standalone script (does NOT import the package)
```

## Design: IoC decomposition of `app.py`

Seven cohesive modules under `src/mdreview/`. Mapping from current `app.py` line ranges:

| Module | Single responsibility | Moves in (current lines) | Depends on |
|---|---|---|---|
| `config.py` | Env constants read once. | `DATA_DIR, PORT, PUBLIC_BASE, WAIT_TIMEOUT_S, LEASE_TTL_S, RID`, `os.makedirs` (40-59, minus `HERE`); add `WEB_DIR` | — |
| `store.py` | **`Store` class**: filesystem persistence + the `_lock` Condition + notify/wait. | `_dir,_exists,_read,_read_bytes,_ctype_for,_read_json,_write,_to_float,_CTYPES`, `_lock` (52-133) | config |
| `reviews.py` | **`ReviewService`**: review lifecycle, summary/list, history snapshot+reads. | `meta,bump,summary,list_reviews,snapshot_round,create_review` (136-222); history reads (inline 677-704) | store, comments |
| `comments.py` | **`CommentService`**: threaded state machine (open→resolved→reopened). | `_comments_path,list_comments,_write_comments,_find_comment,_comment_as_note,create_comment,apply_comment_transition` (268-382) | store |
| `assets.py` | **`AssetService`**: content-hash asset storage + manifest. | `_EXT_RE,_assets_dir,_assets_manifest,list_assets,_stored_name,attach_asset` (225-265) | store, config |
| `handoff.py` | **`HandoffService`**: turn baton + lease decision table (`flip/hand_back/reclaim/claim_lease`). | the `/handoff` POST body (615-672) | store, config |
| `server.py` | HTTP framing + router + composition root. `H` delegates to injected services; `main()`. | `H._send/_json/_body_json/_base` (389-419), `_wait` (421-460), `route` (482-824), `main` (827-829) | all above |

**IoC wiring (the seam):** `BaseHTTPRequestHandler` is built per-request by the server
with a fixed signature, so don't inject into `H`'s constructor. Instead:

- `main()` (composition root) builds `Store(DATA_DIR)` → builds each service with the
  store injected → bundles them.
- Subclass `ThreadingHTTPServer` to carry the bundle: `server.app = services`.
- `H` reads `self.server.app.reviews`, `.comments`, etc. — decoupled from construction.

**Keep dict-based state — reject `@dataclass` Review/Comment/Asset.** State is
dict-shaped on disk; every read is `_read_json -> dict`. Dataclasses would add a
to/from-dict tax on every request for zero behaviour and a new drift surface against the
deliberately **additive-default-safe** schema (e.g. `summary()` tolerating a missing
`turn` key, `app.py:165`). Mark the choice with a `ponytail:` comment.

**`assets.py`** is only 3 small functions — a class there is borderline ceremony; a
plain-function module is acceptable if it reads cleaner. The real cohesion wins are
`Store`, `CommentService`, and `HandoffService` (the hairy inline lease table → named
methods).

**Reuse, don't rewrite:** preserve `summary()` and `_comment_as_note()` projections
verbatim; keep the exact MR-054 Condition pattern in `Store` (`with store.lock` /
`notify_all()` / `wait(t)` as thin pass-throughs — **do not** switch to per-review
locks; long-poll correctness depends on notify under the same lock as the write,
`app.py:46-58`, `app.py:667-672`).

## Path resolution after the move

`app.py:40` `HERE = dirname(__file__)` serves `viewer.html`/`dashboard.html`/`static/`
relative to itself (`app.py:500`, `app.py:812`, `app.py:818`). After the move add one
constant in `config.py`:

```python
# ponytail: repo-root anchor; MDREVIEW_WEB_DIR overrides in container/tests
WEB_DIR = os.environ.get("MDREVIEW_WEB_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")
```

Set `ENV MDREVIEW_WEB_DIR=/app/web` in the `Dockerfile` so prod never relies on the
`../../..` arithmetic, and so the render-smoke can point at a throwaway dir.

## Migration sequence — move first, then decompose

Move and decompose are independent risk classes (path/deploy breakage vs logic
breakage); isolating them means a failed smoke names the cause. Each commit compiles
(`py_compile`) and passes its smoke before the next.

**Phase 0 — relocate + path fix (no logic change):**

1. `git mv app.py src/app.py`; create `web/`, `git mv viewer.html dashboard.html static web/`; swap `HERE`-based web paths for `WEB_DIR`. Verify: boot on a scratch port, `GET /review/<id>` + `/` + `/static/marked.min.js` all 200 and non-empty.
2. Update `Dockerfile` (`COPY src/ ./src/`, `COPY web/ ./web/`, `ENV MDREVIEW_WEB_DIR=/app/web`, `PYTHONPATH=/app/src`, `CMD python src/app.py`). Verify: `docker build .` + throwaway container + render-smoke.
3. `git mv mcp_server.py watch.py src/`; `git mv mcp_smoke.py agent_smoke.py tests/`, `git mv scripts/render-smoke.sh tests/`; update `Dockerfile.watcher` COPY sources (destinations stay `/app/...`, so `agent-mcp.json`'s `/app/mcp_server.py` and compose's `/app/watcher/launch.sh` need **no** change); fix `SERVER = os.path.join(HERE, "..", "src", "mcp_server.py")` in the two smokes. Verify: `mcp_smoke.py`, `docker build -f Dockerfile.watcher .`, `docker run --rm img ls /app`.
4. Update the **3 live gate refs** in `docs/process/README.md` + run-commands in README/CLAUDE/AGENTS. New gate: `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`. **Leave frozen ticket/sprint/review history untouched** (audit trail).

**Phase 1 — decompose internals, bottom-up, one module per commit:**

5. Extract `config.py`. 6. Extract `store.py` + `Store` (verify the long-poll: hit `/api/reviews/wait?since=0`, flip `/handoff to=agent` in another shell, confirm the parked waiter wakes). 7. `comments.py`/`CommentService` (full lifecycle curl incl. 409 on double-resolve). 8. `assets.py` (POST asset → GET `/asset/<stored>` bytes match; `agent_smoke.py`). 9. `reviews.py`/`ReviewService` (POST → 2×PUT → `/history`; `/feedback` comment projection). 10. `handoff.py`/`HandoffService` (MR-055 lease matrix: claim/renew/foreign-fresh→409/stale+turn=agent→grant/stale-reclaimed→409). 11. `git mv src/app.py src/mdreview/server.py`, add `__main__.py`, switch `Dockerfile` CMD to `python -m mdreview`. Verify: full render-smoke + all curl smokes + build + healthcheck.

## Files changed

- **New:** `src/mdreview/{__init__,__main__,config,store,reviews,comments,assets,handoff,server}.py`; `web/`; `tests/`.
- **Moved:** `app.py`→`src/`(then `src/mdreview/server.py`); `mcp_server.py`,`watch.py`→`src/`; frontend→`web/`; smokes→`tests/`.
- **Edited:** `Dockerfile`, `Dockerfile.watcher` (COPY/CMD/ENV); `tests/{mcp_smoke,agent_smoke}.py` (`SERVER` path); `docs/process/README.md` + README/CLAUDE/AGENTS (live gate + run commands — pattern: `app.py`→`src/...`, repeated at the 3 live gate lines and run-command examples only, **not** historical records).
- **Unchanged:** `docker-compose.yml`, `watcher/`, `agent-mcp.json`, `/data` on-disk format, every HTTP response shape.

## Verification

Per the project gate (no test framework — smokes are the oracle):

- **Golden transcript:** before starting, capture a curl run against current behaviour (POST → PUT → comment → reply → resolve → handoff → wait → history → asset). Pure-refactor commits must produce **byte-identical** API responses; diff each commit against it.
- **Per commit:** `python3 -m py_compile` the touched files + the relevant smoke (`tests/mcp_smoke.py`, `tests/agent_smoke.py`, or a targeted curl).
- **Phase boundaries:** `docker build .` + `docker build -f Dockerfile.watcher .`; run a **throwaway container on a scratch port** (never compose :8137 / live :8139); `tests/render-smoke.sh` against the served `/review/<id>` (a 200 is not a render).
- **Final:** the `mdreview-qc` agent for an end-to-end PASS/FAIL on a rebuilt image.

## Execution

**Step 0 (first action, before any change): branch.** `git checkout -b
refactor/oop-src-layout` off `dev` (done). No file is created, moved, or edited on
`dev` — all work lands on the feature branch.

Then runs through `/feature-cycle` (slug `oop-refactor-src-layout`): this brief →
`mdreview-planner` authors `docs/process/epics/<slug>-plan.md` to the project template →
independent `staff-critic` G1 critique + fix loop → `MR-###` tickets (Phase 0 and the
seven Phase-1 extractions map naturally to tickets) → sprint → implement → G7
render-smoke sprint-close → PR. The cycle re-plans to the repo's epic template and
critic-gates before any code; this file is its technical input, not a substitute.

## Amendments

_None yet._
