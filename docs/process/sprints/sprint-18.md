---
id: sprint-18
name: agent-watcher — C2 (watcher core)
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-28
goal: Ship the C2 watcher core — `watch.py`, a fail-closed, single-flight, bounded launcher that long-polls C1's `/wait`, claims the lease before spawning, and runs the operator's configured agent command.
close_review:          # reviews/sprint-NN-close-review-YYYY-MM-DD.md — required by G7 before status: closed
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

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-18-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (C2 specifics).** C2 adds **no product page** — `watch.py` is a new server-side sibling
script (like `mcp_server.py`); it touches no `viewer.html`/`dashboard.html`/`static/**`. So per the G7
pass-condition row **no per-page DOM assertion or screenshot is owed**. But `watch.py` is **not** in the
container, so the G7 smoke is **`python3 -m py_compile watch.py` + the stub-launch end-to-end against a
localhost throwaway service** (a scratch-port container, e.g. 8155 — **never** the live 8139 instance,
**never** `docker compose up`/8137), plus a confirmation that the existing container's `/healthz` and
`GET /api/reviews` still pass (C2 does not touch `app.py`, so this just confirms no regression). The
end-to-end must include the fail-closed-refusal-exits proof, the no-double-spawn (single-flight) proof,
and the crash-stub stranded-baton proof (WC-4/B1).
