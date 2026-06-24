---
id: MR-055
title: Stale-lease takeover on `/handoff {state:working}` (TTL single-source + reclaim-vs-takeover re-check)
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-17
epic: agent-watcher
depends_on: [MR-054]
branch: MR-055-stale-lease-takeover-handoff-working
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Let a watcher reclaim a lease abandoned by a crashed session. Today the `{state:working}` lease arm
(`app.py:557-566`) grants the lease only if the current owner is unset, empty, or equal to the
caller — a foreign owner always `409`s, **even if the holder is dead**. C1 relaxes this: grant the
lease if the current owner is unset, equal, **or stale** (`now − agent_status.at > TTL`). This is
recovery, not preemption — it never evicts a *live* owner. It is its own ticket because it changes
what existing `ping_working` callers observe (a foreign owner can now take a *stale* lease) a full
cycle before any watcher exists, so the G1/G4 review scrutinizes it on its own merits. The change is a
strict superset of today's grant set; a *fresh* foreign lease still `409`s.

## Acceptance criteria

- [ ] **Stale takeover granted.** In the `{state:working}` arm (`app.py:557-566`), under the existing
      `with _lock:` block (`app.py:535`), grant the lease when the current owner is unset (`None`/`""`),
      equal to the body owner, **or stale** (`now − agent_status.at > LEASE_TTL_S`). A stale foreign
      lease is taken over (200, owner reassigned); a **fresh** foreign lease still `409`s (unchanged —
      no regression for live owners).
