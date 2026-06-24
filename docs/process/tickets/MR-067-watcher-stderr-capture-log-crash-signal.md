---
id: MR-067
title: "Watcher: capture child stderr + structured log + crash `hand_back` signal (Half 2)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs (watch.py is service-side server code, not containerized)
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-24
epic: watcher-observability
depends_on: []
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

When a watcher-spawned agent crashes, the failure is near-invisible: `_spawn` passes no
`stderr`/`stdout` to `Popen` so the crash trace is lost among `print()`s, and the reviewer sees a
frozen "working" banner until the 180s lease goes stale — with no idea the agent died or why (#26,
motivated by #25). This ticket makes a failed run diagnosable and surfaced: capture the child's
stderr + structured timestamped logging to a documented location, and on a non-zero exit POST the
**existing** `hand_back{state:blocked}` signal so the reviewer's banner shows "agent run stopped"
instead of spinning. **Visibility only — no auto-relaunch** (B1 fail-safe under-spawn stays). The
file touched is **`watch.py`** (+ README runbook + its docstring), **not `app.py`** — the blocked
hand-back arm already exists (`app.py:623-629`).

## Acceptance criteria

- [ ] `_spawn` (`watch.py:394-411`) captures the child's stderr (`subprocess.PIPE` read on reap, or a
      per-review redirect — PIPE-on-reap preferred, bounded since runs are short); `_reap`
      (`watch.py:299-318`) reads it on a non-zero exit.
- [ ] **Full `print()`→`logging` migration** of `watch.py` — all ~15 call sites, including the B1
      reap traces (`watch.py:311,316`), capacity/skip/cap lines, cursor-seed/startup notices, and the
      spawn line. **No half-migration** (a split log loses the very capacity/lease lines that
      contextualize a crash). Every existing message string is preserved; only the sink changes
      (`print(x)` → `log.info/warning(x)`). `logging` is stdlib (not yet imported — add it).
