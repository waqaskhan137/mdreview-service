---
review_of: sprints/sprint-27.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-25
verdict: PASS
status: resolved
---

# Sprint-27 close review (G7) — oop-refactor-src-layout epic

Independent gate. I did not take the work log's word for anything: I re-read all seven extracted
modules + `server.py`, re-ran the no-store-helper grep, rebuilt the service image from scratch, and
re-drove the full HTTP contract (incl. the comment state machine, the MR-054 long-poll wake, the
MR-055 lease matrix, assets, history, the 410, and both DOM render-smokes) against a **throwaway
container on scratch ports 8158/8159/8160** with anonymous/`.scratch/` data. I never touched the
live `:8139` instance or the `mdreview-data` volume (confirmed `:8139` still up and unmodified after
the run); every test container/host process was torn down.

**Verdict: PASS.** The refactor delivers exactly what the epic promised — a clean root, all code
under `src/`, the 833-line monolith decomposed into seven single-responsibility modules wired by a
real composition root, and **byte-identical external behaviour**. The render gate (container rebuild
+ `/healthz` + `/api/reviews` + per-page DOM) passed from the rebuilt image. The IoC is real, not a
rename: the no-store-helper contract holds with zero hits and the handler reaches `/data` only
through `self.server.app.<service>`. No BLOCKER. The two NITs below are cosmetic and do not gate the
close.

## Evidence I actually ran

### Structure / requirements (verified)
- Root clean — `find . -maxdepth 1 -name '*.py'` → empty. Root holds only docs/infra/dirs
  (`AGENTS.md CLAUDE.md Dockerfile Dockerfile.watcher docker-compose.yml LICENSE README.md docs
  reviews scripts site src tests watcher web`).
- All code under `src/`: `src/mdreview/{__init__,__main__,config,store,comments,assets,reviews,handoff,server}.py`
  + `src/mcp_server.py` + `src/watch.py`. Frontend in `web/` (`viewer.html`, `dashboard.html`,
  `static/` 28 files intact incl. KaTeX woff2/marked/mermaid). Smokes in `tests/`
  (`mcp_smoke.py`, `agent_smoke.py`, `render-smoke.sh`).
- SRP sizing (each module skimmed end-to-end, one responsibility each): config 25, assets 58,
  handoff 86, store 100, comments 136, reviews 153, server 434. The 833-line `app.py` (confirmed on
  `dev`) is genuinely decomposed; `server.py` is the largest only because it is pure HTTP
  framing + router + composition root, all delegation.
- IoC is real: `main()` builds `Services(Store(DATA_DIR))` → injects the one `Store` into
  `CommentService`/`AssetService`/`ReviewService`/`HandoffService` → `MdreviewServer(ThreadingHTTPServer)`
  carries `.app`; the handler reads `self.server.app.<service>` per request with no constructor args
  (`server.py:45-64, 427-431`). `git mv` history preserved (`app.py → src/app.py → src/mdreview/server.py`,
  rename chain R098/R079 in `git log --follow`).

### The no-store-helper contract (the G1-blocker enforcement) — ZERO hits
`grep` over `src/mdreview/server.py` for each token returned 0:
`_comments_path(`, `_assets_dir(`, `_assets_manifest(`, `_dir(`, `_read_json(`, `_read(`,
`_read_bytes(`, `_write(`, `_write_comments(`, `_find_comment(`, `_comment_as_note(`, `_stored_name(`,
and `os.path.join(...DATA_DIR`. The only filesystem reads kept in `server.py` are the three `WEB_DIR`
framing reads (`/`, `/review/{id}`, `/static/*`) via `app.store.read_text`/`read_bytes`/`ctype_for`
(`server.py:184, 412, 418-421`). The folded G1-r2 SHOULD (`_read(`/`_read_bytes(`) is included and
clean.

