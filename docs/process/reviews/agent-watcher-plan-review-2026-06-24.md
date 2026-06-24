---
review_of: epics/agent-watcher-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 Plan-Gate Review — agent-watcher (C1)

Independent review of `epics/agent-watcher-plan.md`. I gate the PLAN (decomposition, sequencing,
the C1 wiring, the validation recipe, footguns), not the already-gated design RFC (`22c9555b3e`) or
the chunking brief (`requirements/agent-watcher.md`, two critic rounds, GO). Only C1 (MR-054,
MR-055) is ticketed now; C2/C3 are chunk summaries and I judge them only for scope-placement.

Every load-bearing code claim below was read against the working tree (`app.py`, `viewer.html`).

## Verdict

**PASS-WITH-NITS.** G1 passes; tickets may be spawned. No finding makes C1 ship broken or unsafe.
The mechanical wiring claims are accurate, the lock design is correct, MR-055's stale-takeover and
its reclaim-race guard are sound. The one sharp finding (the `/wait` level-vs-edge cursor) is a
SHOULD the planner must fold into MR-054 at G2 so the long-poll actually long-polls; I am passing it
as PASS-WITH-NITS rather than BLOCKED because it does not make C1 *unsafe* — it makes `/wait`
*ineffective* in steady state, and the fix is small and additive within MR-054. Resolve it in the
ticket, no second G1 round needed.

## What I verified (claims that hold)

The implementer can trust these — I confirmed each against the code:

- **`_lock` swap is transparent.** Every `_lock` use is a `with _lock:` block (app.py:475, 535, 627,
  646, 663, 685); none calls `.acquire()`/`.release()` directly. None nests another `with _lock:`,
  so the default `Condition()` (RLock-backed) is a strict superset — the swap changes no existing
  semantics. Claim holds.
- **`/handoff` notify placement is sound.** The whole read-decide-write is inside one `with _lock:`
  (535) with `_write(p, json.dumps(mt))` at 570 under the lock. A single `_lock.notify_all()` after
  the `if err is None: _write(...)` block (still under the lock) is correct, and since the only
  writer that ever changes `turn` to/from `agent` is this handler, notifying here is *sufficient*
  for a `turn==agent` predicate. `PUT /source` (475) does not touch `turn`, correctly needs no
  notify.
- **`Condition.wait()` releases the lock — the deadlock crux holds.** Confirmed the design parks on
  `_lock.wait(timeout)` (releases the underlying lock while blocked), so a parked `/wait` does not
  block `PUT /source` / `/handoff` / comment writers. This is the real failure mode and the design
  avoids it.
- **Route placement is correct and non-shadowing.** `route()` (app.py:416) is one ordered `if`-chain
  over `re.fullmatch`. Collection arm at 437-438, per-review `RID` arm at 454. `wait` matches
  `RID = [A-Za-z0-9]{4,40}` (line 47), so the new `/api/reviews/wait` arm MUST go before 454 — the
  plan places it there. Holds.
- **`ThreadingHTTPServer`, thread-per-request.** Confirmed bare `ThreadingHTTPServer` at app.py:727,
  no fixed pool — a 25s held `/wait` occupies one thread and starves no pool. Holds (but see WC-1).
- **MR-055 reclaim arm leaves `agent_status` intact.** The `{to:reviewer,by:reviewer}` reclaim
  (app.py:538-542) sets `mt["turn"]="reviewer"` + `turn_updated` and does NOT clear `agent_status`.
  So a lease can genuinely be *stale AND already reclaimed* — the race the plan calls out is real,
  and the `mt.get("turn")=="agent"` re-check inside the same `with _lock:` (535) is both correct and
  sufficient (the read of `turn` and the write of `agent_status` are atomic vs a concurrent reclaim,
  no TOCTOU). Holds.
- **MR-055 current lease arm.** `{state:working}` (app.py:557-566) grants iff
  `cur_owner in (None,"",owner)` else 409. The plan's relaxation (add the stale-OR clause, gated on
  `turn=="agent"`) is a strict superset of today's grant set — a fresh foreign lease still 409s.
  Holds.
