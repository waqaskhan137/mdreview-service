---
epic: agent-handoff-baton
status: active         # draft | active | done  (active once G1 passes)
created: 2026-06-23
source: requirements/agent-handoff-baton.md
gate: passed 2026-06-23    # G1 (Plan Gate): PASS-WITH-NITS, no blockers (SHOULDs folded into ticket ACs)
review: reviews/agent-handoff-baton-plan-review-2026-06-23.md
related_sprints: [sprint-14]   # sprint-14 holds Chunk 1 (MR-051) only; Chunks 2/3 land in a later sprint
related_tickets: [MR-051, MR-052, MR-053]
---

# Work with the Agent from Inside the Review (turn-based handoff baton) Plan

This epic adds a **turn-based handoff baton** between the mdreview viewer and a running AI session,
so a human can highlight, comment, press **"Send to agent"**, have the agent act, push the revised
draft, and hand the turn back - all from the review page, replacing the agent's "watch the comments
go quiet" heuristic with an explicit fact. The design is already authored, critic-gated, and
**product-owner-approved** (mdreview review `ff60fa640e`). This plan is **decomposition, sequencing,
validation, and footgun-surfacing only** - it does not reopen any locked decision.

**Source requirement:** [`requirements/agent-handoff-baton.md`](../requirements/agent-handoff-baton.md),
the original brief and the verbatim approved design, kept verbatim.

## Product goal

A reviewer working in the viewer can comment, press **Send to agent**, and watch a status banner
tell them what the agent is doing (parked / working / stale / done / blocked / your-turn), with an
always-available **Take back the turn** escape. A looping agent discovers the work by polling
`GET /api/reviews` for reviews it owns with `turn == agent`, claims a cooperative lease, edits and
pushes via the existing `PUT /source`, and hands the turn back over a single MCP call. The "done"
state at the epic level: the full create → comment → Send → agent works → draft updated → your-turn
loop is driveable end to end from the review page, additive over today's behaviour (every existing
flow unchanged), with **no new dependency, no daemon, no new storage file**.

## Core design principle

**mdreview is a broker, not a summoner.** The service is a stateless HTTP broker that now holds one
extra piece of mutable control state per review - a `turn` baton in `meta.json`. It cannot reach
into a Claude session and make it run; the agent finds work by polling. So "Send to agent" hands the
baton to the broker: a living agent picks it up on its next poll, a later-starting agent picks up the
**parked** baton from the work-list, and the **reclaim path** guarantees the human is never locked
out. Everything else serves this: the baton is a depth-1 queue (no `queue.json`), the lease `owner`
is a cooperative compare-and-claim (no server-enforced single-writer in v1), and reclaim is
viewer-side only (no background sweep, preserving the stdlib-only "no scheduler" property).

## Recommended approach

### Service (`app.py`)

The whole server contribution is **one new route arm and four additive `meta.json` fields**, all
backward-compatible. Existing reviews on disk lack every new key; every reader must default a missing
key to today's behaviour (`turn` absent ⇒ treat as `reviewer`; `agent_status` absent ⇒ baton parked
or never handed off).

- **New route** `POST /api/reviews/{id}/handoff`, added as a new `re.fullmatch` arm in `route()`
  (app.py:416). Place it **immediately after the `/status` arm (app.py:503-513) and before the
  `/history` arm (app.py:515)** - `/handoff` is a distinct literal segment, so it cannot shadow nor
  be shadowed by any existing route (the id regex `RID` = `[A-Za-z0-9]{4,40}` and `handoff` is not a
  valid id continuation; the matched paths are disjoint). It is `POST`-only; a `GET /handoff` should
  fall through to the generic 404. Pattern: `re.fullmatch(r"/api/reviews/" + RID + r"/handoff", path)`.

