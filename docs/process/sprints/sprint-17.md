---
id: sprint-17
name: agent-watcher — C1 (server support: turn filter + /wait long-poll + stale-lease takeover)
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Ship C1 server support — the `?turn=agent` filter + `/wait` long-poll + stale-lease takeover — the three server-side primitives the (C2) watcher polls.
close_review:          # reviews/sprint-NN-close-review-YYYY-MM-DD.md — required by G7 before status: closed
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

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-17-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried. (C1 touches no product page — the only `viewer.html` edit is a
      code comment — so per the G7 pass-condition row no per-page DOM assertion/screenshot is owed; the
      sprint still owes the container rebuild + `curl /healthz` + `GET /api/reviews` smoke.)
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
