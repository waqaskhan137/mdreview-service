---
id: MR-054
title: Watcher detection — `?turn=agent` filter + `summary()` turn-default + `/wait` long-poll (Condition over `_lock`, required `?since=<turn_updated>` edge cursor)
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-17
epic: agent-watcher
depends_on: []
branch: MR-054-watcher-detection-turn-filter-wait-longpoll
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Give the (C2) watcher the two server-side read primitives it polls: a `turn==agent` queue filter on
`GET /api/reviews`, and a `/wait` long-poll that returns *immediately* on a baton flip instead of
busy-polling. The long-poll is a polling optimization, not a push: a waiter blocks on a
`threading.Condition` over the existing global lock and is woken by the same `/handoff` write that
flips the baton; if no waiter is parked the flip just happens and is found on the next poll. It is
**edge-triggered on a required `?since=<turn_updated>` cursor** so it returns only reviews *newly*
flipped since the caller last looked — never the steady-state *level* of `turn==agent` (which would
busy-loop while any agent works). All work is additive and default-safe inside the existing service
container: no UI change, no Dockerfile change, no new `meta.json` key.

## Acceptance criteria

- [ ] **`summary()` defaults `turn`.** `summary()` (`app.py:127-149`) sets `m["turn"] = m.get("turn",
      "reviewer")` (alongside the existing `m["revision"] = m.get("revision", 0)` default at
      `app.py:142`), so a legacy review with no `turn` key reads as `"reviewer"` on every
      `GET /api/reviews` row — never `None`/absent.
- [ ] **`?turn=` query filter on `GET /api/reviews`.** The collection arm (`app.py:437-438`) parses
      `parse_qs(urlparse(self.path).query)` (both already imported, `app.py:38`) for a `turn` value
      and, when present, filters the `list_reviews()` result **in Python after `list_reviews()`** to
      rows whose `turn` equals it. An unknown/empty `turn` value ⇒ no filter (return all), preserving
      today's behavior. `?turn=agent` with no matching review returns an empty list; with a flipped
      review returns exactly that review (all `turn==agent`).
- [ ] **`_lock` becomes a `Condition` over the existing lock.** `_lock = threading.Lock()`
      (`app.py:46`) → `_lock = threading.Condition()`. All existing `with _lock:` sites
      (`app.py:475, 535, 627, 646, 663, 685`) are unchanged (none calls `.acquire()` directly, so the
      swap is transparent). **One** Condition over the **one** existing lock — never a second Condition
      over a separate lock (a split lock can miss a flip / let a writer run while a waiter holds the
      lock).
- [ ] **`/handoff` notifies under the lock after the write.** Inside the existing `with _lock:` block
      in the `/handoff` handler (`app.py:535-570`), after a successful `_write` (`app.py:570`) and
      still under the lock, call `_lock.notify_all()` (prefer one `notify_all()` after any successful
      write, so the predicate, not the arm, decides whether a waiter returns). The changed `rid` is
      recorded (module-level, under the lock) just before the notify so woken waiters do an O(1) match,
      not an O(all-reviews) rescan.
