---
review_of: epics/watcher-observability-plan.md
gate: G1
reviewer: staff-critic
independent: true
verdict: GO-WITH-NITS
status: resolved
date: 2026-06-24
---

# G1 review — watcher-observability plan

Independent staff-critic review of the `watcher-observability` epic plan (GH #26). Reviewer is not
the author (the `mdreview-planner` authored and revised; the orchestrator implements). One round.

## Verdict: GO-WITH-NITS — no blocking findings.

Both load-bearing correctness questions were verified against the source and resolve in the plan's
favor:

- **Does the client-elapsed waiting-for-pickup cue actually fire without a `/status` change?**
  **Yes.** `viewer.html:668` calls `renderBanner(s)` on every ~2s poll tick unconditionally (not
  guarded on a turn change) — the same mechanism the existing `STALE_S` working-state row already
  relies on. Half-1's purely client-side grace timeout rides the identical path.
- **Does the existing `hand_back{state:blocked}` arm suffice for Half 2, and can the watcher call
  it?** **Yes to both.** `app.py:623-629` already writes `agent_status={state:"blocked",message,…}`,
  flips `turn`, bumps `turn_updated`, `notify_all()` under `_lock`; the viewer renders blocked at
  `viewer.html:248`. The watcher has `rid` (from `_inflight`), `BASE`/`OWNER`, and the `_http` helper
  at reap time. No `app.py` change is needed.

## Findings + resolution

| # | Sev | Finding | Resolution (planner revision, 2026-06-24) |
|---|-----|---------|-------------------------------------------|
| 1 | worth-fixing | **Crash-after-hand_back false positive.** The child can POST a successful `done` hand_back then exit non-zero for an unrelated reason (cleanup / `set -e` / SIGTERM); an unconditional crash signal would stomp the `done` state with a false "agent run stopped." | **Folded.** MR-067 now pins a MANDATORY `/status` re-check in `_reap` — skip the stopped signal if `turn != "agent"` or `agent_status.state == "done"`. Genuine crashes (stranded at `turn=agent`, stale `working` lease) still signal. |
| 2 | worth-fixing | The false positive ships untested (happy-path stub exits 0). | **Folded.** MR-067 ACs + epic verification add a `done`-then-non-zero stub asserting the watcher skips the signal. |
| 3 | worth-fixing | `print()`→`logging` migration boundary left to implementer guess (~15 sites, several load-bearing). | **Folded.** MR-067 owns the FULL migration of all watch.py `print()` sites. |
| 4 | worth-fixing | `WATCH_LOG_FILE` default under-specified ("a documented path"). | **Folded.** Default = stderr-only when unset; explicit `FileHandler` when set (no baked-in path — the watcher has no `/data` mount). Documented in README runbook + watch.py docstring. |
| 5 | nit | `.warn` class ownership between MR-066 and MR-068. | **Folded.** MR-066 defines `.warn` outright; MR-068 is a pure render-arm change. MR-068 kept SEPARATE (real dependency on MR-067's signal; folding would lose Half-1's independent-ship property). |

**MR-068 fold-or-separate:** critic verdict **keep separate** — the dependency on MR-067's emitted
signal is real (not bookkeeping), and merging would force MR-066 to either ship a dead render or
block on MR-067, losing Half-1's "ships independently and fixes the live bug alone" property.
Sequencing MR-066 → MR-067 → MR-068 confirmed correct.

**Scope:** clean — out-of-scope honored (no auto-relaunch, no #27 progress/streaming, no
arming/caps changes), stdlib-only holds, `py_compile app.py` + `py_compile watch.py` gates stated.

All findings resolved in the plan revision. G1 cleared.