- [ ] **(a) TTL single source of truth.** Define one server-side constant **`LEASE_TTL_S = 180`** near
      the config block (`app.py:40-47`), used by the takeover arm — matching the viewer's `STALE_S =
      180` (`viewer.html:219`). Add a cross-referencing code comment at **both** sites
      (`app.py LEASE_TTL_S` ↔ `viewer.html STALE_S`) stating they are a documented mirror that must
      move together. No new `/config` endpoint (footgun #1 / baton epic's "staleness is
      viewer-computed" decision; Q3 — server-authoritative staleness is a possible small follow-up, not
      a C1 blocker).
- [ ] **Seconds unit, no `*1000`.** `agent_status.at` is epoch **seconds** (float — stamped
      `time.time()` at `app.py:548, 564`; viewer reads `Date.now()/1000 - at` at `viewer.html:233`).
      The takeover computes `now − at` with `now = time.time()`, in the **same seconds unit** — never
      milliseconds.
- [ ] **(b) Reclaim-vs-takeover re-check under the same lock.** When the grant reason is **staleness**
      (not unset/equal owner), require `mt.get("turn") == "agent"` inside the **same `with _lock:`
      block** that decides the grant. The reclaim arm `{to:reviewer, by:reviewer}` (`app.py:538-542`)
      forces `turn = "reviewer"` unconditionally and leaves `agent_status` intact, so a lease can be
      simultaneously *stale* **and** *already reclaimed by the human*. If `turn != "agent"`, **reject
      the stale takeover** → `409 {"error":"lease held","owner":...}` (same back-off shape; the caller
      skips it). Because the read of `turn` and the write of `agent_status` are atomic under the single
      `_lock`, there is no TOCTOU vs a concurrent reclaim.
- [ ] **Normal-claim path unaffected by the turn re-check.** An unset/equal-owner claim is the normal
      claim/renew (not a takeover) and is granted regardless of `turn`; the `turn == "agent"` re-check
      gates only the staleness grant. (Decision table: unset → grant; equal → grant; foreign+fresh →
      409; foreign+stale+`turn==agent` → grant; foreign+stale+`turn!=agent` → 409.)
- [ ] **Overwrite-based, no new key.** The takeover does the full read-mutate-write-whole-dict the
      existing arm does (`app.py:536, 570`); it never partial-merges `meta.json` and adds **no**
      persisted key — it only changes the *grant condition* (footgun #2).
- [ ] **Env-overridable TTL for fast smokes.** `LEASE_TTL_S` is env-overridable (e.g.
      `MDREVIEW_LEASE_TTL_S=2`, default **180**), stdlib-idiomatic (matches `MDREVIEW_DATA`/`PORT` at
      `app.py:41-42`), so the curl smoke does not wait 180s (Q2).
- [ ] **No new exposure / no UI behavior change.** The only `viewer.html` touch is the one-line
      `STALE_S` mirror comment — not render-observable (footgun #6 does not apply), no new served file
      (no Dockerfile COPY, footgun #9 does not apply), so no render-smoke is owed. Stated so a reviewer
      does not expect a render-smoke for a comment-only viewer touch.
- [ ] **Local validation passes:** `python3 -m py_compile app.py`, plus the curl smokes (with a short
      test TTL via `MDREVIEW_LEASE_TTL_S=2`): (1) a fresh foreign owner `409`s; (2) after the TTL a
      stale lease is taken over (200, owner reassigned); (3) a stale-**but-reclaimed** lease
      (`turn==reviewer`) still `409`s — the reclaim-race re-check holds. Confirm `LEASE_TTL_S` defaults
      to 180 (matching `viewer.html STALE_S`) and the mirror comments are present at both sites. All
      smokes run against a **throwaway container on a scratch port** (e.g. 8155), never the live 8139
      instance and never `docker compose up` (8137).

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"Service (`app.py`) — C1" item 3
  (stale-lease takeover), the `{state:working}` decision table, §Key constraints (TTL single source of
  truth), §UI (the comment-only `viewer.html` touch), §Verification → MR-055, and the risks rows
  (stale-takeover races a human reclaim; TTL divergence; behavior-change-leaks-to-existing-callers).
- `app.py` anchors: lease arm `:557-566`; `with _lock:` block `:535`; reclaim arm `{to:reviewer}`
  `:538-542`; `at = time.time()` stamps `:548, 564`; read-mutate-write `:536, 570`; config block
  `:40-47`; env reads `:41-42`.
- `viewer.html` anchors: `STALE_S = 180` `:219`; `Date.now()/1000 - at` staleness read `:233`.
- Depends on MR-054: both touch the `/handoff` handler under the same `_lock` (now a `Condition`);
  sequencing MR-054 first avoids a merge conflict on that block and lets this smoke use `/wait` to
  observe the takeover's effect. The takeover logic is independent of `/wait`'s correctness; the
  ordering is for clean integration, not a hard data dependency.
- This is the only **shipped-behavior change** in C1 (additive otherwise). No `meta.json` key added or
  removed; the baton contract (`turn`/`/handoff`/`agent_status` shapes) is unchanged.

## Work log

- `2026-06-24` — Implemented the stale-lease takeover.
  - `app.py`: added `LEASE_TTL_S = float(os.environ.get("MDREVIEW_LEASE_TTL_S", "180"))` by
    `WAIT_TIMEOUT_S` (seconds; env-overridable for fast smokes), with a mirror comment pointing at
    `viewer.html STALE_S`. Relaxed the `{state:working}` arm: grant when `cur_owner in (None,"",owner)`
    (normal claim/renew, regardless of `turn`) **or** when the lease is stale
    (`now - (agent_status.at or 0) > LEASE_TTL_S`) **and** `mt.get("turn") == "agent"`. A fresh foreign
    lease, or a stale-but-already-reclaimed lease (`turn != "agent"`), still returns
    `409 {"error":"lease held","owner":...}`. Read of `turn` + write of `agent_status` happen inside the
    existing single `with _lock:` block (no TOCTOU vs the reclaim arm). Full read-mutate-write of the
    whole meta dict; **no** new persisted key. Restated the full decision table in a comment.
  - `viewer.html`: extended the `STALE_S = 180` comment to note it mirrors `app.py LEASE_TTL_S` (single
    source of truth, both seconds). Comment-only — no viewer behavior change, no render-smoke owed.
  - Docs: `README.md` `/handoff` row and `CLAUDE.md` "turn baton / Claim the lease" updated to note a
    stale foreign lease is taken over (fresh still 409s; stale-but-reclaimed still 409s). `AGENTS.md`
    only lists the tool (no grant-condition prose) — left untouched.

## Validation

- `2026-06-24` — `python3 -m py_compile app.py` → pass (`PY_COMPILE_OK`).
- Curl smokes against a throwaway `PORT=8158 MDREVIEW_DATA=/tmp/mr055-$$ MDREVIEW_LEASE_TTL_S=2`
  instance (never 8139/8137):
  1. **Fresh foreign lease 409s** — flip `{to:agent}`, owner A `{state:working,owner:A}` → 200;
     owner B immediately → **409** `{"error":"lease held","owner":"A"}`.
  2. **Stale lease taken over** — after `sleep 2.5` (> TTL=2s), owner B `{state:working,owner:B}` →
     **200**, lease owner now `B` (confirmed via `/status` `agent_status.owner`).
  3. **Stale-but-reclaimed still 409s** — A claims, lease goes stale, reclaim
     `{to:reviewer,by:reviewer}` (turn → reviewer, `agent_status` left stale, lease_owner still A);
     owner B's stale claim → **409** `{"error":"lease held","owner":"A"}` (turn != agent → takeover
     refused).
  4. `LEASE_TTL_S` defaults to `180.0` with the env var unset; mirror comments present at both sites
     (`app.py:58` `LEASE_TTL_S`, `viewer.html:219-220` `STALE_S` ↔ `LEASE_TTL_S`).

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