- **The handler takes `_lock` itself and does a guarded read-check-write** - it must **not** call
  bare `bump()`. `bump()` (app.py:120-124) is a read-modify-write that does **not** acquire `_lock`
  (its callers hold it, as the `PUT /source` handler does at app.py:475-478). `turn` and
  `agent_status.owner` are control state both the viewer and the agent write concurrently, so the
  handler must `with _lock:` read the current `meta(rid)`, decide the transition off the **current**
  `turn`/`owner`, mutate the in-memory dict, and `_write` `meta.json` once inside the lock. Read the
  fields with `.get(...)` defaults so a legacy `meta.json` (no `turn`) is handled as `reviewer`.

- **Four body forms** (dispatched on `to` / `state` / `by` in the JSON body via `_body_json()`):

  | Body | Who | Effect (all under `_lock`, single guarded write) |
  |---|---|---|
  | `{to:"agent"}` | viewer | if current `turn` is `reviewer` (or absent): set `turn="agent"`, **clear** any `agent_status`, write `handoff={by:"reviewer",at:now}`, set `turn_updated=now`. If already `agent`: idempotent no-op, return 200 with current meta - do **not** bump `turn_updated`. |
  | `{state:"working", message?}` (no `to`) | agent | lease claim/renew. If `agent_status.owner` is unset **or** equals the body's `owner`: set `agent_status={state:"working", message, owner, at:now}`, set `turn_updated` **unchanged**. If `owner` is set and differs (a fresh lease the caller does not own): reject with `409` (`{"error":"lease held","owner":...}`) so a second agent backs off. |
  | `{to:"reviewer", state:"done"\|"blocked", message}` | agent | hand-back: set `turn="reviewer"`, write `agent_status={state, message, owner, at:now}`, set `turn_updated=now`. |
  | `{to:"reviewer", by:"reviewer"}` | viewer | reclaim: force `turn="reviewer"` regardless of current state, set `turn_updated=now`. (Leave `agent_status` as-is so the banner can still show a stale readout if wanted; the viewer keys reclaim rows on `turn`.) |

  The `owner` for the lease comes from the request body (`{state:"working", owner:"sess-…", …}`). It
  is an opaque caller-chosen id; the server never mints it. An absent `owner` on a `working` claim is
  treated as "unowned claim" - accept it but record `owner` as whatever was sent (possibly `""`);
  this matches the brief's "owner set on first ping" and keeps the server from inventing identity.
  **(Open question Q1 below: confirm `owner` is client-supplied, not server-minted.)**

- **Staleness is NOT computed server-side.** `agent_status.at` is the lease heartbeat; the viewer
  computes `now - at > N` to decide the "stale" banner row. The server only stamps `at`; it runs no
  timer and no sweep (locked decision 3, interactive). This keeps the no-scheduler property.

- **`GET /status` (app.py:503-513) gains four keys**, defaulted from `meta`:
  `turn` (default `"reviewer"`), `turn_updated` (default `0`), `handoff` (default `null`/absent),
  `agent_status` (default `null`/absent - its **absence** is the "parked, not yet claimed" signal the
  viewer relies on). This is the only change to an existing handler; it is purely additive (new keys,
  no removed keys), so MCP `get_status` (which proxies `/status` verbatim, mcp_server.py:363-364) and
  every existing poller keep working with no reconnect.

- **No change to `summary()`/`list_reviews()` (app.py:127-155).** The brief's find-work loop polls
  `GET /api/reviews`, whose per-review payload is `summary(rid)` = `dict(meta(rid))` plus derived
  counts - so the new `meta.json` keys (`turn`, `agent_status`, …) **already flow through**
  `list_reviews()` for free, because `summary()` copies the whole meta dict. The agent filters that
  list by `turn == agent` client-side. No server work is needed here; this is called out so MR-051
  does not redundantly touch `summary()`. **(Verify in MR-051's curl round-trip that `GET
  /api/reviews` shows `turn` on the test review.)**

### UI (`viewer.html` / `dashboard.html` / `static/`)

All UI work is in **`viewer.html`** (no new served file, no `static/` asset, no dashboard change).
Because `viewer.html` is already named in `Dockerfile:8` (`COPY app.py viewer.html dashboard.html
./`), footgun #9 (new served file needs a Dockerfile COPY) **does not apply** to this epic - there is
nothing new to add to the image manifest. State this in MR-052 so a reviewer does not flag a missing
COPY.

- **Send button** in the existing toolbar/dock row next to History (`#histbtn`, viewer.html:175 in the
  `#dockbar` at viewer.html:171-176). Give it a stable class for render-smoke (e.g.
  `class="btn sendagent" id="sendbtn"`). Enabled only while `turn == "reviewer"`; on click `POST
  /handoff {to:"agent"}`, then disable and relabel ("Sent - agent's turn"). Re-enable when a later
  poll sees `turn` back to `reviewer`.

