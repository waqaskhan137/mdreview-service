---
id: MR-057
title: "`watch.py` spawn + child env contract + caps (generic launch template, default Claude) + trusted-base runbook stub"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-18
epic: agent-watcher
depends_on: [MR-056]
branch: MR-057-watcher-spawn-child-contract-caps
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Turn MR-056's claim loop into a real launcher: spawn the operator's configured agent command (default
Claude) on each won lease, hand the child the env it needs to renew the **same** lease and find its
review, and bound spend with two day-one caps. The launch mechanism is a **generic, operator-configured
command template** — the watcher only knows "run this command with this env" — which is exactly what lets
the tests use a stub instead of a real model. This ticket also pins the **corrected crash model** (a
child that exits before `hand_back` STRANDS its baton; the watcher does **not** auto-relaunch under the
default seed — B1) and ships the **trusted-base runbook stub** (`docs`, in-same-change). No `app.py`
change.

## Acceptance criteria

- [x] **Generic `WATCH_LAUNCH_CMD` template, JSON-array preferred, string via `shlex.split`, NEVER
      `shell=True` (WC-2).** The watcher does **not** hard-code `claude -p`; it reads `WATCH_LAUNCH_CMD`.
      The **JSON-array form is preferred** (e.g. `'["claude","-p","..."]'`, parsed with `json.loads` into
      an argv list); a plain-string form is parsed with `shlex.split` into an argv list and spawned
      **without a shell**. The `shlex.split` result must reach the argv of a no-shell `subprocess` spawn,
      **never** a shell — do not add `shell=True` for string-form convenience. (A `{review_id}`-style
      placeholder may be a convenience gated to the server-generated id, but **env is the interface**, so
      the template needs no interpolation.)
- [x] **Default launch command when `WATCH_LAUNCH_CMD` is unset.** A named constant (e.g.
      `DEFAULT_LAUNCH_CMD`) holding the Claude headless invocation; the watcher reads
      `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` from env. Nothing Claude-specific lives in the loop —
      the contract is "run this command with this env."
- [x] **Step 4 — child env contract.** On a `200` grant, spawn with a copy of the watcher's `os.environ`
      plus: `REVIEW_ID = r["id"]` (which review to work), `MDREVIEW_BASE` = the watcher's base (same
      service), and `MDREVIEW_OWNER` = the watcher's `owner` that won the lease — **so the child renews
      the SAME lease** (its `ping_working(owner=…)` is a same-owner `200`, not a foreign-owner `409`
      against a fresh lease, `app.py:652`).
- [x] **Spawn mechanics — non-blocking, tracked.** `subprocess.Popen(cmd, env=child_env)` (the watcher
      does **not** synchronously `wait()`, or one agent session would stall the poll loop); the `Popen`
      handle goes into the in-flight set for the concurrency cap + reaping. argv list, no `shell=True`,
      no interpolated id.
