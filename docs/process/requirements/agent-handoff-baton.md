---
slug: agent-handoff-baton
captured: 2026-06-23            # Europe/London
source: design RFC authored + critic-gated + human-approved this session in mdreview review ff60fa640e ("RFC: Work with the agent from inside the review")
related_epic: epics/agent-handoff-baton-plan.md
---

# Brief — Work with the agent from inside the review (turn-based handoff)

A turn-based **handoff baton** between the mdreview viewer and a running AI session, so a human can
highlight text, comment, press **"Send to agent"**, have the agent act on the feedback, update the
doc, get notified, and go back and forth, all from the review page.

This brief is the **approved design**: it was authored, run through the `staff-critic` (multiple
rounds), and **signed off by the product owner** in mdreview review `ff60fa640e`. The delivery
cycle implements it; it does **not** reopen the design decisions.

## Locked decisions (product-owner sign-off, all resolved in the review)

1. **Fork A** — a pull baton on the broker. No daemon, no "summon a dead session".
2. **One agent per review** — the lease `owner` is cooperative insurance against an accidental
   double-run; **no** server-enforced single-writer gate on `PUT /source` in v1.
3. **Interactive** — viewer-side reclaim only; **no** background sweep / scheduler (preserves the
   stdlib-only "no scheduler" property).
4. **No free-text handoff box** — the open comments are the message; `{to: agent}` is a pure baton
   flip (no `handoff.message`).
5. **Turn-based, no concurrent co-editing** — true simultaneous co-editing (OT/CRDT) is out of
   scope and **deferred as GitHub issue #16**.

## Delivery — 3 dependency-ordered chunks (explicit product-owner request)

The owner asked that the feature be divided into manageable chunks before running the cycle, and
approved this split. Chunk 1 ships first to its own PR; Chunks 2 and 3 depend on 1 and are parallel
to each other.

- **Chunk 1 — Server: the baton contract** (`svc`, `app.py`). `meta.json` fields `turn` (default
  `reviewer`), `turn_updated`, `handoff{by,at}`, `agent_status{state,message,owner,at}`. New route
  `POST /api/reviews/{id}/handoff` with four body forms, all under `_lock` with a guarded
  read-check-write:
  - `{to:"agent"}` — viewer flip; if `turn==reviewer` set `turn=agent`, clear stale `agent_status`,
    write `handoff`, bump `turn_updated`; if already `agent`, idempotent no-op 200.
  - `{state:"working", message?}` (no `to`) — agent lease claim/renew; if `agent_status.owner` is
    unset or yours, set `owner`/`state`/`message`/`at`; bump `agent_status.at` **only**, not
    `turn_updated`; a second agent seeing a fresh lease it does not own backs off.
  - `{to:"reviewer", state:"done"|"blocked", message}` — agent hand-back; set `turn=reviewer`, write
    `agent_status`, bump `turn_updated`.
  - `{to:"reviewer", by:"reviewer"}` — viewer reclaim; force `turn=reviewer`, bump `turn_updated`.

  `GET /status` surfaces `turn`, `turn_updated`, `handoff`, `agent_status`. Additive /
  backward-compatible — ships invisibly (existing flows unchanged). **Validation:**
  `python3 -m py_compile app.py` + a curl round-trip (flip → working-claim → hand-back → reclaim;
  re-flip idempotent; a second owner backs off).

- **Chunk 2 — Viewer: the turn UI** (`ui`, `viewer.html`, depends on Chunk 1). A turn-gated
  **"Send to agent"** button (enabled only while `turn==reviewer`); a **6-state first-match banner**
  (parked / working / stale / done / blocked / your-turn); an always-available **"Take back the
  turn"** control (shown while `turn==agent`); the 2s poll gains a `lastTurn` and the
  source-push-then-banner ordering rule. **Validation:** `scripts/render-smoke.sh` (button + banner
  present) + a node-CDP interaction check (Send → "working" banner → reclaim → "your turn") + a
  browser render.

