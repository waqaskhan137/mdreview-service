---
review_of: sprints/sprint-17.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-17 close review (G7) — agent-watcher Chunk 1 (MR-054 + MR-055)

Independent G7 sprint-close review. The reviewer is not the implementer. Scope under review: the two
`svc` tickets that landed on `dev` for Chunk 1 of the `agent-watcher` epic — MR-054 (`?turn=agent`
filter + `summary()` turn-default + `/wait` long-poll) and MR-055 (stale-lease takeover on the
`/handoff {state:working}` arm). No product page render behavior changed (the only `viewer.html`
touch is a two-line code comment mirroring `STALE_S`), so this sprint owes the container/process
smoke plus a render no-regression check, not a new per-page DOM feature assertion.

**Verdict: PASS.** Every acceptance criterion on both tickets is met by the code that shipped on
`dev` (HEAD `5b3255b`), the decision table and lock discipline match the tickets exactly, the docs
were updated in-sprint, and an independent end-to-end exercise on fresh throwaway instances (ports
8164/8165/8166) reproduces every claimed behavior — including the two correctness properties the
brief flagged as the real risk: the edge-vs-level no-busy-loop guard and the rapid-double-flip edge
that the plan's discarded `_last_change` rid-carry would have dropped. No blockers.

I verified the load-bearing claims by running the code, not by trusting the smoke logs.

## Independent verification (re-run against fresh instances, not the implementer's logs)

- **Turn filter** (8164): `?turn=agent` empty before flip, count 1 after `{to:agent}`. PASS.
- **`/wait` edge/level** (8164): a review already at `turn==agent` polled with `since=<its
  turn_updated>` blocked the full `timeout=2` and returned `{reviews:[], timeout:true}` (~2.15s) — it
  does NOT busy-return on the steady-state level. `since=0` (backlog opt-in) returned the row in
  0.22s. This is the F1/F2 guard #3's happy path can't catch; it holds. PASS.
- **Lease decision table** (8164, `LEASE_TTL_S=2`): owner A claim 200; fresh foreign B → 409
  `{"error":"lease held","owner":"A"}`; after `sleep 2.5` (> TTL) B takeover → 200, owner now B;
  reclaim to reviewer then a stale foreign claim → 409 (turn != agent rejects the takeover). All four
  arms match the ticket. PASS.
- **Concurrent lock-release / no deadlock** (8165): parked a `/wait` (timeout 10) in a thread, fired
  a concurrent `PUT /source` against the same service — writer unblocked in **0.116s**, proving
  `Condition.wait()` releases `_lock` while parked. PASS.
- **Rapid double-flip edge** (8166): waiter parked for a match; a matching flip (ID2→agent)
  immediately followed by a non-matching write (ID→reviewer reclaim) back-to-back. The waiter
  returned exactly `[ID2]` in **0.41s**, not at the timeout — the exact race the rescan-on-wake fixes
  and the rid-carry would have failed. PASS.
- `python3 -m py_compile app.py` → clean.

## MR-054 — turn filter + `/wait` long-poll

- **`summary()` turn default** — `app.py:165` `m["turn"] = m.get("turn", "reviewer")` alongside the
  `revision` default. A legacy review reads `"reviewer"`, never `None`/absent. **Met.** (worth-considering)
- **`?turn=` filter** — `app.py:506-508`, parsed via `parse_qs(urlparse(...).query)`, filtered in
  Python after `list_reviews()`; empty/absent ⇒ no filter; any non-empty value is exact-match (so
  `?turn=bogus` ⇒ `[]`). The ticket's "unknown/empty ⇒ all" wording is internally contradictory with
  "`?turn=agent` with no match ⇒ empty list"; the implementer resolved it the only sound way (empty
  param ⇒ all; non-empty ⇒ exact match) and documented the reading. **Met.** (worth-considering)
- **`_lock` → `Condition`** — `app.py:52`, with the rationale comment at `:47-49`. Confirmed every
  existing `with _lock:` site (source PUT, handoff, comments, assets) is untouched and none calls
  `.acquire()` directly, so the swap is transparent. One Condition over the one lock. **Met.** (nit:
  none)
- **`/handoff` notify under the lock after the write** — `app.py:665-670`: `_write(p, ...)` then
  `_lock.notify_all()`, both inside the single `with _lock:` block, on any successful write. The
  write+wake are atomic; the predicate (not the arm) decides who returns. The `to:agent` flip bumps
  `turn_updated` only on an actual reviewer→agent transition (`:630`), so a re-POST of `{to:agent}`
  does not spuriously re-trigger a waiter. A `{state:working}` grant fires `notify_all` without
  bumping `turn_updated` — a spurious wake correctly filtered out by `turn_updated > since`. **Met.**
- **Route order** — `/api/reviews/wait` arm (`:515-516`) precedes the per-review RID arm (`:532`).
  Since `"wait"` matches `RID = [A-Za-z0-9]{4,40}`, a later placement would 404 it; placement is
  correct and I confirmed `GET /api/reviews/{id}` still returns 200 (not shadowed). **Met.**
