---
epic: oop-refactor-src-layout
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-25
source: requirements/oop-refactor-src-layout.md
gate: passed 2026-06-25 # G1 (Plan Gate): not passed | passed YYYY-MM-DD; tickets blocked until passed
review: reviews/oop-refactor-src-layout-plan-review-2026-06-25-r2.md  # G1 cleared PASS-WITH-NITS (r1 CHANGES-REQUESTED, 1 blocker fixed)
related_sprints: [sprint-27]
related_tickets: [MR-076, MR-077, MR-078, MR-079, MR-080, MR-081, MR-082, MR-083, MR-084, MR-085, MR-086]
---

# OOP Refactor + `src/` Restructure Plan

`app.py` is an 833-line single-file monolith: one `route()` method (40+ regex branches) plus ~25
free functions over module globals, mixing ~10 concerns (config, persistence/locking, review
lifecycle, comment state machine, assets, turn baton/lease, long-poll, HTTP framing, history,
static serving). The repo root also holds loose Python (`app.py`, `mcp_server.py`, `watch.py`, two
smokes) and frontend (`viewer.html`, `dashboard.html`, `static/`). This epic restructures
everything under `src/` with a clean root, decomposes `app.py` into seven single-responsibility
modules wired by inversion of control (constructor injection, no framework), and does so as a
**pure internal refactor**: the HTTP API, the on-disk `/data` format, and the viewer all behave
identically, so rollback is redeploying the prior image. It matters now because the monolith is the
ceiling on every future feature's reviewability: the comment state machine, the lease decision
table, and the long-poll all live tangled in one file, and the next contributor (human or agent)
pays that tax on every change.

**Source requirement:** [`requirements/oop-refactor-src-layout.md`](../requirements/oop-refactor-src-layout.md), the original brief, kept verbatim.

## Product goal

A maintainer (or agent) opening this codebase finds: code under `src/`, a clean root holding only
docs + infra + the standard residents, and `app.py`'s ten tangled concerns split into seven named
modules each with one responsibility, wired by a single composition root via constructor injection.
Externally **nothing changes**: same HTTP responses byte-for-byte, same `/data` files, same viewer
behaviour, same container ports and entrypoints. The "done" state: the service ships from
`python -m mdreview`, every smoke and the render-smoke pass against a rebuilt throwaway container,
and an `mdreview-qc` end-to-end run is green on the new image. This is an internal-quality epic with
a zero-behaviour-change contract; its success is measured by the refactor being invisible from
outside.

## Core design principle

**Byte-identical behaviour is the oracle; structure is the only thing allowed to change.** Every
commit is a pure refactor whose API responses, on-disk writes, and rendered DOM must match a
golden transcript captured *before* the first move. The MR-054 long-poll correctness, one
`Condition` over one lock, `notify_all()` under the same lock as the write, is preserved exactly
inside the new `Store`, never weakened to per-review locks. When in doubt, the rule is: if a change
would alter a single response byte or a single `/data` file, it is out of scope. Structure serves
reviewability; behaviour is frozen.

## Recommended approach

Two independent risk classes are separated in time: **relocation** (path/deploy breakage) and
**decomposition** (logic breakage). Move first so a failed smoke after a move names "path/deploy"
and a failed smoke after an extraction names "logic." Throughout, the seam is inversion of control:
nothing constructs its own dependencies; a `main()` composition root builds a single `Store`,
injects it into each service, bundles the services, and hangs the bundle off a `ThreadingHTTPServer`
subclass that the per-request handler reads.

### Service (`app.py` → `src/mdreview/`)

**Seven modules under `src/mdreview/`.** The mapping below is validated against the current code
(every boundary line confirmed; the file is 833 lines, not 834 as the brief's prose says; no
mapping line drifts):

