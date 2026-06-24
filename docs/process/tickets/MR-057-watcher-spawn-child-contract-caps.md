---
id: MR-057
title: "`watch.py` spawn + child env contract + caps (generic launch template, default Claude) + trusted-base runbook stub"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-18
epic: agent-watcher
depends_on: [MR-056]
branch:                # MR-057-slug, once work starts
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

- [ ] **Generic `WATCH_LAUNCH_CMD` template, JSON-array preferred, string via `shlex.split`, NEVER
      `shell=True` (WC-2).** The watcher does **not** hard-code `claude -p`; it reads `WATCH_LAUNCH_CMD`.
      The **JSON-array form is preferred** (e.g. `'["claude","-p","..."]'`, parsed with `json.loads` into
      an argv list); a plain-string form is parsed with `shlex.split` into an argv list and spawned
      **without a shell**. The `shlex.split` result must reach the argv of a no-shell `subprocess` spawn,
      **never** a shell — do not add `shell=True` for string-form convenience. (A `{review_id}`-style
      placeholder may be a convenience gated to the server-generated id, but **env is the interface**, so
      the template needs no interpolation.)
- [ ] **Default launch command when `WATCH_LAUNCH_CMD` is unset.** A named constant (e.g.
      `DEFAULT_LAUNCH_CMD`) holding the Claude headless invocation; the watcher reads
      `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` from env. Nothing Claude-specific lives in the loop —
      the contract is "run this command with this env."
- [ ] **Step 4 — child env contract.** On a `200` grant, spawn with a copy of the watcher's `os.environ`
      plus: `REVIEW_ID = r["id"]` (which review to work), `MDREVIEW_BASE` = the watcher's base (same
      service), and `MDREVIEW_OWNER` = the watcher's `owner` that won the lease — **so the child renews
      the SAME lease** (its `ping_working(owner=…)` is a same-owner `200`, not a foreign-owner `409`
      against a fresh lease, `app.py:652`).
- [ ] **Spawn mechanics — non-blocking, tracked.** `subprocess.Popen(cmd, env=child_env)` (the watcher
      does **not** synchronously `wait()`, or one agent session would stall the poll loop); the `Popen`
      handle goes into the in-flight set for the concurrency cap + reaping. argv list, no `shell=True`,
      no interpolated id.
- [ ] **Lease lifecycle — child renews, watcher reaps+logs.** The **child** renews the lease
      (`ping_working(owner=MDREVIEW_OWNER)` per the MR-053 agent contract); the watcher's claim is the
      *initial* grab only. When a child exits, the watcher **reaps** it (removes it from the in-flight set,
      freeing a concurrency slot) and **logs** the exit code; it does **not** re-flip the baton or
      re-claim or relaunch in-tick (the baton returns to the human via the child's own `hand_back`).
- [ ] **Corrected crash model (B1) — a child exiting before `hand_back` STRANDS the baton; no
      auto-relaunch under the default seed.** `turn_updated` is bumped only on a real reviewer→agent flip
      (`app.py:629-634`); the `{state:working}` lease arm does **not** bump it (`app.py:635-636`). So a
      crashed/early-exiting child leaves the review at `turn==agent` with `turn_updated` **unchanged**;
      the watcher has already advanced its cursor past that flip, so the edge-triggered `/wait` never
      re-returns it — the failure mode is a **stranded baton (under-spawn)**, not a relaunch storm. What
      recovers it: the human (the 180s stale banner → reclaim/re-Send, a re-Send being a fresh flip) or an
      explicit `--backlog`/`since=0` re-seed / watcher restart. C2 has **no crash-retry** by design
      (non-goal). State this so C3 inherits the correct model.
- [ ] **Step 5 — concurrency cap.** `WATCH_MAX_CONCURRENT` (default `3`): max simultaneous live children,
      tracked via the in-flight `Popen` set; reaping frees slots. Enforced **before the claim** — at the
      cap, a returned agent-turn review is skipped this tick **without claiming** (do not claim-then-fail-
      to-spawn, which would strand the baton at a claimed-but-unspawned review), left claimable later via
      MR-056's pending-set retry-on-timer (WC-3), **not** by re-spinning `/wait` on an un-advanced cursor.
- [ ] **Step 5 — global launches/hour cap.** `WATCH_MAX_LAUNCHES_PER_HOUR` (default `30`): a rolling
      3600s window (a `collections.deque` of spawn timestamps, evicting entries older than the window). At
      the cap, **skip** (no claim/spawn) and log; the window drains over time. Both caps env-overridable.
- [ ] **Caps rationale stated correctly (B1) — they bound NORMAL-load spend, the crash case is fail-safe
      under-spawn.** The caps bound spend in the normal case (many *distinct* reviews flipped to agent).
      Do **not** claim "the global cap bounds a crash-loop" — under C2's edge-triggered design a crashed
      child strands rather than loops, so there is no relaunch storm to bound; the only repeated-relaunch
      path is a `--backlog`/restart re-seed loop, bounded by restart frequency. The per-review attempt
      cap / relaunch-convergence guard is **C3** (it guards a relaunch loop C2 deliberately does not
      create).
- [ ] **Trusted-base runbook stub (`docs`, in-same-change).** Enough README (near the existing "MCP
      server (optional)" section, `README:122`) + a short CLAUDE.md pointer for an operator to run
      `watch.py` in **trusted-base mode**: how to start it, the `MDREVIEW_BASE` / loopback default /
      `WATCH_TRUSTED_BASE` exact-match vouch / `WATCH_LAUNCH_CMD` (generic template, default Claude) /
      cap env vars, and the fail-closed exit behavior. The **full arming / untrusted-base runbook is
      explicitly C3**; C2 owes only the trusted-base runbook and says so.
- [ ] **Local validation passes:** `python3 -m py_compile watch.py`, plus the end-to-end against a
      **localhost throwaway** mdreview container on a scratch port (e.g. 8155 — never the live 8139, never
      `docker compose up`/8137):
  - [ ] **E — child contract:** the spawned stub renews the SAME lease (owner unchanged across the
        working ping — a same-owner `200`, not a foreign `409`) and hands back; assert `agent_status.owner`
        is the watcher's owner throughout and final `turn=="reviewer"`.
  - [ ] **F — concurrency cap:** `WATCH_MAX_CONCURRENT=1` + a slow stub (sleeps before `hand_back`); flip
        two reviews; assert never two concurrent children (the second runs only after the first exits, or
        is skipped-and-re-picked per the cap-skip rule).
  - [ ] **G — hourly cap:** `WATCH_MAX_LAUNCHES_PER_HOUR=2`, flip three reviews; assert exactly 2 spawns,
        the 3rd skipped (logged), no claim on the 3rd.
  - [ ] **H — crash stub (WC-4, the test that catches B1):** `WATCH_LAUNCH_CMD=<crash stub that renews
        the lease, writes a launch marker, then exits WITHOUT `hand_back`>`, default `now` seed; flip one
        review; assert the watcher claims + spawns ONE crash stub (one launch marker), the review STAYS at
        `turn=="agent"` with `turn_updated` UNCHANGED, and across the next several `/wait` cycles the
        watcher does **not** re-claim or re-spawn it (still ONE marker) — proving the stranded-baton
        reality under the default seed (NO auto-relaunch).
  - [ ] **H2 — crash stub, backlog re-surface:** restart the watcher with `--backlog`/`WATCH_SINCE=0`;
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

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
