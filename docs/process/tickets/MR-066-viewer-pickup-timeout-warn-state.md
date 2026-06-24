---
id: MR-066
title: "Viewer: pickup-timeout cue + non-spinning `.warn` state (Half 1)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-24
epic: watcher-observability
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

A reviewer who pressed **Send to agent** when no watcher is running (or nothing claims the lease)
sees the spinner forever — the live 20-minute-spin bug on review `22ba5df2c6`. The waiting-for-pickup
state has no timeout: the `STALE_S` "may have stopped" cue only fires in the WORKING state (which
needs a lease heartbeat), and MR-062's spinner made the parked state look identical to "working".
This ticket — fully independent, fixes the live bug on its own — adds a client-side grace timeout to
the parked banner arm so that after ~60s with no pickup it flips to a distinct, non-spinning warning
telling the reviewer to take the turn back. No server or watcher change (the viewer already polls
`turn`, `agent_status`, `turn_updated`).

## Acceptance criteria

- [ ] `renderBanner` (`viewer.html:232-255`) splits the parked `if(!as){…}` arm (`viewer.html:240`)
      on `Date.now()/1000 - (turn_updated||0) > PICKUP_GRACE_S`, a new constant `PICKUP_GRACE_S = 60`
      declared next to `STALE_S` (`viewer.html:225`) with a one-line comment justifying 60s (> one
      ~25s watcher long-poll cycle + claim/spawn jitter, < `STALE_S=180`, > the ~2s poll).
- [ ] **≤ grace:** today's "Sent — waiting for an agent to pick this up." **with** the spinner
      (`.loading`). **> grace:** "No agent has picked this up — is a watcher running? Take back the
      turn." with **NO** spinner and the new `.warn` class. The reclaim ("Take back the turn") control
      stays available in every agent-turn row.
- [ ] **This ticket defines the `.warn` CSS class outright** (the non-spinning warning treatment — a
      warning accent border/tint via an existing color token, **no animation**) in the turn-baton
      banner CSS (`viewer.html:80-89`), so MR-068 reuses it without redefining. The class ships here
      even though MR-066 only wires it onto the parked-timeout row.
- [ ] The three agent-turn states are visually distinct per the plan's decision table: pre-grace
      waiting (spinner) and working (spinner) spin; the timed-out "no agent" row does not and is
      `.warn`. Only the two genuinely-active rows spin.
- [ ] `.warn` adds no animation, so it is reduced-motion-safe by construction (assert it); `.loading`
      reduced-motion behavior (`viewer.html:89`) is unchanged. The banner re-renders on the existing
      ~2s poll (`viewer.html:668`), so the state flips as the clock crosses the grace boundary with no
      `/status` change (the same property the existing `STALE_S` check relies on).
- [ ] **No `app.py`/server change; no new `/status` call.** `turn_updated` is already in the poll body.
      Old reviews with `turn_updated==0` warn immediately (the safe direction — an ancient parked
      review should warn, not spin forever); note this in the work log.
- [ ] Local validation passes: `python3 -m py_compile app.py` (sanity, unchanged) **plus** the
      node-CDP banner-drive below.

## Notes / context

- Epic plan: `epics/watcher-observability-plan.md` (UI section + the decision table + grace-window
  justification). Relates to MR-062 (the spinner that made the parked state look active).
- All UI work is in `renderBanner` (`viewer.html:232-255`) + the banner CSS (`viewer.html:80-89`).
- `viewer.html` is JS-rendered — **a 200 is not a render**, and this is a *time-dependent* JS state
  transition, so `render-smoke.sh` (a flat one-shot matcher) **cannot** drive it.

## Validation

_How this was verified — node-CDP banner-drive against a **rebuilt throwaway container**._

- **node-CDP eval driver** (the `agent_smoke.py:112-135` `Runtime.evaluate{returnByValue,awaitPromise}`
  pattern) under `.scratch/`, against a rebuilt throwaway container on a scratch port (never
  8137/8139, never `docker compose up`, fresh throwaway volume):
  - Create a review, `POST /handoff {to:agent}`, force `turn=agent`/`agent_status=null`; back-date
    `turn_updated` past the grace (edit the throwaway `meta.json` under `MDREVIEW_DATA`, or drive
    `Date.now` in the eval).
  - Assert: `#turnbanner` classList contains `warn` and NOT `loading`; `#turntext` text matches the
    "no agent" cue; `getComputedStyle(#turntext,'::before').animationName === 'none'`.
  - Assert the **≤ grace** path still spins (classList `loading`, animation present).
  - Both-pane screenshots via `Emulation.setEmulatedMedia` `prefers-color-scheme` dark/light (or
    `--blink-settings=preferredColorScheme=0/1`) — **never `--force-dark-mode`**.
  - Reduced-motion pane (`prefers-reduced-motion:reduce`): assert `.warn` has no animation.
  - Evidence under `reviews/sprint-24-render-evidence-2026-06-24/`.

## Follow-ups

- MR-068 reuses the `.warn` class to render the watcher's crash signal (Half 2 viewer side).
