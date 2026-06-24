---
review_of: sprints/sprint-18.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-18 close review (G7, independent) — agent-watcher C2 (`watch.py`)

Independent G7 review of sprint-18 (epic `agent-watcher`, Chunk 2): MR-056 (fail-closed loop core)
and MR-057 (spawn + child contract + caps + runbook). I did not implement this. I read the shipped
`watch.py` in full, the C1 server contract it consumes (`app.py:419-458` `/wait`, `app.py:604-673`
`/handoff`), and the README/CLAUDE.md docs, then re-ran the load-bearing behaviors myself against a
**scratch-port** throwaway service (`PORT=8175 MDREVIEW_DATA=/tmp/...`; never 8139 live, never 8137
compose; torn down after, port confirmed clear).

**Verdict: PASS.** Both tickets meet their ACs in the shipped code. The security crux (fail-closed
trusted-base) and the load-bearing correctness claim (B1 stranded-baton, no auto-relaunch) both hold
when exercised, not just when asserted in the ticket. No blocking findings. Two nits and one
worth-considering, none of which gate the close.

## What I independently re-ran (with results)

| # | Behavior | Result |
|---|----------|--------|
| 1 | Fail-closed refusal exits non-zero, names both bases | **PASS** — non-loopback/no-vouch, `localhost.evil.com` substring trap, typo-mismatch vouch, and http-vs-https mismatch all `EXIT=2` with both bases in the stderr message |
| 1b | `check_trusted_base` logic (incl. `::1`, scheme/port mismatch, trailing-slash) | **PASS** — 9/9 cases correct (exact membership for loopback, exact string match for vouch) |
| 2 | No command injection | **PASS** (static) — spawn is `subprocess.Popen(_launch_argv(), env=child_env)`, argv list, no `shell=True`, no `os.system/os.popen`, review id flows only via `REVIEW_ID` env, never into argv |
| 3 | Claim-before-spawn single-flight | **PASS** — one flip → exactly one spawn; a second `/wait` cycle produced no second spawn; child renew was a same-owner `200`; final `turn=reviewer` |
| 3b | Foreign-owner 409 skip | **PASS** — pre-claimed by `watch-FOREIGN-live`, watcher logged `lease held … — skip`, no spawn (marker file never created), lease unchanged |
| 4 | B1 crash model — strand, no auto-relaunch | **PASS** — crash stub spawned once, reaped `exited 1 (… no relaunch — see crash model B1)`; review stayed `turn=agent` with `turn_updated` byte-identical (`1782262779.896068`) before/after ~14s of `/wait` ticks |
| 4b | `--backlog`/`WATCH_SINCE=0` re-surfaces the stranded review | **PASS** — same review re-claimed and re-spawned (marker 1→2 lines); the only relaunch path |
| 5 | Concurrency cap (`WATCH_MAX_CONCURRENT=1`) | **PASS** — two simultaneous flips, max 1 concurrent child sampled via `pgrep`; second deferred to pending and drained only after the first reaped; both ended `turn=reviewer` |
| 5b | Hourly cap (`WATCH_MAX_LAUNCHES_PER_HOUR=1`) | **PASS** — two flips, exactly 1 spawn; second stayed `turn=agent` (never claimed — deferral is before the claim, so no claimed-but-unspawned strand) |
| 6 | Child contract / same-owner renewal | **PASS** — child gets `MDREVIEW_OWNER`=winning owner; its `ping_working` was a same-owner `200`; watcher runs no redundant per-child renewal (only `_reap()` tracks the Popen) |
| 7 | Docs (DoD) | **PASS** — README "Watcher (optional, trusted-base mode)" + CLAUDE.md pointer shipped in the MR-057 commit |
| 8 | Scope | **PASS** — MR-056 commit = `watch.py` only; MR-057 = `watch.py`+`README.md`+`CLAUDE.md`; no `app.py`/Dockerfile/compose change; no C3 (arming, per-review attempt cap) leaked in |

## MR-056 — fail-closed loop core