- **Chunk 3 — Agent surface: MCP tool + contract** (`svc`/`docs`, `mcp_server.py` + `CLAUDE.md`,
  depends on Chunk 1, parallel to Chunk 2). New MCP tool
  `hand_back(document_id, message, state?)` → `POST /handoff {to:reviewer}` plus the `working`
  lease ping; confirm `get_status` passes `turn` through (HTTP passthrough, no reconnect). A
  `CLAUDE.md` note documenting the agent contract: the find-work loop (poll `GET /api/reviews` for
  owned reviews with `turn==agent`), the lease-heartbeat obligation, the blocked-via-comment-reply
  convention, and the reconnect required to pick up the new tool. **Validation:** `mcp_smoke.py` +
  `python3 -m py_compile`.

Dependencies: `1 → 2`, `1 → 3`; `2 ∥ 3`.

---

# Approved design (verbatim — mdreview review ff60fa640e)

## TL;DR

You want to highlight text, comment, press **"Send to agent"**, have the agent
act on it, update the doc, notify you, and go back and forth, all from the
review page.

**Most of the *channel* for that already exists** (comments, `PUT /source`, the
2s live-reload poll). What is missing is small and well-defined:

1. An explicit **handoff baton** (a "Send to agent" button + a `turn` the agent polls). Today the agent *guesses* you are done by watching comments go quiet (`CLAUDE.md`, "Detecting the human is done"). The button replaces a heuristic with a fact.
2. An **agent-status surface** in the doc, so you can see *is an agent attending? working? done? blocked?* Right now you are blind between draft pushes.
3. A **reclaim path** + **durable pickup**, so you are never locked out and a baton sent to an absent agent is picked up when one next attends.

**The one caveat, up front:** mdreview is a broker, not a summoner. "Send to
agent" reaches an agent that is **already looping**, *or* parks the baton durably
so the next time an agent of yours runs its loop it picks the work up. It does
**not** wake a dead session on the spot. For a review you open with no agent
attending, the button parks the baton and tells you so, and you can always take
the turn back. Read the headline as *"hand the baton to an attending-or-next-
attending agent,"* not *"summon one."*

Net new code: roughly **1 endpoint, a few fields on `/status`, 1 new viewer UI
region (button + banner + reclaim), 1 MCP tool, 1 agent-contract note.** No
WebSocket, no daemon, no message broker, no new storage.

## What already exists (so we do not rebuild it)

| Piece of your ask | Already in the service |
|---|---|
| You → agent feedback | **Comments** (highlight → thread), the primary feedback surface |
| Agent → doc update | `PUT /api/reviews/{id}/source` (snapshots history, bumps `source_updated`) |
| You get notified | Viewer polls `/status` every 2s and toasts **"Draft updated by AI"** on a source change (`viewer.html:603`) |
| Agent reacts to you | Agent polls `comments_updated` and acts |
| "Which reviews need an agent?" | `GET /api/reviews` already lists every review with a derived `status` (`app.py:127`) — this is the work-list a consumer polls |
| Back-and-forth | The whole create → comment → revise → re-comment loop, today driven by the agent's polling |

What is genuinely **new work**:

- **Server:** one `/handoff` route + a few fields on `meta.json`/`/status`. Small.
- **Viewer:** a **new stateful UI region** — a status banner, a turn-gated "Send to agent" button,
  an always-available "Take back the turn" control, and an agent-status readout, each with its own
  enable/disable logic. The 2s poll (`viewer.html:595`) is extended with a `lastTurn`; note line
  603's source branch does not set `lastSrc` inline, it relies on `load()` re-fetching `/status`
  (`viewer.html:321`), so a turn flip that rides alongside a source push needs explicit ordering or
  the banner and the toast fight.
- **MCP:** one new `hand_back` tool.
- **Agent contract:** a `CLAUDE.md` note: the agent's "find work" loop polls `GET /api/reviews` for
  owned reviews with `turn == agent` (durable pickup), and holding the turn obliges a periodic
  `working` ping (the lease heartbeat).

## The constraint that shapes everything

