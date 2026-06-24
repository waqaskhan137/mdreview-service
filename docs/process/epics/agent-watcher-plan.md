---
epic: agent-watcher
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-24
source: requirements/agent-watcher.md   # the verbatim 3-chunk decomposition brief
gate: passed 2026-06-24   # G1 (Plan Gate): PASS-WITH-NITS, findings folded; tickets unblocked
review: reviews/agent-watcher-plan-review-2026-06-24.md   # independent G1 review (PASS-WITH-NITS); resolutions folded below
related_sprints: [sprint-17, sprint-18]    # C1 -> sprint-17; C2 -> sprint-18; C3 -> later sprint
related_tickets: [MR-054, MR-055, MR-056, MR-057]    # C1: MR-054/MR-055 (sprint-17); C2: MR-056/MR-057 (sprint-18)
c2_detailed: 2026-06-24   # C2 expanded to full implementable depth (this revision); C2 tickets proposed below as MR-056/MR-057 placeholders. C3 still chunk-summary level. A focused C2 critique follows.
---

# Agent Watcher Plan

This epic adds the **automation on top of the handoff baton**: a local `watch.py` that notices a
review whose `turn == agent`, claims the cooperative lease, and launches an agent session — so a
human's **"Send to agent"** reaches a session with **no human in the loop**. It builds directly on
the shipped `agent-handoff-baton` epic (PR #17): `turn` + `POST /handoff` + the `agent_status` lease
already exist. The watcher needs three things the broker does not yet provide, plus a non-containerized
launcher and its safety model. This plan decomposes the work into **three dependency-ordered chunks
(C1 → C2 → C3)**, each shipped as its own sprint under this one epic plan — mirroring how
`agent-handoff-baton` cleared G1 once and shipped three sprints. **C1 and C2 are now planned in full
implementable detail here** (C2 was expanded on 2026-06-24, after C1 shipped, against the real shipped
C1 contract in `app.py` — see the "C2 — Watcher core (full plan)" section below); **C3 remains at the
chunk-summary level** (scope + dependency + what defers to it) and will be decomposed into tickets at
the start of its own cycle. A focused, independent C2 critique follows this expansion (the plan author
expands; the critic remains independent, preserving G1's separation).

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
for), and spend is bounded (the watcher is never an unbounded spawner: C2 caps the normal-load spend
and is fail-safe on a child crash — a crashed child strands its baton rather than relaunching; C3 adds
the per-review convergence guard for the relaunch paths it introduces).

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
itself, its trust model, and its caps are C2/C3. **C2 is now planned in full below; C3 stays
chunk-summary.**

## C2 — Watcher core (full plan)

**Status:** expanded to implementable depth 2026-06-24, against the **shipped** C1 contract in `app.py`
(read from the working tree, not the plan's pre-image). C1 (MR-054 `/wait` + `?turn=` filter, MR-055
stale-takeover) is merged; this is what C2 consumes. C2 introduces `watch.py` — the first piece of this
epic that is **code outside the service container** and the first **credentialed process spawner**, so
its security crux (the fail-closed trusted-base check) is the load-bearing part, not the loop plumbing.

### What C2 consumes from C1 (the contract, pinned to shipped code)

`watch.py` is a pure HTTP client of three already-shipped surfaces. Pinned to the real code so the C2
implementer does not re-derive them:

| C1 surface | Shipped at | Shape C2 depends on |
|---|---|---|
| `GET /api/reviews/wait?turn=agent&since=<cursor>` | `_wait`, app.py:419-458; routed app.py:515-516 | Hit ⇒ `200 {"reviews":[<full summary rows>]}`; timeout ⇒ `200 {"reviews":[],"timeout":true}`. Edge-triggered: returns only rows whose `turn_updated > since`. `?timeout=` is capped to `WAIT_TIMEOUT_S` (app.py:439-440). |
| Returned/`?turn=` row fields | `summary()` app.py:147; filter app.py:501-509 | Each row carries `id`, `turn` (defaulted to `"reviewer"` for legacy), and `turn_updated`. The cursor C2 advances is `turn_updated`. |
| `GET /api/reviews/{id}/status` | app.py:581-596 | `turn`, `turn_updated`, `agent_status` (`{state,owner,at,message}` or `null`). Used to seed the initial cursor. |
| `POST /api/reviews/{id}/handoff {state:"working", owner}` | app.py:635-662 | Lease claim: `200 meta` on grant (unset/equal/stale-takeover), **`409 {"error":"lease held","owner":...}`** on foreign-live or stale-but-reclaimed. This is the claim-before-spawn primitive. |

**No new server primitive is required by C2.** The loop is built entirely on these. If, during
implementation, a genuinely missing server primitive surfaces (e.g. `/wait` cannot express the
watcher's needed predicate), that is a **blocker to flag**, not a thing to bury in `watch.py` — but the
expansion below found none: the claim-before-spawn and edge long-poll are exactly the shape C1 shipped.

### Core design principle (C2)

**`watch.py` is a fail-closed, single-flight, bounded launcher — it spends money only when it can prove
the base is trusted, only once per flip, and only within hard caps.** Three properties, each a real
control and not a caption:

1. **Fail-closed trusted-base** — refuse to start (exit non-zero) unless `MDREVIEW_BASE` is provably
   trusted. This is C2's security crux; C3 *relaxes* it via arming, C2 must **not** ship the relaxation.
2. **Claim-before-spawn (single-flight)** — never spawn without first winning the `/handoff` lease
   (`200`). A `409` ⇒ another owner already has it ⇒ skip. This is what stops a cold start or two ticks
   from double-spawning the same review.
3. **Caps bound spend** — a concurrency cap and a global launches/hour cap, on from day one, bounding
   the **normal** spend (many distinct reviews flipped to agent). They are a cheap backstop; note they do
   **not** bound a crash-loop, because a crashed child *strands* the baton rather than looping (the
   edge-triggered loop under-spawns on crash — see the crash model in Step 4), so there is no relaunch
   storm for them to bound.

### `watch.py` — file shape and conventions

A new file `watch.py` at the repo root, **sibling to `mcp_server.py`**, sharing its conventions:

- **Stdlib only** (footgun #1): `urllib.request`/`urllib.error` (HTTP), `subprocess` (spawn),
  `threading` (long-poll loop + reaping children), `os`/`json`/`time`/`sys`. No pip, nothing vendored.
- **`MDREVIEW_BASE`** read the same way as mcp_server.py:35 — `os.environ.get("MDREVIEW_BASE",
  "http://localhost:8137").rstrip("/")`. Reuse the same default so the watcher and the MCP wrapper agree.
- **Off by default — must be explicitly run.** It is not imported by `app.py`, not in the Dockerfile,
  not started by compose. `python3 watch.py` is the only way it runs (mirrors
  `MDREVIEW_BASE=… python3 mcp_server.py`, README "MCP server" section).
- **Not containerized** (epic non-goal, requirement line 84): the `Dockerfile` is untouched. `watch.py`
  runs where the operator's agent runs, reading local creds and spawning local sessions, exactly like
  `mcp_server.py`.
- **HTTP helper:** a small `_http(method, path, body=None)` like mcp_server.py:376-389, but C2 needs to
  **inspect the status code** (200 vs 409), so it must **not** raise-on-409 the way mcp_server.py's
  `http()` does (that helper raises `ToolError` on any `HTTPError`). `urllib.error.HTTPError` carries
  `.code` and is itself a response object; the watcher catches it and returns `(status, body)` so the
  claim step can branch on `409` rather than treat it as a failure. **Pin this:** a `409` from
  `/handoff {state:working}` is an expected, normal "skip this review" signal, not an error to retry.

### The loop (pinned, step by step)

#### Step 0 — Fail-closed trusted-base check FIRST (the security crux)

Runs **before any network call, before the loop, before reading any review**. If it fails, `watch.py`
prints a one-line reason to stderr and **exits non-zero** (it does not warn-and-continue).

**Exact comparison (pin this verbatim, it is the control):**

```
base   = MDREVIEW_BASE (already rstrip("/"))
host   = urllib.parse.urlparse(base).hostname   # "localhost", "127.0.0.1", "10.0.0.5", ...
trust  = os.environ.get("WATCH_TRUSTED_BASE")   # operator's explicit vouch; may be None

if trust is None or trust == "":
    # default-allow LOOPBACK ONLY
    allowed = host in ("localhost", "127.0.0.1", "::1")
else:
    # explicit vouch: EXACT string match of the configured base. No wildcard, no prefix.
    allowed = (trust.rstrip("/") == base)

if not allowed:
    refuse-and-exit (non-zero), naming base + why.
```

- **`WATCH_TRUSTED_BASE` is an exact-match of the full base string** (after the same `.rstrip("/")`
  normalization applied to `MDREVIEW_BASE`), **not** a host match, **not** a wildcard, **not** a prefix.
  A typo'd or mismatched value ⇒ `allowed=False` ⇒ **refuse**, never "allow because it looks close."
  This is the fail-closed property: the operator must assert the *specific* base they vouch for, and a
  mistake fails toward refusal.
- **The refusal message MUST name BOTH the actual `MDREVIEW_BASE` and the `WATCH_TRUSTED_BASE` it
  compared against (WC-1).** The exact-match is deliberately strict (`http`/`https`, `host`/`host:port`,
  `localhost`/`127.0.0.1` are distinct), so a brittle mismatch (`mdreview.example.com` vs
  `https://mdreview.example.com`, or a `:443`-vs-bare difference) is the expected operator paper-cut.
  Printing both strings makes the strict mismatch **self-explaining** ("refusing: MDREVIEW_BASE=<x> does
  not match WATCH_TRUSTED_BASE=<y>") so the operator fixes their env in one read. **Do not relax the
  match to fix the message** — the strictness *is* the control; the fix is a better message, not a
  looser comparand. Pin "the refusal names both strings" in MR-056.
- **Unset ⇒ loopback only.** `localhost`/`127.0.0.1`/`::1`. (Include `::1` because `urlparse` of an
  IPv6 loopback base yields `::1`; the requirement names loopback, and `::1` is loopback. State it.)
- **Why this is the control, not a caption:** `watch.py` is a credentialed spawner. Pointed at a
  public, no-auth base, *any* URL-holder pressing "Send to agent" would trigger a launch on the
  operator's machine with the operator's creds. The base check is what makes "trusted-base only" a real
  boundary. **C3 relaxes this** (operator arming lets specific reviews auto-run against a non-trusted
  base); **C2 must ship the refusal, never the relaxation.** Stated as a non-goal below.
- **Assertable:** the C2 test points the watcher at a non-loopback base with no `WATCH_TRUSTED_BASE`
  (refuse), and at a base that mismatches a set `WATCH_TRUSTED_BASE` (refuse) — both assert a non-zero
  exit. This is the explicit fail-closed test the requirement demands.

#### Step 1 — Seed the cursor

Before the first `/wait`, read an initial `since` cursor so no flip is missed and the existing backlog
is not blindly re-spawned:

- **Default seed = `now` (`time.time()`)** — the watcher starts watching for the *next* flip, matching
  `/wait`'s own missing-`since` default (app.py:437-438). This is the safe default: a fresh watcher
  does **not** stampede every review already parked at `turn==agent` (those agents may already be
  working, or were handed off while no watcher existed and are intentionally parked).
- **Optional backlog opt-in (`since=0`)** via an env/flag (e.g. `WATCH_SINCE=0` or `--backlog`): the
  operator explicitly asks the watcher to pick up the existing agent-turn backlog on start. Off by
  default. Pin: cold-start backlog is **opt-in**, never the default, because claim-before-spawn (Step 3)
  still single-flights it — but spawning N sessions on startup is a spend surprise the operator should
  ask for.
- The seed reads from `GET /api/reviews?turn=agent` (max `turn_updated` seen) only if backlog mode
  wants "everything strictly newer than the current max"; for the default `now` seed no pre-read is
  needed. Keep it simple: **default = `now`, no pre-read; backlog = `0`.**

#### Step 2 — Long-poll `/wait` and advance the cursor

```
while True:
    resp = GET /api/reviews/wait?turn=agent&since=<cursor>&timeout=<WAIT_TIMEOUT_S>
    if resp is timeout ({"reviews":[],"timeout":true}):  re-poll (cursor unchanged)
    else:
        rows = resp["reviews"]                      # each newly flipped to agent since <cursor>
        cursor = max(cursor, max(r["turn_updated"] for r in rows))   # advance past everything seen
        for r in rows:  handle(r)                    # claim-before-spawn, Step 3
```

- **Cursor seeding/advance pinned so a flip is never missed and never double-processed:** advance the
  cursor to the **max `turn_updated` of the returned rows** (the same value the row carries; the server
  guarantees returned rows have `turn_updated > since`). Passing that max as the next `since` means an
  edge already seen never re-returns (server contract, app.py:443-445), and because the server matches
  `> since` strictly, the next poll sees only strictly-newer flips. On a **timeout** the cursor is
  **unchanged** and re-issued, so no edge is lost across the re-issue boundary (a flip that lands during
  the gap between two `/wait` calls still has `turn_updated > cursor` on the next call).
- **On a `urllib`/network error** (service restart, transient): catch, log, **back off** a couple of
  seconds, and re-poll with the **same cursor** (do not advance). The cursor is the watcher's only
  durable position; never advance it on a failed call.
- **`WAIT_TIMEOUT_S` client value:** the watcher passes a `?timeout=` (e.g. its own
  `WATCH_WAIT_TIMEOUT_S`, default matching the server's 25s); the server caps it to `WAIT_TIMEOUT_S`
  (app.py:440) regardless, so a too-large client value is harmless.

#### Step 3 — Claim-before-spawn (single-flight; protects the wallet)

For each returned agent-turn review `r`:

```
1. enforce caps FIRST (Step 5): if at concurrency cap or hourly cap -> skip r (do NOT claim), log.
2. POST /handoff {state:"working", owner:<watcher-id>}  to r["id"]
3. if status == 200:  spawn the child (Step 4).
   if status == 409:  another owner holds (or it was reclaimed) -> SKIP, do not spawn. (normal, not an error)
   else (4xx/5xx):    log, skip; do not spawn.
```

- **Spawn ONLY on `200`.** The `/handoff {state:working}` claim is the atomic single-flight gate
  (app.py:635-662): the server grants exactly one owner under `_lock`. Two watcher ticks racing the same
  flip, or a cold-start backlog overlapping a steady poll, both resolve here — the second gets `409`
  and skips. **This is what stops double-spawn**, and it is why the claim must precede the spawn, never
  follow it.
- **Watcher-id derivation (stable per watcher process):** `owner = "watch-" + <stable id>`. Pin the id
  as **`WATCH_OWNER` env if set, else a per-process value derived once at startup** —
  `"watch-%s-%d" % (socket.gethostname(), os.getpid())` (or a `uuid4` hex captured once). It must be
  **stable for the life of the process** (so the same watcher renewing or re-claiming uses the same
  owner and hits the unset/equal-owner grant path, not a foreign-owner `409` against itself) and
  **distinct across watcher processes** (so two watchers are genuinely different owners). `socket` and
  `uuid` are stdlib. Pin: compute once at startup, store in a module/global, never re-derive per claim.
- **Watcher-id changes on restart (WC-5) — a restarted watcher does NOT own its predecessor's leases.**
  Because the default id is pid-derived (`getpid()`), a watcher **restart** produces a *new* owner. A
  still-live child from the previous run is renewing under the **old** `MDREVIEW_OWNER`, which is now a
  *foreign* owner to the new watcher — so the new watcher will `409` and **skip** any review that
  child still actively holds (correct: it does not double-spawn a live in-flight child). The new watcher
  must **not** assume it owns leases its predecessor granted; recovery rides the child's own
  `MDREVIEW_OWNER` renewal plus the **MR-055 stale-takeover** (it can reclaim only once that lease goes
  stale), exactly the C1 primitive. State this in MR-056 so the restart case is not a surprise — it is
  why pid-derived owner derivation is correct, not a bug. (A set `WATCH_OWNER` would persist across
  restart and let a new watcher renew its predecessor's leases; that is the operator's choice, not the
  default.)
- **Caps are checked before the claim** (Step 1 of the pseudo above), so the watcher does not claim a
  lease it then cannot spawn into (which would strand the baton at a claimed-but-unspawned review until
  the lease goes stale). Check caps, then claim, then spawn.
- **Cap-skip must NOT busy-spin `/wait` (WC-3).** A naive "when at cap, don't advance the cursor so
  `/wait` re-returns the skipped row" **busy-loops**: the next `/wait` with the un-advanced cursor
  returns the *same* edge instantly (it is still `> since`), the watcher re-checks the cap, skips, and
  re-polls — each iteration re-running the server's O(all-reviews) `list_reviews()` scan (app.py:448).
  That is a CPU/disk spin, not a spend bug, but it defeats the long-poll exactly while the watcher is
  busiest. **Default avoidance (pin in MR-056): advance the cursor past the skipped row and track the
  skipped review ids in an in-process *pending set*, draining it as concurrency slots free** (re-attempt
  the claim on a bounded timer / when a child is reaped) — do **not** rely on `/wait` to re-surface a
  level it already emitted (it won't, unless a newer edge lands). The acceptable alternative is a
  **bounded backoff sleep** before re-polling while at cap; pick the pending-set as the default and name
  the backoff as the fallback. State the chosen mechanism in MR-056.

#### Step 4 — Spawn the launch command with the child env contract

On a `200` grant, spawn the configured launch command as a subprocess, with this **child env contract**
layered onto a copy of the watcher's own `os.environ`:

| Env var | Value | Why the child needs it |
|---|---|---|
| `REVIEW_ID` | `r["id"]` | which review to work |
| `MDREVIEW_BASE` | the watcher's base | the child talks to the same service |
| `MDREVIEW_OWNER` | the watcher's `owner` (the one that won the lease) | **so the child renews the SAME lease** via `ping_working(owner=…)` — the lease the watcher claimed, not a fresh one |

- **Pin the owner hand-off:** the child must `ping_working`/`hand_back` as the **same `owner`** the
  watcher used to claim (Step 3), or its first `ping_working` would be a *foreign* owner against a
  *fresh* lease and `409` (app.py:652 grants only unset/equal/stale). So the watcher passes its `owner`
  to the child via `MDREVIEW_OWNER`, and the launch command/agent contract reads it. (The exact env name
  the real Claude agent reads is a launch-template detail; the watcher's job is to **export the owner**;
  Step "lease renewal" below pins who renews.)

##### Launch mechanism = a GENERIC command template, default Claude (the resolved fork)

Per the requirement's forks table ("Launch mechanism … Decided at C2 planning. Recommendation: a
generic command template, default = Claude"), **resolved here as: a generic, operator-configured
command template; the watcher only knows "run this command with this env."** Pinned:

- **The watcher does not hard-code `claude -p`.** It reads a launch command from configuration:
  **`WATCH_LAUNCH_CMD`** (an env var). **The JSON-array form is preferred** — e.g.
  `WATCH_LAUNCH_CMD='["claude","-p","..."]'`, parsed with `json.loads` into an argv list. **If the
  template is given as a plain string instead, it is parsed with `shlex.split` into an argv list and
  spawned WITHOUT a shell** — `subprocess.Popen`/`run` with the argv list, **never `shell=True`** (WC-2).
  The `shlex.split` result must never reach a shell; it goes straight to the argv of a no-shell spawn.
  Make this explicit in MR-057 so an implementer does not "helpfully" add `shell=True` for the
  string-form convenience. The review id and base reach the command via the **child env**
  (`REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER`) above, so the template needs no placeholder
  interpolation — env is the interface. (A placeholder form like `{review_id}` may be supported as a
  convenience, gated to the server-generated `[0-9a-f]` id only, but env is the contract; pin
  env-as-interface so the template stays injection-free and simple.)
- **Default (when `WATCH_LAUNCH_CMD` is unset):** a Claude headless invocation. Pin the default as a
  named constant (e.g. `DEFAULT_LAUNCH_CMD`) the implementer fills with the operator's intended
  `claude` headless form; the watcher reads `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` from env. **The
  watcher's contract is "run this command with this env," nothing Claude-specific lives in the loop.**
- **Why generic:** this is exactly what lets the **C2 test use a stub** launch command — a tiny script
  that `ping_working`s then `hand_back`s — instead of a real model. The test sets
  `WATCH_LAUNCH_CMD=<stub>` and the watcher runs it identically to how it would run Claude.
- **Spawn mechanics:** `subprocess.Popen(cmd, env=child_env)` (non-blocking — the watcher does not
  `wait()` synchronously, or one long agent session would stall the poll loop). The watcher keeps the
  `Popen` handle in its in-flight set (for the concurrency cap + reaping, Step 5). Do **not** use
  `shell=True` with an interpolated id (injection); pass an argv list.

#### Lease renewal / lifecycle (pinned)

- **The CHILD renews the lease, not the watcher.** The child receives `MDREVIEW_OWNER` and is the thing
  doing the work, so the child `ping_working(owner=…)`s periodically (the agent contract shipped in
  MR-053 already has the child do this). The watcher's claim in Step 3 is the *initial* lease grab; the
  child keeps it warm. **Rationale:** the watcher should not have to track per-child heartbeat timers,
  and the child already owns the ping loop per the baton contract. Pin this division explicitly so it is
  not ambiguous: **watcher claims once; child renews.**
- **If the child never starts pinging / dies immediately**, the lease the watcher grabbed goes stale
  after `LEASE_TTL_S` (180s, MR-055). That stale lease lets a later **claim** reclaim it — but see the
  crash model below: under the default `now` seed nothing re-claims it automatically, because the
  edge-triggered `/wait` never re-surfaces a review whose `turn_updated` did not change. The stale-TTL
  is what lets the **human** (or a `--backlog`/restart watcher) re-claim it; it is not an auto-relaunch.

- **When the child exits:** the watcher **reaps** it (removes it from the in-flight set so the
  concurrency cap frees a slot) and **logs** the exit code. It does **not** re-flip the baton or
  re-claim: the baton returns to the human through the **child's own `hand_back`** (the child calls
  `hand_back(state="done"|"blocked")` per its contract). Pin: **watcher reaps + logs on child exit; it
  does not hand back and does not relaunch in-tick.**

- **Crash model — a child that exits BEFORE `hand_back` STRANDS the baton; the watcher does NOT
  auto-relaunch it (verified against the shipped code).** This is the most important lifecycle fact and
  the plan's earlier text had it backwards. `turn_updated` is bumped **only** on a real reviewer→agent
  flip (app.py:629-634); the `{state:working}` lease arm explicitly does **not** bump it (app.py:635-636,
  comment "turn_updated is NOT bumped (no flip)"). So when a child crashes/exits without `hand_back`:
  - The review stays at `turn==agent` with its `agent_status` lease intact but going stale, and
    `turn_updated` **unchanged**.
  - The watcher advanced its cursor past that flip's `turn_updated` when it first claimed (Step 2). The
    edge-triggered `/wait?turn=agent&since=<cursor>` returns only rows with `turn_updated > since`
    (app.py:445), so this review — `turn_updated <= cursor` — **never re-returns**. There is **no
    auto-relaunch**. The failure mode is a **stranded baton (under-spawn)**, not a relaunch storm.
  - **What recovers it:** the human sees the viewer's working banner go stale at `LEASE_TTL_S` (180s,
    MR-055 / viewer `STALE_S`) — *"Agent may have stopped"* — and either reclaims the turn or re-Sends.
    A human **re-Send** is a fresh reviewer→agent flip, so `turn_updated` bumps and the watcher picks it
    up cleanly on the next `/wait`. A **watcher restart** or an explicit **`--backlog`/`since=0`** seed
    also re-surfaces it (those re-read the agent-turn backlog by `turn_updated > 0`).
  - **C2 has no crash-retry, by design** (stated as a non-goal). Liveness on a crash depends on the
    human (or, later, C3). The watcher does not need to manage per-child heartbeat timers or relaunch
    logic; the stranded review self-heals only via a human action or a deliberate backlog re-seed.

#### Step 5 — Minimal caps from day one (bound the normal-load spend; fail-safe on crash)

Two caps, on by default, enforced **before the claim** (Step 3):

- **Concurrency cap — `WATCH_MAX_CONCURRENT` (default `3`):** max simultaneous live children. The
  watcher tracks its in-flight `Popen` set; reaping (Step 4 lifecycle) frees slots. At the cap, a
  returned agent-turn review must be **skipped this tick** without claiming it — but the cursor handling
  of that skip is subtle (see WC-3 / the cursor-stall avoidance below): a naive "don't advance the
  cursor so `/wait` re-returns it" busy-spins `/wait`. Pin: a cap-skip leaves the review claimable later
  (do not claim-then-fail-to-spawn), via the pending-set retry-on-timer mechanism specified in MR-056,
  **not** by re-spinning `/wait` on an un-advanced cursor.
- **Global launches/hour cap — `WATCH_MAX_LAUNCHES_PER_HOUR` (default `30`):** a rolling-window count of
  spawns in the last 3600s (a `collections.deque` of spawn timestamps, evicting entries older than an
  hour). At the cap, **skip** (do not claim/spawn) and log; the window drains over time.
- **What the caps actually bound (corrected — they do NOT bound a crash-loop).** The caps bound spend
  in the **normal** case: many *distinct* reviews flipped to agent (a busy queue), where each flip is a
  real spawn the operator pays for. They are a cheap backstop and stay on from day one. **They do not
  bound a "crash-loop," because under C2's pure edge-triggered design a crashed child does not loop — it
  strands the baton (under-spawn; see the crash model in Step 4).** The only path where a stranded
  review is re-claimed-and-re-spawned repeatedly is a **watcher restart / `--backlog` re-seed loop**
  (each cold start re-reads the agent-turn backlog by `turn_updated > 0`); there the hourly cap *is* the
  bound, and it is bounded by **restart frequency**, not by a per-review crash loop. Do not state "the
  global cap bounds a crash-loop's total spend" — that asserts a property the edge loop cannot produce.
- **Per-review attempt cap / relaunch-convergence guard is explicitly C3 — and addresses the case where
  relaunches DO happen.** C3's per-review attempt cap matters only once the watcher *re-surfaces*
  stranded reviews (e.g. if C3 or a future change adds a re-trigger so a crashed child auto-relaunches).
  Under C2's pure edge-triggered design a crash **strands rather than loops**, so C2 needs no per-review
  cap and has **no crash-retry at all** (non-goal). State this so C3 planning inherits the correct model:
  the convergence guard guards a relaunch loop C2 deliberately does not create.
- **Defaults are conservative** (`3` concurrent, `30`/hour) and **env-overridable** (stdlib-idiomatic,
  matching `MDREVIEW_*` config).

### Ticket split (C2)

Two tickets, split along the requirement's natural seam (the safe-loop core vs. the credentialed
spawner + caps), both `layer: svc` (precedent: MR-053 tagged `mcp_server.py` as `svc` — a stdlib
sibling client is `svc`; no new layer is invented). The docs portion rides the second ticket as
`docs`-in-same-change (Definition-of-Done convention: docs in the same change or a same-sprint
docs-sweep):

- **MR-056 — `watch.py` fail-closed loop core (trusted-base + long-poll + claim-before-spawn).** The
  file, the **Step 0 fail-closed trusted-base check** (the security crux) — including the **refusal
  message that names BOTH `MDREVIEW_BASE` and `WATCH_TRUSTED_BASE` (WC-1)** so the strict exact-match is
  self-explaining — the HTTP helper that branches on `409`, cursor seeding (`now` default, `0` backlog
  opt-in), the `/wait` long-poll + cursor advance (Step 2) **with the cap-skip cursor-stall avoidance
  (WC-3): advance the cursor + a pending-set drained as slots free, NOT an un-advanced cursor that
  busy-spins `/wait`**, and **claim-before-spawn through the `200`/`409` branch (Step 3) with the
  watcher-id derivation — including the WC-5 note that the pid-derived owner changes on restart, so a
  restarted watcher does NOT own its predecessor's leases (it relies on the child's `MDREVIEW_OWNER` +
  the MR-055 stale-takeover)** — but spawning a **no-op/echo** placeholder (or `WATCH_LAUNCH_CMD` to a
  trivial command) so the claim/skip logic is testable without the real launcher wiring. This ticket
  owns the double-spawn-prevention proof and the fail-closed refusal proof. No `app.py` change.
- **MR-057 — `watch.py` spawn + child contract + caps (generic launch template, default Claude) +
  runbook stub.** The generic `WATCH_LAUNCH_CMD` template (default Claude) and `subprocess.Popen` spawn
  (Step 4) — **the JSON-array form preferred and the string form parsed with `shlex.split` into an argv
  list spawned WITHOUT a shell (never `shell=True`) (WC-2)** — the **child env contract**
  (`REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER`), the lease-renewal division (child renews; watcher
  reaps+logs on exit), the **corrected crash model (a child that exits before `hand_back` strands the
  baton; no auto-relaunch under the default seed — B1)**, and **both caps** (Step 5, bounding the
  normal-load spend, NOT a crash-loop). Validation carries the **crash-stub test (WC-4)** that measures
  the real stranded-baton behavior. Plus the **runbook stub** (`docs`, in-same-change): enough README
  (and a CLAUDE.md pointer) for an operator to run the **trusted-base mode** — how to start `watch.py`,
  the `MDREVIEW_BASE`/`WATCH_TRUSTED_BASE`/`WATCH_LAUNCH_CMD`/cap env vars, and the fail-closed behavior.
  **The full arming/untrusted-base runbook is C3**; C2 owes only the trusted-base runbook. No `app.py`
  change.

**Dependency:** MR-057 `depends_on: [MR-056]` (it spawns into the loop MR-056 builds). The C2 sprint =
`{MR-056, MR-057}`. **Layer note:** both `svc` (the `watch.py` file); MR-057 also carries `docs` for the
runbook stub in the same change. **No `app.py` change in either** — C1 already shipped the server side;
the expansion confirmed no missing server primitive (if implementation reveals one, flag it as a
blocker per the requirement, do not bury it in `watch.py`).

### Validation (C2) — `py_compile` + a stub-launch end-to-end against a localhost throwaway

The repo gate is `python3 -m py_compile` (no test framework); each ticket owes one runnable self-check.
All runs use a **localhost throwaway** mdreview container on a scratch port (e.g. 8155) — never the live
8139 instance, never `docker compose up` (8137). The launch command is a **STUB** (a tiny local script
that claims/renews via `ping_working` and then `hand_back`s — no real model).

**The stub launch command** (the test fixture — author it as part of the C2 sprint, not shipped product;
a `~/scratch`/tmp script, referenced by `WATCH_LAUNCH_CMD`):

```bash
#!/usr/bin/env bash
# stub agent: reads the child env contract, renews the SAME lease, then hands back. No model.
set -euo pipefail
curl -s -X POST "$MDREVIEW_BASE/api/reviews/$REVIEW_ID/handoff" \
  -H 'Content-Type: application/json' \
  -d "{\"state\":\"working\",\"owner\":\"$MDREVIEW_OWNER\"}" >/dev/null   # renew the watcher's lease (same owner -> 200)
sleep 1
curl -s -X POST "$MDREVIEW_BASE/api/reviews/$REVIEW_ID/handoff" \
  -H 'Content-Type: application/json' \
  -d "{\"to\":\"reviewer\",\"state\":\"done\",\"owner\":\"$MDREVIEW_OWNER\",\"message\":\"stub done\"}" >/dev/null  # hand back
```

**The crash stub** (the WC-4 fixture — the test that would have caught B1; also a `~/scratch`/tmp
script referenced by `WATCH_LAUNCH_CMD`). It renews the lease, writes a launch marker so spawns can be
counted, then **exits WITHOUT calling `hand_back`** — simulating a child that crashes before handing
back:

```bash
#!/usr/bin/env bash
# crash stub: claims/renews the SAME lease, marks the launch, then EXITS without hand_back. No model.
set -euo pipefail
echo "launch $REVIEW_ID $(date +%s)" >> "$WATCH_LAUNCH_MARKER"   # count spawns
curl -s -X POST "$MDREVIEW_BASE/api/reviews/$REVIEW_ID/handoff" \
  -H 'Content-Type: application/json' \
  -d "{\"state\":\"working\",\"owner\":\"$MDREVIEW_OWNER\"}" >/dev/null   # renew (same owner -> 200)
exit 1   # crash: no hand_back -> baton stays at turn==agent, turn_updated UNCHANGED
```

#### MR-056 validation (loop core + fail-closed)

Gate: `python3 -m py_compile watch.py`. Then, against a throwaway base `$B` (`http://localhost:8155`):

```bash
# A. FAIL-CLOSED: non-loopback base, no WATCH_TRUSTED_BASE -> refuse (non-zero exit), no poll.
MDREVIEW_BASE=http://10.0.0.5:8137 python3 watch.py ; echo "exit=$?"     # -> exit!=0, stderr names untrusted base
# B. FAIL-CLOSED: WATCH_TRUSTED_BASE set but MISMATCHES the base -> refuse (the typo case).
MDREVIEW_BASE=http://10.0.0.5:8137 WATCH_TRUSTED_BASE=http://10.0.0.6:8137 python3 watch.py ; echo "exit=$?"  # -> exit!=0
# C. TRUSTED: loopback default starts (then idles on /wait). Run it backgrounded for the live test below.
MDREVIEW_BASE=$B WATCH_LAUNCH_CMD="<stub>" python3 watch.py &   WPID=$!

# D. SINGLE-FLIGHT live test: create a review, flip the baton, assert the watcher claims + spawns the stub,
#    and the baton returns to the reviewer; assert a SECOND tick does NOT double-spawn.
ID=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"watch c2","markdown":"# x\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null
# poll status: turn flips agent -> (watcher claims, agent_status.owner == the watcher's owner) -> stub hand_back -> turn reviewer
#   assert: at some point agent_status.owner starts with "watch-"; finally turn=="reviewer" (stub handed back).
# double-spawn guard: a watcher whose lease is already claimed (or already handed back) must NOT spawn a 2nd stub
#   for the same flip — assert exactly ONE stub launched per flip (the stub writes a launch marker / count).
```

**Assert explicitly (the fail-closed refusal is a first-class test):** A and B exit non-zero (refuse to
start); C starts and idles; D shows exactly one claim → one stub spawn → baton back to reviewer, and a
re-poll/second tick produces **no second spawn** for the same flip (the `409` skip path). The
single-flight assertion (one launch per flip) is the double-spawn-prevention proof; the fail-closed exits
are the trusted-base proof.

#### MR-057 validation (spawn + child contract + caps)

Gate: `python3 -m py_compile watch.py`. Then, against `$B`:

```bash
# E. CHILD CONTRACT: the spawned stub renews the SAME lease (owner unchanged across the working ping)
#    and hands back. Assert agent_status.owner is the watcher's owner throughout (the stub's renew was a
#    same-owner 200, not a foreign 409), and final turn=="reviewer".
# F. CONCURRENCY CAP: set WATCH_MAX_CONCURRENT=1, use a SLOW stub (sleeps 5s before hand_back). Flip two
#    reviews to agent. Assert only ONE stub runs at a time; the second is claimed/spawned only after the
#    first child exits (or skipped-and-re-picked, per the cap-skip rule). Never two concurrent children.
# G. HOURLY CAP: set WATCH_MAX_LAUNCHES_PER_HOUR=2, flip three reviews. Assert exactly 2 spawns, the 3rd
#    skipped (logged), no claim on the 3rd. (Use a tiny window override if the deque window is env-tunable.)
# H. CRASH STUB (WC-4 — the test that catches B1): WATCH_LAUNCH_CMD=<crash stub>, default `now` seed.
#    Flip one review to agent. Assert: the watcher claims + spawns ONE crash stub (one launch marker);
#    the stub exits without hand_back; the review STAYS at turn=="agent" with turn_updated UNCHANGED;
#    and across the next several /wait cycles the watcher does NOT re-claim or re-spawn it (still ONE
#    launch marker) — proving B1's stranded-baton reality under the default seed (NO auto-relaunch).
# H2. CRASH STUB, backlog re-surface: restart the watcher with --backlog / WATCH_SINCE=0 (or just
#    re-run it cold with backlog on). Assert the stranded turn==agent review IS now re-claimed + the
#    crash stub spawns again (a SECOND launch marker) — proving the ONLY real relaunch path is the
#    backlog/restart re-seed, not an in-run crash loop.
```

**Assert:** E — the child renews the watcher's lease (same owner, no foreign-`409` self-collision) and
hands back; F — never more than `WATCH_MAX_CONCURRENT` live children; G — never more than
`WATCH_MAX_LAUNCHES_PER_HOUR` spawns in the window (the spend-bound proof); **H — a crash without
`hand_back` STRANDS the review at `turn==agent` (`turn_updated` unchanged) with NO auto-relaunch under
the default `now` seed (this is the test that would have caught B1); H2 — the stranded review is
re-claimed ONLY under a `--backlog`/restart re-seed**, confirming the corrected crash model rather than
the mis-stated "bounded relaunch."

**No `docker build` and no render-smoke for either C2 ticket** — `watch.py` is not containerized
(Dockerfile untouched, footgun #9 does not bite: no new *served* file) and there is no product page
(`viewer.html`/`dashboard.html`/`static/**`) touched, so per the G7 pass-condition row no per-page DOM
assertion or screenshot is owed. The C2 sprint-close still owes the throwaway-container rebuild +
`curl /healthz` + `GET /api/reviews` smoke (the server is unchanged, so this just confirms no
regression), plus the `py_compile watch.py` + the stub-launch end-to-end above.

### Docs the C2 chunk owes (scope, not written now)

- **README "Running the watcher" stub** (rides MR-057, `docs`-in-same-change): how to run `watch.py` in
  **trusted-base mode** — `MDREVIEW_BASE`, the loopback default, `WATCH_TRUSTED_BASE` exact-match vouch,
  `WATCH_LAUNCH_CMD` (generic template, default Claude), the cap env vars, and the fail-closed exit
  behavior. Placed near the existing "MCP server (optional)" section (README:122), since `watch.py` is
  the same class of optional sibling tool as `mcp_server.py`.
- **CLAUDE.md pointer** (rides MR-057): a short "Running the watcher" note under the existing "Running
  your own instance" / process area pointing at the README section, so an agent reading CLAUDE.md learns
  the watcher exists and that it is trusted-base-only in C2.
- **Explicitly deferred to C3:** the **full arming / untrusted-base runbook** (the operator allowlist
  file, running against a public base, the per-review attempt cap). C2's runbook covers only what an
  operator needs to run the **trusted-base** mode; it states plainly that untrusted-base/arming is C3.

### Assumptions & open questions (C2)

All have safe defaults; **none is a BLOCKER-FOR-HUMAN** (the product forks were settled at the RFC/brief
stage — build the daemon, fail-closed trusted base, generic launch template default Claude — these are
implementation clarifications).

- **C2-Q1 (load-bearing) — Who renews the lease while the child runs: the watcher or the child?**
  Assumption: **the child renews** (`ping_working(owner=MDREVIEW_OWNER)`), the watcher only claims once
  and reaps on exit. Justification: the child already owns the heartbeat loop per the MR-053 agent
  contract, and the watcher would otherwise need per-child heartbeat timers; the child has the owner via
  `MDREVIEW_OWNER`. Load-bearing because it sets the watcher↔child division; the safe default (child
  renews) matches the shipped agent contract and is what the stub test exercises. If a launcher cannot
  be made to renew, the watcher renewing is a later refinement, not a C2 blocker.
- **C2-Q7 (RESOLVED — crash liveness) — Is a stranded `turn==agent` after a child crash the intended
  C2 behavior?** Resolved: **yes, by design.** Under C2's pure edge-triggered model a child that exits
  before `hand_back` strands the baton at `turn==agent` with `turn_updated` unchanged, and the watcher
  does **not** auto-relaunch it (the edge never re-fires — verified against app.py:629-636). The plan's
  earlier "bounded relaunch" framing was backwards and has been rewritten (B1). **C2 ships with no
  crash-retry**; liveness on a crash is restored by the human (the 180s stale banner → reclaim/re-Send)
  or by a deliberate `--backlog`/restart re-seed. Crash-recovery (a re-trigger + per-review attempt cap)
  is **explicitly C3**, which is the chunk that would *create* a relaunch loop worth bounding. Stated
  plainly in the Step 4 crash model and the Step 5 caps narrative.
- **C2-Q2 (load-bearing) — Launch interface: env vs. placeholder interpolation?** Assumption:
  **env is the contract** (`REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER`); `WATCH_LAUNCH_CMD` is an argv
  (or `shlex.split` string) run with that env, no `{review_id}` interpolation required (placeholders may
  be a convenience but env is the interface). Justification: env-as-interface keeps the template
  injection-free (no `shell=True`, no string interpolation of an id into a command) and lets the stub
  test be a plain script. Load-bearing because it sets how the operator wires Claude; the safe default
  (env) is the simplest and safest.
- **C2-Q3 (minor) — Cap defaults.** Assumption: `WATCH_MAX_CONCURRENT=3`, `WATCH_MAX_LAUNCHES_PER_HOUR=30`,
  both env-overridable. Justification: conservative enough to bound spend on a single-operator machine,
  generous enough not to throttle normal use; env-overridable per `MDREVIEW_*` precedent. Minor — any
  reasonable default is fine, the operator tunes them.
- **C2-Q4 (minor) — Cold-start backlog default.** Assumption: **`now` seed (ignore backlog) by
  default**; `since=0`/`--backlog` is the explicit opt-in. Justification: a fresh watcher stampeding
  every parked agent-turn review is a spend surprise; default to "watch the next flip." Minor.
- **C2-Q5 (minor) — `::1` (IPv6 loopback) in the loopback allowlist.** Assumption: **include `::1`**
  alongside `localhost`/`127.0.0.1`. Justification: it is loopback; `urlparse` of an IPv6 loopback base
  yields `::1`; omitting it would refuse a legitimately-loopback IPv6 base. Minor; stated for precision.
- **C2-Q6 (RESOLVED — the launch-mechanism fork) — `claude -p` vs generic template.** Resolved per the
  requirement's forks table: **generic operator-configured command template (`WATCH_LAUNCH_CMD`),
  default Claude headless, env as the interface.** The watcher knows only "run this command with this
  env," which is what lets the C2 test use a stub. Recorded as resolved, not open.

**No missing-server-primitive blocker surfaced** during this expansion: the C1 contract (`/wait` edge
long-poll, `?turn=` filter, `/handoff {state:working}` 200/409 claim) is exactly the shape C2 needs. If
implementation reveals a genuinely missing primitive, **flag it as a blocker** (do not bury a server gap
in `watch.py`).

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

**Now planned in full implementable detail** — see "C2 — Watcher core (full plan)" above; tickets
proposed as **MR-056 (fail-closed loop core)** + **MR-057 (spawn + caps + runbook stub)** in the
Ticket-breakdown table below. Scope (from the requirement): `watch.py` (sibling to `mcp_server.py`,
stdlib-only `urllib` + `subprocess` + `threading`) that **fails closed** — refuses to auto-run unless the configured base is trusted (default
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
guard** for the relaunch paths C3 introduces (e.g. if C3 adds a crash re-trigger, a re-launching review
stops after N attempts) — note this guards a relaunch loop **C2 deliberately does not create** (under
C2's edge-triggered model a crashed child *strands* rather than loops; see the C2 crash model), and
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

Create these in `tickets/` only after the chunk's gate clears, then link them here. **C1 shipped
(MR-054, MR-055). C2 is now decomposed (MR-056, MR-057, proposed below — created in `tickets/` when the
C2 cycle opens and after the focused C2 critique).** C3 tickets are created at the start of its cycle.
IDs are the next free sequential IDs (highest existing on disk is MR-055, so C2 = MR-056/MR-057).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-054 | Watcher detection: `?turn=agent` filter + `summary()` turn-default + `/wait` long-poll (Condition over `_lock`, required `?since=<turn_updated>` edge cursor) | svc | 1 (C1) |
| MR-055 | Stale-lease takeover on `/handoff {state:working}` (TTL single-source + reclaim-vs-takeover re-check) | svc | 1 (C1) |
| MR-056 | `watch.py` fail-closed loop core: trusted-base check (loopback default + `WATCH_TRUSTED_BASE` exact-match) + `/wait` long-poll with cursor advance + claim-before-spawn (`200`/`409`, stable watcher-id) | svc | 2 (C2) |
| MR-057 | `watch.py` spawn + child contract + caps: generic `WATCH_LAUNCH_CMD` template (default Claude; JSON-array preferred, string→`shlex.split`→argv, no shell), child env (`REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER`), child-renews-lease lifecycle + crash-strands-baton model (no auto-relaunch), concurrency + launches/hour caps, crash-stub validation, trusted-base runbook stub | svc (+docs) | 2 (C2) |

Dependencies: MR-055 `depends_on: [MR-054]` (shared `/handoff` handler + `Condition` lock); MR-057
`depends_on: [MR-056]` (it spawns into the loop MR-056 builds). Sprint membership: **the C1 sprint =
{MR-054, MR-055}** (shipped); **the C2 sprint = {MR-056, MR-057}**. C3 tickets are not created until its
cycle opens. **No `app.py` change in MR-056/MR-057** — C1 shipped the server side; if implementation
reveals a missing server primitive, flag it as a blocker (do not bury it in `watch.py`).

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
| **(C2) Crashed child STRANDS the baton — no auto-relaunch (B1).** A child that exits before `hand_back` leaves the review at `turn==agent` with `turn_updated` unchanged (app.py:629-636); the edge-triggered `/wait?since=cursor` never re-surfaces it, so it is stuck "Agent is working" with no liveness signal until the 180s stale banner. | **Intended C2 behavior, fail-safe (under-spawn, not over-spawn).** C2 ships **no crash-retry by design** (C2-Q7); recovery is the human (stale banner → reclaim/re-Send, a fresh `turn_updated` flip) or a `--backlog`/restart re-seed. The **WC-4 crash-stub test (H/H2)** measures exactly this so the C2 close cannot claim a relaunch property the loop lacks. Crash-recovery + per-review attempt cap is **C3**. |
| **(C2) Cap-skip busy-spins `/wait` (WC-3).** A naive "don't advance the cursor at cap so `/wait` re-returns the row" re-returns the same edge instantly, re-running the O(all-reviews) scan in a tight loop while the watcher is busiest. | Advance the cursor past the skipped row and track skipped ids in an in-process **pending set** drained as concurrency slots free (re-attempt on a timer / on reap), NOT an un-advanced cursor; a bounded backoff sleep is the named fallback. Pinned as the default in MR-056. |
| **(C2) `WATCH_LAUNCH_CMD` string form reaching a shell (WC-2).** A string template "helpfully" run with `shell=True` re-opens a shell-injection surface the env-as-interface design closed. | JSON-array form preferred; a string form is parsed with `shlex.split` into an argv list and spawned **without a shell** (never `shell=True`). Pinned in MR-057; the result of `shlex.split` goes straight to a no-shell `Popen` argv. |
| **(C2) Restarted watcher does not own its predecessor's leases (WC-5).** A pid-derived owner changes on restart, so a still-live child renewing under the old `MDREVIEW_OWNER` is a foreign owner to the new watcher. | Correct and intended: the new watcher `409`s and skips a review a live child still holds (no double-spawn); it reclaims only via the MR-055 stale-takeover once that lease goes stale. Stated in MR-056 as "why pid-derived owner is fine." |
| **(C2) Brittle `WATCH_TRUSTED_BASE` exact-match confuses the operator (WC-1).** A scheme/port mismatch refuses (the correct fail-closed direction) but a bare refusal leaves the operator guessing. | Keep the strict exact-match (it **is** the control); the refusal message names **both** `MDREVIEW_BASE` and `WATCH_TRUSTED_BASE` so the mismatch is self-explaining. Do not relax the match. Pinned in MR-056. |

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

Independent G1 staff-critic review of the **C2 section**
`reviews/agent-watcher-c2-plan-review-2026-06-24.md` (verdict **PASS-WITH-NITS**; B1 + WC-1..WC-5).
Dispositions, author-applied (G1 stays the critic's call):

- **2026-06-24 — B1 (the crash-loop bound is the wrong model — rewritten).** Accepted; this was the
  important one. Verified against the shipped code: `turn_updated` is bumped **only** on a real
  reviewer→agent flip (app.py:629-634) and **not** by a `{state:working}` lease write (app.py:635-636).
  So a child that crashes before `hand_back` strands the review at `turn==agent` with `turn_updated`
  unchanged, and the edge-triggered `/wait?since=cursor` (cursor already past that flip) **never
  re-surfaces it** — the real failure mode is a **stranded baton (under-spawn)**, not a relaunch storm.
  Rewrote: the **Step 4 lifecycle** (new "Crash model" bullet stating the stranding, the human-re-Send /
  `--backlog` / restart recovery, and "C2 has no crash-retry by design"); the **Step 5 caps narrative**
  (caps bound the *normal* spend, are a backstop, but do **not** bound a crash-loop because the crash
  case is fail-safe — and the per-review attempt cap is C3, which addresses paths where relaunches *do*
  happen); the **C2 core design principle** (#3); the **epic product goal** done-state; the **C3 phase**
  description (the convergence guard guards a loop C2 deliberately does not create); a new **risks row**;
  and a new resolved assumption **C2-Q7** answering the crash-liveness open question (stranded-by-design).
- **2026-06-24 — WC-1 (fail-closed refusal message names BOTH bases).** Accepted. The Step 0 check now
  prints **both** `MDREVIEW_BASE` and `WATCH_TRUSTED_BASE` on refusal so the strict exact-match is
  self-explaining; the match is **not** relaxed (strictness is the control). Pinned in MR-056 (ticket
  scope + risks row).
- **2026-06-24 — WC-2 (string `WATCH_LAUNCH_CMD` never reaches a shell).** Accepted. Pinned: JSON-array
  form preferred; a string template is parsed with `shlex.split` into an argv list and spawned
  **without** a shell (never `shell=True`). Made explicit in the launch-mechanism section and MR-057
  scope (+ risks row).
- **2026-06-24 — WC-3 (cap-skip busy-spins `/wait`).** Accepted. Replaced the "don't advance the cursor,
  it re-returns" rule with: **advance the cursor + a pending-set drained as slots free** (bounded-backoff
  sleep as the named fallback). Pinned as the default in MR-056 (Step 3 bullet, Step 5 concurrency-cap
  bullet, ticket scope, risks row).
- **2026-06-24 — WC-4 (crash-stub validation — the test that catches B1).** Accepted. Added a **crash
  stub** fixture (renews, marks the launch, exits without `hand_back`) and validation steps **H/H2** to
  MR-057: H asserts the review strands at `turn==agent` (`turn_updated` unchanged) with **no**
  auto-relaunch under the default `now` seed; H2 asserts it is re-claimed **only** under `--backlog`/
  restart. This measures the real behavior instead of asserting the mis-stated bound.
- **2026-06-24 — WC-5 (watcher-id changes on restart).** Accepted as a note. Pinned in MR-056: the
  pid-derived owner changes on restart, so a restarted watcher does **not** own its predecessor's leases
  — it relies on the child's `MDREVIEW_OWNER` renewal + the MR-055 stale-takeover, and `409`s/skips a
  review a live child still holds (correct, no double-spawn). New risks row; no code-shape change.