- [ ] **`GET /api/reviews/wait` route arm, placed before the per-review RID arm.** Added as a new
      `re.fullmatch` in `route()` **immediately after** the `GET /api/reviews` collection arm
      (`app.py:437-438`) and **before** the per-review `re.fullmatch(r"/api/reviews/" + RID, path)` arm
      (`app.py:454)` — `wait` is 4 chars and matches `RID = [A-Za-z0-9]{4,40}`, so a later placement
      would be shadowed into a review-id lookup (404). It is a **collection** endpoint (waits across
      the fleet), not per-review.
- [ ] **Parked handler uses `_lock.wait(timeout)` (releases the lock while parked).** The handler:
      `with _lock:` → if the predicate is already satisfied vs the caller's `since`, return the changed
      rows immediately (no wait); else `_lock.wait(remaining_timeout)`; on wake **re-check the
      predicate under the lock** (a `Condition.wait` can wake spuriously and `notify_all` wakes every
      waiter); loop until the predicate holds or the total elapsed exceeds the bound. It must **never**
      sleep/block while *holding* `_lock` — one such waiter would deadlock every writer.
- [ ] **`?since=<cursor>` is REQUIRED; `/wait` matches an EDGE, not a LEVEL.** The cursor is compared
      against `turn_updated` (written on every real flip at `app.py:542/549/556`, surfaced on `/status`
      at `app.py:515`). The endpoint returns only reviews matching the filter whose `turn_updated >
      since`; a review already at agent-turn with `turn_updated <= since` is **not** returned (the call
      blocks up to the timeout). Each returned row carries its `turn_updated`; the watcher advances its
      cursor to the **max** received and passes it as `since` next call, so a seen flip never
      re-returns.
- [ ] **Missing `since` ⇒ default `now` (`time.time()`), the safer degrade.** An omitted cursor means
      "wait for the next flip from this instant," so `/wait` **blocks** (clean timeout) rather than
      dumping the whole agent-turn backlog. `since=0` is the explicit backlog opt-in. Missing-`since`
      is **not** equivalent to `since=0`.
- [ ] **Bounded server-side timeout, long-poll not a stream.** Default server timeout ≈ **25s**
      (env-overridable, e.g. `MDREVIEW_WAIT_TIMEOUT_S`; the client may pass `?timeout=` capped to the
      server max), returning `200 {"reviews":[], "timeout":true}` on expiry so the watcher re-issues.
- [ ] **Thundering-herd O(1)-per-wake.** Each `notify_all()` wakes every parked waiter; a woken waiter
      checks whether the recorded changed `rid` matches its filter (one `meta(rid)` read, O(1)) before
      deciding to return — never re-running the disk-heavy `list_reviews()` (`app.py:152-155`) per
      wake. `list_reviews()` runs once on entry (baseline) and again only when actually returning rows.
- [ ] **Parked-thread cost stated, not claimed cost-free.** The `ThreadingHTTPServer` (`app.py:37,
      727`) is thread-per-request with no fixed pool, so a 25s-parked `/wait` starves **no** pool;
      concurrent requests get their own threads. But N concurrent `/wait` opens = N parked OS threads
      (up to 25s each) — a cheap parked-thread DoS on this no-auth service. Disposition: **accepted**
      for the trusted/single-operator case (the service is already trivially floodable, so no new
      exposure class; the real trust boundary is C2's fail-closed base check). The ticket **states**
      this cost. Optional unbuilt mitigation flagged: an in-flight-waiter counter that `503`s past a
      ceiling (~3 lines) — not a separate ticket.
- [ ] **No new exposure.** `?turn=agent` and `/wait` return no field `GET /api/reviews` does not
      already disclose and add no cross-review aggregation — a server-side convenience over data
      already public on this no-auth service (footgun #5). Stated so a reviewer does not flag a phantom
      exposure widening.
- [ ] **Back-compat.** Legacy reviews (no `turn`/`agent_status`) read via `.get(...)` defaults; a
      legacy review is simply absent from the `turn==agent` queue. Existing `GET /api/reviews`
      (unfiltered), `GET /status`, `PUT /source`, and `/handoff` respond unchanged for a review that
      never touches `/wait`.
- [ ] **Local validation passes:** `python3 -m py_compile app.py`, the curl smokes below (#1 filter,
      #2 clean timeout, #3 immediate-on-new-flip, **#4 the steady-state no-busy-loop assertion**), and
      the ~20-line concurrent lock-release self-check (parks a `/wait` in a thread, fires a concurrent
      writer against the same service, asserts the writer is **not** blocked < 2s). #4 is the assertion
      that distinguishes the correct edge trigger from the level-trigger bug (#3's happy-path flip
      passes either way). All smokes run against a **throwaway container on a scratch port** (e.g.
      8155), never the live 8139 instance and never `docker compose up` (8137).

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"Service (`app.py`) — C1" items 1 & 2,
  §Key constraints, §Verification → MR-054, and the risks rows (lock-discipline, lost/spurious wake,
  level-vs-edge busy-loop F1, validation-green-lights-level-bug F2, parked-thread cost WC-1,
  thundering herd).
- `app.py` anchors: `summary()` `:127-149` (revision default `:142`); collection arm `:437-438`;
  per-review RID arm `:454`; `_lock` decl `:46`; `with _lock:` sites `:475, 535, 627, 646, 663, 685`;
  `/handoff` handler `:535-570` (turn-flip `:550-556`, hand-back/reclaim `:538-549`, lease renew
  `:557-566`, `_write` `:570`); `turn_updated` writes `:542/549/556`, surfaced on `/status` `:515`;
  `list_reviews()` `:152-155`; `parse_qs`/`urlparse` imported `:38`; `ThreadingHTTPServer` `:37, 727`.
- Q1 (resolved): `/wait` is **collection-level** (`/api/reviews/wait`), the long-poll replacement for
  busy-polling the queue — not per-review.
- Q4 (resolved at G1, folding critic F1): `?since=` is **required**, edge not level — not a deferrable
  refinement. Without it the C1 deliverable busy-loops in steady state and C2 inherits a level-trigger
  to paper over.
- No UI change, no Dockerfile change, no new served file (footgun #9 does not apply); no render-smoke
  owed (no UI behavior change). MR-055 (lease takeover) builds on the same lock / `/handoff` block and
  depends on this ticket.

## Work log

- `2026-06-24` — implemented all of MR-054 in `app.py` (single file); README API table updated.
  Branch `MR-054-watcher-detection-turn-filter-wait-longpoll` off `dev`. Changes:
  - **`summary()` turn default** (`app.py`): `m["turn"] = m.get("turn", "reviewer")` alongside the
    existing `revision` default, so legacy reviews read `"reviewer"`, never `None`/absent.
  - **`?turn=` filter** on the `GET /api/reviews` collection arm: `parse_qs(urlparse(self.path).query)`
    for `turn`; when non-empty, filter `list_reviews()` in Python to exact-`turn` rows. Empty/absent ⇒
    no filter (all). No new field, no cross-review aggregation.
  - **`_lock` swap**: `threading.Lock()` → `threading.Condition()`. Verified the only `_lock` uses are
    `with _lock:` blocks (app.py:475/535/627/646/663/685 pre-edit) — none calls `.acquire()` directly,
    so the swap is transparent. One Condition over the one lock.
  - **`/handoff` notify**: inside the existing `with _lock:` block, after the successful `_write`,
    record the changed `rid` in module-level `_last_change` and call `_lock.notify_all()` — both under
    the lock so write+wake are atomic. Notify on any successful write; the `/wait` predicate decides
    whether a waiter returns.
  - **`GET /api/reviews/wait`** route arm placed immediately after the collection arm and **before**
    the per-review `re.fullmatch(RID)` arm (exact-string match, so not shadowed; the per-review `{id}`
    GET still returns 200, smoke-confirmed). New `_wait()` handler: required `?since=<turn_updated>`
    edge cursor (missing ⇒ `now`, `=0` ⇒ backlog); returns only filter-matching rows with
    `turn_updated > since`; else parks on `_lock.wait(remaining)` (releases the lock), re-runs the
    predicate scan under the lock on wake; bounded by `WAIT_TIMEOUT_S` (env `MDREVIEW_WAIT_TIMEOUT_S`,
    default 25s; client `?timeout=` capped to it); `200 {"reviews":[], "timeout":true}` on expiry.
  - `_to_float()` query-number helper added.
- **Correctness deviation from the plan's `_last_change` rid-carry (rescan-on-wake instead).** The
  plan pinned an O(1) per-wake optimization: record only the single most-recent changed `rid` and,
  on wake, re-scan only if that rid matches the waiter's filter. That drops an edge under a rapid
  flip: a matching flip A immediately followed by a non-matching flip B (before the woken waiter
  re-acquires the lock) overwrites `_last_change` to B, so the waiter sees no match and re-parks,
  missing A until the timeout (bounded delay, not a lost event — the next poll's baseline scan
  catches it). Replaced with an unconditional `changed_rows()` re-scan on every wake: O(all-reviews)
  per wake, but trivially cheap at this scale (a handful of reviews, one operator) and correct under
  rapid flips. `_last_change` removed entirely (no dead state). Regression-guarded by a deterministic
  rapid-double-flip smoke (below).
- Files touched: `app.py`, `README.md`. No UI/Dockerfile/`meta.json`-key change (additive + default-safe).

## Validation

- `2026-06-24` — all gates run against a **throwaway service on scratch port 8156** with a scratch
  `MDREVIEW_DATA` dir (never 8139/8137). Real results:
  - **`python3 -m py_compile app.py`** → `PY_COMPILE OK` (exit 0).
  - **Smoke #1 (turn filter):** `?turn=agent` count = `0` before any flip; unfiltered list has all
    rows `turn=="reviewer"` (= `True`, the `summary()` default lands); after `POST /handoff {to:agent}`
    `?turn=agent` returns exactly `['<ID>']` with `all turn==agent`; after `{to:reviewer,by:reviewer}`
    reclaim, count back to `0`. Empty `?turn=` and `?turn=` absent both return the full list.
  - **Smoke #2 (clean timeout):** `wait?turn=agent&since=<now>&timeout=2` → `True 0` in **2.017s**
    (capped at client timeout under the server bound).
  - **Smoke #3 (immediate on a NEW flip):** with a concurrent `POST /handoff {to:agent}` fired after
    0.5s, `wait?turn=agent&since=<now>&timeout=25` returned `[('<ID>', <new turn_updated>)]` in
    **0.525s** — the edge, well under the bound.
  - **Smoke #4 (F1/F2 steady-state no-busy-loop):** with `<ID>` already at `turn==agent`, polling
    `wait?turn=agent&since=<that flip's turn_updated>&timeout=2` returned `True 0` in **2.017s** — the
    already-working review does NOT return instantly. This is the edge-vs-level guard #3 alone can't
    catch.
  - **Concurrent lock-release self-check** (~20-line script, scratchpad, not committed — the ticket
    does not ask for a `test_*.py`): parks a `/wait` in a thread, fires a concurrent `PUT /source`
    against the same service → `OK: writer unblocked in 0.006s while a /wait was parked`, proving
    `Condition.wait()` releases `_lock`. (The plan's verbatim script POSTs to `/source`, which only
    accepts GET/PUT — a `POST` 404s; the writer was run as the intended `PUT /source`, the actual
    concurrent-writer the plan names.)
  - **Smoke #5 (rapid double-flip edge — regression guard for the rescan-on-wake fix):** a waiter
    parked on `wait?turn=agent&since=<cur>`; a matching flip (a new review → agent) fired immediately
    followed by a non-matching write (reclaim of another review → reviewer); the waiter returned the
    matching review in **0.41s**, not after the timeout — proving the wake re-scan catches the edge
    the `_last_change` rid-carry would have dropped. Re-ran #1/#2/#4 + the lock-release check after the
    fix: all green (`ALL SMOKES PASS`).
  - **Back-compat:** `GET /status` still carries `turn`/`turn_updated`; `GET /api/reviews/{id}`
    per-review meta still returns `200` (not shadowed by `/wait`); `since=0` returns the agent-turn
    backlog immediately (the explicit opt-in).
  - **Interpretation note (plan ambiguity, resolved):** the criterion reads "unknown/empty `turn` ⇒
    no filter (return all)" but also "`?turn=agent` with no matching review returns an empty list".
    Treating an *unrecognized string* (e.g. `?turn=bogus`) as "return all" would make `?turn=agent`
    itself return all whenever no review is at agent-turn, contradicting smoke #1. So "unknown/empty"
    is read as **empty/absent param ⇒ no filter**; any non-empty value is an exact match (an
    unrecognized value matches nothing). This keeps the filter sound and satisfies every testable
    criterion. `?turn=bogus` returns `[]` by design.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