**mdreview is a broker, not a summoner.** It is a stateless HTTP service. It holds documents,
comments, and now a turn baton. It **cannot reach into a Claude session and make it run.** The
agent finds work by *polling*. So "Send to agent" hands a baton to the broker. A living, watching
agent picks it up on its next poll; an agent that starts looping later picks up the parked baton
from the work-list. A session that has ended and never restarts will not wake by itself. The
**reclaim path** guarantees the human always has a way out, and **durable pickup** guarantees a
late agent still gets the work.

## Design (Fork A): a turn baton

### Data model (no new files) — added to `meta.json`

```jsonc
{
  "turn": "reviewer",              // | "agent"     (default reviewer)
  "turn_updated": 1750680000.0,    // bumped ONLY on an actual turn flip
  "handoff": { "by": "reviewer", "at": 1750680000.0 },   // who flipped the baton last (no free-text)
  "agent_status": {                // written by the consuming agent; ABSENT until one picks up
    "state": "working",            // working | done | blocked
    "message": "On it — revising section 3.",
    "owner": "sess-9f3a",          // opaque id of the agent holding the lease (set on first ping)
    "at": 1750680001.0             // lease heartbeat; staleness = now - at
  }
}
```

The **absence** of `agent_status` is meaningful: `turn == agent` with no `agent_status` = the baton
is **parked, not yet claimed**.

### Endpoint — `POST /api/reviews/{id}/handoff` (all under `_lock`, guarded read-check-write)

| Body | Who | Effect |
|---|---|---|
| `{to:"agent"}` | viewer | if `turn==reviewer`: set `turn=agent`, clear stale `agent_status`, write `handoff`, bump `turn_updated`. If already `agent`: idempotent no-op 200. |
| `{state:"working", message?}` (no `to`) | agent | claim/renew the lease: if `agent_status.owner` unset or yours, set `owner`/`state`/`message`/`at`; bump `agent_status.at` only, NOT `turn_updated`. A second agent with a fresh lease it does not own backs off. |
| `{to:"reviewer", state:"done"|"blocked", message}` | agent | set `turn=reviewer`, write `agent_status`, bump `turn_updated`. The single hand-back call. |
| `{to:"reviewer", by:"reviewer"}` | viewer | reclaim: force `turn=reviewer` regardless of state; bump `turn_updated`. |

`turn`/`owner` are shared mutable control state both parties write, so `/handoff` takes `_lock` and
does a guarded read-check-write (read current `turn`/`owner`, decide, write once), **not** a bare
`bump()` (which does not take `_lock` — callers hold it, as the `PUT /source` handler does). The
lease `owner` makes a second agent back off before it edits. This single-writer property is a
**cooperative convention**, not a server guarantee (the owner gate is in `/handoff`; `PUT /source`
is not gated) — honest only under "one agent per review" (a v1 decision). `GET /status` gains
`turn`, `turn_updated`, `handoff`, `agent_status`.

### Viewer — button + banner + reclaim

- **Button** (toolbar, next to History): "Send to agent ▶", enabled only while `turn==reviewer`; on
  click `POST /handoff {to:agent}`, then disabled "Sent — agent's turn".
- **Status banner** (thin bar under the top bar) — a **first-match decision** (agent cases key on
  `turn==agent`; reviewer cases key on `agent_status.state`), so no row shadows another:
  1. `turn=agent`, `agent_status` **absent** → "Sent — waiting for an agent to pick this up." (parked)
  2. `turn=agent`, `agent_status.at` **recent** → "Agent is working on your feedback…"
  3. `turn=agent`, `agent_status.at` **stale** (> N min, default ~3) → "Agent may have stopped — Take back the turn?"
  4. `turn=reviewer`, `agent_status.state=done` → "Agent updated the draft: «message». Your turn."
  5. `turn=reviewer`, `agent_status.state=blocked` → "Agent needs you: «message»."
  6. `turn=reviewer`, otherwise (no/cleared `agent_status`) → "Your turn. Comment, then Send to agent."
- **"Take back the turn"** control — shown whenever `turn==agent` (rows 1–3); always clickable;
  `POST /handoff {to:reviewer, by:reviewer}`.
