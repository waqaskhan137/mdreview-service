---
id: MR-056
title: "`watch.py` fail-closed loop core — trusted-base check + `/wait` long-poll + claim-before-spawn"
status: review         # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-18
epic: agent-watcher
depends_on: []
branch: MR-056-watcher-fail-closed-loop-core
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Build the core of `watch.py` — a new stdlib-only file at the repo root, sibling to `mcp_server.py` — that
turns C1's server primitives into an automatic baton pickup loop **without** the credentialed spawn yet.
This ticket owns the two load-bearing safety proofs: the **fail-closed trusted-base check** (the security
crux — `watch.py` is a credentialed spawner, so it must refuse to start against a base it cannot vouch for)
and the **claim-before-spawn single-flight** gate (winning C1's `/handoff {state:working}` lease before
ever spawning, so a cold start or two ticks can never double-spawn the same flip). It spawns only a
trivial placeholder command, so the claim/skip/refuse logic is testable before the real launcher
(MR-057) is wired. No `app.py` change — C1 already shipped the server side.

## Acceptance criteria

- [ ] **New `watch.py` at repo root, stdlib only, off by default.** Sibling to `mcp_server.py`:
      `urllib.request`/`urllib.error` (HTTP), `subprocess` (spawn), `threading`, `os`/`json`/`time`/`sys`
      — no pip, nothing vendored. `MDREVIEW_BASE` read the same way as `mcp_server.py:35`
      (`os.environ.get("MDREVIEW_BASE", "http://localhost:8137").rstrip("/")`). Not imported by `app.py`,
      not in the Dockerfile, not started by compose — `python3 watch.py` is the only way it runs.
- [ ] **Step 0 — fail-closed trusted-base check runs FIRST, before any network call.** On failure it
      prints a one-line reason to stderr and **exits non-zero** (refuse-and-exit, never warn-and-continue).
      Exact comparison: `host = urllib.parse.urlparse(base).hostname`; `trust =
      os.environ.get("WATCH_TRUSTED_BASE")`. If `trust` is None/empty ⇒ allow **loopback only**
      (`host in ("localhost", "127.0.0.1", "::1")`). Else allow iff `trust.rstrip("/") == base` — an
      **exact-string match** of the full normalized base (no wildcard, no prefix, no host-only match). Any
      mismatch ⇒ `allowed=False` ⇒ refuse.
