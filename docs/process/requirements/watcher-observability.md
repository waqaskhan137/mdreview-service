---
slug: watcher-observability
captured: 2026-06-24
source: this session — GitHub issue #26 ("Watcher observability: surface spawned-agent errors + exit traces so a failed run is diagnosable"), made concrete by a live-instance product-owner bug (Send-to-agent with no watcher running → review parked at turn=agent/agent_status=null → banner spun ≈20 min with no cue). Follow-up to the done agent-watcher epic; relates to MR-062 (the spinner that made the parked state look active) and the deferred #27 (progress/streaming).
related_epic: epics/watcher-observability-plan.md
---

# Watcher observability: surface a stuck/failed agent run instead of a silent forever-spinner

GH #26. When the watcher-spawned agent fails — or when no watcher is running at all — the reviewer
sees an indefinite "working" spinner with no cue, and a failed run is hard to diagnose. Two halves.

## What triggered it (the live bug)

On the live instance the product owner pressed **Send to agent** on review `22ba5df2c6` with **no
watcher running**. The review parked at `turn=agent` / `agent_status=null` and the banner **spun for
≈20 minutes** with no indication anything was wrong. Root cause, confirmed against `/status`
(`turn=agent`, `agent_status=None`, `turn_updated` ~18 min old) and `pgrep` (no `watch.py` process):

- The **waiting-for-pickup state has no timeout.** The `STALE_S=180` "agent may have stopped" cue
  only fires in the **working** state, which needs a lease heartbeat; the parked state has
  `agent_status=null` (no lease ever claimed), so it never goes stale and the banner waits forever.
- **MR-062's loading spinner now covers the waiting-for-pickup state too**, so "no watcher will ever
  come" is visually identical to "agent is actively working."

## What's wanted (verbatim from #26 + the live finding)

### HALF 1 — Reviewer-facing: time out + distinguish the "no agent" states

- A **waiting-for-pickup timeout cue** in `renderBanner` (`viewer.html`; the parked arm is
  `if(!as){…"Sent — waiting for an agent to pick this up."…}`): using the existing `turn_updated`
  from `/status` (the viewer already polls it ~every 2s), if `turn==='agent'` and `agent_status` is
  null AND it has been longer than a grace window (~45-90s, justify the default), change the banner
  from the spinner to a **distinct, non-spinning "no agent has picked this up — is a watcher running?
  Take back the turn" cue**. Client-side only — no server change (the viewer already has `turn`,
  `agent_status`, `turn_updated`). The spinner stays ONLY while genuinely pre-grace-waiting or working.
- **Distinguishability:** the three agent-turn states — waiting-for-pickup (pre-grace, spinner),
  working (spinner), and "no pickup / stopped / failed" (no spinner, a warning cue) — must be visually
  distinct. (Pre-grace waiting and working both legitimately spin; the fix is the TIMED-OUT cue.)

### HALF 2 — Operator + reviewer-facing: surface a crashed/exited agent (the issue's core)

- **Watcher error capture + log visibility:** when the watcher's spawned child exits NON-ZERO (or
  exits without ever calling `hand_back` — a crash before finishing), `watch.py` must (a) capture and
  log the child's exit code + stderr (structured, timestamped, to a known/documented log location) so
  a failed run is diagnosable — today the only trace is a buried stdout line; and (b) surface a signal
  the reviewer sees instead of a frozen "working" banner.
- Recall the **B1 crash model**: a crashed child that already claimed the lease leaves the review at
  `turn==agent` with a stale lease; the 180s TTL is the only current recovery. Decide HOW to surface
  the failure — e.g. the watcher writes a "stopped/failed" signal back via `/handoff` (a new
  `agent_status` state, or `hand_back` with `state=blocked` + a message like "agent process exited
  without finishing"), and the viewer renders it as a distinct "agent run stopped — Take back the
  turn" banner. If a NEW `agent_status` state or `/handoff` arm is needed, that is a small `svc`
  (`app.py`) change — pin it; if the existing `hand_back{state:blocked,message}` suffices, prefer it.
- Do **NOT** add auto-relaunch (the fail-safe under-spawn / no-crash-loop model from C2/C3 stays;
  this is about VISIBILITY, not retry). Mind the no-auth posture — surface enough to be actionable
  without leaking internals to a public viewer.

## Constraints

stdlib-only; `app.py` single-file regex router under `_lock`, overwrite-based meta.json (full
read-mutate-write, no new persisted key unless justified); `viewer.html` JS-rendered (a 200 is not a
render); `watch.py` is the non-containerized sibling; Europe/London dates; keep the Claude commit
trailer; `py_compile app.py` + `py_compile watch.py` are gates.

## Validation each ticket owes (the headline — time-dependent + click-gated + the watcher)

- **Viewer banner cues** — a **node-CDP eval driver** (render-smoke.sh can't open/drive a
  time-dependent JS banner; use the `agent_smoke.py` WebSocket / `Runtime.evaluate` pattern) against a
  REBUILT throwaway container (scratch port, never 8139/8137, never `docker compose up`): force
  `turn=agent` + `agent_status=null`, drive the client clock or back-date `turn_updated` so the grace
  elapses, and assert the banner transitions from spinner to the distinct "no agent" cue (the cue text
  + the spinner `::before` animation gone / the state class changed); both-pane screenshots;
  reduced-motion respected.
- **Watcher error surfacing** — a localhost-throwaway run with a **crash-stub** launch command (claims
  the lease then exits non-zero WITHOUT `hand_back`): assert the watcher log captures the exit code +
  stderr, AND the review's `/status` + the viewer banner show the "stopped/failed" signal (not a
  frozen working state). Plus the happy-path no-regression (a normal `hand_back` still shows "your
  turn"). Evidence under `reviews/sprint-NN-render-evidence-2026-06-24/`.

## Out of scope

- Auto-relaunching crashed/stranded reviews (stays the deliberate fail-safe under-spawn behavior).
- The rest of #27 (progress steps, streamed updates, the waiting-animation UX beyond the timeout cue).
- Arming / caps changes.