- **Status banner** - a thin bar rendered under the top bar (insert after `#docmeta`,
  viewer.html:160, or as a fixed bar; give it a stable class e.g. `class="turnbanner"
  id="turnbanner"` so render-smoke can assert it by `.turnbanner`). It is a **first-match decision**,
  agent rows keyed on `turn == "agent"`, reviewer rows on `agent_status.state`, so no row shadows
  another:
  1. `turn=agent`, `agent_status` **absent** → "Sent - waiting for an agent to pick this up." (parked)
  2. `turn=agent`, `agent_status.at` **recent** → "Agent is working on your feedback…"
  3. `turn=agent`, `agent_status.at` **stale** (`now - at > N`, default N ≈ 3 min) → "Agent may have stopped - Take back the turn?"
  4. `turn=reviewer`, `agent_status.state="done"` → "Agent updated the draft: «message». Your turn."
  5. `turn=reviewer`, `agent_status.state="blocked"` → "Agent needs you: «message»."
  6. `turn=reviewer`, otherwise (no/cleared `agent_status`) → "Your turn. Comment, then Send to agent."

- **Take back the turn** control - shown whenever `turn == "agent"` (rows 1–3), always clickable;
  on click `POST /handoff {to:"reviewer", by:"reviewer"}`. Give it a stable class (e.g.
  `class="btn reclaim" id="reclaimbtn"`). Render-smoke asserts presence; the staleness/visibility
  toggling is exercised by the CDP interaction check, not by render-smoke (a flat node counter).

- **Poll extension** - the 2s poll (viewer.html:595-607) gains a `lastTurn` alongside `lastSrc`
  (203) / `lastCmt` (204). **Ordering rule (load-bearing):** line 603's source branch calls
  `load()`, and `load()` re-fetches `/status` and overwrites `lastSrc` (viewer.html:318-321) - it does
  **not** set `lastSrc` inline in the poll. So when one tick sees **both** a source push and a turn
  flip, render the doc reload first (`await load()` - which resets `lastSrc` from a fresh `/status`),
  then update the banner from a `/status` body, so the "Draft updated by AI" toast (viewer.html:603)
  and the banner do not race. Update `lastTurn` from the same `/status` read used for the banner. The
  banner update must also run on a turn-only tick (turn flipped, no source change), so add a
  `s.turn !== lastTurn` branch to the poll's `if/else` chain. **The poll already early-returns during
  an in-progress comment gesture (viewer.html:600)** - the banner simply updates on the next tick;
  that is acceptable (the banner is persistent state, not a transient event).

- **Banner state is derived purely from the `/status` body** the poll already fetches
  (viewer.html:602) - no new fetch, no new endpoint call on the hot path. `boot()`/`load()` should
  set the banner once on first load too (call the banner-render from `load()` after it sets
  `lastSrc`/`lastCmt`, viewer.html:321, using the `/status` body it already has).

### Agent surface (`mcp_server.py` + `CLAUDE.md`)

- **One new MCP tool** `hand_back(document_id, message, state?)` mapping to `POST /handoff
  {to:"reviewer", state, message}` (state defaults to `"done"`). Add it to the `TOOLS` list
  (mcp_server.py:67-272, place it adjacent to the comment tools) and a `route()` arm
  (mcp_server.py:349-407, before the `return None`). The `working` lease ping is **also** reachable
  via `hand_back`'s sibling: the brief's loop needs a `working` claim too - expose it either as a
  second tool (`claim_turn`/`ping_working`) or as a `state:"working"` mode of a single
  handoff tool. **(Open question Q2 below: is the lease-ping a second tool, or a mode of `hand_back`?
  Default: a second tool `take_turn(document_id, message?, owner)` → `POST /handoff
  {state:"working", owner, message}`, because overloading `hand_back` with a non-hand-back mode is
  confusing in the tool description.)**