- [ ] **The refusal message names BOTH `MDREVIEW_BASE` and `WATCH_TRUSTED_BASE` (WC-1).** Because the
      match is deliberately strict (`http`/`https`, `host`/`host:port`, `localhost`/`127.0.0.1` are
      distinct), the refusal prints both strings so a brittle mismatch is self-explaining (e.g. "refusing:
      MDREVIEW_BASE=<x> does not match WATCH_TRUSTED_BASE=<y>"). The fix for a paper-cut mismatch is the
      better message, **not** a looser comparand — the strictness is the control.
- [ ] **`::1` is in the loopback allowlist** alongside `localhost`/`127.0.0.1` (an IPv6 loopback base
      yields `::1` from `urlparse`).
- [ ] **HTTP helper that branches on status, does NOT raise-on-409.** A small `_http(method, path,
      body=None)` like `mcp_server.py:376-389`, but it must **inspect the status code** — it catches
      `urllib.error.HTTPError` (which carries `.code` and is itself a response) and returns `(status,
      body)` so the claim step can branch on `200` vs `409`. A `409` from `/handoff {state:working}` is an
      expected, normal "skip this review" signal, not an error to retry.
- [ ] **Step 1 — cursor seeding.** Default seed = `now` (`time.time()`) — watch for the *next* flip, no
      pre-read, matching `/wait`'s own missing-`since` default; a fresh watcher does **not** stampede the
      existing agent-turn backlog. A `since=0` / `--backlog` (e.g. `WATCH_SINCE=0`) env/flag is the
      explicit, off-by-default opt-in to pick up the existing backlog on start.
- [ ] **Step 2 — long-poll `/wait` and advance the cursor.** Loop:
      `GET /api/reviews/wait?turn=agent&since=<cursor>&timeout=<WATCH_WAIT_TIMEOUT_S>`; on timeout
      (`{"reviews":[],"timeout":true}`) re-poll with the **cursor unchanged**; else advance the cursor to
      the **max `turn_updated`** of the returned rows and `handle(r)` each. On a `urllib`/network error,
      catch, log, **back off** a couple of seconds, and re-poll with the **same** cursor (never advance on
      a failed call — the cursor is the watcher's only durable position).
- [ ] **WC-3 — cap-skip must NOT busy-spin `/wait`.** When a review is skipped (e.g. at a cap), the
      watcher **advances the cursor past it** and tracks the skipped review ids in an in-process
      **pending set**, draining them as concurrency slots free (re-attempt the claim on a bounded timer /
      when a child is reaped) — it must **not** rely on `/wait` to re-surface an already-emitted level
      (an un-advanced cursor would make the next `/wait` return the same edge instantly, re-running the
      server's O(all-reviews) scan each iteration). A bounded backoff sleep is the named fallback; the
      pending set is the default.
- [ ] **Step 3 — claim-before-spawn (single-flight), spawn ONLY on `200`.** For each returned
      agent-turn review: enforce caps FIRST (skip without claiming if capped — caps land in MR-057), then
      `POST /handoff {state:"working", owner:<watcher-id>}`; on `200` spawn the placeholder; on `409`
      **SKIP, do not spawn** (another owner holds it or it was reclaimed — normal, not an error); on any
      other 4xx/5xx log and skip. The claim must precede the spawn, never follow it.
- [ ] **Watcher-id derivation — stable per process, distinct across processes.** `owner = "watch-" +
      <stable id>`: `WATCH_OWNER` env if set, else a per-process value derived **once at startup**
      (`"watch-%s-%d" % (socket.gethostname(), os.getpid())` or a captured `uuid4` hex). Computed once,
      stored in a module/global, never re-derived per claim — so a watcher renewing/re-claiming hits the
      unset/equal-owner grant path against itself, not a foreign-owner `409`.
- [ ] **WC-5 — pid-derived owner changes on restart; a restarted watcher does NOT own its predecessor's
      leases.** Because the default id is pid-derived, a restart produces a *new* owner; a still-live
      child renewing under the **old** `MDREVIEW_OWNER` is now *foreign* to the new watcher, which will
      `409` and **skip** any review that child actively holds (correct — no double-spawn of a live
      in-flight child). The new watcher must not assume it owns predecessor leases; recovery rides the
      child's own `MDREVIEW_OWNER` renewal plus the **MR-055 stale-takeover** (it can reclaim only once
      that lease goes stale). State this in the ticket so the restart case is not a surprise — it is why
      pid-derived derivation is correct, not a bug. (A set `WATCH_OWNER` persists across restart and lets
      a new watcher renew its predecessor's leases — the operator's choice, not the default.)
- [ ] **Placeholder spawn only.** This ticket spawns a no-op/echo placeholder (or `WATCH_LAUNCH_CMD` to a
      trivial command) so the claim/skip/refuse logic is testable; the real generic launch template +
      child env contract + caps are MR-057.
- [ ] **Local validation passes:** `python3 -m py_compile watch.py`, plus the end-to-end against a
      **localhost throwaway** mdreview container on a scratch port (e.g. 8155 — never the live 8139,
      never `docker compose up`/8137) with a stub `WATCH_LAUNCH_CMD`:
  - [ ] **Fail-closed refusal EXITS (the trusted-base proof):** non-loopback base with no
        `WATCH_TRUSTED_BASE` ⇒ **non-zero exit**, stderr names the untrusted base; a set
        `WATCH_TRUSTED_BASE` that **mismatches** the base ⇒ **non-zero exit** (the typo case).
  - [ ] **Trusted start:** loopback default starts and idles on `/wait`.
  - [ ] **Single-flight / no-double-spawn:** create a review on the throwaway, flip the baton to agent,
        assert the watcher claims (the review's `agent_status.owner` begins `watch-`) and spawns exactly
        ONE stub, the stub hands back, and `turn` returns to `reviewer`; a SECOND tick / re-poll produces
        **no second spawn** for the same flip (the `409` skip path — the double-spawn-prevention proof).

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"C2 — Watcher core (full plan)", specifically
  Step 0 (fail-closed trusted-base, the security crux), Step 1 (cursor seed), Step 2 (long-poll + cursor
  advance, WC-3), Step 3 (claim-before-spawn, watcher-id, WC-5), the §"`watch.py` — file shape and
  conventions", and §"MR-056 validation (loop core + fail-closed)".
- C1 contract this consumes (pinned to shipped code): `GET /api/reviews/wait?turn=agent&since=<cursor>`
  (`_wait`, `app.py:419-458`; routed `app.py:515-516`) — hit ⇒ `200 {"reviews":[…]}`, timeout ⇒ `200
  {"reviews":[],"timeout":true}`, edge-triggered on `turn_updated > since`, `?timeout=` capped to
  `WAIT_TIMEOUT_S` (`app.py:439-440`); row fields `id`/`turn`/`turn_updated` from `summary()`
  (`app.py:147`, filter `app.py:501-509`); `GET /api/reviews/{id}/status` (`app.py:581-596`) for the seed;
  `POST /api/reviews/{id}/handoff {state:"working", owner}` (`app.py:635-662`) — `200` grant /
  `409 {"error":"lease held","owner":…}` on foreign-live or stale-but-reclaimed — the claim-before-spawn
  primitive.
- Sibling conventions from `mcp_server.py`: `MDREVIEW_BASE` read at `mcp_server.py:35`; HTTP helper shape
  at `mcp_server.py:376-389` (but this watcher must NOT raise-on-409 the way that helper does).
- `socket`/`uuid` are stdlib; no new dependency (footgun #1). Not containerized (Dockerfile untouched,
  epic non-goal).
- C3 relaxes the fail-closed refusal via operator arming; **C2 must ship the refusal, never the
  relaxation.** Crash-retry / per-review attempt cap are also C3.
- MR-057 (`depends_on: [MR-056]`) spawns the real launch command into this loop and adds the caps.

## Work log

- `2026-06-24` — Added `watch.py` at the repo root (the only file this ticket touches; `app.py`
  unchanged — C1 already shipped the server side). Stdlib only (`urllib`, `subprocess`, `socket`,
  `shlex`, `json`/`os`/`time`/`sys`), `MDREVIEW_BASE` read the same way as `mcp_server.py:35`. Not
  imported by `app.py`, not in the Dockerfile, not in compose.
  - **Step 0** `check_trusted_base` / `require_trusted_base_or_exit`: runs FIRST in `main()` before any
    network call. `host = urlparse(base).hostname`, loopback allowlist is **exact membership** in
    `("localhost","127.0.0.1","::1")` (not a substring test, so `localhost.evil.com` is refused);
    otherwise `WATCH_TRUSTED_BASE.rstrip("/") == base` exact match. On failure: stderr refusal naming
    BOTH bases (vouch shown as `(unset)` when empty) [WC-1] + `sys.exit(2)`. No bypass env.
  - **HTTP helper** `_http`: catches `urllib.error.HTTPError` and returns `(status, body)` (does NOT
    raise on 409); only a real `URLError` propagates, caught by the loop for backoff.
  - **Step 1** `seed_cursor`: default `time.time()`; `WATCH_SINCE=0` / `--backlog` opts into the
    existing backlog.
  - **Step 2** `run`: long-polls `/api/reviews/wait?turn=agent&since=<cursor>`; timeout/empty re-polls
    cursor unchanged; a hit advances cursor to `max(turn_updated)`; network error logs + bounded
    backoff + re-polls the SAME cursor.
  - **Step 3** `handle`: caps-check first (`_at_capacity()` stub returns False — real caps MR-057),
    then `POST /handoff {state:working, owner:OWNER}`; spawn ONLY on 200, skip on 409, log+skip on
    other. `OWNER = _watcher_id()` computed once at startup (`WATCH_OWNER` or
    `watch-<host>-<pid>`); WC-5 documented in the `_watcher_id` docstring.
  - **WC-3**: a capacity-skipped review still advances the cursor and is held in a `pending` set
    drained as slots free (`_drain_pending`) — not an un-advanced cursor that busy-spins `/wait`; a
    bounded `CAP_BACKOFF_S` is the named fallback.
  - **Placeholder spawn** `_spawn_placeholder`: `WATCH_LAUNCH_CMD` parsed as a JSON argv array (else
    `shlex.split`), spawned via `subprocess.Popen(argv, env=child_env)` — never `shell=True`; default
    is a no-op. Leaves a clean seam (`REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` in the child env) for
    MR-057's real launch template + child contract.

## Validation

- `2026-06-24` — `python3 -m py_compile watch.py` → **PYCOMPILE_OK**.
- **Fail-closed refusal EXITS** (against a fresh throwaway service on scratch port 8170,
  `MDREVIEW_DATA=/tmp/mr056svc-$$` — never 8139/8137):
  - `MDREVIEW_BASE=http://192.0.2.1:9999` (non-loopback, no vouch) → **EXIT=2**, stderr:
    `MDREVIEW_BASE=http://192.0.2.1:9999 does not match WATCH_TRUSTED_BASE=(unset)`.
  - `MDREVIEW_BASE=http://192.0.2.1:9999 WATCH_TRUSTED_BASE=http://192.0.2.1:8888` (typo mismatch) →
    **EXIT=2**, refusal names both bases.
  - `MDREVIEW_BASE=http://localhost.evil.com:9999` (substring trap) → **EXIT=2** (exact membership, not
    substring).
  - `MDREVIEW_BASE=http://192.0.2.1:9999 WATCH_TRUSTED_BASE=http://192.0.2.1:9999` (exact vouch) →
    **passed Step 0, kept running / long-polling** (killed after 2s).
  - `MDREVIEW_BASE=http://localhost:8170` (loopback default) → **passed Step 0, long-polling** (killed
    after 2s).
- **Single-flight / no-double-spawn:** created review `d2abf53a16` on the throwaway, started the
  watcher (`WATCH_OWNER=watch-mr056-test`, `WATCH_LAUNCH_CMD` = a stub that appends to a stamp file,
  seed=now), then `POST /handoff {to:agent}`:
  - Watcher returned from `/wait`, claimed the lease (`/status` → `agent_status.owner=watch-mr056-test`)
    and spawned the stub **exactly once** (`spawned placeholder for review d2abf53a16`; stamp file = 1
    line).
  - A second full `/wait` cycle (7s, client timeout 5s) produced **no second spawn** (stamp still 1
    line) — the edge-triggered cursor advanced past the flip, so `/wait` did not re-surface the
    still-`turn==agent` review.
  - **409 skip proof:** a foreign owner (`watch-OTHER-cold-start`) claiming the held lease → **HTTP
    409**, which `handle()` treats as skip (no spawn) — the single-flight gate.
- Throwaway service + scratch data dir torn down; no stray `app.py`/`watch.py` processes left.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