- **AC: new `watch.py`, stdlib only, off by default** — met. Imports are stdlib (`urllib`,
  `subprocess`, `socket`, `shlex`, `collections`, `json`/`os`/`time`/`sys`). `MDREVIEW_BASE` read
  exactly as `mcp_server.py` (`.rstrip("/")`). Not imported by `app.py`, absent from Dockerfile/compose.
  (worth-considering, not blocking) The AC text lists `threading` among the expected imports;
  `watch.py` is correctly single-threaded (the poll loop owns all state, as its comments note) and
  uses none. The import list in the AC is aspirational, not a contract; the shipped no-threading
  design is the better one. Flagging only so the AC/impl mismatch is on record.
- **AC: Step 0 fail-closed runs FIRST, exits non-zero** — met and re-verified. `main()` calls
  `require_trusted_base_or_exit(BASE)` before `run()`, i.e. before any network call. All refusal
  cases `sys.exit(2)`. (blocking-severity area, verified clean.)
- **AC: exact comparison, no substring trap** — met. `urlparse(base).hostname` + exact membership in
  `("localhost","127.0.0.1","::1")`; `http://localhost.evil.com:9999` is **refused** (re-run, EXIT=2).
  Vouch path is exact string match `trust.rstrip("/") == base`. No wildcard/prefix/host-only match.
- **AC: refusal names both bases (WC-1)** — met; vouch shown as `(unset)` when empty. Re-confirmed in
  every refusal run.
- **AC: `::1` in loopback allowlist** — met (unit-checked, `http://[::1]:8137` → allowed).
- **AC: `_http` branches on status, no raise-on-409** — met. Catches `HTTPError`, returns
  `(e.code, body)`; only `URLError` propagates to the loop's backoff. The 409 claim path depends on
  this and works (re-verified in 3b).
- **AC: cursor seed = now, `--backlog`/`WATCH_SINCE=0` opt-in** — met (`seed_cursor`). Re-exercised:
  default seed strands the crash review (4), `--backlog` re-surfaces it (4b).
- **AC: long-poll + cursor advance, network-error backoff re-polls same cursor** — met. `run()`
  advances to `max(turn_updated)` only on a hit; timeout re-polls unchanged; `URLError` logs +
  `NET_BACKOFF_S` + same cursor.
- **AC: WC-3 cap-skip does not busy-spin `/wait`** — met. Capacity-skipped reviews advance the cursor
  and land in `pending`, drained by `_drain_pending` on idle ticks / as slots free. Re-observed in the
  cap tests: the deferred review was held in pending and picked up after a reap, with no un-advanced-cursor
  re-spin.
- **AC: claim-before-spawn, spawn only on 200; 409 skip; watcher-id once at startup; WC-5** — met.
  `handle()` caps-check → claim → spawn-on-200 / skip-on-409 / log-on-other. `OWNER` computed once at
  module load. Single-flight (3) and 409 skip (3b) both re-verified.
  - Note on WC-5: my 4b backlog re-spawn reused the **same** `WATCH_OWNER`, which is the same-owner
    renew-grant path (correct, since the crashed child is dead). WC-5's distinct claim — a *restarted
    pid-derived* watcher 409s on a still-**live** foreign child — is sound by inspection of
    `app.py:652` (fresh foreign lease → 409) but I did not stage a live-child-survives-restart race;
    it is a server-contract property already covered by C1/MR-055, not new code in this sprint.

## MR-057 — spawn + child contract + caps + runbook

- **AC: generic `WATCH_LAUNCH_CMD`, JSON-array preferred, string via `shlex.split`, never
  `shell=True` (WC-2)** — met. `_launch_argv()` does `json.loads` (must be a list) else `shlex.split`;
  result reaches `Popen(argv, env=…)` with no shell. (blocking-severity injection area, verified clean.)
- **AC: `DEFAULT_LAUNCH_CMD` constant, Claude headless, env is the interface** — met. The only
  Claude-specific knowledge is the constant; the loop never references it by name. Child reads
  `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` from env, not argv.
- **AC: Step 4 child env contract, same-owner renewal** — met and re-verified (6): `MDREVIEW_OWNER`
  = winning owner → child `ping_working` is a same-owner `200`.
- **AC: spawn non-blocking, tracked** — met. `Popen` (no synchronous `wait()`); handle in `_inflight`
  for cap + reaping.