- **TTL single source / units.** `STALE_S=180` at viewer.html:219 with the comment "agent_status.at
  is epoch SECONDS (float)"; the banner computes `Date.now()/1000-(as.at||0)>STALE_S` (line 233).
  Server stamps `at=time.time()` (seconds, app.py:548/564). So `LEASE_TTL_S=180` mirrors it and the
  takeover's `now-at` must be seconds — the plan says exactly this. Units match; the mirror-with-
  cross-comment approach is the right weight (a `/config` endpoint would be over-build). Holds.

## Findings

### F1 (SHOULD / worth-considering, fold into MR-054) — `/wait` returns on a LEVEL, not an EDGE; the `since` cursor must be REQUIRED, not "deferred otherwise"

`turn` is a level that stays `"agent"` from the human's Send until the agent's `hand_back` — i.e.
for the entire time an agent is working. The plan's Q4 default (lines 124-131, 526-533) is "compute
the matching set on entry and return immediately if any matching review already satisfies the
predicate," with the `?since=` cursor demoted to "an optional refinement... can be added in MR-054
if cheap, deferred otherwise."

Trace the watcher's steady-state loop (the loop C2 will run): poll `?turn=agent` → claim+spawn →
the agent is now working but `turn` is STILL `agent` → the watcher calls `/wait?turn=agent` again →
**the predicate is already true, so `/wait` returns instantly with the already-working review**, every
call, with zero delay. The long-poll degenerates into a busy-loop in exactly the normal operating
state (one or more reviews parked at agent-turn while their agents work), and the watcher must dedup
client-side or it re-claims/re-spawns. That defeats the stated purpose of MR-054 ("returns
immediately on a flip instead of busy-polling").

The watcher wants the *edge* (a review newly flipped to agent since it last looked), not the *level*
(any review currently at agent-turn). The `turn_updated` timestamp already exists and is written on
every real flip (app.py:542/549/556) and surfaced on `/status` (515) — the cursor is essentially
free. **Make `?since=<epoch>` (compare `turn_updated > since`, also fold into the on-entry baseline
check) a required part of MR-054, not a deferrable nicety.** Without it, the C1 deliverable does not
deliver and C2 inherits a busy-loop with a level-trigger it has to paper over.

This is also why F2 matters: the current validation would pass while hiding this.

### F2 (worth-considering, fold into MR-054 validation) — the `/wait` self-checks don't exercise the steady-state, so they'd green-light F1

The curl steps (lines 412-417) test (a) a clean timeout and (b) a single flip from a clean state
returns. The ~20-line self-check (425-441) proves only the lock-release property (a writer isn't
blocked behind a parked waiter) — which is the right thing for the deadlock crux and I credit it as
a genuine proof, not theatre, *for that property*.

But neither test covers: "a review is ALREADY at `turn==agent`; call `/wait?turn=agent&since=<the
flip's turn_updated>`; assert it does NOT return instantly with that already-known review (it parks
until a *new* flip or times out)." Add that assertion. As written, MR-054's validation would pass
with the level-trigger bug fully present. The lock-release self-check is good; the edge-vs-level
assertion is the one the recipe is missing.

### WC-1 (worth-considering) — unbounded parked `/wait` threads on a no-auth service

