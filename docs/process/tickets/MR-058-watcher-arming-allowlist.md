---
id: MR-058
title: "`watch.py` arming / allowlist — relax C2's fail-closed Step 0 (local `WATCH_ARMED_FILE`/`WATCH_ARMED`, run-but-gate, run()-side terminal skip)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-19
epic: agent-watcher
depends_on: []
branch: MR-058-watcher-arming-allowlist
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Let the watcher run against a **public / no-auth** instance, where provenance is not a trust boundary,
by **relaxing** C2's fail-closed refusal in one controlled way: an **operator-controlled local
allowlist** of review ids the watcher may auto-run. On an un-vouched non-loopback base with arming
configured, the watcher **runs but gates** — it auto-runs only **armed** reviews and **skips un-armed
ones without claiming their lease**, even at `turn==agent`. With **no** arming configured, C2's EXIT is
**byte-for-byte preserved**. The allowlist is **local operator config only** — there is no `app.py`
change and thus no HTTP route through which a review could arm itself, which is the whole point on a
no-auth service. No `app.py` change.

## Acceptance criteria

- [x] **Arming loader — `WATCH_ARMED_FILE` (primary) + `WATCH_ARMED` (env id-list), unioned, local-only.**
      A loader reads the allowlist from `WATCH_ARMED_FILE` (a local file path) and/or `WATCH_ARMED` (a
      comma/space-separated inline env id-list); if both are set, the two id sets are **unioned**. Both
      are **operator-local config**; **neither is settable via any HTTP endpoint** (there is no `app.py`
      change, so no route exists through which a review could add itself).
- [x] **File format (pinned).** One review id per line; blank lines and lines beginning `#` are ignored
      (comments); surrounding whitespace stripped. Each non-comment token must match the
      server-generated id shape `[A-Za-z0-9]{4,40}` (the same `RID` regex the router enforces); a token
      that does not match is **ignored with a logged warning** (fail-safe: a typo'd/garbage line never
      silently widens the allowlist and never crashes the watcher).
- [x] **No `*`/`ALL` wildcard "arm-everything" sentinel (N2).** A `*` (and `ALL`) token does **not** match
      the id shape, so it is dropped-and-logged like any other bad token, **never** treated as match-all.
      **The loader test asserts a `*` line is dropped-and-logged (not armed)** — the wildcard non-goal is
      a test, not just prose. An operator who genuinely wants "every review on a trusted remote" uses the
      C2 path (`WATCH_TRUSTED_BASE` vouch); arming is for the untrusted base where the operator names
      specific reviews.
- [x] **`_is_armed(review_id)` — default-safe hinge.** Returns True iff arming is **OFF** (neither
      `WATCH_ARMED_FILE` nor `WATCH_ARMED` configured) **OR** the id is in the allowlist. When arming is
      off, `_is_armed` is unconditionally True, the `run()` gate never rejects, and the loop is
      **byte-for-byte C2** (arming unconfigured ⇒ every review is "armed" ⇒ C2 preserved).
