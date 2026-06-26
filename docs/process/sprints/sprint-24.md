---
id: sprint-24
name: watcher-observability — pickup timeout + crash surfacing
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Make a stuck or crashed agent run visible — time out the viewer's waiting-for-pickup spinner into a distinct non-spinning warning, and have the watcher capture a crashed child's exit/stderr to a documented log and signal "agent run stopped" back to the reviewer.
close_review: reviews/sprint-24-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent — rebuilt container, re-drove all 3 tickets incl. the conflation guard; F1 resolved)
---

## Goal

Land the three-ticket `watcher-observability` batch (GH #26), so a reviewer who pressed **Send to
agent** can always tell within ~a minute whether they're waiting, the agent is working, no agent
picked it up, or the run crashed — and an operator can diagnose a failure from a documented log.
Success by the end date: MR-066 `done` (ui — the client-side pickup-timeout `.warn` cue that fixes
the live 20-minute-spin bug on its own, node-CDP banner-drive verified), MR-067 `done` (svc/`watch.py`
— child stderr capture + full `print()`→`logging` migration + `WATCH_LOG_FILE` + the guarded crash
`hand_back{state:blocked}` signal, crash-stub + false-positive + happy-path verified), and MR-068
`done` (ui — render the crash signal as the "agent run stopped" `.warn` banner, end-to-end verified).
No `app.py` change; no auto-relaunch. Sprint closes at G7.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-066 | Viewer: pickup-timeout cue + non-spinning `.warn` state (Half 1) | ui | P1 | done |
| MR-067 | Watcher: capture child stderr + structured log + crash `hand_back` signal (Half 2) | svc | P1 | done |
| MR-068 | Viewer: render the watcher "agent run stopped" blocked signal (Half 2) | ui | P1 | done |

## Preferred execution order

Dependencies (from the epic plan): MR-066 → none; MR-067 → none to emit; MR-068 `depends_on`
[MR-066, MR-067] (it reuses MR-066's `.warn` class and renders MR-067's real signal end-to-end).

1. **MR-066** (ui) — pickup-timeout cue + `.warn` class (defined here) + three-state
   distinguishability. Fully independent; lands first and fixes the live no-watcher bug alone.
2. **MR-067** (svc/`watch.py`) — child stderr capture + full `logging` migration + `WATCH_LOG_FILE`
   + the guarded crash signal (mandatory `/status` re-check). Independent to emit.
3. **MR-068** (ui) — render the crash signal as the "agent run stopped" `.warn` banner. Depends on
   both; the watcher→service→viewer end-to-end proof is its own gate.

## Notes / retro

_Filled in as the sprint runs and at close._

- G1 PASS 2026-06-24 (staff-critic GO-WITH-NITS, five nits folded — see
  `reviews/watcher-observability-plan-review-2026-06-24.md`).
- 2026-06-24 — all three tickets implemented + G4-validated (behavioral, working-tree service on
  scratch port 8181): MR-066 warn-cue past grace + spinner within grace; MR-067 crash signal +
  false-positive guard + happy-path (the conflation guard verified); MR-068 crash banner end-to-end +
  question no-regression. Evidence: `reviews/sprint-24-render-evidence-2026-06-24/`.

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-24-close-review-2026-06-24.md`;
rebuilt a throwaway container on scratch port 8182 and re-drove all three tickets via node-CDP + real
watcher stub runs, including the **conflation guard** end-to-end). MR-066 + MR-067 + MR-068 `done`, no
carry-overs. **This closes the `watcher-observability` epic.** Closes GH #26.

- **Shipped (GH #26):** the live "Send to agent with no watcher → ~20-minute silent spin" bug is fixed
  by MR-066 alone (a client-side 60s pickup-timeout that flips the parked spinner to a non-spinning
  `.warn` "no agent has picked this up" cue, using the `turn_updated` already in the poll body — no
  server change). MR-067 makes a crashed run diagnosable (stderr capture to `WATCH_LOG_FILE` + full
  `print()`→`logging` migration) and surfaces it (a guarded crash `hand_back{state:blocked}` signal,
  with a MANDATORY `/status` re-check so a child that handed back `done` then died in teardown is never
  stomped with a false "stopped"). MR-068 renders that signal as a distinct "Agent run stopped" banner,
  kept apart from a deliberate agent question.
- **G7 finding folded:** F1 (the crash log record omitted the resolved argv the AC names) resolved on
  dev — `proc._argv` now logged. F2 (pre-existing question double-period), F3 (message-prefix keying),
  F4 (unconditional server blocked-arm → client-side re-check is the sole guard) accepted as
  non-blocking; F4 noted for revisit only if multi-watcher contention or a server-side guard becomes real.
- **Validation wall (named):** the viewer cues are *time-dependent* (the grace clock) and *signal-driven*
  (the crash hand_back), so `render-smoke.sh` (a flat one-shot matcher) can't drive either — both G4 and
  the independent G7 used a **node-CDP eval driver** + real `watch.py` stub runs. Worth keeping node-CDP
  as the standard for any time/JS-dependent banner state.
- **Carry-overs:** none.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-066 + MR-067 + MR-068 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-24-close-review-2026-06-24.md`, verifying shipped work against each ticket's
      acceptance criteria, **including the node-CDP banner-drive render proof** of the touched viewer
      states (the time-dependent pickup-timeout transition + the crash-stopped banner — `render-smoke.sh`
      can't drive either) **and** the watcher crash-stub + false-positive-guard runs, with its findings
      resolved or carried (F1 resolved; F2/F3/F4 accepted non-blocking);
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (watcher-observability specifics).** **MR-066 and MR-068 are product-page changes**
(`viewer.html`, baked into the container at build time) whose deliverable is a *time-dependent /
signal-driven JS banner state* — `scripts/render-smoke.sh` (a flat one-shot DOM matcher) **cannot**
drive the grace clock or post a crash signal, so both owe a **node-CDP eval driver** (the
`agent_smoke.py:112-135` `Runtime.evaluate{returnByValue,awaitPromise}` pattern) asserting the
classList flip `loading`→`warn` and `getComputedStyle(#turntext,'::before').animationName==='none'`,
plus both-pane screenshots via `Emulation.setEmulatedMedia` `prefers-color-scheme` (**never
`--force-dark-mode`**) and a reduced-motion pane. **MR-067 is `watch.py`** (service-side, not
containerized) — its gate is `py_compile watch.py` + `py_compile app.py` + the three localhost
throwaway stub runs (crash, false-positive guard, happy-path) asserting the log capture + the guarded
`/status` signal. All tickets rebuild a **throwaway container** on a **scratch port** (never
8139/8137, never `docker compose up`); all temp under the gitignored `.scratch/`, evidence moved to
`reviews/sprint-24-render-evidence-2026-06-24/`.