- **Parked handler releases the lock** — `_wait()` `app.py:450-458`: baseline `changed_rows()` under
  the lock, then `while not rows: _lock.wait(remaining); rows = changed_rows()`. The baseline scan
  under the same lock that guards the `/handoff` write closes the lost-wakeup gap (a flip either
  committed-before-scan and is seen, or commits-after and `notify_all` wakes the parked waiter — no
  in-between). `wait()` releases the lock (independently verified, 0.116s). **Met.**
- **`?since=` required, EDGE not LEVEL** — predicate `turn_updated > since` (`:445`); `turn_updated`
  is monotonic (`time.time()` on every flip, never decremented), so an edge can't be skipped.
  Missing `since` ⇒ `time.time()` (`:438`), the block-for-next-flip degrade; `since=0` is the
  explicit backlog opt-in. Independently confirmed both. **Met.**
- **Bounded timeout** — `WAIT_TIMEOUT_S` (`:54`, env `MDREVIEW_WAIT_TIMEOUT_S`, default 25s); client
  `?timeout=` capped via `min(client_timeout, WAIT_TIMEOUT_S)` (`:440`); `200 {reviews:[],
  timeout:true}` on expiry (`:455`). **Met.**
- **Rescan-on-wake deviation from the planned rid-carry** — the implementer dropped the plan's pinned
  `_last_change` O(1) rid-carry for an unconditional `changed_rows()` rescan, citing a dropped edge
  under rapid flips (a matching flip A overwritten by a non-matching flip B before the woken waiter
  re-acquires the lock). The reasoning is sound and I reproduced the failure mode the rescan fixes
  (rapid-double-flip test → 0.41s return of the matching review, not a timeout). The rescan
  introduces no new correctness issue: it reads fresh full state each wake, the predicate is
  monotonic, and `_last_change` was fully removed (no dead state — grep confirms). The O(all-reviews)
  per-wake cost is trivial at this scale and the ticket states it. **Met; the deviation is an
  improvement.** (worth-considering)
- **Parked-thread cost / DoS** — stated and accepted in the ticket for the trusted single-operator
  case; `ThreadingHTTPServer` is thread-per-request so a parked `/wait` starves no pool. No new
  exposure class. Accepted. (worth-considering)
- **Back-compat** — legacy reviews read via `.get()` defaults and are simply absent from the
  `turn==agent` queue; unfiltered list/status/PUT/handoff unchanged for a review that never touches
  `/wait`. Confirmed by the empty-filter and per-review-GET checks. **Met.**

## MR-055 — stale-lease takeover

- **Decision table in code matches the ticket** — `app.py:648-662`: `cur_owner in (None,"",owner)` ⇒
  grant (normal claim/renew, regardless of turn); `elif stale and mt.get("turn")=="agent"` ⇒ grant
  (takeover); else 409. That is exactly: unset/equal → grant; foreign+fresh → 409; foreign+stale+
  turn==agent → grant; foreign+stale+turn!=agent → 409. The full table is restated in a code comment
  at `:637-647`. Independently reproduced all four arms. **Met.**
- **Turn re-check + agent_status write under the SAME lock** — both happen inside the existing single
  `with _lock:` block at `:613`. The reclaim arm (`:616-620`) forces `turn="reviewer"` under the same
  lock, so the stale-but-reclaimed case is rejected with no TOCTOU. **Met.**
- **Seconds unit, no `*1000`** — `LEASE_TTL_S = float(os.environ.get("MDREVIEW_LEASE_TTL_S", "180"))`
  (`:58`); `stale = (now - (cur.get("at") or 0)) > LEASE_TTL_S` with `now = time.time()` (`:651`);
  `at` is stamped `time.time()` at `:660`/`:626`. Same seconds unit throughout. **Met.**
- **TTL single source of truth + mirror comment** — `app.py:56-58` comment points at
  `viewer.html STALE_S`; `viewer.html:219-220` `STALE_S=180` comment points back at
  `app.py LEASE_TTL_S` ("MIRRORS … move together"). Both present. No `/config` endpoint added. **Met.**
- **Never preempts a live owner** — `at` is re-stamped on every `{state:working}` grant, and the
  documented `ping_working` pattern renews periodically; a lease only goes stale if the owner stops
  pinging for > TTL (crash/abandon). The `mcp_server.py:453-454` `ping_working` maps to
  `{state:working, owner}`, so a live agent keeps its lease fresh. The defensive `(cur.get("at") or
  0)` only bites a non-existent state, which routes through the unset-owner grant, not the stale
  branch. Safe. **Met.**
- **Overwrite-based, no new persisted key** — the arm does the full read-mutate-write of the whole
  meta dict (`:614`, `:666`); it changes only the grant *condition*. No new `meta.json` key. **Met.**
