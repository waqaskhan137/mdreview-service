---
id: MR-073
title: "Live progress timeline + elapsed/duration timer in the working banner (derived from /status)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-26
epic: viewer-transparency
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

While an agent works a turn, the viewer is opaque — a static "Agent is working…" banner makes a
healthy 2.5-min run indistinguishable from a hung one, and there's no sense of how long it's taking.
This ticket adds, in `renderBanner` (`viewer.html`), a **live progress timeline** (Connected — reading
your comments → Editing → Updating comments → Done/Stopped) **derived entirely from the `/status`
signals the viewer already polls**, plus an **elapsed/duration timer** (live ticking while working +
final "revised in M:SS" on done). UI-only — no service change, no agent instrumentation. The literal
tool-call stream (Tier-2) is explicitly out of scope (deferred).

## Acceptance criteria

- [ ] **Derived timeline** in/under the working banner, assembled from `/status` (`turn`,
      `agent_status.state/at`, `turn_updated`, `source_updated`, `comments_updated`) — no new endpoint,
      no new persisted field. Steps: **Connected — reading your comments** (claimed; "reading" is a
      non-derivable resting label of the claimed step, NOT a separate timed signal) → **Editing** (a
      `source_updated` increase *after this turn began*) → **Updating comments** (a `comments_updated`
      increase after this turn began) → terminal **Done** / **Stopped**.
- [ ] **Cumulative, not a single-pointer:** once a step's signal has fired this turn it stays "reached"
      (so a skipped 2s poll that lands two signals at once never loses a step). Steps are baselined
      against `turn_updated` at turn start — only an increase **after** the current turn began counts
      (a stale `source_updated`/`comments_updated` from a prior round must NOT light "editing").
- [ ] **Signal-honest labels:** the comment step is **"Updating comments"** (off the non-resolve-specific
      `comments_updated` bump, which also fires on reply/reopen/create/delete) — the word **"Resolved"**
      appears **only** when the terminal state is `done`. A reply-then-`blocked` turn must NEVER claim
      "resolved".
- [ ] **Live timer** while `turn==='agent'` + working: `#turntimer` shows `M:SS` = `now - turn_updated`,
      **ticking ~1s** via a single fetch-free interval (re-renders from the cached last `/status`, no
      new poll), guarded to no-op outside the working state (no double-timers / leaks).
- [ ] **Final duration on done:** "Agent revised in M:SS" computed **client-side** (remember first-seen
      `turn==='agent'` for this review, delta on `done`) — because `turn_updated` is re-bumped on
      hand_back (`app.py:629`) so the start is gone from `/status`. Documented limitation: a page
      loaded AFTER `done` shows **no** duration (never a wrong number).
- [ ] **No regression of MR-062/066/067/068** — the timeline WRAPS the existing arms (same
      `turn`/`as.state`/`at` conditions), not replaces them: the spinner, the pickup-timeout `.warn`
      cue, the stale-lease "may have stopped", the crash "agent run stopped", and "Agent needs you"
      all still render. Reduced-motion still respected (`.warn`/static; spin only on the active step).
- [ ] Agent-controlled text (`agent_status.message`) stays set via `textContent` (no HTML injection).
- [ ] Local validation passes (below).

## Notes / context

- Epic plan: `epics/viewer-transparency-plan.md` (signal table, honesty rules, the timer client-side
  capture, the Risks table). G1 review: `reviews/viewer-transparency-plan-review-2026-06-24.md`.
- Builds on MR-062 (spinner), MR-066 (`.warn` cue), MR-067/068 (crash banner). All UI in `renderBanner`
  (`viewer.html:241-281`) + the 2s `poll()` (`viewer.html:~679`).
- `viewer.html` is JS-rendered and this is a *time-dependent, signal-sequenced* state — `render-smoke.sh`
  CANNOT drive it.

## Validation

_How this was verified — a node-CDP lifecycle driver against a **rebuilt throwaway container**._

- New `timeline_smoke.py` (the `agent_smoke.py:112-148` CDP pattern) on a throwaway image/port/`MDREVIEW_DATA`
  under `.scratch/` (never :8139/:8137): create a review, open `/review/{id}` over CDP, walk the
  lifecycle by POSTing real `/handoff`/`/source`/`/comments` between reads and assert the live DOM:
  Send → claim (**"Connected — reading your comments"** + `#turntimer` shows `M:SS`) → **timer ticks**
  (poll suppressed, read `#turntimer`, wait ~1.2s, read again → advanced) → `PUT /source` (**"Editing"**
  appears, was absent before) → comment+resolve (**"Updating comments"**) → hand_back `done` (**done +
  final "revised in M:SS"**, comment step may say "Resolved"). Plus: **reply-then-`blocked`** ("Resolved"
  NEVER appears; "Agent needs you" renders), **reopen-after-done** (no bogus duration), **crash**
  ("agent run stopped" — MR-068 intact), **pickup-timeout** ("no agent" — MR-066 intact).
- Both panes (`preferredColorScheme=1`/`=0`, never `--force-dark-mode`); reduced-motion via computed
  `animationName==='none'` (not screenshot — hidden-tab memo). `py_compile app.py watch.py`. A cheap
  first-paint `render-smoke.sh <url> '#turnbanner' '#turnsteps' '#turntimer'` complement (not the proof).
- Evidence under `reviews/sprint-26-render-evidence-2026-06-24/`.

## Follow-ups

- Deferred (backlog): Tier-2 stream-json events (watch.py stdout parse + `/events` API + viewer rendering).
- MR-075 documents the new timeline behaviour.