- **`get_status` already proxies `/status` verbatim** (mcp_server.py:363-364), so the new `turn`/
  `agent_status` fields flow through with **no code change and no reconnect** - confirm this in the
  MR-053 smoke, do not re-implement it.
- **`mcp_smoke.py`** must add coverage for the new tool(s): list shows them, a call round-trips
  through a running service. Adding a tool changes the `tools_hash` (mcp_server.py:275-283), so
  `python3 mcp_server.py --print-version` will report a new hash - that is expected.
- **`CLAUDE.md` agent-contract note** documents: the find-work loop (poll `GET /api/reviews`, take
  owned reviews with `turn == agent`); the lease-heartbeat obligation (periodic `working` ping while
  holding the turn); the **blocked** convention (a comment **reply** + `hand_back state:blocked`,
  never `reopen` - reopen is the reviewer's UI action, deliberately not an MCP tool); and **the
  reconnect requirement** to pick up the new tool (the stdio server loads its tool list at startup;
  a render/HTTP change needs no reconnect, but a new tool does).

## Rollout phases

Deliver in **three dependency-ordered chunks** (explicit product-owner request, approved in the
brief). **Chunk 1 ships first to its own PR**; Chunks 2 and 3 depend on Chunk 1 and are parallel to
each other. **Sprint plan: sprint-14 = MR-051 (Chunk 1) only.** MR-052 and MR-053 are scheduled into
the **next sprint(s) after Chunk 1 ships** - they are not committed to sprint-14. This is the chunked
delivery the owner asked for, made explicit so the cycle does not bundle all three into one sprint.

### Phase 1 - Server: the baton contract (Chunk 1 → MR-051, sprint-14)

The foundation and the only chunk in sprint-14. The four `meta.json` fields, the `POST /handoff`
route with its four guarded body forms under `_lock`, and the four added `/status` keys. Additive and
backward-compatible - it ships **invisibly** (no UI, no behaviour change to existing flows). Once this
PR lands, the baton contract exists server-side and Chunks 2 and 3 can be built against it in parallel.

### Phase 2 - Viewer: the turn UI (Chunk 2 → MR-052, depends on MR-051)

The Send button, the 6-state first-match banner, the always-available reclaim control, and the 2s
poll's `lastTurn` + source-push-then-banner ordering rule. `viewer.html` only. Scheduled into the
sprint after sprint-14.

### Phase 3 - Agent surface: MCP tool + contract (Chunk 3 → MR-053, depends on MR-051, parallel to MR-052)

The new MCP tool(s) (`hand_back` + the `working` lease ping), the `get_status` passthrough
confirmation, the `mcp_smoke.py` coverage, and the `CLAUDE.md` agent-contract note. Scheduled into
the sprint after sprint-14, alongside MR-052 (no dependency between MR-052 and MR-053).

## Non-goals

Explicit scope boundaries (all locked in the brief - recorded here as fixed constraints, not open
forks):

- **No daemon / summoner / session registry.** Fork A is a pull baton on the broker; "Send to agent"
  reaches an attending-or-next-attending agent, it does not wake a dead session.
- **No background sweep / scheduler.** Reclaim is viewer-side only (interactive); the server runs no
  timer. Staleness is computed in the viewer from `agent_status.at`, never server-side.
- **No server-enforced single-writer.** The lease `owner` is a **cooperative** compare-and-claim;
  `PUT /source` is **not** gated. Single-writer is honest only under "one agent per review" (v1).
  Server-enforced single-writer is a v2 step, out of scope here.
- **No free-text handoff box.** The open comments are the message; `{to:agent}` is a pure baton flip
  (no `handoff.message`).
- **No concurrent co-editing (OT/CRDT).** `PUT /source` stays last-writer-wins whole-document
  overwrite. Deferred as GitHub issue #16.
- **No server-enforced ownership.** `project`/`session`/`source_path` are optional, default `""`, no
  uniqueness; cross-session pickup is a provenance/tag **convention**. Overlapping tags degrade to
  the case-2 lease (one wins `owner`, the other backs off), not to a clobber.
- **No WebSocket/SSE, no `queue.json`, no new storage file.** The baton is the depth-1 queue; the
  existing list endpoint is the fleet queue.
- **No auth.** The service has none by design; `/handoff` is the first control-flow surface - when
  auth lands it must cover `/handoff` first (logged as a risk, not built here).
- **No dashboard (`dashboard.html`) change.** The turn surface is the viewer only in v1.

## Key constraints

Hard repo rules this epic must not violate (made specific to this work):

- **Stdlib-only, zero pip, no new dependency.** Every chunk is pure stdlib Python / vanilla JS. No
  library is tempting here; nothing is vendored into `static/`. The "no scheduler" property is
  preserved because staleness is viewer-computed and reclaim is interactive.
- **Single-file regex router.** The new route is a new `re.fullmatch` arm placed after the `/status`
  arm (app.py:503) and before `/history` (app.py:515); it is a distinct literal segment that cannot
  shadow or be shadowed by an existing route. No existing arm moves.
- **`/handoff` takes `_lock` itself; never call bare `bump()`.** `bump()` (app.py:120-124) is an
  unlocked read-modify-write that assumes the caller holds `_lock`; `/handoff` is a guarded
  read-check-write of shared control state, so it must `with _lock:` read → decide → write `meta.json`
  once. (Mirror the `PUT /source` lock discipline at app.py:475-478, which holds `_lock` across
  `snapshot_round` + write + `bump`.)
- **Overwrite-based JSON storage under `_lock`.** `meta.json` is rewritten whole; `_write` (app.py:111)
  truncates. The handler must read the current full meta, mutate, and write the full dict back - never
  a partial merge that drops existing keys.
- **`meta.json` back-compat.** Existing on-disk reviews have **no** `turn`/`agent_status`. Every
  reader (`/handoff` decision logic, `/status`, the viewer banner) defaults a missing key:
  `turn` absent ⇒ `reviewer`; `agent_status` absent ⇒ parked-or-never-handed-off. New POST fields are
  optional. This is the additive-default-safe rule (footgun #3, #8).
- **No new served file ⇒ no Dockerfile COPY needed.** MR-052 edits `viewer.html`, already in
  `Dockerfile:8`. No `static/` asset is added. Footgun #9 does not bite - state this in MR-052 so a
  reviewer does not flag a phantom missing COPY.
- **MCP tool addition requires a client reconnect.** MR-053 adds a tool to `mcp_server.py`; the stdio
  server loads its tool list at startup, so a human/CI must reconnect the MCP client to pick it up
  (and the `tools_hash` at mcp_server.py:275-283 will change). Pure HTTP/render changes (MR-051,
  MR-052) need **no** reconnect. Document the reconnect in `CLAUDE.md` (per the brief).
- **Validation gate is `python3 -m py_compile app.py`** (+ for MR-052, `scripts/render-smoke.sh` from
  the rebuilt image; for MR-053, `mcp_smoke.py` + `python3 -m py_compile mcp_server.py`). No test
  framework.
- **render-smoke selectors are flat** (`tag`, `.class`, `tag.class[.class…]`, `#id`) - **no attribute
  selectors, no descendant combinators**. Assert the Send button and banner by **class/tag/id**
  (`.sendagent`, `.turnbanner`, `.reclaim`), never `[data-act=…]` or `#dockbar .sendagent`. A 200 is
  not a render.
- **Local instance is on port 8139; never `docker compose up` (it binds 8137).** All smokes run
  against a **throwaway** container on a scratch port (e.g. 8155), never the live 8139 instance and
  never the compose 8137.
- **Dates `Europe/London`; commits keep the `Co-Authored-By: Claude` trailer and reference the
  ticket ID.**

## Preferred execution order

1. **MR-051 (Chunk 1, sprint-14)** - the server baton contract. Must land and ship to its own PR
   before MR-052/MR-053 begin (both depend on the `/handoff` route + `/status` fields existing).
2. **MR-052 (Chunk 2)** and **MR-053 (Chunk 3)** - parallelizable after MR-051 ships, in the sprint
   after sprint-14. MR-052 (viewer) and MR-053 (MCP + docs) have no dependency on each other. If
   sequencing one first, do **MR-053** slightly ahead so the `CLAUDE.md` contract and the
   `hand_back` tool are ready for an agent to exercise the MR-052 UI end-to-end, but this is a
   preference, not a hard dependency.

## Ticket breakdown

Create these in `tickets/` only after G1 passes, then link them here. IDs are the next free
sequential IDs (highest existing is MR-050).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-051 | Handoff baton contract: `POST /handoff` + 4 `meta.json` fields + `/status` surfacing | svc | 1 |
| MR-052 | Viewer turn UI: Send button + 6-state banner + reclaim + `lastTurn` poll | ui | 2 |
| MR-053 | Agent surface: `hand_back` MCP tool + lease-ping + `CLAUDE.md` contract note | svc/docs | 3 |

Dependencies: MR-052 `depends_on: [MR-051]`; MR-053 `depends_on: [MR-051]`; MR-052 ∥ MR-053.
Sprint membership: **sprint-14 = {MR-051}**; MR-052 and MR-053 are committed to the next sprint after
Chunk 1 ships.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Liveness** - "Send to agent" reaches nothing if no agent ever runs. | Locked design: the baton **parks** durably (`turn=agent`, `agent_status` absent → banner row 1), a later agent picks it from the work-list, and the reviewer can always reclaim. Banner row 1 tells the human it parked. (Attending badge + push notification are v2.) |
| **No auth on the first control-flow surface.** Any URL-holder can seize the turn or spam an agent loop; CSRF-able if proxied. | Documented honest risk (matches the brief). v1 ships on the no-auth service by design; **when auth lands it must cover `/handoff` first.** No auth is built in this epic. |
| **Concurrency on shared `turn`/`owner`.** Two writers race the baton. | The turn flip is safe: `/handoff` does a guarded read-check-write under `_lock`. Single-**writer** of `source.md` is **cooperative** (lease `owner` back-off), not server-enforced - honest only under one-agent-per-review (v1). The lease `409`-on-foreign-owner is exercised in the MR-051 smoke. |
| **Double-notify** - `source_updated` already toasts; the banner could fight the toast on a combined tick. | The ordering rule (render doc reload via `load()` first → then banner from the same `/status` body) keeps the transient toast and the persistent banner from racing. Exercised by the MR-052 CDP interaction check (Send → working → reclaim → your-turn). |
| **Banner row shadowing.** A later row masks an earlier state. | First-match decision with agent rows keyed on `turn==agent` and reviewer rows on `agent_status.state` - verified row-by-row in the MR-052 interaction check, not by static markup. |
| **Legacy `meta.json` with no `turn`.** A pre-epic review breaks the banner or the handler. | Every reader defaults a missing key (`turn` ⇒ `reviewer`, `agent_status` ⇒ parked/absent). MR-051's smoke includes a review created **before** any handoff call (default state) to prove the default path. |
| **MCP staleness** - MR-053's new tool invisible until reconnect. | `CLAUDE.md` documents the reconnect; `server_info`/`--print-version` `tools_hash` change is the signal. MR-053's Work log notes the reconnect obligation explicitly. |

## Verification

Each chunk's evidence below becomes that ticket's G4 (review) / G7 (sprint-close) evidence. All
smokes run against a **throwaway container on a scratch port** (e.g. 8155), never the live 8139
instance and never `docker compose up` (8137).

### MR-051 (svc) - `py_compile` + a curl round-trip

Gate: `python3 -m py_compile app.py`. Then, on a throwaway container, a single round-trip proving
every body form and the lease back-off (replace `$B` with the scratch base URL, `$ID` with the
created review id):

```bash
# create a review (default state: no turn yet -> /status must show turn "reviewer")
ID=$(curl -s -X POST "$B/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"baton smoke","markdown":"# x\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s "$B/api/reviews/$ID/status"     # expect turn=="reviewer", agent_status absent/null (legacy default)

# 1. viewer flip {to:agent}: turn flips to agent, turn_updated bumps, agent_status cleared/absent
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'
#    -> turn=="agent"; record turn_updated (T1)

# 2. owner A claims the lease {state:working}: agent_status.owner set, agent_status.at set,
#    turn_updated UNCHANGED (still T1)
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' \
  -d '{"state":"working","owner":"sess-A","message":"on it"}'
#    -> agent_status.owner=="sess-A", agent_status.at>0, turn_updated==T1

# 3. a DIFFERENT owner B claims {state:working}: rejected (409) / backs off, owner stays sess-A
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$B/api/reviews/$ID/handoff" \
  -H 'Content-Type: application/json' -d '{"state":"working","owner":"sess-B"}'
#    -> 409 (lease held); GET shows agent_status.owner still "sess-A"

# 4. hand back {to:reviewer,state:done,message}: turn flips to reviewer, turn_updated bumps (T2>T1)
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' \
  -d '{"to":"reviewer","state":"done","message":"revised section 3"}'
#    -> turn=="reviewer", agent_status.state=="done", turn_updated==T2 (> T1)

# 5. re-flip to agent, then reclaim {to:reviewer,by:reviewer}: forces turn=reviewer, turn_updated bumps
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' \
  -d '{"to":"reviewer","by":"reviewer"}'
#    -> turn=="reviewer", turn_updated bumped again

# 6. idempotency: {to:agent} twice does not re-bump turn_updated on the second (already-agent) call
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'   # flips, bumps
T=$(curl -s "$B/api/reviews/$ID/status" | python3 -c 'import sys,json;print(json.load(sys.stdin)["turn_updated"])')
curl -s -X POST "$B/api/reviews/$ID/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'   # no-op 200
curl -s "$B/api/reviews/$ID/status"     # expect turn_updated == $T (unchanged)

# 7. surfacing: GET /status shows turn, turn_updated, handoff, agent_status; GET /api/reviews shows turn
curl -s "$B/api/reviews/$ID/status"     # all four new keys present
curl -s "$B/api/reviews" | python3 -c 'import sys,json;print([r.get("turn") for r in json.load(sys.stdin)["reviews"]])'
```

Pass: every numbered expectation holds; existing endpoints (`GET /api/reviews`, `GET /status`,
`PUT /source`) still respond unchanged for a review that never touches `/handoff`.

### MR-052 (ui) - render-smoke (rebuilt image) + node-CDP interaction + browser render

Gate (G4): rebuild the throwaway container, then assert the new DOM nodes by **class/tag/id**
(render-smoke is a flat node counter; a 200 is not a render):

```bash
# rebuild + run on a scratch port, create a review, open its viewer URL, assert the new nodes
scripts/render-smoke.sh "$B/review/$ID" '.sendagent' '.turnbanner' '.reclaim'
#   -> exit 0: Send button, banner, and reclaim control all rendered (>=1 each)
```

Then a **node-CDP interaction check** following the repo's existing pattern (`agent_smoke.py` /
MR-049): drive the rendered page to prove the state machine, not just node presence -
(a) initial `turn=reviewer`: Send enabled, banner shows row 6 ("Your turn…");
(b) click Send → `POST /handoff {to:agent}` fires, banner moves to row 1 ("waiting…") then, after a
scripted `{state:working}` POST, row 2 ("Agent is working…"); Send is disabled;
(c) click reclaim → `POST /handoff {to:reviewer,by:reviewer}`, banner returns to a reviewer row, Send
re-enables;
(d) push a `{to:reviewer,state:done,message}` and confirm row 4 ("Agent updated the draft… Your
turn.") renders and the source-push toast does not clobber it (the ordering rule).
Plus a screenshot under `reviews/sprint-NN-render-evidence-*` per G7 (a product page was touched).
**Theme note:** if any banner styling is pane-adaptive (`@media (prefers-color-scheme)`), capture
both panes with `--blink-settings=preferredColorScheme=0` (dark) / `=1` (light) or CDP
`Emulation.setEmulatedMedia` - **never `--force-dark-mode`** (that is Chrome's auto-invert, not
scheme emulation, and bare headless resolves dark by default).

### MR-053 (svc/docs) - `mcp_smoke.py` + `py_compile`, with the reconnect noted

Gate: `python3 -m py_compile mcp_server.py`, then `mcp_smoke.py` against a throwaway service:

```bash
MDREVIEW_BASE="$B" python3 mcp_smoke.py     # exit 0; the new tool(s) appear in tools/list and round-trip
python3 mcp_server.py --print-version        # tools_hash CHANGED vs the pre-MR-053 value (expected; new tool)
```

The smoke must show: `tools/list` includes `hand_back` (and the lease-ping tool); a `hand_back` call
hits `POST /handoff {to:reviewer}` and flips `turn`; `get_status` (unchanged code) returns the new
`turn`/`agent_status` fields - proving the **passthrough needs no reconnect** while the **new tool
does** (the stdio server loads its tool list at startup). MR-053's Work log records the reconnect
obligation, and `CLAUDE.md` documents it for agents.

## Assumptions and open questions

The design is **locked** (product-owner sign-off, mdreview `ff60fa640e`), so the load-bearing product
forks (Fork A, one-agent-per-review, interactive/no-sweep, no-free-text-box, co-editing deferred to
issue #16) are **fixed constraints, not open questions** - they appear in Non-goals, not here. What
remains are small **implementation** clarifications with safe defaults; none is a BLOCKER-FOR-HUMAN
(no product-fork-with-no-safe-default).

- **Q1 (minor) - Where does the lease `owner` id come from?** Assumption: **client-supplied** in the
  `{state:"working", owner:"…"}` body; the server never mints identity (the service has no session
  concept). Justification: the brief says "opaque id of the agent holding the lease (set on first
  ping)" and mdreview has no auth/session to derive an id from. An absent `owner` on a `working`
  claim is accepted as an unowned claim (recorded as sent). Safe default; does not change the design.
- **Q2 (minor) - Is the `working` lease ping a second MCP tool or a mode of `hand_back`?** Assumption:
  a **separate tool** (e.g. `take_turn(document_id, message?, owner)` → `POST /handoff
  {state:"working"}`), because overloading `hand_back` (whose name and description say "hand the turn
  back to the reviewer") with a non-hand-back "claim/renew the lease" mode is misleading to a tool-
  selecting agent. Justification: clearer tool semantics; the brief names `hand_back` explicitly and
  separately mentions "the `working` lease ping". Either is buildable; this is an MR-053 detail, not a
  design fork. The owner can collapse them at ticket-grooming if preferred.
- **Q3 (minor) - Staleness threshold N.** Assumption: viewer-side constant, default **~3 min**
  (matches the brief's "> N min, default ~3"). Tunable in `viewer.html`; no server involvement.
  Safe default.
- **Q4 (minor) - `409` vs `200`-with-`backed_off` for the foreign-owner lease claim.** Assumption:
  return **`409`** with `{"error":"lease held","owner":...}` so the second agent's HTTP layer (and
  `mcp_server.py`'s `http()` which raises `ToolError` on non-2xx, mcp_server.py:342-344) surfaces the
  back-off explicitly. Justification: an HTTP error is the cleanest "back off" signal and matches the
  existing `409` convention for illegal comment transitions (app.py:337-338). The agent treats a
  `409` on a `working` claim as "another agent owns this - skip it." Safe default; revisit at grooming
  if a soft `200` is preferred.

No load-bearing open questions remain and there is **no BLOCKER-FOR-HUMAN**: every fork above has a
safe default that does not waste a sprint, and the product-level decisions were resolved in the
approved brief.