- [ ] **`WATCH_LOG_FILE` default pinned:** unset ⇒ log to **stderr only** (`StreamHandler`,
      preserving today's "wherever the operator redirected" behavior); set ⇒ **also** write that exact
      file (`FileHandler`). **No baked-in file path** (the watcher has no `/data` mount; a default path
      would surprise-write the operator's CWD). `--verbose` raises the level (INFO→DEBUG).
- [ ] Both `WATCH_LOG_FILE` and `--verbose` are documented in the README **"Watcher (optional) —
      operator runbook"** section **and** in `watch.py`'s module-docstring Config block (which already
      enumerates the env vars).
- [ ] On a non-zero child exit, a **structured, timestamped** record is emitted carrying the review
      id, exit code, the resolved argv, and the captured stderr tail.
- [ ] **Crash signal with a MANDATORY `/status` re-check guard.** On a non-zero child exit, `_reap`
      first `GET /api/reviews/{rid}/status` and **SKIPS** the signal when `turn != "agent"` **or**
      `agent_status.state == "done"` (the child handed the turn back before a non-zero teardown — do
      **not** stomp a successful `done`). Only when the re-check confirms `turn == "agent"` does it
      POST `/api/reviews/{rid}/handoff`
      `{to:"reviewer", state:"blocked", owner:OWNER, message:"agent process exited <code> without
      finishing"}` — a **short fixed reason, never raw stderr** (no-auth posture; raw stderr stays in
      the operator log only).
- [ ] B1 unchanged: **no relaunch**; per-review/global caps untouched. The signal **and** its
      re-check are best-effort — a failed `/status` read or POST logs and continues, never crashes the
      reap loop (the safe direction: a missed signal still self-heals via the 180s stale banner + the
      MR-066 pickup-timeout cue).
- [ ] Local validation passes: `python3 -m py_compile watch.py` **and** `python3 -m py_compile app.py`,
      plus the throwaway crash-stub runs below.

## Notes / context

- Epic plan: `epics/watcher-observability-plan.md` (Watcher section + the mandatory-re-check
  subtlety + Risks row 3). The viewer render of this signal is **MR-068** (depends on this + MR-066).
- Reuses the existing `hand_back` arm verified at `app.py:623-629,667-672` (writes
  `agent_status={state:"blocked",…}`, flips turn, bumps `turn_updated`, `notify_all()` under `_lock`).
  `_reap` has `rid` (from `_inflight`), `BASE`/`OWNER` (module globals), and the `_http` helper
  (`watch.py:245`, already used for the lease claim).
- **No `app.py` change** — no new route, no new `agent_status` state, no new `/handoff` arm, no new
  `meta.json` key.

## Work log

- `2026-06-24` — `watch.py`: added `import logging`/`import tempfile`; a `log` logger + `_setup_logging()`
  (stderr always, +`FileHandler` when `WATCH_LOG_FILE` set, `--verbose`/`WATCH_VERBOSE`→DEBUG), called
  first in `main()`; migrated all 15 `print()` sites to `log.info/warning` (stripped the redundant
  `watch.py:` literal now in the formatter); `_spawn` captures child stderr to a `tempfile.TemporaryFile`
  (not PIPE — avoids the chatty-child deadlock) attached as `proc._errf`; `_reap` reads the tail
  (`_read_errtail`), logs it on a non-zero exit, and calls `_signal_crash`; `_signal_crash` does the
  MANDATORY `GET /status` re-check (skip if `turn!=agent` or `state==done`) then POSTs
  `hand_back{to:reviewer,state:blocked,message:"agent process exited N without finishing"}`. README
  runbook env-var table + the crash-diagnosis paragraph + the module-docstring Config block updated. No
  `app.py` change (the blocked arm already exists, `app.py:623-629`). Committed on dev.

## Validation

_Verified 2026-06-24 (G4) via three host runs of `watch.py` against the service from the working tree
(scratch port 8181), `WATCH_LOG_FILE` set, bash stub launch commands. Result: **PASS**. Logs:
`reviews/sprint-24-render-evidence-2026-06-24/watch-{crash,falsepos,happy}.log`._

- **Crash** (exit 1, no hand_back): log captured exit code + stderr marker `BOOM-CRASH-MARKER`;
  `/status` re-check saw `turn=agent` → signal POSTed → `turn=reviewer`, `agent_status.state=blocked`,
  message `"agent process exited 1 without finishing"`. PASS.
- **False-positive guard** (hand_back `done` THEN exit 1): re-check saw `turn=reviewer`/`state=done` →
  *"no false 'stopped'"* logged, signal SKIPPED; review stayed `done`. PASS (the G1-critic guard).
- **Happy path** (hand_back `done`, exit 0): no signal; review stayed `done`. PASS.
- `py_compile watch.py` + `py_compile app.py` pass; unconfigured watcher still exits 2; `WATCH_LOG_FILE`
  wiring writes the `FileHandler` file.

### Owed at G7 (re-drive against the rebuilt container)

_How this was verified — localhost throwaway runs under `.scratch/`, `WATCH_LOG_FILE=.scratch/watch.log`._

- **Crash stub** (claims the lease via the child env, writes a stderr marker, exits non-zero
  WITHOUT `hand_back`): assert (a) `grep -q "exited 1" .scratch/watch.log` and the stderr marker is
  captured; (b) `GET /status` → `turn=="reviewer"` + `agent_status.state=="blocked"` with the stopped
  message.
- **False-positive guard test** (the conflation guard — must ship tested): a stub that POSTs
  `hand_back {state:done}` and **then** exits non-zero. Assert the `/status` re-check **SKIPS** the
  signal — the review stays `turn=="reviewer"` + `agent_status.state=="done"`, **no** false "agent run
  stopped" written (`grep -L "blocked"` for that review's signal).
- **Happy-path no-regression:** a stub that hands back `done` and exits 0 leaves the normal
  done/"your turn" state and emits no crash signal.
- Evidence under `reviews/sprint-24-render-evidence-2026-06-24/`; all throwaway data + stub scripts
  under the gitignored `.scratch/`, cleaned after (contents only, don't rmdir).

## Follow-ups

- MR-068 renders the blocked crash signal as the `.warn` "agent run stopped" banner end-to-end.