Exactly **one** `threading.Condition` in the tree (`store.py:39`), zero stray `Lock(`/`RLock(`. Lock
**acquisition** sites are only the 7 permitted ones, all in `server.py` route arms + `_wait`
(`server.py:135, 141, 239, 286, 332, 351, 368, 387`); no service method acquires `store.lock`
(the `.lock` strings inside service files are all docstrings/comments, verified by reading them).
`list_reviews()`/`summary()` are lock-free (`reviews.py:36-66`), so `_wait`'s nested `list_reviews()`
call under the lock keeps its shape. `notify_all()` is called once, in `handoff.py:85`, after a
successful write under the caller's lock; `wait()` parks at `server.py:141` releasing `app.store.lock`.

### Validation gate
`python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py` → OK.

### Behaviour preserved — rebuilt container + render gate (the G7 gate)
- `docker build -t mdreview-oop-g7 .` → OK. `docker inspect` CMD = `["python","-m","mdreview"]`;
  env `MDREVIEW_WEB_DIR=/app/web`, `PYTHONPATH=/app/src`, `PORT=8080`.
- Throwaway container `-p 8158:8080` (anon `/data`). `curl /healthz` → `{"ok": true}`;
  `curl /api/reviews` → `{"reviews": []}`; `/api` descriptor correct; `/static/marked.min.js`
  → `Content-Type: text/javascript`; `/review/{id}` → `text/html; charset=utf-8`; HEAD → 501
  (no `do_HEAD`, as designed).
- **Per-page DOM render-smoke from the rebuilt image** (a 200 is not a render):
  - `tests/render-smoke.sh "<url>/review/<id>" '#article' 'h1'` → `#article` (1), `h1` (2) — exit 0.
  - `tests/render-smoke.sh "<url>/" '#list' '.card'` → `#list` (1), `.card` (1) — exit 0.
- Screenshots captured from my own container run under
  `reviews/sprint-27-render-evidence-2026-06-25/` (`viewer.png`, `dashboard.png`, `render-smoke.txt`):
  the viewer shows the rendered heading, inline code, and **KaTeX `E = mc²`** (proving `web/static`
  KaTeX assets serve), the comment toolbar and "Send to agent" baton; the dashboard shows the review
  card rendered into `#list`.

### Behaviour preserved — full HTTP contract sweep (against the rebuilt container)
Each arm reproduced and matched the documented contract:
- `GET /source` (text/markdown, exact bytes); `PUT /source` → revision bump + `source_updated`.
- `GET /feedback` with **no** comment → `notes: []`; **with** a comment → projection exercised
  (`note: "reviewer: tighten"`, `addressed: false`) — `as_note` is genuinely hit (the folded G1 nit).
- Comment state machine: create → reply → **resolve 200** → **double-resolve 409**
  (`{"error":"comment is not open/reopened","status":"resolved"}`) → **reopen 200** (status reopened)
  → **reopen-non-resolved 409** → **DELETE 200** → **re-GET 404**.
- `POST /feedback` → **410** `{"error":"gone, use comments"}`.
- Assets: POST → `stored=11ab96b2f4a42881.png` (content-hash) → `GET /asset/<stored>` bytes ==
  `PNGDATA` (exact); bad stored → **404**.
- History: `GET /history` → 1 round after the PUT (keys `feedback,notes,round,source,ts`);
  `/history/99` → **404** `{"error":"no such round"}`.
- Handoff flip → `turn: agent`; `/status` returns the additive `turn`/`handoff`/`agent_status`.
- `DELETE /api/reviews/<id2>` (throwaway) → **200** then **404**.

### MR-054 long-poll wake (the store.py gate)
Parked `GET /api/reviews/wait?since=<now>&turn=agent&timeout=15` in the background; a concurrent
`POST /handoff {"to":"agent"}` on another review woke it with `{"reviews":[{... "turn":"agent"}]}`,
`timeout: None` — the single-Condition `notify_all` under the lock survived the Store extraction.

### MR-055 lease decision matrix (the handoff.py gate) — 5/5
Against the container (claim/renew/foreign-fresh) and a host boot with `MDREVIEW_LEASE_TTL_S=0` for
instant-stale (the two stale cases):
- claim (cur unset) → grant 200; renew (cur==owner) → grant 200; foreign + fresh → **409**
  (`{"error":"lease held","owner":"sessA"}`); foreign + stale + `turn==agent` → **takeover grant 200**
  (MR-055); foreign + stale + already-reclaimed (`turn` forced to reviewer) → **409** (the TOCTOU
  re-check rejects the takeover).

