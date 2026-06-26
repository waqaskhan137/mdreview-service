"""mdreview watcher: auto-pick-up the handoff baton (MR-056 loop core + MR-057 launcher, C2).

A stdlib-only sibling of the mcp package, run where the operator's agent runs. It long-polls the
service's C1 /wait endpoint for reviews newly flipped to turn==agent (the "Send to agent" baton),
claims each review's cooperative lease (POST /handoff {state:working}), and — on a winning claim —
spawns the operator's configured launch command; with WATCH_LAUNCH_CMD unset it REFUSES to start
(exit 2 with guidance) — there is no runnable default. It is a CREDENTIALED process spawner, so its
load-bearing safety property is the fail-closed trusted-base check (Step 0): it refuses to start
against a base it cannot vouch for, rather than warn-and-continue.

Split from the original single-file watch.py into SRP modules: `config` (env + logging + owner),
`http` (the branch-on-status HTTP helper), `arming` (the C3 local allowlist gate), `safety` (the
fail-closed startup refusals), `spawn` (children + caps + reap + crash-signal + launch), `loop` (the
claim-before-spawn poll loop), and `__main__` (the startup sequence). Run with `python -m watcher`;
the legacy `python3 src/watch.py` path still works via a thin entry point that re-exports main().

The launch mechanism is a GENERIC, operator-configured command template (WC-2): the loop only knows
"spawn this argv with this env." Nothing Claude-specific lives in the loop — env is the entire
interface (REVIEW_ID / MDREVIEW_BASE / MDREVIEW_OWNER, Step 4). That genericity is exactly what lets
the tests drive a stub launch command instead of a real model.

Crash model (B1): a child that exits before `hand_back` STRANDS its review at turn==agent. The server
bumps `turn_updated` only on a real reviewer->agent flip, NOT on a {state:working} lease write, so the
edge-triggered /wait?since=cursor never re-surfaces a stranded review. The watcher therefore does NOT
auto-relaunch — it reaps + logs the exit and moves on. The failure mode is a fail-safe UNDER-spawn
(the human recovers via the 180s stale banner, or a --backlog/restart re-seed), not a relaunch storm.
There is no crash-retry by design. The per-review attempt cap (WATCH_MAX_ATTEMPTS_PER_REVIEW) bounds
the path where spawns DO repeat — the re-Send / re-surface loop (one review flipped back to turn==agent
again and again) — never a crash-loop.

NOT containerized by the service image, NOT imported by mdreview, NOT started by the default compose
profile. `python -m watcher` (or `python3 src/watch.py`) is how it runs.

On a crashed child (non-zero exit, no hand_back) the watcher captures the child's stderr tail to the
log AND — after a MANDATORY /status re-check that it is still stranded at turn==agent (so it never
stomps a successful hand_back) — POSTs hand_back{state:blocked,"agent process exited N without
finishing"} so the reviewer's banner shows "agent run stopped" instead of a frozen spinner. Still B1:
no relaunch (visibility, not retry). The viewer gets a short fixed reason; raw stderr is log-only.
"""