- [x] **Step-0 relaxation (decision table).** C3 does **not** change `check_trusted_base`
      (`watch.py:74-83`); it changes the **consequence** of an untrusted base when arming is configured.
      `require_trusted_base_or_exit` (`watch.py:86-102`) becomes conditional on arming:
  - [x] loopback (`localhost`/`127.0.0.1`/`::1`) ⇒ **run** (C2, unchanged);
  - [x] non-loopback **exact `WATCH_TRUSTED_BASE`** match ⇒ **run** (C2, unchanged);
  - [x] non-loopback, **no vouch**, **arming configured** ⇒ **run, do NOT exit** (the C3 relaxation —
        run-but-gate; the per-review arming check does the real gating);
  - [x] non-loopback, **no vouch**, **no arming** ⇒ **EXIT 2** (C2 behavior **preserved** when arming
        isn't configured).
- [x] **Refusal message stays self-explaining + gains an arming line (WC-1 forward).** The row-4 EXIT
      reuses the existing message (names **both** `MDREVIEW_BASE` and `WATCH_TRUSTED_BASE`) and **adds a
      third line** naming arming (`WATCH_ARMED_FILE`/`WATCH_ARMED`) as the way to run un-vouched. The
      refusal still fires (row 4) when arming is **not** configured; the new line documents the
      relaxation, it does not weaken row 4.
- [x] **Arming is a single, base-independent gate (C3-Q1).** If an allowlist is configured, it applies on
      **every** base (loopback and vouched included): `_is_armed` is consulted whenever arming is
      configured, regardless of base. The base check decides *run-vs-exit*; the arming check decides
      *which reviews*. (An operator wanting "all on loopback, only-armed on remote" runs two watcher
      processes.)
- [x] **Startup notice when arming is configured (W2).** After the Step-0 decision and before the loop,
      print a one-line notice whenever arming is configured, naming **how many ids are armed** and that
      the gate is base-independent — e.g. `arming active: N ids armed; un-armed reviews are skipped on ALL
      bases (loopback/vouched included)`. When `N == 0` on a **loopback/vouched** base, the notice must
      make the "spawns nothing until you arm a review" consequence explicit, so a silently-idle loopback
      watcher is never a surprise. (A `print`, not a behavior change.)
- [x] **Configured-but-empty ⇒ run-but-gate, spawn nothing (not "treat as unconfigured").** The
      run-vs-exit decision reads **only** `check_trusted_base` + "is arming configured"; it does **not**
      consult the allowlist contents. A **configured** but empty armed file (exists, zero valid ids) on an
      untrusted base ⇒ **run but spawn nothing** (every review un-armed ⇒ skipped). Do **not** collapse
      "configured-but-empty" into "unconfigured" (which would EXIT).
- [x] **Arming gate in `run()` BEFORE `handle()`, skip via `continue` (W1) — NOT a literal
      `handle()` early-return.** The per-review arming gate sits in `run()`'s per-row loop **before**
      `handle()` (and thus before `_at_capacity()` and the `/handoff` claim). An un-armed review is
      `continue`d — it never reaches `handle()`, the caps, the claim, OR the `pending` logic. This keeps
      the shipped `_at_capacity()`-keyed `pending.add` (`watch.py:302-304`) **unchanged**, so a terminal
      skip is structurally incapable of entering `pending`. Do **NOT** ship the literal
      `if not _is_armed(rid): return False` at the top of `handle()` — keyed on `_at_capacity()`, it would
      leak the un-armed review into `pending` whenever the watcher is at capacity and re-attempt it
      forever. (The tri-state `handle()` return — `SPAWNED`/`AT_CAPACITY`/`SKIPPED`, with `run()` adding to
      `pending` **only** on the `AT_CAPACITY` signal — is the **only** acceptable alternative.)
- [x] **Terminal skip advances the cursor and NEVER enters `pending`.** An un-armed skip advances the
      cursor exactly as today (computed over **all** returned rows before the per-row loop, so `/wait`
      never stalls — the WC-3 busy-spin footgun is avoided without touching `pending`) and is **not**
      added to `pending` (distinct from a capacity-defer, which *does* go to `pending`). It is "we will not
      run this until the operator arms it"; a later **re-Send** is a fresh `turn_updated` flip that `/wait`
      re-surfaces on its own.
- [x] **No lease side-effect on a skip.** Because the gate precedes the claim, an un-armed review's
      `agent_status` lease is **never** touched — the watcher leaves it exactly as the human left it
      (`turn==agent`, no agent lease).
- [x] **Allowlist freshness — default no cache, re-read per check.** The file is **re-read on each
      `_is_armed` check** (cheap; small file, single-threaded loop, no lock) so an operator can arm a
      review **while the watcher runs** by appending a line — no restart. **If (and only if)** an
      mtime-cache refinement is taken, key it on **`(mtime, size)`, not mtime alone (N1)** (1s mtime
      granularity can miss a same-second append; size catches it). Default: **no cache, re-read per
      check**. The env `WATCH_ARMED` list is fixed at process start; the file is the live-editable surface.
- [x] **Local validation passes:** `python3 -m py_compile watch.py`, plus the stub-launch end-to-end
      against a **localhost throwaway** mdreview container on a scratch port (e.g. 8155 — never the live
      8139, never `docker compose up`/8137):
  - [x] **A — C2 EXIT preserved:** untrusted base, NO arming ⇒ still **EXIT 2** (the relaxation must not
        weaken row 4); stderr names the untrusted base.
  - [x] **A2 — refusal names arming (WC-1 forward):** the row-4 refusal also names `WATCH_ARMED` as the
        escape hatch.
  - [x] **B — un-armed-skipped-without-claim (the central C3 property):** two reviews flipped to agent,
        only ONE armed; the **armed** review is claimed + runs the stub + hands back (turn→reviewer), the
        **un-armed** review is SKIPPED with **turn still `agent` and `agent_status` still null/untouched**
        (never claimed).
  - [x] **B2 — un-armed NOT retried into `pending` even at capacity (W1):** with `WATCH_MAX_CONCURRENT=0`
        (`_at_capacity()` true every tick — the case where the literal early-return bug would loop it
        forever), the un-armed review's skip is logged once per real edge (NOT growing each idle tick), it
        **never enters `pending`**, and it **never claims a lease**.
  - [x] **B3 — configured-but-empty ⇒ run-but-gate, spawn nothing + startup notice (W2/W3):** an empty
        armed file on an untrusted base ⇒ the watcher **RUNs** (does not EXIT — empty != unconfigured),
        the **startup notice** is shown (`arming active: 0 ids armed`), and it **spawns nothing** (lease
        stays null).
  - [x] **C — arming-not-HTTP-settable:** a probe `POST /api/reviews/<id>/arm` returns **404** (no such
        route) — arming is local-only, a review cannot arm itself.
  - [x] **F — `*` token dropped (N2):** an armed file with only `*` (+ a comment) ⇒ `*` is
        **dropped-and-logged**, arms **no** review (lease stays null).

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"C3 — Watcher safety + ops (full plan)",
  §"1. Arming / allowlist", the §"Where the arming check sits in the loop (W1)", the §"Step-0 relaxation
  decision table", the §"Allowlist freshness (N1)", the C3 Ticket-breakdown row for MR-058, and the
  §"MR-058 validation (arming / Step-0 relaxation)" (tests A/A2/B/B2/B3/C/F + the stub fixture).
- Shipped C2 `watch.py` line refs the change extends (read from the working tree, 329 lines):
  `check_trusted_base`/`require_trusted_base_or_exit` at `watch.py:74-102`; `handle()` claim-before-spawn
  at `watch.py:237-254`; `_at_capacity()` at `watch.py:177-192`; the pending-set + cursor loop in `run()`
  at `watch.py:266-306` (the `_at_capacity()`-keyed `pending.add` at `watch.py:302-304`, the cursor
  advance at `watch.py:299`); `seed_cursor`/`--backlog` at `watch.py:258-263`; the watcher-id at
  `watch.py:131-145`; `_reap()` crash model at `watch.py:156-174`; the single-thread invariant the
  freshness re-read relies on at `watch.py:148-153`.
- The `RID` regex `[A-Za-z0-9]{4,40}` is the router's constant in `app.py` — reuse its value for the
  id-shape validation.
- No `app.py` change (the C1 server contract is complete; flag a blocker if implementation reveals a
  genuinely missing primitive — an arming endpoint would re-create the self-arming hole). No Dockerfile
  change, no render-smoke (`watch.py` is not containerized, no product page touched — footgun #9 does not
  bite). `os`/`json`/`time`/`re`/`collections` are stdlib (footgun #1).

## Work log

- `2026-06-24` — Extended `watch.py` only (no `app.py`/`Dockerfile` change). Added the C3 arming
  section: `_RID_RE` (reusing app.py's `[A-Za-z0-9]{4,40}` value), module-level `WATCH_ARMED_FILE` /
  `WATCH_ARMED` config, `arming_configured()` (true iff either source is set, even when the resulting
  set is empty), `_valid_id()` (drops-and-logs any token failing the id shape — `*`/`ALL` included),
  `_env_armed_ids()` (comma/space-split, fixed at start), `_file_armed_ids()` (re-read per call, one
  id/line, `#` comments + blanks ignored, missing file = empty allowlist, never crash), `armed_ids()`
  (env ∪ file), and `_is_armed()` (true iff arming unconfigured OR id ∈ allowlist).
  Relaxed `require_trusted_base_or_exit`: after the existing `check_trusted_base` pass-through, a
  `return` when `arming_configured()` (the row-3 run-but-gate); the row-4 EXIT 2 is unchanged when
  arming is unconfigured, and its refusal message gained a third stderr line naming
  `WATCH_ARMED_FILE`/`WATCH_ARMED` as the un-vouched escape hatch.
  W1: in `run()`'s per-row loop, an un-armed `rid` is `continue`d BEFORE `handle()` — so it never
  reaches the caps, the `/handoff` claim, or the `_at_capacity()`-keyed `pending.add`. `handle()`,
  `_at_capacity()`, `_spawn()`, and the `pending.add` block are byte-for-byte C2 (see diff).
  W2: `_arming_startup_notice()` prints the armed-id count + base-independence after Step-0/before the
  loop when arming is configured, with the explicit "spawn NOTHING until you arm a review" tail at N==0.
  Also refreshed the module-docstring Config block (added the two env vars; dropped the stale "C3 adds
  the relaxation" note now that it is shipped).
  Files: `watch.py`. Commit `b2a5ded`.

## Validation

- `2026-06-24` — `python3 -m py_compile watch.py` → `PY_COMPILE_OK` (passes). End-to-end against a
  throwaway service on a SCRATCH port/data dir (`PORT=8180 MDREVIEW_DATA=/tmp/mr058svc-$$ python3
  app.py`; never 8139/8137, never `docker compose up`), driven with a stub `WATCH_LAUNCH_CMD` that
  records each spawn (`WATCH_LAUNCH_MARKER`, a TEST-FIXTURE env, not a `watch.py` config var) and hands
  back. The un-vouched non-loopback base was the service's own `0.0.0.0` bind reached via the LAN IP
  `http://100.65.0.151:8180` (urlparse sees it as non-loopback). Two reviews: X=`6f399adbfd` (armed),
  Y=`c649283038` (un-armed). Results:
  - **A — C2 EXIT preserved:** untrusted base, NO arming →
    `MDREVIEW_BASE=http://192.0.2.1:9999 python3 watch.py` → **exit code 2**; stderr names the base.
  - **A2 — refusal names arming:** stderr third/fourth lines:
    `To run on this base, either vouch for it with WATCH_TRUSTED_BASE, or configure arming
    (WATCH_ARMED_FILE/WATCH_ARMED) to run armed reviews only.`
  - **B — un-armed skipped without claim:** armed file lists X only; both flipped to `agent`. Spawn
    marker contained **only X**; X's `agent_status.owner == watch-rmw-<pid>` then handed back
    (`turn:reviewer`). **Y: `turn: agent`, `agent_status: null`** — never claimed, never spawned.
  - **B2 — un-armed NOT retried into pending even at capacity:** `WATCH_MAX_CONCURRENT=0` (always at
    capacity). Over ~10s of idle ticks, the log showed armed X = `at capacity, deferring review
    6f399adbfd (pending)` (a genuine capacity defer) while un-armed Y = `review c649283038 not armed —
    skip (no claim)` logged **exactly once** (`grep -c` = 1) and Y stayed `turn: agent`,
    `agent_status: None`. The literal early-return bug would have leaked Y into `pending` and re-logged
    it every drain tick — it did not.
  - **B3 — configured-but-empty ⇒ run-but-gate, spawn nothing + notice:** empty armed file on the
    untrusted base → watcher **did not exit** (still running after 6s), startup notice
    `arming active: 0 ids armed; … will spawn NOTHING until you arm a review`, both reviews skipped,
    spawn marker EMPTY, X lease stayed null.
  - **C — arming not HTTP-settable:** `GET`/`POST /api/reviews/<id>/arm` and `POST /api/arm` all → **404**;
    `grep -i arm app.py` finds only comment text (route-arm / lease internals), no arming endpoint.
  - **F — `*` token dropped (N2):** armed file with `*` and `ALL` → both
    `watch.py: ignoring invalid armed id '*'/'ALL' … (not [A-Za-z0-9]{4,40})`, notice `0 ids armed`,
    X (flipped to agent) skipped, spawn marker EMPTY — wildcard is never match-all.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