### Host smokes (boot via `python -m mdreview`, PYTHONPATH=src)
- `MDREVIEW_BASE=<url> python3 tests/mcp_smoke.py` → **PASS** (all assertions; three-way
  `tools_hash` identity; `tool_count == 20`; full comment lifecycle; lease/`hand_back`;
  attach-by-path). `SERVER` path fix `../src/mcp_server.py` resolves.
- `python3 tests/agent_smoke.py` (Node v22 + Chrome CDP) → **PASS**: `server_info` 20 tools,
  `attach_asset(path=)` → stored+url, asset served 200 image/png, viewer repoints `<img>`, render
  proof `#article img naturalWidth>0 AND src==asset` (nw=1). The folded `18→20` fix (MR-083) is in
  place (`agent_smoke.py:156-157`).

### Infra / docs
- Watcher: `docker build -f Dockerfile.watcher .` → OK; `docker run --rm <img> ls /app` →
  `mcp_server.py watch.py watcher` (destinations stable). `Dockerfile.watcher:19` COPY =
  `src/watch.py src/mcp_server.py ./`.
- `watcher/agent-mcp.json` (`/app/mcp_server.py`) and `docker-compose.yml` (`/app/watcher/launch.sh`)
  **unchanged** (`git status` clean for both) — no path drift, as MR-078 required.
- Live gate refs repointed: `docs/process/README.md` Divergences (L43), Dev-flow step 5 (L117), and
  the **G4 pass-condition row (L162)** all quote `python3 -m py_compile src/mdreview/*.py
  src/mcp_server.py src/watch.py`; `CLAUDE.md:257` too. Zero `py_compile app.py` / `scripts/render-smoke.sh`
  remain in any forward doc. Frozen history untouched (the `app.py` mentions in tickets/sprints/reviews
  and the explanatory docstrings in `config.py`/`__init__.py`/`watch.py` are audit-trail/comments, not
  live refs).

## Findings

### BLOCKER
None.

### SHOULD
None.

### NIT
1. **`src/mdreview/__main__.py:2` uses an absolute import, not the relative form the AC quotes.**
   AC (MR-086) and the work log say `from .server import main`; the shipped file is
   `from mdreview.server import main`. Functionally identical under `python -m mdreview` with
   `PYTHONPATH=src` (verified: the container and host both boot), and it is arguably more consistent
   with `server.py`'s own `from mdreview.config import ...` absolute style. No behaviour impact; flag
   only because the AC text and the artifact differ. Fix (optional): either is fine; leave as-is or
   switch to `from .server import main` to match the ticket text verbatim.
2. **Empty `scripts/` directory lingers on the filesystem.** MR-078's work log says "`scripts/`
   emptied out and is gone — one fewer root dir," and git tracks **0** files under it (so it will
   NOT appear in a fresh clone or the PR — `git ls-files scripts/` is empty). The empty dir is only a
   local worktree artifact. No fix required; noted so the "is gone" claim is understood as
   "untracked, absent from the repo," not "removed from this checkout's filesystem."

## Resolution log

- 2026-06-25 — Independent G7 verification complete. Rebuilt `mdreview-oop-g7` + `mdreview-watcher-g7`
  from scratch; ran the full contract sweep, both render-smokes (with screenshots), the MR-054 wake,
  the MR-055 5/5 lease matrix, `mcp_smoke` (20 tools) and `agent_smoke` (render proof) — all green
  against throwaway containers/host on scratch ports, live `:8139` untouched and torn down after.
- No-store-helper contract: zero hits (incl. folded `_read(`/`_read_bytes(`); one Condition; lock
  acquired only at the 7 permitted sites; `list_reviews`/`summary` lock-free.
- Verdict **PASS**. Two NITs (absolute import in `__main__.py`; lingering empty untracked `scripts/`)
  are cosmetic and do not gate the close. Sprint-27 may be marked `closed`; set
  `close_review: reviews/sprint-27-close-review-2026-06-25.md` in the sprint frontmatter.