- **AC: lease lifecycle — child renews, watcher reaps+logs, no relaunch** — met. `_reap()` frees the
  slot and logs the exit code; no re-flip/re-claim/relaunch. Watcher runs **no** redundant per-child
  renewal timer (confirmed: the only lease write the watcher makes is the initial claim in `handle()`).
- **AC: corrected crash model B1 — strand, no auto-relaunch under default seed** — **met, and this is
  the load-bearing claim I most wanted to break.** Re-exercised (4): `turn_updated` is byte-identical
  before and after the crash, the edge-triggered `/wait` never re-surfaces the stranded review, and
  no relaunch occurs across many ticks. The rationale in the code matches the server reality
  (`app.py:629-634` bumps `turn_updated` only on a real flip; `app.py:635-662` `{state:working}` does
  not). Recovery is the human or `--backlog`/restart (4b). Solid.
- **AC: concurrency cap, enforced before the claim** — met and re-verified (5): cap-skip defers
  without claiming, so no claimed-but-unspawned strand.
- **AC: launches/hour rolling-window cap** — met and re-verified (5b): `collections.deque` evicts
  entries older than 3600s; at the cap the review is skipped without a claim.
- **AC: caps rationale stated correctly (bound normal-load spend, not a crash-loop)** — met. The
  docstrings and README say exactly this and tie it to B1 (a crash strands, it does not loop, so there
  is no storm to bound; the per-review attempt cap is C3). The rationale is correct given the verified
  B1 behavior.
- **AC: trusted-base runbook stub (docs, in-same-change)** — met. README §"Watcher (optional,
  trusted-base mode)" covers start commands, the loopback default, the `WATCH_TRUSTED_BASE` exact
  vouch, the generic template / no-shell-injection, the child contract, the caps rationale, the
  not-containerized note, and explicitly defers the untrusted-base/arming runbook to C3. CLAUDE.md has
  the pointer. Shipped in the MR-057 feat commit (not a follow-up).

## Worth considering

- **`json.loads` of a non-list `WATCH_LAUNCH_CMD` silently falls through to `shlex.split`.** If an
  operator sets `WATCH_LAUNCH_CMD='"claude -p foo"'` (a JSON *string*, not array) or `'42'`,
  `_launch_argv()` raises `ValueError` internally and re-parses the raw text with `shlex.split` —
  for the JSON-string case that splits `"claude -p foo"` (quotes included) into surprising argv.
  Not a safety issue (still no shell, still an argv list) and not an AC violation (string-form via
  `shlex` is explicitly supported), but a malformed JSON array degrades quietly rather than erroring.
  A one-line "couldn't parse as JSON array, treating as a shell-words string" log on the fallback
  would save an operator a confusing debug session. Non-blocking.

## Nits

- AC-vs-impl: MR-056's AC enumerates `threading` as an expected import; the shipped (better)
  single-threaded design uses none. Cosmetic AC drift, already noted above.
- `_drain_pending`'s docstring still says "With the MR-056 stub `_at_capacity()` this is a no-op" —
  stale now that MR-057 shipped the real caps. Harmless, but the comment describes a prior state.

## Resolution log

- 2026-06-24 — Independent G7 review authored. Re-ran, against a scratch-port (8175) throwaway
  service: fail-closed refusal exits (4 cases) + `check_trusted_base` unit matrix (9 cases),
  injection static-audit, single-flight no-double-spawn, foreign-owner 409 skip, B1 crash strand +
  no-relaunch + `turn_updated` invariance, `--backlog` re-surface, concurrency cap, hourly cap, child
  same-owner renewal. All PASS. Scope/docs confirmed from the per-commit diff. Scratch service and
  temp files torn down; port 8175 confirmed clear. **Verdict: PASS** — no blocking findings; one
  worth-considering (quiet JSON-array parse fallback) + two cosmetic nits, none gating the close.

- 2026-06-24 — Verdict PASS confirmed; review `status: resolved`. The two trivial code-doc nits
  (non-list-JSON `WATCH_LAUNCH_CMD` fallback log; stale `_drain_pending` docstring) were applied
  post-review in a small refactor commit; the WC-5 live-child-survives-restart property is a
  C1/MR-055 server contract (not new code this sprint) and was confirmed by inspection. sprint-18
  closed at G7.