The plan calls the held `/wait` "safe" because `ThreadingHTTPServer` has no pool to exhaust (true).
But thread-per-request with no cap means N concurrent `/wait` calls = N parked OS threads for up to
25s each, on a service with no auth. A flood of `/wait` opens is a cheap memory/thread-DoS. This is
not new exposure in the data sense (the plan's "no new field" exposure analysis is correct), and the
service is already trivially floodable, so I am NOT making it blocking. But "occupies one thread and
exhausts no pool" undersells it — note the unbounded-thread cost in MR-054 and, if cheap, consider a
soft cap on concurrent waiters (reject with 503 past a ceiling). At minimum, don't let the ticket
claim the held `/wait` is cost-free.

### N-1 (nit) — `summary()` line cite

The plan cites `summary()` at app.py:127-149 in places and 127-142 elsewhere; it is 127-149, with
the `revision` default at 142. Minor; fix the cite in MR-054 so the implementer lands the `turn`
default next to the existing `revision` default as intended.

### N-2 (nit) — RFC id typo

The plan body cites the design RFC as `22c9555b3e` (lines 26, 496) while the task brief and one spot
reference `22c9525b3e`. Reconcile the id in the epic frontmatter/prose so the trail is followable.

## Scope / sequencing assessment (no blocking issues)

- **2-ticket split (MR-054 detection / MR-055 lease-change) is right.** The stale-takeover is a
  shipped-behavior change to `ping_working` callers a cycle before any watcher exists; isolating it
  so G1/G4 scrutinize it alone is correct. MR-055 `depends_on:[MR-054]` is justified by the shared
  `/handoff` block + the `Condition` lock (clean-merge dependency, not a hard data dependency, as the
  plan honestly states).
- **No misassignment between C1 and C2/C3.** The three server primitives correctly sit in C1; the
  spawner + fail-closed guard correctly sit in C2; arming + per-review crash-loop cap correctly sit
  in C3. The fail-closed guard living in C2 (the chunk that introduces the spawner), not C3, is the
  right call.
- **Q1 (collection-level `/wait`) is the correct default** and does not paint C1 into a corner: a
  per-review `/api/reviews/{id}/wait` is a different route that can be added additively later if C2
  needs it. No corner.
- **No YAGNI over-build to cut.** The thundering-herd `rid`-carry is borderline for "a handful of
  waiters," but the plan explicitly offers the simpler "accept O(all-reviews) per wake, justified for
  scale" fallback, so the implementer isn't forced to over-build. Acceptable.
- **No missing C1 ticket.** The work is fully covered by MR-054 + MR-055. (F1's cursor is a line
  item inside MR-054, not a new ticket.)

## Open questions for the planner

- F1: do you accept making `?since=` (edge semantics on `turn_updated`) a required part of MR-054? If
  you instead intend the watcher to dedup client-side in C2, say so explicitly in MR-054 and in the
  C2 summary — but that pushes a correctness concern across a chunk boundary into code that doesn't
  exist yet, which I'd advise against.
- WC-1: is a concurrent-waiter ceiling worth the ~3 lines in C1, or consciously deferred with the
  no-auth-flood risk noted?

## Resolution log

- 2026-06-24 — Review opened. Verdict PASS-WITH-NITS. F1/F2 to be folded into MR-054 at G2; WC-1 and
  the nits noted. Awaiting planner disposition on F1's cursor question.
- 2026-06-24 — Planner revised the plan (author preserved, G1 independence intact). Dispositions:
  **F1 accepted** — `?since=<cursor>` is now REQUIRED on `/wait` (edge on `turn_updated > since`;
  missing `since` defaults to "now"/block, `since=0` is the explicit backlog opt-in); MR-054 ACs,
  `/wait` wiring, route note, Q4 (RESOLVED), and a risks row updated. **F2 accepted** — MR-054 smoke
  step added: a review already at agent-turn polled with `since >=` its `turn_updated` must return a
  clean `timeout:true`, not an instant hit; smokes #2/#3 + the self-check now pass an explicit
  `since`. **WC-1 accepted** — unbounded parked-thread/cheap-DoS cost stated, accepted for the
  trusted single-operator case, optional `503`-past-N waiter ceiling flagged (no new ticket).
  **N-1/N-2** — plan body already cited `summary()` as 127-149 and the RFC id as `22c9555b3e` at both
  spots (the stale cites were in this review/the brief, not the plan); recorded. No second G1 round
  needed (the critic explicitly scoped F1 as fold-into-ticket, not a re-review trigger). **G1 PASS.**
