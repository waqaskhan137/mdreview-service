---
id: sprint-17
name: agent-watcher — C1 (server support: turn filter + /wait long-poll + stale-lease takeover)
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Ship C1 server support — the `?turn=agent` filter + `/wait` long-poll + stale-lease takeover — the three server-side primitives the (C2) watcher polls.
close_review: reviews/sprint-17-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent)
---

## Goal

Land Chunk 1 of the `agent-watcher` epic: the detection + recovery primitives the watcher needs,
entirely inside the existing service container. MR-054 adds the `turn==agent` queue filter and the
`/wait` long-poll (a `threading.Condition` over the existing `_lock`, a `notify_all()` on the
`/handoff` write, and a required `?since=<turn_updated>` edge cursor so it returns only newly-flipped
reviews, never the steady-state level). MR-055 relaxes the `{state:working}` lease arm to allow a
stale-lease takeover (with a single-source TTL and a reclaim-vs-takeover re-check). Success by the end
date: both tickets `done` on `dev`, each with `py_compile` + curl smokes (MR-054 also the ~20-line
concurrent lock-release self-check and the steady-state no-busy-loop assertion). No UI change, no
Dockerfile change — C1 ships invisibly. Once C1 lands, the watcher (C2) can be built against it.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-054 | Watcher detection — `?turn=agent` filter + `summary()` turn-default + `/wait` long-poll (Condition over `_lock`, required `?since=<turn_updated>` edge cursor) | svc | P1 | done |
| MR-055 | Stale-lease takeover on `/handoff {state:working}` (TTL single-source + reclaim-vs-takeover re-check) | svc | P1 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-054 — detection (filter + `/wait`). Introduces the `Condition` swap and the `notify_all()` in
   `/handoff`; the foundational edit MR-055 builds on.
2. MR-055 — lease change (stale-takeover). `depends_on: [MR-054]` — both touch the `/handoff` handler
   under the same lock; sequencing MR-054 first avoids a merge conflict on that block.

## Notes / retro

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-17-close-review-2026-06-24.md`).
Both committed tickets `done`, no carry-overs.

- **Shipped:** MR-054 (turn filter + `summary()` turn-default + `/wait` long-poll with the required
  `?since=` edge cursor) and MR-055 (stale-lease takeover with the reclaim re-check + single-source
  TTL). All in `app.py`; one comment-only `viewer.html` edit; README + CLAUDE.md lease/endpoint docs
  updated in-sprint.
- **One mid-sprint correction (good catch):** the G1 plan pinned a `_last_change` rid-carry as an O(1)
  per-wake optimization for `/wait`. Verifying the merged code surfaced a missed-edge race (a matching
  flip immediately followed by a non-matching one overwrites the single recorded rid before the woken
  waiter re-acquires the lock, dropping the edge until timeout). Replaced with an unconditional
  rescan-on-wake — simpler and correct at this scale — and added a deterministic rapid-double-flip
  regression smoke. The G7 critic independently reproduced both the bug-that-would-have-been and the
  fix. Lesson: a pinned micro-optimization in a plan still owes a correctness check at implementation;
  the cheaper correct version won.
- **Carry-overs:** none. C1 is complete; C2 (the `watch.py` watcher core, fail-closed trusted-base
  only) is the next chunk and runs as its own cycle against these primitives.
- **Validation gap accepted:** the 180s stale-takeover path was unit-smoked with
  `MDREVIEW_LEASE_TTL_S=2` (identical, TTL-value-independent branch), not waited out in-container.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-054 + MR-055 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-17-close-review-2026-06-24.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried. (C1 touches no product page — the only `viewer.html` edit is a
      code comment — so per the G7 pass-condition row no per-page DOM assertion/screenshot is owed; the
      sprint still owes the container rebuild + `curl /healthz` + `GET /api/reviews` smoke — done, see
      `reviews/sprint-17-render-evidence-2026-06-24/SMOKE.md`.)
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
