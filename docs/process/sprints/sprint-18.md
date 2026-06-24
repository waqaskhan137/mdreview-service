---
id: sprint-18
name: agent-watcher — C2 (watcher core)
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-28
goal: Ship the C2 watcher core — `watch.py`, a fail-closed, single-flight, bounded launcher that long-polls C1's `/wait`, claims the lease before spawning, and runs the operator's configured agent command.
close_review: reviews/sprint-18-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent)
---

## Goal

Land Chunk 2 of the `agent-watcher` epic: `watch.py`, the first piece of this epic that is code outside
the service container and the first credentialed process spawner. It long-polls C1's `/wait` for
`turn==agent` flips, **fails closed** (refuses to start against a base it cannot vouch for),
**claims-before-spawn** (wins the `/handoff {state:working}` lease, spawns only on `200`, so a cold start
or two ticks never double-spawn), spawns the operator's configured launch command (default Claude) with a
child env contract, and bounds normal-load spend with a concurrency cap and a launches/hour cap. Success
by the end date: both tickets `done` on `dev`, each with `py_compile watch.py` + the stub-launch
end-to-end against a localhost throwaway service — including the fail-closed-refusal-exits proof, the
no-double-spawn proof, and the crash-stub stranded-baton proof. No `app.py` change (C1 already shipped the
server side).

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-056 | `watch.py` fail-closed loop core — trusted-base check + `/wait` long-poll + claim-before-spawn | svc | P1 | done |
| MR-057 | `watch.py` spawn + child env contract + caps (generic launch template, default Claude) + trusted-base runbook stub | svc | P1 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-056 — fail-closed loop core (trusted-base check + `/wait` long-poll + claim-before-spawn). Builds
   `watch.py` and the two safety proofs; spawns only a placeholder.
2. MR-057 — spawn + child env contract + caps + runbook stub. `depends_on: [MR-056]` — it spawns the real
   launch command into the loop MR-056 builds and adds the caps.

## Notes / retro

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-18-close-review-2026-06-24.md`).
Both committed tickets `done`, no carry-overs.

- **Shipped:** `watch.py` — the first code outside the service container and the first credentialed
  process spawner. MR-056 (fail-closed trusted-base check + `/wait` long-poll + claim-before-spawn
  single-flight) + MR-057 (generic `WATCH_LAUNCH_CMD` template default Claude + child env contract +
  concurrency/launches-hour caps + the B1 stranded-baton crash model + trusted-base runbook in
  README/CLAUDE.md). No `app.py`/Dockerfile change.
- **G7 critic independently re-ran** the security crux (fail-closed exit incl. the `localhost.evil.com`
  substring trap), the no-injection spawn, single-flight, the caps, and the **B1 crash model** (a
  crash-stub strands the review at `turn==agent`, `turn_updated` byte-identical before/after, no
  auto-relaunch; `--backlog` re-surfaces it) — all hold in code, not just in claims.
- **Two trivial nits applied post-review:** a fallback log when `WATCH_LAUNCH_CMD` parses as JSON but
  isn't an array; a stale `_drain_pending` docstring. One worth-considering accepted as-is.
- **Carry-overs:** none. C2 is complete. **Next: C3** (arming/allowlist + trusted-base gating relaxation
  for the untrusted/public-instance case + per-review attempt cap + the full runbook).
- **Crash-model note for C3:** under C2's edge-triggered design a crashed child STRANDS (under-spawn,
  fail-safe), it does not relaunch — so C3's "per-review attempt cap / relaunch-convergence guard"
  applies only to paths where relaunches actually happen (e.g. if C3 adds re-surfacing). C3 inherits
  this corrected model.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-056 + MR-057 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-18-close-review-2026-06-24.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried. (C2 touches no product page — `watch.py` is a server-side
      sibling script — so no per-page DOM/screenshot is owed; the G7 smoke was `py_compile watch.py`
      + the stub-launch end-to-end against a localhost throwaway, re-run independently by the critic.)
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (C2 specifics).** C2 adds **no product page** — `watch.py` is a new server-side sibling
script (like `mcp_server.py`); it touches no `viewer.html`/`dashboard.html`/`static/**`. So per the G7
pass-condition row **no per-page DOM assertion or screenshot is owed**. But `watch.py` is **not** in the
container, so the G7 smoke is **`python3 -m py_compile watch.py` + the stub-launch end-to-end against a
localhost throwaway service** (a scratch-port container, e.g. 8155 — **never** the live 8139 instance,
**never** `docker compose up`/8137), plus a confirmation that the existing container's `/healthz` and
`GET /api/reviews` still pass (C2 does not touch `app.py`, so this just confirms no regression). The
end-to-end must include the fail-closed-refusal-exits proof, the no-double-spawn (single-flight) proof,
and the crash-stub stranded-baton proof (WC-4/B1).
