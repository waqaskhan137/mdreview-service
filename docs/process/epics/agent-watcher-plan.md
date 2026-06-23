---
epic: agent-watcher
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-24
source: requirements/agent-watcher.md   # the verbatim 3-chunk decomposition brief
gate: passed 2026-06-24   # G1 (Plan Gate): PASS-WITH-NITS, findings folded; tickets unblocked
review: reviews/agent-watcher-plan-review-2026-06-24.md   # independent G1 review (PASS-WITH-NITS); resolutions folded below
related_sprints: [sprint-17]    # C1 -> one sprint; C2, C3 -> later sprints
related_tickets: [MR-054, MR-055]    # C1 tickets created 2026-06-24 (G1 passed)
---

# Agent Watcher Plan

This epic adds the **automation on top of the handoff baton**: a local `watch.py` that notices a
review whose `turn == agent`, claims the cooperative lease, and launches an agent session — so a
human's **"Send to agent"** reaches a session with **no human in the loop**. It builds directly on
the shipped `agent-handoff-baton` epic (PR #17): `turn` + `POST /handoff` + the `agent_status` lease
already exist. The watcher needs three things the broker does not yet provide, plus a non-containerized
launcher and its safety model. This plan decomposes the work into **three dependency-ordered chunks
(C1 → C2 → C3)**, each shipped as its own sprint under this one epic plan — mirroring how
`agent-handoff-baton` cleared G1 once and shipped three sprints. **C1 is planned in full implementable
detail here; C2 and C3 are planned at the chunk-summary level** (scope + dependency + what defers to
them) and will be decomposed into tickets at the start of their own cycles.

**Source requirement:** [`requirements/agent-watcher.md`](../requirements/agent-watcher.md) — the
verbatim 3-chunk decomposition (itself decomposing the design RFC, mdreview review `22c9555b3e`),
kept untouched.

## Product goal

A human presses **"Send to agent"** in the viewer; a watcher process running where the operator's
agent runs picks the baton up automatically — long-polling rather than busy-spinning — claims the
review's lease, and spawns an agent session pointed at that review, all without a human babysitting
the queue. The epic-level "done" state: the full **comment → Send → watcher detects → claims →
spawns → agent works → hands back** loop runs end to end with no human between the Send and the
launch, the watcher is **fail-closed** (it never auto-runs against an untrusted base it cannot vouch
for), and a crash-looping review cannot become an unbounded spawner.

**C1's slice of that goal:** the three server-side primitives the watcher polls — a `turn==agent`
filter (the queue), a `/wait` long-poll (so the watcher returns *immediately* on a flip instead of
busy-polling), and a stale-lease takeover (so a watcher can reclaim a lease abandoned by a dead
session). C1 ships entirely inside the existing service container; **the Dockerfile is untouched and
no watcher code is written** (`watch.py` is C2).

## Core design principle

**The broker gains detection and recovery primitives; it still never summons.** The baton epic
established that mdreview is a *pull* broker — it holds control state, an agent finds work by polling.
The watcher does not change that: the broker still cannot reach into a session. C1 only makes the
*pull* cheaper and more recoverable. **The `/wait` long-poll is a polling optimization, not a push** —
a waiter blocks on a `threading.Condition` and is woken by the same `/handoff` write that flips the
baton, but if no waiter is parked the flip just happens and is found on the next poll. **The
stale-takeover is recovery, not preemption** — it lets a *new* owner claim a lease whose heartbeat has
gone cold, it never evicts a *live* owner. Every C1 primitive is additive and default-safe: a legacy
review with no `turn` reads as `reviewer` and is simply absent from the `turn==agent` queue; a `/wait`
with no flip returns an empty timeout; a takeover against a fresh lease still `409`s.

## Recommended approach

### Service (`app.py`) — C1, planned in full

All C1 work is in `app.py`. It is two additive read surfaces (the filter, the `/wait` endpoint) plus
one **shipped-behavior change** (the stale-takeover on the existing `/handoff` lease arm). The wiring
crux is shared: a `threading.Condition` built over the **existing** global lock.

#### 1. `?turn=agent` filter on `GET /api/reviews` + `summary()` defaults `turn`

- `summary()` (app.py:127-149) already does `m = dict(meta(rid))`, so `turn` and `agent_status`
  **already flow into every `GET /api/reviews` row for free** — the baton epic confirmed this
  (MR-051 verified `turn` appears on the list). C1 adds **two** things, not a re-surfacing:
  1. **Default `turn` in `summary()`** so a legacy review with no `turn` key reads as `"reviewer"`
     and is filterable, never `None`/absent. Add `m["turn"] = m.get("turn", "reviewer")` in
     `summary()` (alongside the existing `m["revision"] = m.get("revision", 0)` default at
     app.py:142). This is the additive-default-safe rule (footgun #3, #8): the filter must not depend
     on a key legacy reviews lack.
  2. **A `?turn=` query filter** on the `GET /api/reviews` arm (app.py:437-438). Today it is
     `if path == "/api/reviews" and m == "GET": return self._json(200, {"reviews": list_reviews()})`.
     Parse `parse_qs(urlparse(self.path).query)` (both already imported, app.py:38) for a `turn`
     value and, when present, filter the `list_reviews()` result to rows whose `turn` equals it.
     **Filter in Python after `list_reviews()`** (do not push the predicate into `list_reviews()`);
     the list is small and `summary()` is where the default lands. Unknown/empty `turn` value ⇒ no
     filter (return all), preserving today's behavior.
- **Exposure note (footgun #5, no-auth id-only tenancy):** `?turn=agent` does **not** widen exposure
  beyond what `GET /api/reviews` already discloses — the unfiltered list already returns every
  review's `turn`. The filter is a server-side convenience over data already public on this no-auth
  service; it adds **no new field and no new cross-review aggregation**. State this in the ticket so a
  reviewer does not flag a phantom exposure widening. (The watcher's own trust boundary is C2/C3, not
  this filter.)

#### 2. `/wait` long-poll endpoint — the load-bearing wiring

A new route arm `GET /api/reviews/wait` (collection-level, not per-review — the watcher waits across
*its* fleet, see Q1) that **blocks server-side** until a baton flips or a bounded timeout elapses,
then returns the changed review(s) or an empty timeout.

**The wiring the G1 critic will check (pin every line):**

- **The lock becomes a `Condition` over the existing lock.** Today `_lock = threading.Lock()`
  (app.py:46). A plain `Lock` has **no `wait()`/`notify_all()`** — only a `Condition` does. Change it
  to **`_lock = threading.Condition()`**. A `Condition()` *is* a context manager that acquires/releases
  its internal lock, so **every existing `with _lock:` site is unchanged** (verified: the only `_lock`
  uses are `with _lock:` blocks at app.py:475, 535, 627, 646, 663, 685 — none calls `.acquire()`
  directly, so the swap is transparent). The default `Condition()` wraps a reentrant `RLock`; that is
  a superset of the current non-reentrant `Lock` (no site relies on non-reentrancy), so the swap does
  not change existing semantics. **Do not create a second Condition over a separate lock** — the
  notify and the writes must share one lock or a flip can be missed (lost-wakeup) or a writer can run
  while a waiter holds the lock.
- **The `/handoff` baton-flip calls `notify_all()`.** Inside the existing `with _lock:` block in the
  `/handoff` handler (app.py:535-570), **after** the `_write(p, json.dumps(mt))` (app.py:570) and
  still **under the lock**, call `_lock.notify_all()` on any arm that changes `turn` (the `{to:agent}`
  flip at app.py:550-556 and the `{to:reviewer,...}` hand-back/reclaim arms at app.py:538-549). A
  lease-only `{state:working}` renew (app.py:557-566) need not notify (no turn change) — but notifying
  on every successful write is also safe and simpler; **prefer notifying once after any successful
  `_write` in the handler** (one `notify_all()` after the `if err is None: _write(...)` block), so the
  predicate, not the arm, decides whether a waiter actually returns. Carry the changed `rid` into the
  notify path (see thundering-herd below).
- **The parked handler does `wait(timeout)` which RELEASES `_lock` while blocked.** This is the
  correctness crux: `Condition.wait()` **atomically releases the underlying lock** while parked and
  re-acquires it on wake. So a parked `/wait` does **not** hold `_lock`, and a concurrent `PUT /source`
  / `/handoff` / comment write can take the lock and proceed. **If `/wait` held the lock across the
  block, one parked waiter would deadlock every writer** — that is the failure the happy-path curl
  misses, and the concurrent self-check below exists to prove it does not happen.
- **`?since=<cursor>` is REQUIRED — `/wait` matches an EDGE, not a LEVEL (F1).** `turn` is a *level*:
  a review stays `turn=="agent"` from the human's Send until the agent's `hand_back`, i.e. for the
  **entire** time an agent is working. So "return immediately if any review already matches the filter"
  is wrong: in steady state (one or more reviews parked at agent-turn while their agents work) that
  predicate is *already true*, so `/wait` would return instantly on **every** call and the long-poll
  degenerates into a busy-loop — defeating the whole point of MR-054. The watcher wants the **edge**
  (a review *newly* flipped to agent since it last looked), not the level (any review *currently* at
  agent-turn). **The cursor is `turn_updated`** — already written on every real flip (app.py:542/549/
  556) and surfaced on `/status` (app.py:515), so it is essentially free. **Exact semantics:**
  - The caller **MUST** pass `?since=<cursor>`. The watcher reads an initial cursor from the list (the
    max `turn_updated` it currently knows, or `0` for a cold start that wants the existing backlog) or
    from `/status`, then long-polls `GET /api/reviews/wait?turn=agent&since=<that cursor>`.
  - The endpoint returns only reviews matching the filter (`turn=="agent"`) **whose `turn_updated >
    since`** — i.e. newer than the cursor. A review already at agent-turn with `turn_updated <= since`
    is **not** returned; the call **blocks** (up to the timeout) until something newer appears.
  - Each returned row carries its `turn_updated`; the watcher advances its cursor to the **max
    `turn_updated`** it received and passes that as `since` on the next `/wait` — so a flip it has
    already seen never re-returns. On timeout the response carries the **unchanged** cursor (or the
    watcher simply re-uses its last cursor), so no edge is lost across the re-issue boundary.
  - **Missing `since` ⇒ treat as `now` (`time.time()`), the safer default.** An omitted cursor means
    "wait for the next flip from this instant," so `/wait` **blocks** rather than dumping the whole
    agent-turn backlog instantly — a misuse without `since` degrades to a clean timeout, never to a
    busy-loop. (A caller that *wants* the backlog passes `since=0` explicitly.) State this default in
    the ticket; do **not** make missing-`since` equivalent to `since=0`.
- **Bounded server-side timeout, re-check the predicate on wake.** The handler computes a snapshot of
  the predicate (the set of reviews matching the caller's filter with `turn_updated > since`), then
  loops: `with _lock:` → if the predicate is already satisfied vs the caller's `since` cursor, return
  the changed rows immediately (no wait); else `_lock.wait(remaining_timeout)`; on wake (spurious or
  real) **re-check the predicate** (a `Condition.wait` can wake spuriously and a `notify_all` wakes
  every waiter, so a bare wake is not proof a *newer-than-`since`* flip happened); loop until either
  the predicate is satisfied or the total elapsed exceeds the bound. **Default server timeout ≈ 25s**
  (under typical 60s proxy/client read timeouts; tunable via an env var, see Q2), returning `200
  {"reviews":[], "timeout":true}` on expiry so the watcher simply re-issues — a long-poll, not an open
  stream.
- **Thundering herd — carry the changed `rid`, do not re-scan per waiter.** `list_reviews()`
  (app.py:152-155) is **O(all reviews)**: `os.listdir(DATA_DIR)` + a `summary()` (which itself reads
  `meta.json`, `notes.json`, and the comments file) per review. Each `notify_all()` wakes **every**
  parked waiter; if each then re-runs `list_reviews()` that is O(waiters × all-reviews) disk reads per
  flip. **Mitigation:** the `/handoff` write records the changed `rid` (e.g. a module-level
  `_last_change = {"rid": rid, "at": now}` set under the lock just before `notify_all()`), and the
  woken waiter checks **whether the changed `rid` matches its filter** (one `meta(rid)` read, O(1))
  before deciding to return — only constructing a full row for the matched review, never re-scanning
  the whole fleet on a wake. The expensive `list_reviews()` runs **once** on entry (to compute the
  baseline) and again **only** when actually returning rows. State the chosen mechanism in the ticket;
  the O(1)-per-wake check is the recommendation, the "accept O(all-reviews) per wake for a handful of
  waiters" fallback is acceptable only if explicitly justified for the expected scale.
- **`ThreadingHTTPServer` makes the held `/wait` safe from pool-starvation — but parked threads are
  not free (WC-1).** The server is a bare `ThreadingHTTPServer` (app.py:37, 727) — **thread-per-
  request, no fixed worker pool** — so a `/wait` that blocks for 25s occupies one thread and exhausts
  **no pool**; concurrent requests get their own threads. (A fixed-pool server could be starved by N
  parked waiters; this one cannot.) **Honest cost:** thread-per-request with no connection cap and no
  auth means N concurrent `/wait` opens = N parked OS threads (each up to 25s). On this trusted, no-
  auth, single-operator service a flood of `/wait` opens is a cheap parked-thread DoS vector — but the
  service is already trivially floodable (any endpoint), so this adds no *new* exposure class. **The
  ticket must state this cost rather than calling the held `/wait` cost-free.** Default disposition:
  **accept it** for the trusted/single-operator case (consistent with how the requirement treats the
  trust model — the watcher's real trust boundary is C2's fail-closed base check). **Mitigation if it
  ever matters (flag, do not build now):** a module-level in-flight-waiter counter incremented on
  entry / decremented in a `finally`, and refuse (`503`) or fall to a very short timeout past a ceiling
  `N`. ~3 lines; noted as an optional refinement, not a separate ticket. Confirm the pool-safety and
  state the parked-thread cost in MR-054.
- **Route placement.** Add the arm as a new `re.fullmatch` in `route()`. **`/wait` is a collection
  endpoint** (`/api/reviews/wait`), so it must be matched **before** the per-review arm
  `re.fullmatch(r"/api/reviews/" + RID, path)` at app.py:454 — `wait` is 4 chars and matches
  `RID = [A-Za-z0-9]{4,40}`, so placed *after* the RID arm it would be shadowed as a review id
  lookup (404 "not found"). Place it **immediately after the `GET /api/reviews` collection arm
  (app.py:437-438) and before the per-review `mo = re.fullmatch(r"/api/reviews/" + RID, path)` arm
  (app.py:454).** Cite this placement in the ticket (footgun #4: a new route must not be shadowed).

#### 3. Stale-lease takeover on `{state:working}` — the shipped-behavior change

Today the lease arm (app.py:557-566) grants the lease only if `cur_owner in (None, "", owner)` — an
unset lease or the caller's own. A foreign owner always `409`s, **even if the lease holder is dead**.
C1 relaxes this: grant the lease if the current owner is unset, equal, **OR stale**
(`now − agent_status.at > TTL`). This lets a watcher reclaim a lease abandoned by a crashed session.
**It is its own ticket** because it changes what existing `ping_working` callers observe (a foreign
owner can now take a *stale* lease) a full cycle before any watcher exists — the G1 critic scrutinizes
it on its own merits.

**Two items the ticket must pin:**

- **(a) TTL single source of truth.** The server-arm staleness TTL and the viewer's `STALE_S = 180`
  (viewer.html:219 — "lease-heartbeat staleness (~3 min); agent_status.at is epoch SECONDS") must not
  silently diverge: today the viewer decides "stale" at 180s and shows *"Agent may have stopped"*; if
  the server takes over at, say, 120s, the viewer would still be showing a live banner for a lease the
  server already reassigned (or vice-versa). **Canonical value:** define a single server-side constant
  **`LEASE_TTL_S = 180`** (matching the viewer's 180s) near the config block (app.py:40-47), used by
  the takeover arm. The viewer's `STALE_S` is hand-kept in sync as a **documented mirror** — add a code
  comment at **both** sites naming the other (`app.py LEASE_TTL_S` ↔ `viewer.html STALE_S`) and stating
  they must move together. (The viewer cannot read a server constant without a new endpoint; per
  footgun #1/no-new-dependency and the baton epic's "staleness is viewer-computed" decision, a
  documented mirror is the right weight here, not a new `/config` endpoint. Surfaced as Q3 — if a
  reviewer wants the server to be the only source, that is a small follow-up, not a C1 blocker.)
  **`agent_status.at` units:** the server stamps `at = time.time()` (epoch **seconds**, float —
  app.py:548, 564) and the viewer reads `Date.now()/1000 - at` (viewer.html:233). The takeover must
  compute `now - at` in the **same seconds unit** — `now = time.time()`; do not mix in `*1000`.
- **(b) The reclaim-vs-takeover race — re-check `turn == agent` under the same `_lock`.** The takeover
  must, **inside the same `with _lock:` block** that decides the grant, re-check that `turn` is still
  `"agent"` before granting a stale takeover. Why: the reclaim arm `{to:reviewer, by:reviewer}`
  (app.py:538-542) forces `turn = "reviewer"` **unconditionally and leaves `agent_status` intact**
  (the stale lease's `owner`/`at` are *not* cleared on reclaim). So a lease can be simultaneously
  *stale* **and** *already reclaimed by the human*. Without the re-check, a watcher's stale-takeover
  would grant the lease and (in C2) spawn a credentialed session **against a review whose turn is
  already `reviewer`** — exactly the wasted/unsafe spawn the requirement calls out. **Resolution:** in
  the `{state:working}` arm, when the grant reason is *staleness* (not unset/equal owner), require
  `mt.get("turn") == "agent"`; if `turn != "agent"`, **reject the takeover** (return `409
  {"error":"lease held","owner":...}` — same back-off shape, the caller skips it). A non-stale foreign
  owner still `409`s as today; an unset/equal-owner claim is unaffected by the turn re-check (it is the
  normal claim path, not a takeover). Because the whole decision is already inside the single
  `with _lock:` block (app.py:535), the read of `turn` and the write of `agent_status` are atomic with
  respect to a concurrent reclaim — no TOCTOU.

**Resulting `{state:working}` decision (under `_lock`):**

| Current lease state | Body owner | Grant? |
|---|---|---|
| unset (`None`/`""`) | any | **grant** (normal claim) |
| equals body owner | same | **grant** (renew) |
| foreign, **fresh** (`now − at ≤ TTL`) | different | **409** (live owner — unchanged from today) |
| foreign, **stale** (`now − at > TTL`), `turn == "agent"` | different | **grant** (takeover) |
| foreign, **stale**, `turn != "agent"` (reclaimed) | different | **409** (don't spawn at a reclaimed review) |

### UI (`viewer.html` / `dashboard.html` / `static/`)

**No UI change in C1.** The only viewer touchpoint is **documentation, not behavior**: the `STALE_S`
comment at viewer.html:219 gains a mirror note pointing at `app.py LEASE_TTL_S` (and vice-versa) so the
two staleness thresholds stay in sync (item 3a). This is a one-line comment edit, not a render-observable
change — **footgun #6 (a 200 is not a render; UI changes need render-smoke) does not apply**, and there
is **no new served file, so no Dockerfile COPY** (footgun #9 does not bite). The C2/C3 watcher has no UI
at all (`watch.py` is a CLI process). State this in the lease-takeover ticket so a reviewer does not
expect a render-smoke for a comment-only viewer touch.

### Watcher (`watch.py`) — C2/C3 only, NOT C1

No `watch.py`, no launcher, no new file ships in C1. C1 is purely the server primitives. The watcher
itself, its trust model, and its caps are C2/C3 (summarized below).

## Rollout phases

Three dependency-ordered chunks, **one sprint each**, all under this one epic plan. **C1 ships first
and is the only chunk decomposed into tickets now.** C2 and C3 are decomposed at the start of their own
cycles (they run as later sprints once C1 ships).

### Phase 1 — C1: Server support (`svc`, `app.py`) — sprint TBD, the immediate deliverable

The detection + recovery primitives, as **two tickets** (the requirement's default: "C1 as one cycle
with two tickets", split detection vs lease-change):

- **MR-054 (detection):** `?turn=agent` filter + `summary()` `turn` default **and** the `/wait`
  long-poll endpoint (the `Condition` swap, the `notify_all()` in `/handoff`, the parked
  `wait(timeout)` that releases `_lock`, the bounded timeout, the **required `?since=<turn_updated>`
  edge cursor** so the long-poll matches an edge not a level, the thundering-herd `rid`-carry).
- **MR-055 (lease change):** the stale-lease takeover on `{state:working}` — the shipped-behavior
  change, with TTL single-source-of-truth and the reclaim-vs-takeover re-check.

Additive + one isolated behavior change; ships invisibly inside the existing container (no UI, no
Dockerfile change). Once C1 lands, the watcher can be built against it.

### Phase 2 — C2: Watcher core (`watch.py`, fail-closed: trusted base only) — later sprint

**Planned at chunk-summary level; decomposed into tickets at the start of its own cycle.** Scope (from
the requirement): `watch.py` (sibling to `mcp_server.py`, stdlib-only `urllib` + `subprocess` +
`threading`) that **fails closed** — refuses to auto-run unless the configured base is trusted (default
allow `localhost`/`127.0.0.1`, plus an explicit operator-set `WATCH_TRUSTED_BASE` exact-match). Flow:
trusted-base check → long-poll C1's `/wait` → **claim-before-spawn** (atomic lease claim via
`/handoff {state:working}`, spawn **only on 200**, so a cold start cannot double-spawn) → spawn the
launch command with the child env contract (`REVIEW_ID`, `MDREVIEW_BASE`, `owner`). **Minimal caps from
day one** (a concurrency cap + a global launches/hour cap) so it is never an unbounded spawner. The
launch mechanism is a **generic command template** (default = Claude), decided at C2 planning, so the
C2 test can use a stub launch command. **Depends on C1.** This chunk is where the credentialed spawner
*and its real fail-closed guard* are introduced — the guard lives here, not in C3.

### Phase 3 — C3: Watcher safety + ops (`watch.py` + docs) — later sprint

**Planned at chunk-summary level; decomposed into tickets at the start of its own cycle.** Scope: lets
the watcher run against a **public / no-auth** base (where provenance is not a trust boundary) by
**relaxing** C2's fail-closed refusal in a controlled way — an operator-controlled **arming/allowlist
file** (not API-settable, so a request can't arm itself) naming which reviews may auto-run; un-armed
reviews are skipped even when `turn==agent`. Adds a **per-review attempt cap + relaunch-convergence
guard** (a crash-looping review stops relaunching after N attempts, refining C2's global rate cap), and
a **runbook** (`CLAUDE.md` + README: how to run the watcher, the arming model, the trusted-base/arming
requirement). **Depends on C2.**

## Non-goals

Scope boundaries for this epic (and for C1 specifically):

- **No watcher code in C1.** `watch.py`, the launcher, the trust check, and the caps are C2/C3. C1 is
  server primitives only.
- **No Dockerfile / container change anywhere in this epic.** `watch.py` runs where the operator's
  agent runs (like `mcp_server.py`), reading local creds and spawning local sessions — it is **not**
  containerized. C1 ships inside the existing service image with no new served file (footgun #9 does
  not apply).
- **No push / WebSocket / SSE.** `/wait` is a **long-poll** (bounded server timeout, then the client
  re-issues), not a persistent stream. No new dependency, no async framework (footgun #1).
- **No background sweep / scheduler / server-side staleness timer.** The takeover computes staleness
  **on demand** inside a `{state:working}` request (`now − at > TTL`); the server runs no timer and no
  sweep — preserving the baton epic's no-scheduler property. (The viewer still computes its own banner
  staleness; the two thresholds are a documented mirror, not a server push.)
- **No server-enforced single-writer.** The lease stays a **cooperative** compare-and-claim; the
  stale-takeover relaxes *who* may claim, it does not gate `PUT /source`. Single-writer remains honest
  only under one-agent-per-review (inherited from the baton epic, issue #16).
- **No change to the baton contract itself** (the `turn`/`/handoff`/`agent_status` shapes shipped in
  PR #17). C1 adds the filter and `/wait`, and relaxes one branch of the existing lease arm; it adds
  no new `meta.json` key and removes none.
- **No auth.** The service has none by design. `/wait` and `?turn=agent` disclose nothing
  `GET /api/reviews` does not already disclose. The watcher's trust boundary is the C2 fail-closed
  base check, not anything in C1. (When auth lands it must cover `/handoff` first — logged risk,
  inherited from the baton epic.)
- **Concurrent co-editing of one review by multiple agents (OT/CRDT)** — deferred, issue #16.

## Key constraints

Hard repo rules C1 must not violate (made specific):

- **Stdlib-only, zero pip, no framework, no new dependency.** The `Condition` is `threading.Condition`
  (stdlib); the long-poll is a blocking `wait(timeout)` on a thread the `ThreadingHTTPServer` already
  spawns. Nothing is vendored, no `static/` asset, no async runtime (footgun #1).
- **Single-file regex router, ordered match (footgun #4).** `/api/reviews/wait` is added as a new
  `re.fullmatch` arm placed **after** the `GET /api/reviews` collection arm (app.py:437) and **before**
  the per-review `RID` arm (app.py:454) — `wait` matches `RID`, so a later placement would be shadowed
  into a review-id lookup. The `?turn=` filter extends the existing collection arm in place. Cite
  `app.py:437`/`app.py:454` in MR-054.
- **`/wait` is edge-triggered on a REQUIRED `?since=` cursor (F1).** The endpoint returns only reviews
  whose `turn_updated > since` (the cursor uses the existing `turn_updated`, written at app.py:542/549/
  556, surfaced on `/status` at app.py:515) — never the current *level* of `turn==agent`. Missing
  `since` ⇒ default `now` (block for the next flip), the safer degrade; `since=0` is the explicit
  backlog opt-in. This is a hard part of MR-054's contract, not a deferrable refinement — without it
  the long-poll busy-loops in steady state.
- **The `Condition` wraps the existing `_lock`; `wait()` releases it while parked.** Swap
  `_lock = threading.Lock()` (app.py:46) → `_lock = threading.Condition()`. All existing `with _lock:`
  sites (app.py:475, 535, 627, 646, 663, 685) are unchanged (none calls `.acquire()` directly). The
  parked `/wait` must use `_lock.wait(timeout)` (releases the lock) — **never** a sleep-while-holding —
  or one waiter deadlocks every writer. This is the correctness crux MR-054 must prove with the
  concurrent self-check.
- **`/handoff` notifies under the lock after the write.** Add `_lock.notify_all()` inside the existing
  `with _lock:` block in the `/handoff` handler, after `_write` (app.py:570), so the notify and the
  write are atomic. Record the changed `rid` (module-level, under the lock) before notifying so woken
  waiters do an O(1) match, not an O(all-reviews) rescan.
- **Overwrite-based JSON storage under the lock (footgun #2).** The takeover still does the full
  read-mutate-write-whole-dict the existing arm does (app.py:536, 570); it never partial-merges
  `meta.json`. The takeover adds **no** persisted key — it only changes the *grant condition*.
- **`meta.json` back-compat (footgun #3, #8).** `summary()` must default `turn` to `"reviewer"` for
  legacy reviews; the `/wait` predicate and the takeover read `turn`/`agent_status` with `.get(...)`
  defaults (`agent_status` absent ⇒ no lease ⇒ a `working` claim is the normal unset-owner grant, not
  a takeover). A legacy review is simply absent from the `turn==agent` queue.
- **No-auth, id-only tenancy (footgun #5).** `?turn=agent` and `/wait` aggregate over reviews but
  expose **no field** `GET /api/reviews` does not already expose, and add **no** cross-review data. The
  watcher's per-review trust filtering is C2/C3 (the fail-closed base check + arming), not C1. State
  the "no new exposure" finding in both C1 tickets.
- **TTL single source of truth (the lease-change ticket).** `LEASE_TTL_S` (server) and `STALE_S`
  (viewer.html:219) are mirrored at 180s with a cross-referencing comment at both sites; they move
  together. `agent_status.at` is epoch **seconds** (float) — the takeover computes `now − at` in
  seconds, never milliseconds.
- **Validation gate is `python3 -m py_compile app.py`** (no test framework). Each C1 ticket owes
  `py_compile` + curl smokes **plus** one ~20-line assert-based self-check for the non-trivial
  concurrency (the lock-release proof) — the repo's one-runnable-check convention. No `docker build`
  needed (no Dockerfile change); no render-smoke (no UI behavior change).
- **Local instance is on port 8139; never `docker compose up` (binds 8137).** All smokes run against a
  **throwaway** container on a scratch port (e.g. 8155), never the live 8139 instance and never the
  compose 8137.
- **Dates `Europe/London`; commits keep the `Co-Authored-By: Claude` trailer and reference the ticket
  ID.**

## Preferred execution order

1. **MR-054 (detection: filter + `/wait`)** — must land first. It introduces the `Condition` swap and
   the `notify_all()` in `/handoff`; the lease-takeover ticket builds on the same lock and may want the
   `/wait` to demonstrate end-to-end. The `Condition` change is the foundational edit.
2. **MR-055 (lease change: stale-takeover)** — depends on MR-054 only because both touch the
   `/handoff` handler under the same lock; sequencing MR-054 first avoids a merge conflict on that
   block and lets MR-055's smoke use `/wait` to observe the takeover's effect. (The takeover logic is
   independent of `/wait`'s correctness; the ordering is for clean integration, not a hard data
   dependency.)
3. **C2, then C3** — later sprints, decomposed at the start of their own cycles, each depending on the
   prior chunk.

## Ticket breakdown

Create these in `tickets/` only after G1 passes, then link them here. **Only C1 is decomposed now**;
C2/C3 tickets are created at the start of their cycles. IDs are the next free sequential IDs (highest
existing is MR-053).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-054 | Watcher detection: `?turn=agent` filter + `summary()` turn-default + `/wait` long-poll (Condition over `_lock`, required `?since=<turn_updated>` edge cursor) | svc | 1 (C1) |
| MR-055 | Stale-lease takeover on `/handoff {state:working}` (TTL single-source + reclaim-vs-takeover re-check) | svc | 1 (C1) |

Dependencies: MR-055 `depends_on: [MR-054]` (shared `/handoff` handler + `Condition` lock). Sprint
membership: **the C1 sprint = {MR-054, MR-055}**. C2 and C3 tickets are not created until their cycles
open.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Lock-discipline failure: a parked `/wait` deadlocks every writer.** If the handler sleeps/blocks while *holding* `_lock` instead of `wait()`-ing on the `Condition`, one waiter freezes all writes. | Use `_lock.wait(timeout)` (atomically releases the lock while parked). **MR-054's ~20-line concurrent self-check parks a `/wait` in a thread and fires a concurrent writer, asserting the writer is NOT blocked** — proving the release. This is the failure the happy-path curl cannot catch. |
| **Lost wakeup / spurious wake.** A flip that happens between the predicate snapshot and the `wait()`, or a bare wake, returns wrong/empty. | Predicate is re-checked **under the lock** both before waiting (return immediately if already changed) and on every wake; the notify is under the same lock after the write, so no flip is missed. `wait` is in a loop bounded by the deadline. |
| **`/wait` matches a LEVEL not an EDGE → busy-loop in steady state (F1).** `turn` stays `agent` for the whole time an agent works, so "return if any review currently matches" returns instantly on every poll while any agent is busy — the long-poll degenerates into a busy-loop and the watcher re-claims/re-spawns. | `?since=<cursor>` is **required**; the endpoint returns only reviews with `turn_updated > since` (an edge), blocking otherwise. Missing `since` defaults to `now` (block), never to the backlog. **MR-054 validation #4 asserts the steady-state property** (a review already at agent-turn, polled with `since>=` its `turn_updated`, returns a clean timeout — not an instant hit). |
| **Validation green-lights the level-trigger bug (F2).** The single-flip-from-clean happy path passes with OR without the edge fix. | Add the explicit steady-state assertion (#4 above) so the recipe fails when `/wait` returns an already-known agent-turn review. |
| **Unbounded parked `/wait` threads on a no-auth service (WC-1).** Thread-per-request, no cap, no auth ⇒ N concurrent `/wait` opens = N parked OS threads (up to 25s each) — a cheap parked-thread DoS. | Pool-safe (no fixed pool to starve), but **not** cost-free. Accepted for the trusted/single-operator case (consistent with the requirement's trust model; the real trust boundary is C2's fail-closed base check); the service is already trivially floodable so this is no new exposure class. Flagged mitigation if it ever matters: an in-flight-waiter counter that `503`s past a ceiling (~3 lines, optional). MR-054 states the cost, does not claim cost-free. |
| **Thundering herd: each flip wakes every waiter into an O(all-reviews) rescan.** N waiters × a full `list_reviews()` (disk-heavy) per flip. | Carry the changed `rid` (module-level, under the lock) into the notify; woken waiters do an O(1) `meta(rid)` match before deciding to return; the full scan runs once on entry and once on return, not per wake. |
| **Stale-takeover races a human reclaim → a credentialed spawn at a reviewer-turn review.** Reclaim forces `turn=reviewer` but leaves `agent_status` stale (app.py:538-542), so a lease can be stale AND reclaimed. | The takeover re-checks `turn == "agent"` **inside the same `with _lock:` block** before granting a stale takeover; `turn != "agent"` ⇒ `409`. Atomic with the concurrent reclaim, no TOCTOU. Exercised by an MR-055 smoke (flip → let lease go stale → reclaim → assert a foreign `working` claim still `409`s). |
| **TTL divergence: server takes over before/after the viewer's 180s "stale" banner.** A reassigned lease still shows live in the viewer (or vice-versa). | Single canonical `LEASE_TTL_S = 180` server-side, mirrored to viewer.html `STALE_S = 180` with a cross-referencing comment at both sites; they move together. (Q3: a server-authoritative `/config` is a possible follow-up, out of C1.) |
| **Behavior change leaks to existing `ping_working` callers a cycle early.** A foreign owner can now take a *stale* lease before any watcher exists. | Isolated to its own ticket (MR-055) so the G1/G4 review scrutinizes it alone; the change is *only* "stale + turn==agent ⇒ grant", a strict superset of today's grant set, and the smoke proves a *fresh* foreign lease still `409`s (no regression for live owners). |
| **`?turn=agent` perceived as an exposure widening on the no-auth service.** | It returns no field `GET /api/reviews` does not already return and adds no cross-review aggregation; stated as a "no new exposure" finding in both tickets so a reviewer does not flag a phantom widening. |

## Verification

Each C1 ticket's evidence below becomes its G4 (review) and the sprint's G7 (close) evidence. All
smokes run against a **throwaway container on a scratch port** (e.g. 8155), never the live 8139
instance and never `docker compose up` (8137). C1 touches **no product page**, so per the G7
pass-condition row a render-smoke/screenshot is **not** owed; the sprint still owes the container
rebuild + `curl /healthz` + `GET /api/reviews` smoke.

### MR-054 (svc) — `py_compile` + curl + a concurrent lock-release self-check

Gate: `python3 -m py_compile app.py`. Then, on a throwaway container (`$B` = scratch base):

```bash
# create a review (legacy default: turn must read "reviewer" in the list even before any handoff)
ID=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"watch smoke","markdown":"# x\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 1. filter: with no turn==agent review, ?turn=agent returns an empty list; unfiltered shows the review
curl -s "$B/api/reviews?turn=agent" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["reviews"]))'   # -> 0
curl -s "$B/api/reviews" | python3 -c 'import sys,json;rs=json.load(sys.stdin)["reviews"];print(all(r.get("turn")=="reviewer" for r in rs))'  # -> True (summary() defaults turn)

# flip the baton, then the filter returns exactly this review
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null
curl -s "$B/api/reviews?turn=agent" | python3 -c 'import sys,json;rs=json.load(sys.stdin)["reviews"];print([r["id"] for r in rs])'  # -> ['<ID>'] only, all turn==agent
# reclaim back so it leaves the queue
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"reviewer","by":"reviewer"}' >/dev/null
curl -s "$B/api/reviews?turn=agent" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["reviews"]))'   # -> 0

# 2. /wait times out cleanly when nothing flips NEWER than the cursor (bounded server timeout)
NOW=$(python3 -c 'import time;print(time.time())')
time curl -s "$B/api/reviews/wait?turn=agent&since=$NOW&timeout=2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("timeout"),len(d["reviews"]))'  # -> True 0, returns ~2s

# 3. /wait returns immediately on a NEW flip (turn_updated > since) fired from a second request:
NOW=$(python3 -c 'import time;print(time.time())')
( sleep 0.5; curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null ) &
time curl -s "$B/api/reviews/wait?turn=agent&since=$NOW&timeout=25" | python3 -c 'import sys,json;rs=json.load(sys.stdin)["reviews"];print([(r["id"],r["turn_updated"]) for r in rs])'  # -> [('<ID>', <new turn_updated>)] in well under 25s

# 4. F2 — STEADY-STATE no-busy-loop: a review ALREADY at turn==agent must NOT make /wait return
#    instantly when polled with a since at-or-after that review's turn_updated. This is the edge-vs-
#    level property; the happy-path flip above (#3) would pass WITH the level-trigger bug present.
CUR=$(curl -s "$B/api/reviews/$ID/status" | python3 -c 'import sys,json;print(json.load(sys.stdin)["turn_updated"])')   # the flip's turn_updated; ID is at turn==agent now
time curl -s "$B/api/reviews/wait?turn=agent&since=$CUR&timeout=2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("timeout"),len(d["reviews"]))'  # -> True 0, returns ~2s (does NOT return the already-working review)
```

**Plus the ~20-line concurrent self-check (the lock-release proof the curl misses)** — an inline
Python script that, against the throwaway base, parks a `/wait` in a background thread and fires a
concurrent writer (a `/handoff` flip **or** a `PUT /source`) against the *same service*, asserting the
**writer returns promptly (not blocked behind the parked waiter)**:

```python
# proves Condition.wait() releases _lock while parked: a writer must NOT block on a parked /wait.
import threading, time, urllib.request, json, sys
B = sys.argv[1]                                   # scratch base, e.g. http://localhost:8155
def post(path, body):
    r = urllib.request.urlopen(urllib.request.Request(B+path, json.dumps(body).encode(),
        {"Content-Type":"application/json"}), timeout=30); return json.load(r)
RID = post("/api/reviews", {"title":"lock","markdown":"# x\n"})["id"]
SINCE = time.time()                               # cursor = now; nothing newer, so /wait parks
def park():                                       # block on /wait for up to ~10s (no newer flip)
    urllib.request.urlopen(B+"/api/reviews/wait?turn=agent&since=%f&timeout=10" % SINCE, timeout=15).read()
t = threading.Thread(target=park, daemon=True); t.start(); time.sleep(0.5)  # ensure the waiter is parked
t0 = time.time()
post("/api/reviews/%s/source" % RID, {"markdown":"# y\n"})                  # concurrent writer
dt = time.time() - t0
assert dt < 2.0, "writer blocked behind a parked /wait (%.2fs) — Condition did not release _lock" % dt
print("OK: writer unblocked in %.2fs while a /wait was parked" % dt)
```

Pass: every numbered curl expectation holds — including **#4, the steady-state no-busy-loop assertion
(F2)**: a review already at `turn==agent` polled with `since` at-or-after its `turn_updated` returns a
clean `timeout:true` empty list, **not** an instant hit (this is the assertion that distinguishes the
correct edge trigger from the level-trigger bug; #3's happy-path flip passes either way); the self-
check prints `OK` (writer unblocked < 2s); existing endpoints (`GET /api/reviews` unfiltered, `GET
/status`, `PUT /source`, `/handoff`) respond unchanged for a review that never touches `/wait`.

### MR-055 (svc) — `py_compile` + curl (live lease 409s; stale lease taken over; reclaim-race 409s)

Gate: `python3 -m py_compile app.py`. Then (lease-takeover behavior), with a **short test TTL** wired
to an env override so the smoke does not wait 180s (see Q2 — make `LEASE_TTL_S` env-overridable, e.g.
`MDREVIEW_LEASE_TTL_S=2`, default 180):

```bash
ID=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"lease","markdown":"# x\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null

# owner A claims the lease
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-A"}' >/dev/null

# 1. FRESH foreign owner B is rejected (live lease — unchanged behavior)
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$B/api/reviews/$ID/handoff" \
  -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-B"}'   # -> 409 (lease held)

# 2. wait past the (test) TTL so A's lease goes stale, then B TAKES IT OVER (the new behavior)
sleep 3
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$B/api/reviews/$ID/handoff" \
  -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-B"}'   # -> 200 (stale takeover)
curl -s "$B/api/reviews/$ID/status" | python3 -c 'import sys,json;print(json.load(sys.stdin)["agent_status"]["owner"])'  # -> sess-B

# 3. reclaim-vs-takeover: re-flip to agent, let the lease go stale, RECLAIM (turn->reviewer, agent_status left stale),
#    then a foreign stale claim must STILL 409 (don't spawn at a reclaimed review)
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-C"}' >/dev/null
sleep 3                                                                            # lease goes stale
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"reviewer","by":"reviewer"}' >/dev/null  # human reclaims; turn->reviewer
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$B/api/reviews/$ID/handoff" \
  -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-D"}'   # -> 409 (stale BUT turn==reviewer => no takeover)
```

Pass: (1) a fresh foreign lease still `409`s (no regression for live owners); (2) a stale lease is
taken over (200, owner reassigned); (3) a stale-but-reclaimed lease (`turn==reviewer`) still `409`s —
the reclaim-race re-check holds. Confirm `LEASE_TTL_S` defaults to 180 (matching viewer.html `STALE_S`)
and the mirror comments are present at both sites.

### Sprint-close (G7) smoke — container rebuild

Per the G7 pass-condition row: rebuild the throwaway container, `curl /healthz` (→ `{"ok":true}`) and
`GET /api/reviews` (→ `200`, list renders). **No product page was touched** (the only viewer edit is a
code comment), so no `scripts/render-smoke.sh` per-page DOM assertion or screenshot is owed — state
this explicitly in the close review so the sprint is not flagged non-compliant for lacking a render
that the row does not require.

## Assumptions and open questions

The design of record is the RFC (mdreview `22c9555b3e`) and the critic-gated chunking brief
(`requirements/agent-watcher.md`, two staff-critic rounds, GO), so the **product forks are settled**
(build the daemon: yes; trust model: C2 fail-closed base + C3 arming; launch mechanism: generic
template, decided at C2). What remains are **implementation** clarifications for C1, each with a safe
default. **None is a BLOCKER-FOR-HUMAN** — every fork has a default that does not waste a sprint.

- **Q1 (load-bearing) — Is `/wait` collection-level (`/api/reviews/wait`) or per-review
  (`/api/reviews/{id}/wait`)?** Assumption: **collection-level**, `GET /api/reviews/wait?turn=agent`,
  returning the changed matching review(s). Justification: the watcher waits across *its fleet* for
  *any* review to flip to `turn==agent` (the requirement frames `/wait` as the long-poll replacement
  for busy-polling `GET /api/reviews`, i.e. the queue), not one known id; a per-review wait would force
  the watcher to busy-poll the list to discover *which* id to wait on, defeating the purpose. The
  collection form also matches the thundering-herd design (one notify, every fleet-waiter re-checks).
  Load-bearing because it sets the route shape and the predicate; the safe default is the
  collection form. (A per-review `/wait` could be added later as a refinement without breaking the
  collection one.)
- **Q2 (minor) — Are the `/wait` server timeout and `LEASE_TTL_S` env-overridable, and what are the
  defaults?** Assumption: **yes, both env-overridable with sane defaults** — `/wait` default ≈ **25s**
  (bounded under typical 60s proxy read timeouts; the client also passes a `?timeout=` capped to the
  server max), `LEASE_TTL_S` default **180** (mirrors viewer `STALE_S`). Justification: the smokes need
  short values to run fast (a 180s TTL or 25s wait would make the curl tests slow), and an env override
  is the stdlib-idiomatic, dependency-free way (matches `MDREVIEW_DATA`/`PORT` at app.py:41-42). Safe
  default; the production defaults are the 25s/180s above.
- **Q3 (minor) — Should the server be the single authority for staleness (a `/config` endpoint the
  viewer reads), rather than a mirrored constant?** Assumption: **no — keep the documented mirror**
  (`LEASE_TTL_S` ↔ `STALE_S`, cross-referenced comments), no new endpoint. Justification: the baton
  epic deliberately made staleness viewer-computed and added no scheduler/config surface (footgun #1,
  no new dependency); a `/config` endpoint is scope the requirement does not ask for. The mirror is
  the right weight for two 180s constants that change rarely. If a reviewer wants server-authoritative
  staleness, it is a small follow-up ticket, not a C1 blocker.
- **Q4 (RESOLVED at G1 — `?since=` is REQUIRED, not deferred) — `/wait` change detection: edge vs
  level.** Resolution (folding the G1 critic's F1): `/wait` matches an **edge**, gated on a **required**
  `?since=<cursor>` compared against `turn_updated`, returning only reviews whose `turn_updated >
  since`. The earlier "return immediately if any matching review already satisfies the predicate" is
  **wrong** — `turn` is a level that stays `agent` for the whole time an agent works, so an on-entry
  level check returns instantly on every steady-state poll and busy-loops. A missing `since` defaults
  to `now` (block for the next flip), the safer degrade; `since=0` is the explicit "give me the
  backlog" opt-in. This is now specified in the `/wait` wiring above and is part of MR-054's acceptance
  criteria and validation (F2's steady-state assertion). Not deferrable: without it the C1 deliverable
  does not deliver and C2 inherits a busy-loop with a level-trigger to paper over.

No load-bearing fork lacks a safe default; there is **no BLOCKER-FOR-HUMAN**.

## Review resolutions

Independent G1 staff-critic review `reviews/agent-watcher-plan-review-2026-06-24.md` (verdict
**PASS-WITH-NITS**). Dispositions, all folded into MR-054 (author-applied; G1 stays the critic's call):

- **2026-06-24 — F1 (`/wait` matches a LEVEL not an EDGE; make `?since=` required).** Accepted. The
  `/wait` wiring now specifies a **required** `?since=<cursor>` compared against the existing
  `turn_updated` (app.py:542/549/556, surfaced on `/status` at app.py:515): the endpoint returns only
  reviews whose `turn_updated > since` and blocks otherwise, so a review already parked at `turn==agent`
  while its agent works no longer returns instantly on every poll. Missing `since` defaults to `now`
  (block for the next flip) — the safer degrade — with `since=0` the explicit backlog opt-in. Changed:
  the `/wait` wiring section (new `?since=` bullet + reworked bounded-timeout bullet), the MR-054
  Phase-1 summary, the key-constraints route note, Q4 (now RESOLVED, no longer "deferred otherwise"),
  the ticket-table title, and a new risks row. **This changes MR-054's acceptance criteria** (the
  cursor is now contract, not a nicety).
- **2026-06-24 — F2 (validation must exercise steady-state, not just single-flip-from-clean).**
  Accepted. Added MR-054 validation step **#4**: a review already at `turn==agent`, polled with
  `since` at-or-after its `turn_updated`, must return a clean `timeout:true` empty list (not an instant
  hit). The curl smokes #2/#3 now pass an explicit `since` cursor and #3 asserts the returned
  `turn_updated`; the pass criteria call out #4 as the assertion that distinguishes the edge trigger
  from the level bug. The lock-release self-check now passes an explicit `since` too.
- **2026-06-24 — WC-1 (parked-thread cost of the held `/wait`).** Accepted as a note, not a build. The
  `ThreadingHTTPServer` bullet no longer calls the held `/wait` cost-free: it states the unbounded
  parked-thread / cheap-DoS cost honestly, accepts it for the trusted/single-operator case (consistent
  with the requirement's trust model), and flags a ~3-line in-flight-waiter ceiling (`503` past `N`) as
  an optional mitigation if it ever matters — no new ticket. A matching risks row was added.
- **2026-06-24 — N-1 / N-2 (nits: `summary()` cite, RFC id typo).** Verified against the working tree:
  the plan body already cites `summary()` consistently as **app.py:127-149** (the stale `127-142` and
  the `22c9525b3e` RFC id lived in the review/brief, not the plan). The RFC id reads `22c9555b3e` at
  both occurrences (lines 26, 496). No plan-body change was needed; recorded here for the trail.