- [x] **Lease lifecycle — child renews, watcher reaps+logs.** The **child** renews the lease
      (`ping_working(owner=MDREVIEW_OWNER)` per the MR-053 agent contract); the watcher's claim is the
      *initial* grab only. When a child exits, the watcher **reaps** it (removes it from the in-flight set,
      freeing a concurrency slot) and **logs** the exit code; it does **not** re-flip the baton or
      re-claim or relaunch in-tick (the baton returns to the human via the child's own `hand_back`).
- [x] **Corrected crash model (B1) — a child exiting before `hand_back` STRANDS the baton; no
      auto-relaunch under the default seed.** `turn_updated` is bumped only on a real reviewer→agent flip
      (`app.py:629-634`); the `{state:working}` lease arm does **not** bump it (`app.py:635-636`). So a
      crashed/early-exiting child leaves the review at `turn==agent` with `turn_updated` **unchanged**;
      the watcher has already advanced its cursor past that flip, so the edge-triggered `/wait` never
      re-returns it — the failure mode is a **stranded baton (under-spawn)**, not a relaunch storm. What
      recovers it: the human (the 180s stale banner → reclaim/re-Send, a re-Send being a fresh flip) or an
      explicit `--backlog`/`since=0` re-seed / watcher restart. C2 has **no crash-retry** by design
      (non-goal). State this so C3 inherits the correct model.
- [x] **Step 5 — concurrency cap.** `WATCH_MAX_CONCURRENT` (default `3`): max simultaneous live children,
      tracked via the in-flight `Popen` set; reaping frees slots. Enforced **before the claim** — at the
      cap, a returned agent-turn review is skipped this tick **without claiming** (do not claim-then-fail-
      to-spawn, which would strand the baton at a claimed-but-unspawned review), left claimable later via
      MR-056's pending-set retry-on-timer (WC-3), **not** by re-spinning `/wait` on an un-advanced cursor.
- [x] **Step 5 — global launches/hour cap.** `WATCH_MAX_LAUNCHES_PER_HOUR` (default `30`): a rolling
      3600s window (a `collections.deque` of spawn timestamps, evicting entries older than the window). At
      the cap, **skip** (no claim/spawn) and log; the window drains over time. Both caps env-overridable.
- [x] **Caps rationale stated correctly (B1) — they bound NORMAL-load spend, the crash case is fail-safe
      under-spawn.** The caps bound spend in the normal case (many *distinct* reviews flipped to agent).
      Do **not** claim "the global cap bounds a crash-loop" — under C2's edge-triggered design a crashed
      child strands rather than loops, so there is no relaunch storm to bound; the only repeated-relaunch
      path is a `--backlog`/restart re-seed loop, bounded by restart frequency. The per-review attempt
      cap / relaunch-convergence guard is **C3** (it guards a relaunch loop C2 deliberately does not
      create).
- [x] **Trusted-base runbook stub (`docs`, in-same-change).** Enough README (near the existing "MCP
      server (optional)" section, `README:122`) + a short CLAUDE.md pointer for an operator to run
      `watch.py` in **trusted-base mode**: how to start it, the `MDREVIEW_BASE` / loopback default /
      `WATCH_TRUSTED_BASE` exact-match vouch / `WATCH_LAUNCH_CMD` (generic template, default Claude) /
      cap env vars, and the fail-closed exit behavior. The **full arming / untrusted-base runbook is
      explicitly C3**; C2 owes only the trusted-base runbook and says so.
- [x] **Local validation passes:** `python3 -m py_compile watch.py`, plus the end-to-end against a
      **localhost throwaway** mdreview container on a scratch port (e.g. 8155 — never the live 8139, never
      `docker compose up`/8137):
  - [x] **E — child contract:** the spawned stub renews the SAME lease (owner unchanged across the
        working ping — a same-owner `200`, not a foreign `409`) and hands back; assert `agent_status.owner`
        is the watcher's owner throughout and final `turn=="reviewer"`.
  - [x] **F — concurrency cap:** `WATCH_MAX_CONCURRENT=1` + a slow stub (sleeps before `hand_back`); flip
        two reviews; assert never two concurrent children (the second runs only after the first exits, or
        is skipped-and-re-picked per the cap-skip rule).
  - [x] **G — hourly cap:** `WATCH_MAX_LAUNCHES_PER_HOUR=2`, flip three reviews; assert exactly 2 spawns,
        the 3rd skipped (logged), no claim on the 3rd.
  - [x] **H — crash stub (WC-4, the test that catches B1):** `WATCH_LAUNCH_CMD=<crash stub that renews
        the lease, writes a launch marker, then exits WITHOUT `hand_back`>`, default `now` seed; flip one
        review; assert the watcher claims + spawns ONE crash stub (one launch marker), the review STAYS at
        `turn=="agent"` with `turn_updated` UNCHANGED, and across the next several `/wait` cycles the
        watcher does **not** re-claim or re-spawn it (still ONE marker) — proving the stranded-baton
        reality under the default seed (NO auto-relaunch).
  - [x] **H2 — crash stub, backlog re-surface:** restart the watcher with `--backlog`/`WATCH_SINCE=0`;
        assert the stranded `turn==agent` review IS re-claimed and the crash stub spawns again (a SECOND
        marker) — proving the only real relaunch path is the backlog/restart re-seed, not an in-run crash
        loop.

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"C2 — Watcher core (full plan)", Step 4 (spawn
  + child env contract, the generic launch template / WC-2), the §"Lease renewal / lifecycle" and crash
  model (B1), Step 5 (caps + corrected rationale), §"MR-057 validation (spawn + child contract + caps)"
  (tests E/F/G/H/H2 + the stub and crash-stub fixtures), and §"Docs the C2 chunk owes".
- C1 contract consumed: `POST /api/reviews/{id}/handoff {state:"working", owner}` (`app.py:635-662`) for
  the claim, `app.py:652` for the unset/equal/stale grant; `turn_updated` bumped only on a real flip
  (`app.py:629-634`), NOT on the `{state:working}` arm (`app.py:635-636`) — the fact the crash model
  rests on; `LEASE_TTL_S` 180s (MR-055) / viewer `STALE_S` is the stale-banner threshold the human
  recovery relies on.
- Test fixtures (author as part of the sprint, NOT shipped product — `~/scratch`/tmp scripts referenced by
  `WATCH_LAUNCH_CMD`): the **stub** (renews the same lease via `ping_working`, then `hand_back`s) and the
  **crash stub** (renews, writes a `$WATCH_LAUNCH_MARKER` line, then `exit 1` without `hand_back`) — both
  in the plan's §Validation (C2).
- `subprocess`/`collections`/`shlex`/`json` are stdlib (footgun #1). Not containerized; Dockerfile
  untouched; no served file (footgun #9 does not bite). No product page touched ⇒ no render-smoke owed.
- Runbook placement: README near `README:122` ("MCP server (optional)" — `watch.py` is the same class of
  optional sibling tool); CLAUDE.md a short "Running the watcher" pointer. Full arming/untrusted-base
  runbook + per-review attempt cap are C3.

## Work log

- `2026-06-24` — Extended `watch.py` (MR-056 loop core) into the real launcher:
  - **Generic launch template (WC-2):** new `_launch_argv()` reads `WATCH_LAUNCH_CMD` as a JSON array
    (preferred, `json.loads`) or a string via `shlex.split`, always reaching `subprocess.Popen(argv,
    env=…)` — never `shell=True`, never the id interpolated. New named `DEFAULT_LAUNCH_CMD` constant
    (Claude headless) used when unset; it is the only Claude-specific knowledge in the file and lives
    in a constant, not the loop. Env is the interface.
  - **Child env contract (Step 4):** `_spawn()` layers `REVIEW_ID` / `MDREVIEW_BASE` / `MDREVIEW_OWNER`
    (= the watcher's winning `OWNER`) onto a copy of `os.environ`, so the child renews the **same**
    lease (same-owner `200`, not a foreign `409`). Non-blocking `Popen`, tracked in `_inflight`.
  - **Lifecycle / crash model (B1):** new `_reap()` polls finished children, frees the concurrency
    slot, and **logs** the exit code; it never re-flips/re-claims/relaunches. A crash before
    `hand_back` strands the review at `turn==agent` (the server bumps `turn_updated` only on a real
    reviewer→agent flip, app.py:629-636), which the edge-triggered `/wait` never re-surfaces — the
    failure mode is fail-safe under-spawn, recovered by the human or a `--backlog`/restart re-seed.
  - **Caps (Step 5):** real `_at_capacity()` enforces `WATCH_MAX_CONCURRENT` (default 3, via the
    `_inflight` set) and `WATCH_MAX_LAUNCHES_PER_HOUR` (default 30, via a `collections.deque` rolling
    3600s window), **before** the claim; capacity-skipped reviews use MR-056's pending-set (drained on
    idle ticks + as slots free), not a `/wait` busy-spin. Caps rationale (bound normal-load spend, NOT
    a crash-loop) stated in the docstrings/comments; per-review attempt cap noted as C3.
  - Idle `/wait` timeout tick now also calls `_reap()` so finished/crashed children are collected
    promptly even with an empty pending set.
- `2026-06-24` — Docs (same change): README "Watcher (optional, trusted-base mode)" section (env vars,
  fail-closed trusted-base behavior, generic template, caps rationale, not-containerized, full
  arming/untrusted-base runbook explicitly deferred to C3); CLAUDE.md turn-baton pointer to it.
- Files touched: `watch.py`, `README.md`, `CLAUDE.md`, this ticket.

## Validation

- `2026-06-24` — `python3 -m py_compile watch.py` → **PASS** (clean, before and after).
- `2026-06-24` — End-to-end against a throwaway service (`PORT=8171 MDREVIEW_DATA=/tmp/mr057svc-$$
  python3 app.py`; **not** 8139/8137), with a `stub.sh` (renews same lease → sleeps → `hand_back`) and
  a `crash.sh` (renews → writes a launch marker → `exit 1`, no `hand_back`) as `WATCH_LAUNCH_CMD`.
  Watcher started **before** each flip so its `now` cursor precedes the reviewer→agent edge.
  - **E — child contract / same-owner.** Flipped a review to agent; watcher claimed (lease
    `owner=watch-E-owner`), spawned the stub; the stub's `ping_working` was a same-owner `200`
    (response showed `agent_status:{state:working, owner:watch-E-owner}`, not 409); `hand_back`
    returned `turn=reviewer`. The only lease owner ever seen was `watch-E-owner`. **PASS.**
  - **F — concurrency cap.** `WATCH_MAX_CONCURRENT=1`, slow stub (3s); flipped two. Sampling
    `pgrep stub.sh` over the run showed **max 1** concurrent child; the second was deferred to pending
    (`at capacity, deferring`), then drained after the first was reaped (markers 4s apart, serialized);
    both ended `turn=reviewer`. **PASS.**
  - **G — hourly cap.** `WATCH_MAX_LAUNCHES_PER_HOUR=1`, fast stub; flipped two. Exactly **1** spawn
    (one marker line); the second stayed `turn=agent` (deferred) across ~8s of idle ticks even after
    the first child was reaped and the concurrency slot freed — the hourly cap held. **PASS.**
  - **H — crash stub (B1 guard, WC-4).** Default `now` seed, crash stub; flipped one. Watcher claimed
    + spawned **one** crash stub (one marker), child `exited 1 (reaped; no relaunch — see crash model
    B1)`; the review **stayed at `turn==agent` with `turn_updated` UNCHANGED** (`1782262379.981189`
    before and after) across 8+s of `/wait` ticks; **still one marker** — no auto-relaunch. **PASS.**
  - **H2 — backlog re-surface.** Restarted the watcher with `--backlog` / `WATCH_SINCE=0` (cursor=0);
    the stranded `turn==agent` review from H **was re-claimed and the crash stub re-spawned** (a second
    marker line for the same id). It also re-surfaced the other stranded `turn==agent` reviews and hit
    the default concurrency cap (deferred one to pending) — confirming the only relaunch path is the
    backlog/restart re-seed, never an in-run crash loop. **PASS.**

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
