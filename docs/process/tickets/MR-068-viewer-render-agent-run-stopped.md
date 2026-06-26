---
id: MR-068
title: "Viewer: render the watcher \"agent run stopped\" blocked signal (Half 2)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-24
epic: watcher-observability
depends_on: [MR-066, MR-067]
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

When the watcher signals a crashed run (MR-067 POSTs `hand_back{state:blocked,
message:"agent process exited N without finishing"}`), the reviewer should see a distinct
**"agent run stopped — Take back the turn"** banner, not a normal "your turn" or an ambiguous
spinner. The viewer's reviewer-turn `state==='blocked'` arm (`viewer.html:248`) today renders "Agent
needs you: <message>." for a deliberate agent question; this ticket gives the watcher's crash signal
the non-spinning `.warn` stopped-state treatment (the class defined in MR-066) while keeping it
distinguishable from a genuine agent-asked-a-question block. This is the viewer half of Half 2 and
the end-to-end watcher→service→viewer proof — hence its own gate, separate from MR-066.

## Acceptance criteria

- [ ] The reviewer-turn `state==='blocked'` arm (`viewer.html:248`) renders the watcher's crash
      message as a distinct **"agent run stopped — Take back the turn"** banner using the MR-066
      `.warn` treatment (no spinner, warning style). It reuses the `.warn` class **defined in MR-066**
      — this ticket does **not** redefine it, it is purely a render-arm change.
- [ ] The crash/stopped banner stays distinguishable from a deliberate "Agent needs you: <message>"
      question block (e.g. keyed on the watcher's fixed message shape, or a sub-state) — a real agent
      question must not read as a crash and vice-versa.
- [ ] Reduced-motion respected (`.warn` has no animation by construction); the reclaim ("Take back
      the turn") control is available.
- [ ] **Happy-path no-regression:** `state==='done'` still shows "Agent updated the draft… Your turn."
      and a deliberate agent-question `blocked` still reads as a question, not a crash.
- [ ] Local validation passes: `python3 -m py_compile app.py` (sanity, unchanged) plus the node-CDP
      drive below.

## Notes / context

- Epic plan: `epics/watcher-observability-plan.md` (UI section "Agent run stopped" treatment +
  MR-068 ACs). **`depends_on: [MR-066, MR-067]`** — the `.warn` class is defined in MR-066, and the
  real signal to render comes from MR-067; this ticket verifies the two end-to-end.
- The signal contract MR-068 renders is pinned by MR-067: `state:"blocked"`, `message:"agent process
  exited <code> without finishing"`.

## Work log

- `2026-06-24` — `viewer.html`: in the reviewer-turn `state==='blocked'` arm of `renderBanner`, branch
  on the watcher's crash message prefix (`as.message.indexOf('agent process exited')===0`) → render
  `"Agent run stopped: <message>. Your turn."` with the MR-066 `.warn` class (no spinner); else keep
  today's `"Agent needs you: …"` for a deliberate agent question. Copy says "Your turn" (not "Take back
  the turn") because the watcher's `hand_back` already flipped the turn to the reviewer. Committed on dev.

## Validation

_Verified 2026-06-24 (G4) end-to-end (watcher → service → viewer) against the working-tree service on
scratch port 8181. Result: **PASS**. Evidence: `reviews/sprint-24-render-evidence-2026-06-24/SUMMARY.md`
(MR-068 section)._

- Crash signal (review `310fec7735`, left `blocked` by the MR-067 crash run): banner
  `className="turnbanner show warn"`; text `"Agent run stopped: agent process exited 1 without
  finishing. Your turn."`; `::before animationName==="none"` (no spinner). PASS.
- No-regression — a deliberate agent question (`96f35fcf16`, message "Do you mean X or Y here?") renders
  `"Agent needs you: …"` with NO `.warn`/`loading`. PASS (a question is not mistaken for a crash).

### Owed at G7 (re-drive against the rebuilt container)

_How this was verified — node-CDP drive against the **rebuilt container**._

- node-CDP eval driver under `.scratch/`, rebuilt throwaway container on a scratch port (never
  8137/8139, never `docker compose up`): POST the blocked crash signal (or reproduce end-to-end via
  the MR-067 crash-stub run), then assert the banner shows the "agent run stopped — Take back the
  turn" cue with `.warn` (classList contains `warn`, no spinner animation —
  `getComputedStyle(#turntext,'::before').animationName === 'none'`) in both panes
  (`Emulation.setEmulatedMedia` `prefers-color-scheme`, never `--force-dark-mode`).
- Reduced-motion pane: assert no `.warn` animation.
- Happy-path: `state==='done'` still renders "Your turn"; a deliberate agent-question `blocked` still
  reads as a question.
- Evidence under `reviews/sprint-24-render-evidence-2026-06-24/`.

## Follow-ups

- None planned. Closes the Half-2 viewer surface for #26.
