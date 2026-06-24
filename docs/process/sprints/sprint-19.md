---
id: sprint-19
name: agent-watcher — C3 (watcher safety + ops)
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-28
goal: Ship the FINAL agent-watcher chunk — relax C2's fail-closed refusal via a local operator arming/allowlist so the watcher can run armed reviews on a public/no-auth base, add a per-review attempt cap bounding the re-Send loop, and write the full operator runbook.
close_review: reviews/sprint-19-close-review-2026-06-24.md   # G7 PASS-WITH-NITS 2026-06-24 (staff-critic, independent); nit fixed
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
| MR-058 | `watch.py` arming / allowlist — relax C2's fail-closed Step 0 (local `WATCH_ARMED_FILE`/`WATCH_ARMED`, run-but-gate, run()-side terminal skip) | svc | P1 | done |
| MR-059 | `watch.py` per-review attempt cap + full operator runbook (`docs`) — bound the re-Send loop, document the public-instance arming story | svc | P1 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-058 — arming / allowlist (relaxes C2's fail-closed Step 0). Introduces the allowlist loader, the
   Step-0 run-but-gate relaxation, and the `run()`-side terminal arming gate (the W1 skip discipline) the
   per-review cap then slots into.
2. MR-059 — per-review attempt cap + full operator runbook. `depends_on: [MR-058]` — the cap sits in the
   same `run()`-side terminal-gate sequence MR-058 introduces before `handle()`, and the runbook documents
   both.

## Notes / retro

**Closed 2026-06-24, G7 PASS-WITH-NITS** (staff-critic, independent — `reviews/sprint-19-close-review-2026-06-24.md`).
Both committed tickets `done`, no carry-overs. **This closes the `agent-watcher` epic (C1+C2+C3) — epic `done`.**

- **Shipped:** MR-058 (local arming/allowlist relaxing C2's fail-closed Step-0 — run-but-gate on an
  un-vouched base, armed reviews only, un-armed skipped without a claim via the run()-side terminal gate)
  + MR-059 (per-review attempt cap bounding the re-Send/re-surface loop — NOT a crash-loop — composing
  with the C2 global caps, + the full operator runbook in README/CLAUDE.md). No `app.py` change.
- **G7 critic independently re-ran** the full matrix (`.scratch/` throwaway service): C2 fail-closed EXIT
  preserved byte-for-byte when arming unconfigured (the critical no-regression), no self-arming (no
  `app.py` route), un-armed skipped without claim and never into `pending` (W1), `*` dropped, the cap
  stops a 3× re-Send at cap=2 while a distinct review is unaffected. C1+C2+C3 compose into the full loop.
- **One nit fixed post-review:** the README arming example used `rev_abc123` ids that fail the documented
  id shape; replaced with real 10-hex-char ids. Re-log-noise nit accepted (intended per-check freshness).
- **Carry-overs:** none. The `agent-watcher` epic is COMPLETE.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-058 + MR-059 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-19-close-review-2026-06-24.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried. (C3 touches no product page — `watch.py` + Markdown docs — so
      no `docker build`/`render-smoke.sh` DOM assertion is owed; the lack of one is COMPLIANT. The owed
      smoke — `py_compile watch.py` + the stub-launch end-to-end + a throwaway-container `/healthz` +
      `/api/reviews` no-regression — was run independently by the critic.)
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter;
- [x] the `agent-watcher` epic is marked `done` (this is the final chunk).

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