| Module | Single responsibility | Moves in (current `app.py` lines) | Depends on |
|---|---|---|---|
| `config.py` | Env constants read once at import. | `DATA_DIR`, `PORT`, `PUBLIC_BASE` (`app.py:41-43`), `WAIT_TIMEOUT_S`, `LEASE_TTL_S`, `RID` (`app.py:54-59`), the `os.makedirs(DATA_DIR)` (`app.py:45`); **drops `HERE`** (`app.py:40`); **adds `WEB_DIR`**. | (none) |
| `store.py` | **`Store` class:** filesystem persistence + the `_lock` Condition + notify/wait pass-throughs + content-type table. | `_dir`, `_exists`, `_read`, `_read_bytes`, `_ctype_for`, `_read_json`, `_write`, `_to_float`, `_CTYPES` (`app.py:62-133`); `_lock` (`app.py:52`) becomes `self._cond`. (`_to_float` lives here as `store.to_float` but is called only from `server.py`'s `_wait`/query parsing, NIT-5 below.) | config |
| `comments.py` | **`CommentService`:** threaded state machine (open→resolved→reopened) **and every comment-arm read/mutate the handler does inline today**. | `_comments_path`, `list_comments`, `_write_comments`, `_find_comment`, `_comment_as_note`, `create_comment`, `apply_comment_transition` (`app.py:276-382`); **plus two methods lifting handler arms that currently mutate/read `/data` inline:** `get_comment(rid, cid)` (lifts the inline `_find_comment(list_comments(rid), cid)` at `app.py:760`, returns the thread or `None`→404) and `delete_comment(rid, cid) -> (code, payload)` (lifts the full read-filter-write at `app.py:765-772`: `_read_json(_comments_path(rid))` → filter → `_write_comments` → the `comments_updated` bump, including the 404 when nothing is removed; caller holds `store.lock` exactly as today). | store |
| `assets.py` | **`AssetService`:** content-hash asset storage + manifest. | `_EXT_RE`, `_assets_dir`, `_assets_manifest`, `list_assets`, `_stored_name`, `attach_asset` (`app.py:232-265`). | store, config |
| `reviews.py` | **`ReviewService`:** review lifecycle, summary/list, history snapshot + reads, and the raw `source.md`/`feedback.md`/`notes.json` reads the router does inline today. | `meta`, `bump`, `summary`, `list_reviews`, `snapshot_round`, `create_review` (`app.py:136-222`); the inline history reads (`app.py:677-704`); the inline `source.md`/`feedback.md`/notes reads (`app.py:551`, `app.py:566-574`). | store, comments |
| `handoff.py` | **`HandoffService`:** turn baton + lease decision table (reclaim / hand-back / flip / claim-lease). | the `/handoff` POST body logic (`app.py:611-675`, the read-decide-write under `_lock`). | store, config |
| `server.py` | HTTP framing + router + composition root. `H` delegates to injected services; `main()` wires + serves. | `H._send`/`_json`/`_body_json`/`_base` (`app.py:389-419`), `_wait` (`app.py:421-460`), `route` (`app.py:482-824`), `main` (`app.py:827-829`); plus `__init__.py` / `__main__.py`. | all above |

**The IoC seam (verified feasible).** `socketserver.BaseRequestHandler.__init__` sets
`self.server = server` (confirmed in stdlib), and `BaseHTTPRequestHandler` inherits it, so the
handler can always reach its server. Therefore:

- `main()` (composition root) builds `store = Store(DATA_DIR)` → builds each service with the store
  injected (`ReviewService(store, comments)`, `CommentService(store)`, `AssetService(store)`,
  `HandoffService(store)`) → bundles them into a small `Services` holder (a plain object/namespace
  with `.reviews`, `.comments`, `.assets`, `.handoff`).
- A `ThreadingHTTPServer` subclass carries the bundle: `class MdreviewServer(ThreadingHTTPServer):`
  with `self.app = services` set after construction (or in an overridden `__init__`).
- `H` never takes constructor args (its signature is fixed by the framework). It reads
  `self.server.app.reviews`, `.comments`, `.assets`, `.handoff` per request, decoupled from
  construction. This is the brief's seam exactly; no DI framework, no global service singletons.

**The router must call services, not store primitives (the real decomposition work).** The current
`route()` reaches into low-level store helpers inline in many arms (counted: 13× `_exists`, **9×**
`_dir` (`app.py:542, 551, 557, 568, 572, 613, 682, 697` + `_assets_dir` at `app.py:802`), 6× `_read`,
6× `_read_json`, 5× `meta`, 5× `bump`, 2× `_read_bytes`, 2× `_ctype_for`, 2× `_write`, plus the
inline comment read/mutate at `app.py:760` and `app.py:765-772`). **The hand-count is illustrative,
not the completeness proof**: the proof is the objective grep in the server ticket's acceptance
criteria below (a hand-count missed the DELETE-comment arm in review round 1, which is exactly why
the grep, not the count, is the gate). A cosmetic move that leaves the handler doing
`_read(os.path.join(_dir(rid), "source.md"))`, or the inline `_write_comments` of the DELETE arm,
would leave the decoupling fake. The plan's stance:

- **Existence guard:** the ubiquitous `if not _exists(rid)` guard (the first line of nearly every
  arm) becomes `self.server.app.reviews.exists(rid)` (a thin `ReviewService` method delegating to
  `store`), so the handler never path-joins `DATA_DIR`.
- **Raw document reads** (`GET /source` reads `source.md`; `GET /feedback` reads `feedback.md` +
  `notes.json` + projects comments; the two `/history` arms read `round.json`/`source.md`/
  `feedback.md`/`notes.json`) become **methods on `ReviewService`** (`read_source(rid)`,
  `feedback(rid)`, `history(rid)`, `history_round(rid, n)`). These reads are review-scoped, so
  `ReviewService` is their natural owner; `ReviewService.feedback()` calls `CommentService` for the
  projection (the existing `summary()`→`list_comments()` edge already establishes
  reviews→comments).
- **Comment-arm read + mutate** (the two arms a hand-count missed): `GET /comments/{cid}`
  (`app.py:760`) does an inline `_find_comment(list_comments(rid), cid)` and `DELETE /comments/{cid}`
  (`app.py:765-772`) does an inline `_read_json(_comments_path(rid))` → filter → `_write_comments` →
  `bump`. Both reach `/data` (the DELETE *mutates* it) inside the handler. They become
  `CommentService.get_comment(rid, cid)` and `CommentService.delete_comment(rid, cid) -> (code,
  payload)` (mapped in the `comments.py` row above); the handler calls
  `self.server.app.comments.get_comment(...)` / `.delete_comment(...)` and never touches
  `comments.json`. The DELETE stays under `store.lock` at the same call site as today.
- **Static / asset bytes** (`/static/*`, `/review/{id}`, `/`, the asset GET) read files the handler
  *frames* but a service *owns*: static-file and viewer/dashboard reads are framing concerns the
  handler keeps (they read from `WEB_DIR`, not `/data`), but they go through `store.read_text` /
  `store.read_bytes` + `store.ctype_for` so there is one read/content-type path, not two. The asset
  GET resolves via `AssetService.find(rid, stored)` then reads bytes through the store.
- **`bump`** (the `comments_updated` / `source_updated` timestamp writes) becomes
  `ReviewService.bump(rid, field)` (it writes `meta.json`, a review concern), called by the router
  arms exactly where it is called today, always under the lock where it is under the lock today.

**Acceptance check for the boundary (non-gameable, on the server ticket).** A `_dir(`/`DATA_DIR`
substring grep is *not* sufficient: the DELETE-comment arm reaches `/data` via `_comments_path(rid)`,
which contains neither token, so that grep would pass a `server.py` that still mutates comments
inline. The server ticket instead asserts a **positive no-store-helper contract**: grep `server.py`
for every store/service-internal name that touches `/data` and require **zero** hits:
`_comments_path(`, `_assets_dir(`, `_assets_manifest(`, `_dir(`, `_read_json(`, `_write(`,
`_write_comments(`, `_find_comment(`, `_comment_as_note(`, `_stored_name(`, and `os.path.join(` with
a `DATA_DIR`/`_dir`/`_assets_dir` argument. The *only* filesystem reads `server.py` keeps are the
three `WEB_DIR` framing reads (`/`, `/review/{id}`, `/static/*`) via `store.read_text` /
`store.read_bytes`; everything `/data`-shaped goes through `self.server.app.<service>`. The grep is
the boundary's proof; the hand-count is not.

Net: the handler ends up calling `self.server.app.<service>.<method>(...)` and the response
helpers; it imports `os`/`json`/`re`/`urllib` only for path/query framing, never to build a
`/data` path. That is the difference between IoC and a rename.

**`Store` exposes lock + typed I/O as the single persistence seam.** `Store` owns `DATA_DIR` and the
one `threading.Condition`. The MR-054 pattern is preserved *exactly* by making the lock and its
notify/wait first-class pass-throughs, so every `with _lock:` site becomes `with store.lock:` with
identical semantics (a `Condition` is its own context manager). Concretely `Store` exposes:

- `store.lock` → the `Condition` itself (so `with store.lock:` acquires/releases its internal lock,
  unchanged from `with _lock:` today).
- `store.notify_all()` → `self._cond.notify_all()` (called by `HandoffService` after a write, under
  the lock, MR-054).
- `store.wait(timeout)` → `self._cond.wait(timeout)` (called by the long-poll, releases the lock
  while parked).
- Typed read/write: `dir(rid)`, `exists(rid)`, `read_text(path, default="")`,
  `read_bytes(path, default=b"")`, `read_json(path, default)`, `write_text(path, text)`,
  `ctype_for(name)`, `to_float(s, default)`.

`to_float` is the one member that is **not** persistence: it is a query-string number parser used
only by `server.py`'s `_wait` / `?since=`/`?timeout=` parsing, which stays in `server.py` (NIT-5).
The deliberate choice (called, not left implicit): keep it on `Store` as `store.to_float` so all the
moved helpers travel together as one block and there is a single home for the small utilities, and
accept that `server.py` reaches the store for this one string-parse. The alternative (a free
function `server.py` imports directly) is equally fine; the implementer may do either, but the plan
defaults to `store.to_float` and the boundary grep above explicitly does **not** flag `to_float` (it
touches no `/data` path).

**Critical invariant, stated as a key constraint below:** there is still exactly **one** `Condition`
over **one** lock, owned by the single `Store` instance, injected (not re-created) into every
service. No service constructs its own lock. `notify_all()` is still called only after a successful
write and only while holding `store.lock`; the long-poll still parks on `store.wait()` which
releases that same lock. Per-review locks remain forbidden. (`app.py:46-58`, `app.py:667-672` are
the lines whose semantics must survive verbatim.)

**Keep dict-based state: reject `@dataclass` Review/Comment/Asset.** State is dict-shaped on disk;
every read is `read_json -> dict`. Dataclasses would add a to/from-dict tax on every request for
zero behaviour and a new drift surface against the deliberately additive-default-safe schema
(`summary()` tolerating a missing `turn` key, `app.py:165`; `/status` defaulting absent
`turn`/`handoff`/`agent_status`, `app.py:594-597`). The services hold no per-review in-memory
state; each method reads from disk, mutates the dict, writes back, exactly as today. Mark the choice
with a `ponytail:` comment in `store.py` or `reviews.py`.

**`assets.py` may stay function-shaped if it reads cleaner.** It is three small functions over the
store; a class there is borderline ceremony. The plan defaults to `AssetService` for symmetry with
the other services (uniform `self.server.app.assets.*` call sites in the router), but the
implementer may keep it a plain-function module taking an explicit `store` arg if that reads better;
the constraint is only that it not build its own dependencies. The real cohesion wins are `Store`,
`CommentService`, and `HandoffService` (the hairy inline lease table → named methods on
`HandoffService`).

**Reuse, do not rewrite.** Preserve `summary()` and `_comment_as_note()` projections verbatim
(byte-identical output). Keep the exact MR-054 Condition pattern. Keep the PINNED handoff body
dispatch order (reclaim → hand-back → flip → lease → 400, `app.py:605`) so an ambiguous body stays
deterministic. Keep the content-hash asset naming and manifest-only resolution (path-traversal-proof
by construction, `app.py:230-231`, `app.py:798`).

### `mcp_server.py` and `watch.py` (moved as-is, no internal refactor)

Both are **self-contained and do not import `app`** (verified): `mcp_server.py` is a pure HTTP
client keyed off `MDREVIEW_BASE` (it never reads `viewer.html`/`static`/`__file__`-relative web
assets); `watch.py` is keyed off `WATCH_LAUNCH_CMD` and the env contract. So `git mv mcp_server.py
watch.py src/` is path-neutral for the scripts themselves. The **only** consequence is the two
smokes that point at `mcp_server.py` (see below). They do **not** join the `mdreview` package (the
brief's "standalone script (does NOT import the package)" is correct) and are not internally
refactored this epic.

### UI (`viewer.html` / `dashboard.html` / `static/`) → `web/`

No behaviour change and no markup change. The frontend is `git mv`-ed to `web/` (`viewer.html`,
`dashboard.html`, `static/`). The **only** code consequence is path resolution in the service:
`app.py` serves these via `os.path.join(HERE, ...)` (`app.py:500` dashboard, `app.py:812` viewer,
`app.py:818` static). After the move, `HERE` (the module dir, now `src/mdreview/`) no longer points
at the frontend. Replace with a single `WEB_DIR` constant in `config.py`:

```python
# ponytail: repo-root anchor; MDREVIEW_WEB_DIR overrides in container/tests
WEB_DIR = os.environ.get("MDREVIEW_WEB_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")
```

The three-level `dirname` walk is `src/mdreview/config.py` → `src/mdreview/` → `src/` → repo root,
then `+ "/web"`. The container sets `ENV MDREVIEW_WEB_DIR=/app/web` so prod never relies on the
`../../..` arithmetic, and the render-smoke / local boots can point `MDREVIEW_WEB_DIR` at a throwaway
dir. **The viewer's `STALE_S=180` constant (`viewer.html:249`) is untouched**: it mirrors
`LEASE_TTL_S` and the mirror relationship is unchanged by the move (both stay seconds; the constant
just lives in `web/viewer.html` now).

**Render proof is the gate, not a 200.** Because the viewer renders client-side (marked + mermaid +
KaTeX), every phase boundary that touches the served pages asserts the rendered DOM from a rebuilt
throwaway container with `tests/render-smoke.sh` (the relocated `scripts/render-smoke.sh`), not a
curl 200. The selectors are flat (`tag` / `.class` / `tag.class` / `#id`, no combinators) per the
matcher's contract.

### Infra (stays at root)

`Dockerfile`, `Dockerfile.watcher`, `docker-compose.yml`, `.env.example`, and `watcher/` stay at
root (conventional infra residents; root's "no dangling" rule means "no loose source/frontend"). The
edits, with container destinations held stable so `agent-mcp.json` and `docker-compose.yml` need no
change:

- **`Dockerfile`** (service): replace `COPY app.py viewer.html dashboard.html ./` + `COPY static/
  ./static/` with `COPY src/ ./src/` and `COPY web/ ./web/`; add `ENV MDREVIEW_WEB_DIR=/app/web` and
  `ENV PYTHONPATH=/app/src` (so `python -m mdreview` resolves); change the final `CMD`. **Phase 0**
  lands `CMD ["python", "src/app.py"]` (the relocated monolith); **Phase 1's final ticket** switches
  it to `CMD ["python", "-m", "mdreview"]` once `server.py`/`__main__.py` exist. The `HEALTHCHECK`
  hits `127.0.0.1:8080/healthz` and is unchanged.
- **`Dockerfile.watcher`**: change `COPY watch.py mcp_server.py ./` to `COPY src/watch.py
  src/mcp_server.py ./`. This **flattens** the two scripts to `/app/watch.py` and
  `/app/mcp_server.py`, destinations identical to today, so `CMD ["python3", "watch.py"]`,
  `agent-mcp.json`'s `["/app/mcp_server.py"]`, and `compose`'s `/app/watcher/launch.sh` all need
  **no** change. `COPY watcher/ ./watcher/` is unchanged.
- **`tests/mcp_smoke.py`, `tests/agent_smoke.py`**: both currently set `SERVER =
  os.path.join(HERE, "mcp_server.py")` (`mcp_smoke.py:19`, `agent_smoke.py:34`) because today the
  smoke and the server are siblings at root. After the moves (smokes → `tests/`, server → `src/`)
  the relative path becomes `SERVER = os.path.join(HERE, "..", "src", "mcp_server.py")`. (The
  brief's step-3 text quotes the *target* string, not the current code; the current code is the
  bare-sibling form; this plan corrects that and cites the real current lines.)

**Unchanged by this epic:** `docker-compose.yml`, `watcher/launch.sh`, `watcher/agent-mcp.json`, the
`/data` on-disk format, every HTTP response shape, and `viewer.html`/`dashboard.html` markup.

## Rollout phases

Each phase is independently shippable: Phase 0 leaves a working, relocated service on the new layout
even if Phase 1 never lands; each Phase-1 step leaves a working service with one more concern
extracted.

### Phase 0: relocate + path fix (no logic change)

The whole monolith moves to `src/app.py` and the frontend to `web/`, with only the `HERE`→`WEB_DIR`
path swap as a logic-touching edit. At the end of Phase 0 the service runs from the new layout, the
container builds and serves a rendered viewer, the watcher image builds, the smokes pass from their
new home, and the three live gate refs point at the new target. No `app.py`-internal decomposition
yet; `src/app.py` is still the monolith, just relocated and path-fixed.

### Phase 1: decompose internals, bottom-up, one module per commit

With the layout settled, extract the seven modules from `src/app.py` in dependency order
(config → store → comments → assets → reviews → handoff → server), one per commit, each
`py_compile`-clean and smoke-green before the next, each diffed against the golden transcript for
byte-identical API responses. The final step renames `src/app.py` to `src/mdreview/server.py`, adds
`__init__.py` + `__main__.py`, and flips the container entrypoint to `python -m mdreview`.

## Non-goals

Explicit scope boundaries: what this epic is deliberately **not** doing.

- **No behaviour change of any kind.** Not one HTTP response byte, not one `/data` file, not one
  rendered DOM node differs. Any "while I'm in here" improvement (new endpoint, schema field, viewer
  tweak, perf change) is out of scope and belongs in its own epic.
- **No `@dataclass` / typed domain models.** Dict-on-disk state is retained on purpose (see Core
  design principle). This epic does not introduce `Review`/`Comment`/`Asset` model classes.
- **No internal refactor of `mcp_server.py` or `watch.py`.** They move to `src/` as-is. Their
  internal structure is untouched.
- **No DI framework.** Wiring is hand-written constructor injection through one `main()`. No
  container library, no service locator, no decorators.
- **No change to the lock model.** One `Condition` over one lock stays; per-review locks are not
  introduced (they would break MR-054 long-poll correctness).
- **No rewrite of `agent-mcp.json` / `docker-compose.yml`.** Container destinations are held stable
  precisely so these need no edit.
- **No edits to frozen ticket/sprint/review history.** The many historical `py_compile app.py`
  mentions across `docs/process/tickets/**`, `sprints/**`, `reviews/**`, and shipped epic plans (well
  over a hundred, in dozens of files) are the audit trail and stay verbatim. Only the live,
  forward-governing refs change (see Key constraints).
- **No new vendored frontend asset.** Nothing is added to `static/`; the Dockerfile-COPY-for-new-
  served-file footgun does not apply here (no new served file; `web/` is the *same* files relocated,
  and the `COPY web/ ./web/` is the relocation of the existing `COPY static/`).

## Key constraints

Hard rules the implementation must not violate.

- **Stdlib-only, zero pip, no build.** Nothing added to the runtime. The whole refactor is
  rearranging stdlib Python; no library is reached for. (The small image / "no installs" is
  load-bearing.)
- **Byte-identical API.** Every pure-refactor commit must produce responses byte-identical to the
  pre-start golden transcript. The transcript is the oracle (there is no test framework).
- **MR-054 lock invariant survives verbatim.** Exactly one `threading.Condition` over one lock,
  owned by the single `Store`, injected into all services. `notify_all()` only after a successful
  write and only under `store.lock`; the long-poll parks on `store.wait()` (which releases that
  lock). **Never** a second lock; **never** per-review locks. (`app.py:46-58`, `app.py:667-672`.)
- **Services never acquire `store.lock`; the lock is taken only where it is taken today.** Once
  `store.lock` is a reachable member, the realistic split-time bug is not a *second* lock but a
  service method "made thread-safe" by re-acquiring the *one* lock (e.g. wrapping `list_reviews()`
  or `summary()` in `with self.store.lock:`). That is forbidden. The lock is acquired at exactly the
  call sites that acquire it today (the router arms `PUT /source`, `/handoff`, `POST`/`DELETE`
  comments, `POST` assets, and `_wait`), never inside a service method that a locked arm calls. The
  service writers keep their existing "caller holds the lock" contract (`create_comment`,
  `_write_comments`, `attach_asset`, `apply_comment_transition`, `snapshot_round`,
  `delete_comment`). **`list_reviews()` and `summary()` must stay lock-free** (verified lock-free
  today): `_wait` holds `store.lock` and calls `list_reviews()` *under it* (`app.py:452-459`), so if
  `list_reviews`/`summary` ever took the lock the nested call would re-acquire it. (The stdlib
  `Condition` wraps an `RLock`, so re-acquisition does not *deadlock* and `wait()` still fully
  releases, so this is a contract/clarity violation, not a correctness crash, but it defeats the
  single-lock reasoning the whole design rests on, so it is barred.) The store + server tickets grep
  the extracted tree for `store.lock`/`.lock:` **acquisition** sites and confirm they are only the
  ones above, and that `list_reviews`/`summary` contain no acquisition.
- **Overwrite-based persistence is unchanged.** `PUT /source` still `snapshot_round()`s then
  overwrites `source.md`; comment/asset writes are still whole-file. No new history surface, no
  append-only conversion. The refactor moves these writes into services without changing when or how
  they fire.
- **Additive-default-safe reads preserved.** Every reader still defaults missing keys
  (`summary()` `turn`/`revision`; `/status` `turn`/`turn_updated`/`handoff`/`agent_status`). Legacy
  reviews on the live `/data` volume lack newer keys; the services must not assume presence.
- **Single-file regex router semantics preserved.** Route order and the `RID = [A-Za-z0-9]{4,40}`
  pattern are unchanged. The `/api/reviews/wait` arm must still precede the per-review `RID` arm
  (`app.py:517` before `app.py:534`) or it gets shadowed into a 404 lookup; this ordering moves
  into `server.py`'s `route()` intact. The handoff body dispatch keeps its pinned order.
- **No auth / id-only tenancy is unchanged.** This epic adds no listing/aggregation surface, so it
  does not widen exposure. `list_reviews()` already aggregates across reviews; its behaviour is
  preserved, not extended.
- **HEAD still 501; `Content-Type`/`Content-Length` checks use a GET header-dump.** The handler
  defines only `do_GET/POST/PUT/DELETE/OPTIONS` (no `do_HEAD`), so `curl -sI` hits the 501 page.
  Every verification step that inspects a header (e.g. asserting `/static/*.woff2` serves as
  `font/woff2`, or the viewer is `text/html; charset=utf-8`) uses `curl -sD - -o /dev/null <url>`,
  never `curl -sI`. (The `_send` framing, including the `X-Content-Type-Options: nosniff` and CORS
  headers, `app.py:393-399`, moves into `server.py` unchanged.)
- **render-smoke is a flat matcher.** Its selectors are `tag` / `.class` / `tag.class` / `#id` only:
  no descendant combinators, attributes, or pseudo-classes (a space gives exit 2, not a miss). Assert
  a node *inside* a container with two separate selectors, never `'#parent child'`.
- **`WEB_DIR` is env-overridable with a repo-root default.** `MDREVIEW_WEB_DIR` wins; absent, the
  `../../..`-from-`config.py` anchor resolves to `<repo>/web`. The container sets it explicitly so
  prod never depends on the path arithmetic.
- **Container destinations are stable.** `/app/mcp_server.py`, `/app/watcher/launch.sh`, the service
  on `:8080`, `python -m mdreview` from `PYTHONPATH=/app/src`, chosen so `agent-mcp.json` and
  `docker-compose.yml` need no edit. Any change that would force editing those two files is wrong.
- **Only the LIVE gate refs change in docs; history is frozen.** Update exactly the three forward-
  governing `python3 -m py_compile app.py` refs in `docs/process/README.md` (the Divergences
  bullet, Development-flow step 5, and the **G4 pass-condition row**) and the one validation-gate
  mention in `CLAUDE.md` (the "Delivery process" bullet). New gate command:
  `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`. **Do not** touch the
  many historical mentions in tickets/sprints/reviews/shipped-epics. The `docs/process/README.md`
  Divergences bullet and the validation-gate sentence are prose; the **G4 pass-condition row** is
  the enforcing row and must carry the new command text, not merely be cited (see the Risk register
  gate-ref risk, and the enforcement note below).
- **Validate against a rebuilt throwaway container on a scratch port, never `docker compose up`,
  never the live volume.** Compose says `:8137`; the live instance is `:8139`. All build/smoke/
  render verification runs a fresh `docker run` on a scratch port with a throwaway `MDREVIEW_DATA`
  (a gitignored `.scratch/` dir), never touching `mdreview-data` or the running service.
- **Europe/London dates; `Co-Authored-By: Claude` trailer; conventional subject with the ticket
  ID.** Every commit references its `MR-###`. `git mv` is used for all relocations to preserve file
  history.

**Enforcement note (G4 row).** This epic changes the project's standing validation gate (the
`py_compile` target moves from `app.py` to `src/...`). Per the process's "wire enforcement into the
gate row" rule, the new command must be written **into the G4 pass-condition row text** in
`docs/process/README.md`, not only into the Development-flow step or the Divergences prose. A docs
ticket in Phase 0 carries that edit, and the Phase-0 acceptance criteria assert the G4 row itself
quotes `py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`.

## Preferred execution order

1. **Capture the golden transcript first (before any move).** Boot current `app.py` on a scratch
   port against a throwaway `MDREVIEW_DATA`; run the full endpoint sweep (POST → GET source → PUT →
   GET feedback → POST comment → reply → resolve → 409-double-resolve → GET status → handoff flip →
   `/wait` wake → POST asset → GET asset bytes → GET history → GET history/{n} → 410 on POST
   feedback). Save responses (and the asset bytes' sha) as the oracle. This is the artifact every
   later commit diffs against; it is not a ticket deliverable but the **first action of the first
   ticket**.
2. **Phase 0, in four slices** (relocate + path fix; service Dockerfile; scripts/smokes + watcher
   Dockerfile; live doc gate refs).
3. **Phase 1, seven slices, bottom-up** (config → store → comments → assets → reviews → handoff →
   server-rename+`__main__`+entrypoint-flip), each diffed against the golden transcript.
4. **Final `mdreview-qc`** end-to-end PASS/FAIL on the rebuilt image; then the sprint-close G7
   render-smoke + container rebuild + `curl /healthz` + `/api/reviews`.

## Ticket breakdown

Create these in `tickets/` after G1. Phase 0 is split so a path/deploy break is isolated from a
script/smoke break; each Phase-1 extraction is its own ticket so a logic break is isolated to one
module. Layer tags: `infra` where the deliverable is a Dockerfile/COPY/CMD change or a move that the
container build depends on; `svc` for `app.py`/`src/mdreview/**` logic; `docs` for the gate refs.
(The frontend move is tagged `infra`, not `ui`: no markup or render behaviour changes, so it is a
relocation + COPY change, not a UI change; its acceptance criteria still include a render-smoke
because a served page moved.)

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-### | Capture golden API transcript + relocate `app.py`→`src/app.py`, frontend→`web/`, swap `HERE`→`WEB_DIR`; boot-on-scratch-port smoke | svc | 0 |
| MR-### | Service `Dockerfile`: `COPY src/`+`web/`, `ENV MDREVIEW_WEB_DIR`/`PYTHONPATH`, `CMD python src/app.py`; build + throwaway container + render-smoke | infra | 0 |
| MR-### | Move `mcp_server.py`/`watch.py`→`src/`, smokes→`tests/`, `render-smoke.sh`→`tests/`; fix smoke `SERVER` path; update `Dockerfile.watcher` COPY sources; watcher build + `mcp_smoke.py` | infra | 0 |
| MR-### | Update the 3 live `py_compile` gate refs in `docs/process/README.md` (incl. the G4 row text) + the `CLAUDE.md` validation-gate bullet to `src/...`; leave frozen history untouched | docs | 0 |
| MR-### | Extract `config.py` (constants + `WEB_DIR`, drop `HERE`); `py_compile` + boot smoke | svc | 1 |
| MR-### | Extract `store.py` + `Store` (typed I/O + the one Condition as `lock`/`notify_all`/`wait`); long-poll wake smoke (`/wait?since=0` parks, `/handoff to=agent` wakes it) | svc | 1 |
| MR-### | Extract `comments.py` + `CommentService` (full state machine); comment lifecycle curl incl. 409 on double-resolve | svc | 1 |
| MR-### | Extract `assets.py` + `AssetService`; POST asset → GET `/asset/<stored>` bytes match + `agent_smoke.py` | svc | 1 |
| MR-### | Extract `reviews.py` + `ReviewService` (lifecycle + summary/list + history + the inline source/feedback reads); POST → 2×PUT → `/history`; `/feedback` projection diff | svc | 1 |
| MR-### | Extract `handoff.py` + `HandoffService` (lease decision table); MR-055 matrix (claim/renew/foreign-fresh→409/stale+turn=agent→grant/stale-reclaimed→409) | svc | 1 |
| MR-### | `git mv src/app.py → src/mdreview/server.py`, add `__init__.py`/`__main__.py`, flip `Dockerfile` `CMD` to `python -m mdreview`; full render-smoke + all smokes + build + healthcheck + `mdreview-qc` | svc | 1 |

## Risks and mitigations

| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| **No behavioural tests**: only smokes + `py_compile`; a subtle byte difference (e.g. JSON key order, a `dict(meta(rid))` copy lost, a default flipped) slips through. | Med / High | The **golden transcript captured before any change** is the oracle; every pure-refactor commit diffs its responses byte-for-byte against it (including the asset bytes' sha). `summary()`/`_comment_as_note()` are moved **verbatim**. Diff is run per commit, not just per phase, so the breaking commit is named. |
| **Live service / data on `:8139`**: a verification step accidentally hits the live instance or the `mdreview-data` volume and corrupts real reviews. | Low / High | Every build/smoke/render step runs a **fresh `docker run` on a scratch port** with a throwaway `MDREVIEW_DATA` under gitignored `.scratch/`. The plan forbids `docker compose up` (it binds `:8137`) and forbids touching `mdreview-data`. Acceptance criteria name the scratch port + throwaway dir explicitly. |
| **`HERE`→`WEB_DIR` path resolution**: the `../../..` anchor miscounts a level (`src/mdreview/config.py` is three `dirname`s from repo root, not two), or the container forgets `ENV MDREVIEW_WEB_DIR`, so `/review/{id}` and `/static/*` serve empty 200s (the sprint-01-class bug). | Med / High | `WEB_DIR` is **env-overridable**, and the container **sets `MDREVIEW_WEB_DIR=/app/web` explicitly** so prod never depends on the arithmetic. The Phase-0 acceptance criteria assert `/review/{id}`, `/`, and `/static/marked.min.js` all return **200 and non-empty** *and* a `tests/render-smoke.sh` asserts real DOM nodes from the rebuilt container (a 200 is not a render). The arithmetic is verified once against a local boot before the container relies on the env var. |
| **Lock/Condition extraction**: moving `_lock` into `Store` creates a second lock, re-creates the Condition per service, moves a `notify_all()` outside the lock, **or a service method re-acquires the one `store.lock` it (or its caller) already holds** (e.g. `list_reviews`/`summary` "made thread-safe"), breaking or muddying MR-054 long-poll. | Med / High | The store ticket is isolated and its smoke is the **long-poll wake test** (`/wait?since=0` parks in one shell; `/handoff to=agent` in another must wake it). The plan mandates: one `Condition`, owned by the single injected `Store`; `notify_all()` only under `store.lock` after a write; `wait()` releases that same lock; and **services never acquire `store.lock`** (it is taken only at the arms + `_wait` that take it today, with `list_reviews`/`summary` lock-free so `_wait`'s nested `list_reviews()` call keeps its shape). Checklist items on the store + server tickets grep the extracted tree both for a second `Lock(`/`Condition(` constructor (exactly one) **and for `store.lock`/`.lock:` *acquisition* sites** (only the permitted ones; none inside `list_reviews`/`summary`). |
| **Router still calls store primitives**: the move is cosmetic (handler keeps doing `_read(os.path.join(_dir(rid), ...))` *or* the inline `_write_comments` of the DELETE-comment arm), so "IoC" is a rename and the next contributor still can't reason about a service in isolation. | Med / Med | The plan maps **every** inline `/data` touch in `route()` to a service method (including the two comment arms a hand-count missed, `get_comment` and `delete_comment`), and the handler may import `os`/`json`/`re`/`urllib` only for path/query *framing*, never to build a `/data` path. The acceptance check is a **positive no-store-helper grep** (a `_dir(`/`DATA_DIR` substring grep is gameable: the DELETE arm reaches `/data` via `_comments_path`, which contains neither token). The server ticket asserts `server.py` has **zero** hits for `_comments_path(`, `_assets_dir(`, `_assets_manifest(`, `_dir(`, `_read_json(`, `_write(`, `_write_comments(`, `_find_comment(`, `_comment_as_note(`, `_stored_name(`, and `os.path.join(` with a `/data` arg; the only kept reads are the three `WEB_DIR` framing reads via `store.read_text`/`read_bytes`. |
| **Doc gate refs**: the new `py_compile` target lands only in prose (the Divergences bullet / Development-flow step) while the **G4 pass-condition row** still says `app.py`, so the enforced gate is wrong even though the docs "mention" the new path. | Med / Med | Per the process "wire enforcement into the gate row" rule, the docs ticket's acceptance criteria require the **G4 row text itself** to quote `python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`; the prose mentions are necessary but explicitly not sufficient. A grep asserts the row, not just the file, contains `src/mdreview`. |
| **`git mv` history / partial move**: a file moved but a stale reference (a smoke's `SERVER`, a Dockerfile COPY) left pointing at the old path; build/smoke breaks late. | Med / Med | Phase 0 is sliced so each move + its dependent edits land in **one ticket** (frontend move with the `WEB_DIR` swap; scripts move with the smoke `SERVER` fix + watcher COPY; service Dockerfile with its `CMD`). Each slice's acceptance criteria rebuild the relevant image and run its smoke before the next slice starts. |
| **`python -m mdreview` packaging**: `__main__.py` / `__init__.py` wrong, or `PYTHONPATH=/app/src` missing, so the final entrypoint flip fails in the container though it worked locally. | Low / Med | The entrypoint flip is the **last** Phase-1 ticket; until then the container runs `python src/app.py` (proven in Phase 0). The flip ticket's acceptance criteria run `python -m mdreview` **inside a rebuilt throwaway container** (not just locally) plus the full smoke + render + healthcheck + `mdreview-qc`. |
| **`mdreview-qc` / staff-critic find a behaviour delta at the end**: a regression survived the per-commit diffs (e.g. an edge endpoint not in the transcript). | Low / Med | The golden transcript covers the **full** endpoint surface (listed in execution order step 1, including 404/409/410 error arms). The final `mdreview-qc` run is an independent end-to-end check on the rebuilt image; G7 adds the independent staff-critic sprint-close review with its own render smoke. |

## Verification

No test framework: smokes + `py_compile` + render-smoke + a golden curl transcript are the oracle.
All commands run against a **rebuilt throwaway container on a scratch port** with a throwaway
`MDREVIEW_DATA` (gitignored `.scratch/`), never `docker compose up` (binds `:8137`) and never the
live `:8139` / `mdreview-data` volume.

**Golden transcript (capture once, before the first move; diff every pure-refactor commit against
it).** Boot current `app.py` on a scratch port and capture each response (and the asset bytes' sha):

```bash
# in .scratch/, against a fresh throwaway data dir, e.g. PORT=8155
B=http://localhost:8155
id=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"golden","markdown":"# H\n\npara `x` and $a+b$\n","project":"qc","session":"g"}' | tee /dev/stderr | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s "$B/api/reviews/$id"                                          # GET meta (app.py:539-540)
curl -s "$B/api/reviews/$id/source"                                   # text/markdown, exact bytes
curl -s -X PUT "$B/api/reviews/$id/source" -H 'Content-Type: application/json' -d '{"markdown":"# H2\n\nrevised\n"}'
curl -s "$B/api/reviews/$id/feedback"                                 # {markdown, notes:[...], ...meta}
cid=$(curl -s -X POST "$B/api/reviews/$id/comments" -H 'Content-Type: application/json' \
  -d '{"anchor":{"quoted_text":"revised"},"text":"tighten","role":"reviewer"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["comment_id"])')
curl -s "$B/api/reviews/$id/comments/$cid"                            # GET single thread (app.py:760 -> CommentService.get_comment)
curl -s -X POST "$B/api/reviews/$id/comments/$cid/reply"   -H 'Content-Type: application/json' -d '{"text":"ok?","role":"agent"}'
curl -s -X POST "$B/api/reviews/$id/comments/$cid/resolve" -H 'Content-Type: application/json' -d '{"justification":"done"}'
curl -s -X POST "$B/api/reviews/$id/comments/$cid/resolve" -H 'Content-Type: application/json' -d '{}'   # expect 409 {"error":"comment is not open/reopened","status":"resolved"}
# reopen branch of apply_comment_transition (app.py:370-378); drive it so it has an oracle:
curl -s -X POST "$B/api/reviews/$id/comments/$cid/reopen"  -H 'Content-Type: application/json' -d '{"text":"not quite"}'  # expect 200, status "reopened"
curl -s -X POST "$B/api/reviews/$id/comments/$cid/reopen"  -H 'Content-Type: application/json' -d '{}'                   # expect 409 (not resolved), status "reopened"
curl -s "$B/api/reviews/$id/status"                                  # source_updated/comments_updated/turn/...
curl -s -X POST "$B/api/reviews/$id/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'   # flip
curl -s -X POST "$B/api/reviews/$id/feedback" -H 'Content-Type: application/json' -d '{}'              # expect 410 {"error":"gone, use comments"}
b64=$(printf 'PNGDATA' | base64); curl -s -X POST "$B/api/reviews/$id/assets" -H 'Content-Type: application/json' -d "{\"name\":\"fig/p.png\",\"content_b64\":\"$b64\"}"
stored=$(curl -s "$B/api/reviews/$id/assets" | python3 -c 'import sys,json;print(json.load(sys.stdin)["assets"][0]["stored"])')
curl -s "$B/api/reviews/$id/asset/$stored" | shasum                  # bytes sha must match post-refactor
curl -s "$B/api/reviews/$id/history"; curl -s "$B/api/reviews/$id/history/0"
# DELETE a comment (app.py:765-772 -> CommentService.delete_comment): delete, then re-GET -> 404
curl -s -X DELETE "$B/api/reviews/$id/comments/$cid"                 # expect 200 {"deleted": "<cid>"}
curl -s -X DELETE "$B/api/reviews/$id/comments/$cid"                 # second delete -> expect 404 {"error":"no such comment"}
# DELETE a review (app.py:541-543), destructive: use a SEPARATE throwaway review so the sweep above survives:
id2=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' -d '{"title":"throwaway","markdown":"# x\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X DELETE "$B/api/reviews/$id2"                              # expect 200 {"deleted": "<id2>"}
curl -s "$B/api/reviews/$id2"                                        # re-GET -> expect 404 {"error":"not found"}
```

The acceptance gate for every Phase-1 (and Phase-0) commit: re-running this sweep against the
rebuilt service yields **byte-identical** JSON bodies (modulo the inevitably-changing timestamps and
the random `id`/`id2`/`comment_id`/`stored` hash, which are normalized out of the diff) and an
identical asset-bytes sha. The sweep now covers every mutation with no other oracle (DELETE-comment,
DELETE-review, and the `reopen` state-machine branch), plus GET-meta and GET-single-comment.

**Long-poll wake (the MR-054 invariant), the `store.py` ticket's gate:**

```bash
# shell A: park a backlog waiter (since=0 is the explicit backlog opt-in)
curl -s "$B/api/reviews/wait?since=0&turn=agent&timeout=20"   # blocks
# shell B (within the timeout): flip a review to agent
curl -s -X POST "$B/api/reviews/$id/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'
# shell A must return {"reviews":[{... "turn":"agent" ...}]} (woke on notify_all), NOT {"timeout":true}
```

**Lease decision matrix (the `handoff.py` ticket's gate)**: claim grants, same-owner renews,
foreign-fresh 409s, foreign-stale-with-turn=agent grants, foreign-stale-already-reclaimed 409s
(MR-055). Drive with `state:"working"` bodies varying `owner`/turn per `app.py:639-664`.

**Per commit:** `python3 -m py_compile` the touched files (after Phase 0, the gate command is
`python3 -m py_compile src/mdreview/*.py src/mcp_server.py src/watch.py`) + the relevant smoke
(`tests/mcp_smoke.py`, `tests/agent_smoke.py`, or the targeted curl above).

**Phase boundaries:** `docker build .` **and** `docker build -f Dockerfile.watcher .`; run a
throwaway service container on a scratch port; then a **render-smoke from the rebuilt container**
(a 200 is not a render):

```bash
# rebuilt service container on scratch port 8155, throwaway data; then create a review and assert DOM.
# Real ids, confirmed against viewer.html / dashboard.html (#article is the markdown render target;
# h1 is the rendered heading; render-smoke can't do '#article h1' (no descendant combinator) so the
# two are SEPARATE selectors per the flat-matcher contract):
tests/render-smoke.sh "http://localhost:8155/review/$id" '#article' 'h1'
tests/render-smoke.sh "http://localhost:8155/"            '#list' '.card'   # dashboard renders cards into #list
# header check uses a GET dump, never curl -sI (HEAD 501s):
curl -sD - -o /dev/null "http://localhost:8155/static/marked.min.js"   # expect Content-Type: text/javascript
curl -sD - -o /dev/null "http://localhost:8155/review/$id"             # expect Content-Type: text/html; charset=utf-8
curl -s  "http://localhost:8155/healthz"                               # {"ok": true}
```

These selectors are real (`#article`/`h1` in `viewer.html`; `#list`/`.card` in `dashboard.html`,
confirmed at plan time); after the move they live in `web/`. `.card` rendering requires at least one
review to exist (create the golden review first); `#article` + `h1` require the viewer to have
rendered the markdown, which is the whole point of asserting DOM rather than a 200.

**Final:** the `mdreview-qc` agent for an end-to-end PASS/FAIL on a rebuilt image, then the G7
independent staff-critic sprint-close review (container rebuild + `curl /healthz` + `/api/reviews`,
plus per-page render-smoke + screenshot under `reviews/sprint-NN-render-evidence-*` because served
pages moved).

## Assumptions & open questions

Recorded per the planner's method. Each is tagged **load-bearing** (changes the design) or **minor**;
the best-effort assumption the plan proceeds on is stated. No question here has *no* safe default, so
there is **no BLOCKER-FOR-HUMAN**; but the load-bearing ones are flagged for the critic/owner.

1. **(load-bearing) How aggressively must the router stop calling store primitives?** The brief's
   IoC model says "H delegates to injected services," but `route()` calls low-level store helpers
   inline in ~30 places. **Assumption:** the handler must reach `/data` *only* through service
   methods (existence guard, source/feedback/history reads, and `bump` all become service methods);
   it may still use the store's text/bytes reader for `WEB_DIR` static/viewer files, since those are
   framing, not domain state. Justification: anything less makes "IoC" a rename and fails the core
   reviewability goal; anything more (e.g. routing static files through a service) is ceremony for
   files that aren't review state. If the owner wants the handler to keep doing ad-hoc `/data` reads,
   that materially shrinks the `ReviewService` surface and should be said before tickets.
2. **(load-bearing) Is `AssetService` a class or a plain-function module?** The brief explicitly
   leaves this open ("a class there is borderline ceremony"). **Assumption:** ship it as
   `AssetService` for call-site symmetry (`self.server.app.assets.*`), but the implementer may keep
   it functions-with-explicit-store if cleaner. Justification: the cohesion win is marginal either
   way; the constraint that matters (no self-built dependencies) holds in both shapes. This does not
   block tickets; it's an implementer's-discretion note on one ticket.
3. **(minor) Phase-0 transitional entrypoint.** The brief's Phase-0 Dockerfile step says
   `CMD python src/app.py` (the relocated monolith), and Phase 1's last step switches to
   `python -m mdreview`. **Assumption:** keep that two-step entrypoint (monolith runs from
   `src/app.py` through all of Phase 0 and most of Phase 1; the package entrypoint lands only when
   `server.py`/`__main__.py` exist). Justification: it keeps every intermediate commit runnable and
   isolates the packaging change to one ticket. Alternative (build the package skeleton in Phase 0)
   couples layout and decomposition, which the brief explicitly separates.
4. **(minor) Smoke `SERVER` path correction.** The brief's step-3 text quotes
   `SERVER = os.path.join(HERE, "..", "src", "mcp_server.py")` as if it were current code; the
   actual current code is `os.path.join(HERE, "mcp_server.py")` (`mcp_smoke.py:19`,
   `agent_smoke.py:34`). **Assumption:** the brief is describing the *target* string; the edit is
   bare-sibling → `../src/`. No design impact; recorded so the critic isn't surprised by the
   discrepancy.
5. **(minor) Scope of the live doc-ref edit.** The brief says "the 3 live gate refs in
   `docs/process/README.md` + run-commands in README/CLAUDE/AGENTS." **Verified:** the three
   README.md `py_compile app.py` refs are the Divergences bullet, Development-flow step 5, and the
   G4 row; the only other live run-ref is `CLAUDE.md`'s validation-gate bullet. README.md / AGENTS.md
   "run your own instance" sections are `docker compose`/`docker run` (container-based, unaffected by
   the move). **Assumption:** edit those four spots only; leave the many historical mentions frozen.
   Justification: matches the brief's "leave frozen history untouched" and the process's
   cite-by-name / audit-trail rules. (NIT-6: an earlier draft cited "~290" historical mentions; the
   exact figure is scope-dependent and unimportant, so the plan describes the surface qualitatively.)
6. **(minor) `agent-mcp.json` lives in `watcher/`, not root.** The brief's "Files changed →
   Unchanged" lists `agent-mcp.json`; it is at `watcher/agent-mcp.json` and references
   `/app/mcp_server.py`. **Assumption:** it stays unchanged because the watcher Dockerfile flattens
   `src/mcp_server.py` → `/app/mcp_server.py` (destination preserved). Recorded because the brief's
   target-layout tree implies a root `agent-mcp.json` that does not exist there.