- **Env-overridable TTL** — `MDREVIEW_LEASE_TTL_S` default 180, used to drive the fast smokes. **Met.**
- **No render-observable change** — only the `viewer.html` comment; no Dockerfile COPY, no new served
  file. Render-smoke owed only as a no-regression check, which the evidence provides. **Met.**

## Docs (DoD)

- README `/api/reviews` row documents `?turn=agent`; a new `/api/reviews/wait` row documents the
  required `?since=` edge cursor, `?turn=`, `?timeout=`, the long-poll semantics, and the timeout
  payload (`README.md:46-47`). **Met.**
- README `/handoff` row documents the stale-takeover (`LEASE_TTL_S`/180, fresh 409, stale-but-
  reclaimed 409) (`README.md:54`). **Met.**
- CLAUDE.md "Claim the lease" now states a lease older than `LEASE_TTL_S` (180s) may be taken over,
  a 409 means the holder is alive, and a stale-but-reclaimed lease still 409s (`CLAUDE.md:115-117`).
  **Met.**
- No durable behavior shipped without its doc.

## Validation adequacy

The tickets' smokes + the container evidence (`reviews/sprint-17-render-evidence-2026-06-24/SMOKE.md`)
prove the ACs: real container rebuild on a scratch port 8162 (not 8139/8137), `/healthz`,
`/api/reviews`, the turn filter both directions, the `/wait` steady-state timeout, the fresh-foreign
409, and a headless-Chrome DOM render-smoke (5 anchors, exit 0) confirming no viewer regression. I
re-derived the deeper properties (edge/level, lock-release, rapid-double-flip, stale takeover) myself
above rather than trust the logs; all reproduce.

The one acknowledged gap — the **180s** stale-takeover was not waited out in-container; it was
unit-smoked with `MDREVIEW_LEASE_TTL_S=2`, and the in-container run confirms only the fresh-foreign
409 — is **acceptable**. The takeover branch is TTL-value-independent (a float compared against
`now - at`); `LEASE_TTL_S=2` exercises the identical code path, and the default-180 fact is directly
readable in source and confirmed by MR-055 validation item 4. Waiting 180s in-container would prove
nothing the short-TTL smoke doesn't. (worth-considering, not blocking)

## Scope discipline

Product changes are confined to `app.py`, `viewer.html` (comment-only), `README.md`, `CLAUDE.md`;
everything else is process docs (epic plan, requirements, plan-review, sprint doc, tickets, tracker).
No watcher (C2) code, no Dockerfile change, no new served file, no new `meta.json` key. No scope
creep, no missed AC. Clean.

## Findings

| # | Ticket | Finding | Tag |
|---|--------|---------|-----|
| 1 | MR-054 | `summary()` turn default lands; legacy reviews read `"reviewer"`. | worth-considering |
| 2 | MR-054 | `?turn=` filter: ticket wording ("unknown ⇒ all") is self-contradictory; resolved soundly as empty⇒all, non-empty⇒exact-match (`?turn=bogus`⇒`[]`). Note the reading; not a defect. | worth-considering |
| 3 | MR-054 | `_lock`→`Condition` swap transparent; all existing `with _lock:` sites intact. | nit |
| 4 | MR-054 | `/wait` baseline-scan-under-lock + `notify_all`-under-lock closes the lost-wakeup gap; edge/level guard independently confirmed (2.15s block, no busy-return). | nit |
| 5 | MR-054 | Rescan-on-wake deviation from the planned rid-carry is correct and an improvement; rapid-double-flip edge independently reproduced (0.41s). `_last_change` fully removed. | worth-considering |
| 6 | MR-054 | Parked-thread DoS stated + accepted for the single-operator trust boundary; optional in-flight-waiter `503` ceiling left unbuilt. | worth-considering |
| 7 | MR-055 | Decision table in code (`:648-662`) matches the ticket exactly; all four arms independently reproduced. | nit |
| 8 | MR-055 | Turn re-check + agent_status write under the same `_lock`; no TOCTOU vs reclaim. Stale takeover never preempts a live (pinging) owner. | nit |
| 9 | MR-055 | TTL mirror comments present at both sites; seconds unit, no `*1000`; no new persisted key. | nit |
| 10 | both | 180s default TTL not waited out in-container (short-TTL smoke covers the identical branch). Acceptable gap. | worth-considering |
| 11 | both | Docs (README rows + CLAUDE.md lease note) updated in-sprint. No undocumented durable behavior. | nit |

No blocking findings.

## Resolution log

- 2026-06-24 — Independent G7 review complete. Both MR-054 and MR-055 ACs verified against shipped
  code on `dev` HEAD `5b3255b` and re-exercised end-to-end on fresh throwaway instances. Verdict
  **PASS**; sprint-17 may close. No blockers; all findings are worth-considering or nits.
- 2026-06-24 — Verdict label confirmed `PASS` (not `PASS-WITH-NITS`): every AC is met and no finding
  requires an implementer change. Review `status: resolved`; sprint-17 closed at G7.