- The 2s poll (`viewer.html:595`) gains a `lastTurn`. Ordering: when a tick sees both a source push
  and a turn flip, render the doc reload first (it calls `load()`, which resets `lastSrc`), then
  update the banner from the same `/status` body, so the toast and banner do not race.

### Agent side (mostly convention)

The agent runs a poll/loop. Find-work: poll `GET /api/reviews`, take owned reviews with
`turn==agent` (durable pickup). On a claimed review: `POST /handoff {state:working}` to take the
lease → read open comments → edit → `update_source` → reply/resolve → `POST /handoff {to:reviewer,
state:done, message}`. While holding the turn it re-pings `working` periodically (lease heartbeat).
The **blocked** path uses a comment **reply** + `handoff {to:reviewer, state:blocked}` — never
`reopen` (reopen is the reviewer's UI action, deliberately not an MCP tool). MCP delta: `get_status`
proxies `/status` so the new fields flow through with **no reconnect**; **one new tool**
`hand_back(document_id, message, state?)` → `POST /handoff {to:reviewer}` (+ the `working` ping) —
a new tool **does** need an MCP client reconnect (the stdio server loads its tool list at startup).

## Multiple agents, multiple documents (resolved)

1. **Different docs, different agents — isolated at the data layer.** Each review is keyed by `id`;
   its baton and `source.md` are private. Each agent's find-work loop filters `GET /api/reviews` to
   the reviews it owns by `session`/`project` provenance or the ids it created. **Ownership is a
   convention, not a guarantee:** `project`/`session`/`source_path` are optional, default `""`, no
   uniqueness — overlapping tags **degrade to the case-2 lease** (one wins `owner`, the other backs
   off), not to a clobber. A freshly started agent's durable pickup relies on the provenance filter
   (a new process has no memory of ids it did not create), so tag reviews for cross-session pickup.
2. **Same doc, one agent at a time (worker pool) — supported by the lease `owner`** (compare-and-
   claim; cooperative in v1 since `PUT /source` is not gated; server-enforced single-writer is the
   v2 step). **Not pursued in v1** (one agent per review).
3. **Same doc, two agents simultaneously (co-editing) — out of scope.** `PUT /source` is a
   whole-document overwrite = last-writer-wins; real co-authoring needs OT/CRDT. **Deferred — issue
   #16.**

## What this is NOT (ponytail boundaries)

No producer/consumer queue, no broker, no `queue.json` (the baton is the depth-1 queue; the list
endpoint is the fleet queue). No WebSocket/SSE. No agent-runner daemon, no session registry, no
background sweep. No free-text handoff box (v1). No server-enforced single-writer (v1). No
server-enforced ownership (provenance/tag convention). No concurrent co-editing (issue #16). No
auth (the service has none by design). No new storage.

## Honest risks

1. **Liveness.** The button reaches a running agent immediately and a next-attending agent via
   durable pickup; if no agent ever runs, the baton parks and you can reclaim. (Heartbeat
   "attending" badge + Fork A+ notification are v2.)
2. **No auth, and `/handoff` is the first *control-flow* surface.** Any URL-holder can seize the
   turn or spam an agent's loop; CSRF-able if proxied. **When auth lands, it must cover `/handoff`
   first.**
3. **Concurrency.** The turn flip is safe (the locking). Single-*writer* is cooperative, not
   enforced in v1 — honest only under one-agent-per-review.
4. **Double-notify.** `source_updated` already toasts; the banner is the persistent state, the
   toast the transient event; the ordering rule keeps them from fighting.

## Scope / phasing

- **v1:** turn baton + reclaim + durable pickup + lease owner (cooperative) + `/handoff` (locked) +
  `/status` fields + button + banner + one MCP tool + the `CLAUDE.md` contract note.
- **v2 (later):** Fork A+ notification; presence/attending badge; server-enforced single-writer;
  fleet dispatch (compare-and-claim over the list endpoint); doc-level chat thread; SSE; a
  server-side sweep only if walk-away/async is wanted.
- **Deferred (logged):** concurrent co-editing (OT/CRDT) — issue #16.

## Amendments

(none yet)
