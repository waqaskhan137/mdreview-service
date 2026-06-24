---
id: sprint-20
name: watcher-launch-fix — inert default + runbook
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Replace the watcher's silently-no-op runnable Claude default with an inert must-configure stub that refuses to start (exit 2 with guidance) when WATCH_LAUNCH_CMD is unset, plus the runbook recipes and injection caveat.
close_review:          # reviews/sprint-NN-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Land the single `watcher-launch-fix` slice — a small follow-up to the now-done `agent-watcher` epic.
The shipped watcher's runnable `DEFAULT_LAUNCH_CMD` (`claude -p …`) silently no-ops headless (MCP tool
use routes to a no-TTY approval prompt; the agent claims the lease and hands back without doing the
work). Replace it with an **inert must-configure stub** so the watcher **refuses to start at startup**
(exit 2 with guidance) when `WATCH_LAUNCH_CMD` is unset — never claiming a lease it cannot honour — move
the permission posture into runbook recipes, sweep the 8 "default Claude headless" doc spots, and ship
the injection caveat. Success by the end date: MR-060 `done` on `dev`, validated by
`py_compile watch.py` + the 2-arm stub-launch self-check. No `app.py` / Dockerfile / UI change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-060 | Watcher must-configure launch stub — refuse-to-start at startup when `WATCH_LAUNCH_CMD` unset + runbook recipes + injection caveat (svc + same-change docs) | svc | P1 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-060 — the inert sentinel + `launch_configured()` / `require_launch_configured_or_exit()` startup
   gate in `watch.py`, the 8-spot docs sweep + runbook recipes + injection caveat, validated by
   `py_compile watch.py` + the 2-arm stub-launch end-to-end. Single ticket, no dependencies.

## Notes / retro

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-NN-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (watcher-launch-fix specifics).** This sprint touches **no product page** — it extends
`watch.py` (a server-side sibling script like `mcp_server.py`) and edits Markdown docs (`README.md` /
`CLAUDE.md`); it touches no `viewer.html` / `dashboard.html` / `static/**`, and no `app.py` /
`Dockerfile`. So per the G7 pass-condition row **no `docker build` and no `scripts/render-smoke.sh`
per-page DOM assertion / screenshot is owed**, and the close review must state that the **lack of a
render-smoke is COMPLIANT** (the row does not require one for a non-containerized, no-page change) so the
sprint is not flagged. The G7 smoke is **`python3 -m py_compile watch.py` + the 2-arm stub-launch
end-to-end** against a localhost throwaway service (a scratch-port `python3 app.py` run with a `.scratch/`
data dir, e.g. port 8151 — **never** the live 8139 instance, **never** `docker compose up`/8137, never
`docker compose up`), plus the existing throwaway-container `curl /healthz` (→ `{"ok":true}`) +
`GET /api/reviews` (→ `200`) no-regression smoke confirming the **server is unchanged** (no `app.py`
change). The 2 arms: **Arm A** — unconfigured exits 2 at STARTUP before any `/wait` poll / lease claim;
**Arm B** — a configured stub runs claim → spawn → hand-back, using the corrected `/handoff` schemas
(flip `{"to":"agent"}`, hand-back `{"to":"reviewer","state":"done"}`).
