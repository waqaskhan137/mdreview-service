---
id: sprint-19
name: agent-watcher — C3 (watcher safety + ops)
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-28
goal: Ship the FINAL agent-watcher chunk — relax C2's fail-closed refusal via a local operator arming/allowlist so the watcher can run armed reviews on a public/no-auth base, add a per-review attempt cap bounding the re-Send loop, and write the full operator runbook.
close_review:          # reviews/sprint-19-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Land Chunk 3 — the **FINAL** chunk — of the `agent-watcher` epic: extend `watch.py` so it can run
against a **public / no-auth** instance (where provenance is not a trust boundary) by **relaxing** C2's
fail-closed refusal in one controlled way — a **local operator arming/allowlist** (`WATCH_ARMED_FILE`
primary + `WATCH_ARMED` env, unioned, **not** HTTP-settable) naming which reviews may auto-run; un-armed
reviews are **skipped without a claim** even at `turn==agent`. The Step-0 relaxation is precise:
un-vouched non-loopback + arming configured ⇒ **run-but-gate**; un-vouched + **no** arming ⇒ **EXIT
preserved**. Add a **per-review attempt cap** bounding repeated **re-Sends** of one review (the corrected
B1 model — it guards the re-Send/re-surface loop, **NOT** a crash-loop; crashes strand by design and C3
adds no auto-relaunch), composing with the C2 global caps. Ship the **full operator runbook**
(README + CLAUDE.md): the public-instance story, the arming model + local-only rationale, the per-review
cap, the full env-var reference. Success by the end date: both tickets `done` on `dev`, each with
`py_compile watch.py` + the stub-launch end-to-end against a localhost throwaway — including the
C2-EXIT-preserved proof, the un-armed-skipped-without-claim proof, the W1 not-retried-into-`pending`
proof, the `*`-dropped proof, and the per-review-cap re-Send-loop proof. No `app.py` change (C1 already
shipped the server side). **This is the FINAL chunk — at close, the `agent-watcher` epic is marked
`done`.**

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-058 | `watch.py` arming / allowlist — relax C2's fail-closed Step 0 (local `WATCH_ARMED_FILE`/`WATCH_ARMED`, run-but-gate, run()-side terminal skip) | svc | P1 | ready |
| MR-059 | `watch.py` per-review attempt cap + full operator runbook (`docs`) — bound the re-Send loop, document the public-instance arming story | svc | P1 | ready |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-058 — arming / allowlist (relaxes C2's fail-closed Step 0). Introduces the allowlist loader, the
   Step-0 run-but-gate relaxation, and the `run()`-side terminal arming gate (the W1 skip discipline) the
   per-review cap then slots into.
2. MR-059 — per-review attempt cap + full operator runbook. `depends_on: [MR-058]` — the cap sits in the
   same `run()`-side terminal-gate sequence MR-058 introduces before `handle()`, and the runbook documents
   both.

## Notes / retro

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.
- **This is the FINAL chunk of the `agent-watcher` epic.** At close (G7 PASS), the epic is marked `done`
  (C1 sprint-17 + C2 sprint-18 + C3 sprint-19, all under the one G1-passed plan).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-19-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter;
- [ ] the `agent-watcher` epic is marked `done` (this is the final chunk).

**G7 scope note (C3 specifics).** C3 touches **no product page** — it extends `watch.py` (a server-side
sibling script like `mcp_server.py`) and edits Markdown docs (`README.md` / `CLAUDE.md`); it touches no
`viewer.html`/`dashboard.html`/`static/**`. So per the G7 pass-condition row **no `docker build` and no
`scripts/render-smoke.sh` per-page DOM assertion / screenshot is owed**, and the close review must state
that the **lack of a render-smoke is compliant** (the row does not require one for a non-containerized,
no-page change) so the sprint is not flagged. The G7 smoke is **`python3 -m py_compile watch.py` + the
stub-launch end-to-end against a localhost throwaway service** (a scratch-port container, e.g. 8155 —
**never** the live 8139 instance, **never** `docker compose up`/8137), plus a throwaway-container
`curl /healthz` (→ `{"ok":true}`) + `GET /api/reviews` (→ `200`) no-regression smoke confirming the
**server is unchanged** (C3 touches no `app.py`). The end-to-end must include the C2-EXIT-preserved proof,
the un-armed-skipped-without-claim proof, the W1 not-retried-into-`pending` proof, the `*`-dropped proof,
and the per-review-cap re-Send-loop + distinct-review-unaffected proofs.
