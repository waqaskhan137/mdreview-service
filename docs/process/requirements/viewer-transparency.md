---
slug: viewer-transparency
captured: 2026-06-24
source: this session — product owner, after watching the containerized watcher action a multi-comment review (~2.5 min). GitHub issue #27. The "Agent is working" banner is opaque: a long task looks identical to a hung one, and there is no visibility into what the agent is doing or whether it errored.
related_epic: epics/viewer-transparency-plan.md
---

# Viewer agent-turn transparency — live behind-the-scenes progress + error surfacing

GH #27. While an agent works a turn, show **what is actually happening in real time** — connection
established, agent picked up, reading comments, thinking, updating the document, resolving, done — a
live activity feed that maps to the real backend steps, **plus** surface any error / exception /
watcher-not-working state as it happens, instead of a single static "Agent is working…" banner.

## What triggered it (verbatim intent)

> "There is transparency missing — when it says agent is working it should show what is happening
> behind the scenes in real time. Like: connection established, agent call, agent thinking, updating,
> done — some sort of real-time actions which map to the actual stuff happening behind the scenes. And
> if an error happens, or the watcher isn't working, or any exception, it should show that as well."

Concretely: a long task (a doc-wide rename across prose + a Mermaid diagram, ~2.5 min) is currently
indistinguishable from a hung agent — the banner just says "Agent is working…" the whole time.

## What's wanted (from #27 + the live ask)

1. **A live progress timeline while the agent works** — the steps the agent goes through, with a
   sense of liveness, so a slow-but-working run reads as progress, not a freeze. Steps roughly:
   *no agent → claimed/connected → reading comments → editing → resolving → done* (or *stopped/error*).
2. **Real-time error / exception surfacing** — if the agent crashes, hits an MCP error, or the watcher
   isn't running, show it as it happens (extends the #26 "agent run stopped" + "no agent has picked
   this up" states with finer, live detail where available).
3. *(from #27, lower priority)* **Streamed, non-jerky document updates** — instead of a hard full
   `<article>` swap on `update_source`, ease the change in (diff-and-animate, or smoother reload).

## Already shipped (do NOT re-do — build on it)

- **Working-banner animation** (the spinner) — MR-062. **Pickup-timeout "no agent" cue** — MR-066.
  **Agent-crash "agent run stopped" signal + watcher crash logging** — MR-067/MR-068. So #27 part 1
  (waiting animation) and part 2's *crash* case largely exist; this epic adds the **step-by-step live
  timeline** and finer in-progress detail.

## Key design question (planner resolves; the load-bearing fork)

**How does the viewer learn the agent's real-time steps?** The agent is a black-box `claude -p`
process running in a separate container/host; the service only sees coarse signals. Options the
planner must weigh and PIN:

- **(A) Derive from existing signals (cheap, robust, no agent instrumentation).** The viewer already
  polls `/status` (`turn`, `agent_status.state`, `turn_updated`, `source_updated`, `comments_updated`).
  A live timeline can be assembled from these: *claimed* (agent_status=working), *editing* (source_updated
  bumped), *resolving* (comments_updated bumped), *done/stopped* (hand_back / blocked). Plus the
  watcher already logs spawn/exit. This is a viewer-side change with maybe a tiny status-message add.
- **(B) `ping_working` carries a status string.** #27 notes the lease heartbeat could carry a short
  status the banner shows; the agent prompt instructs it to ping with "reading comments"/"editing"/etc.
  Agent-dependent (it must call it), adds tokens/latency.
- **(C) The launch wrapper parses `claude -p --output-format stream-json` events** (tool_use / text /
  result) and POSTs them to a new service progress-events endpoint the viewer streams/polls. This maps
  to the ACTUAL backend activity (real tool calls = the real "agent call / editing"), no reliance on
  the agent self-reporting — but needs a new events API + stream parsing in `watcher/launch.sh`.

Likely a **tiered** plan: Tier-1 = (A) (a robust live timeline from existing signals, fixes the
"looks frozen" problem with no new API or agent change); Tier-2 = (C) for fine-grained real steps if
warranted. The planner pins the tiers + what ships first.

## Constraints

stdlib-only `app.py` (single-file regex router under `_lock`, overwrite-based meta.json — a progress
event store, if any, must justify its persistence/shape); `viewer.html` JS-rendered (a 200 is not a
render; the timeline is a live JS state); `watch.py` is the non-containerized-or-containerized sibling;
Europe/London dates; keep the Claude commit trailer; `py_compile` gates. Don't regress MR-062/066/067/068.

## Validation (the headline — live, time-dependent JS)

The progress timeline is a *time-dependent, signal-driven* JS state, so `render-smoke.sh` can't drive
it — use a **node-CDP eval driver** (the `agent_smoke.py` pattern) against a rebuilt throwaway
container: drive a review through the lifecycle (Send → claim → source update → resolve → hand_back, or
a crash) and assert the viewer renders the corresponding live steps + the error state, both panes,
reduced-motion respected. If Tier-2 (events API) is in scope, a throwaway end-to-end with the real
wrapper emitting events. Never the live `mdreview`/:8139.

## Out of scope

- The handoff diff (#19/#21 — "review the agent's changes") — a separate feature.
- Re-doing the already-shipped working-banner animation / crash banner (MR-062/066/067/068).

## Amendments

### 2026-06-24 — add an elapsed/duration timer
Product owner: *"add the timer as well so the user knows how much time it takes the agent to revise."*
While the agent works, show a **live elapsed timer** (ticking, e.g. "Agent is working… 0:47"), and on
completion show the **total revision duration** (e.g. "Agent revised in 2:14. Your turn."). Derivable
from existing timestamps (`turn_updated` = Send/flip time while `turn==agent`; `agent_status.at`) — but
note `turn_updated` is **bumped again on hand_back** (turn flips back to reviewer), so the *final*
duration needs the viewer to capture the start client-side (remember first-seen `turn==agent`, delta on
done) or a small service-recorded duration. Live-elapsed-while-working needs no new data. Part of the
timeline ticket (MR-073).
