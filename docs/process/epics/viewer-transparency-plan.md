---
epic: viewer-transparency
status: active          # draft | active | done  (stays draft until G1 passes)
created: 2026-06-24
source: docs/process/requirements/viewer-transparency.md
gate: passed 2026-06-24    # G1 (Plan Gate): not passed | passed YYYY-MM-DD — tickets blocked until passed
review: reviews/viewer-transparency-plan-review-2026-06-24.md
related_sprints: [sprint-26]    # [sprint-26]
related_tickets: [MR-073, MR-075]    # empty until G1 passes and tickets are created
---

# Viewer agent-turn transparency Plan

While an agent works a review turn, the viewer shows a single static "Agent is working on your
feedback…" line for the whole run. A real multi-step task (the trigger: a doc-wide rename across
prose + a Mermaid diagram, ~2.5 minutes) is therefore indistinguishable from a hung agent — the
owner watched a healthy run and could not tell it from a freeze. This epic replaces the single line
with a **live, behind-the-scenes progress timeline** that maps to the real backend steps the service
already observes (connected → reading → editing → resolving → done, or stopped/error), plus a **live
elapsed timer** while the agent works and the **total revision duration** on completion, with the same
liveness and error treatment already shipped for the crash and pickup-timeout cases. The headline
value — a slow-but-working run reads as progress and a stalled one is visibly stalled — is reachable
**entirely from signals the viewer already polls**, with no new agent instrumentation and no new API.

**Source requirement:** [`requirements/viewer-transparency.md`](../requirements/viewer-transparency.md)
— the original brief, kept verbatim, plus the 2026-06-24 **Amendments** entry adding an
elapsed/duration timer (folded into MR-073). GitHub issue #27.

## Product goal

A reviewer watching the working banner sees a live, ordered timeline of what the agent is doing
*right now* — not a static label — with a ticking elapsed timer ("Agent is working… 0:47") and, on
completion, the total time the revision took ("Agent revised in 2:14. Your turn."). A long-but-healthy
run reads as forward motion; a stalled or crashed run is visibly distinct from a working one, surfaced
as it happens (no agent picked it up, agent run stopped, agent needs you). The reviewer never again
has to guess "is it working or hung?" — or "how long did that take?" — from an unmoving banner.

## Core design principle

**Derive the timeline from the coarse signals the service already exposes; do not make the agent
self-report, and do not add a new API unless a measured need forces it.** The agent is a black-box
`claude -p` process in a separate container — but the service already records, on every `/status`
poll the viewer runs, the exact transition timestamps that *are* the agent's steps: the lease claim
(`agent_status.state == "working"`), the document edit (`source_updated` bump), the comment
resolution (`comments_updated` bump), and the hand-back (`agent_status.state == "done"/"blocked"`).
The timeline is a **viewer-side reduction of these four monotonic timestamps plus the turn/state**,
re-evaluated on the existing 2-second poll tick. This is robust (no reliance on the agent calling
anything new), cheap (zero new service surface for Tier-1), and additive-default-safe (a legacy
review with no `agent_status` reads exactly as today).

The **timer** follows the same principle. The live elapsed value is trivially derivable from the
existing body — `now - turn_updated` while `turn=="agent"` and `state=="working"` (`turn_updated` is
the Send/flip time, `app.py:636`) — and needs no new data. The **final duration** is the one place the
derived-signal approach has a gap, called out explicitly below: `turn_updated` is **bumped again on
hand_back** (`app.py:629`), so the start time is gone from `/status` at the exact moment you'd show
the total. This is resolved **client-side** (the viewer remembers when it first observed
`turn=="agent"` for this review and computes the delta when it observes `done`) — no service change,
correct for the live-watching use case — at the cost of one limitation (a page loaded *after* `done`
cannot know the start, so it shows no final duration). The live timer always works. See the timer
design note under UI.

## Recommended approach

The load-bearing fork in the brief — **how does the viewer learn the agent's real-time steps?** — is
resolved in favour of **(A), derived signals, as the shipping tier**, with **(C), real stream-json
events, scoped as a deferred Tier-2 follow-on** that this epic does not ship. The reasoning is
verified against the code, not asserted:

### The fork, resolved (A vs B vs C)

| Option | What it needs | Verified against | Verdict |
|--------|---------------|------------------|---------|
| **(A) Derive from `/status` signals** | viewer-side reduction of `turn`, `agent_status.state`, `turn_updated`, `source_updated`, `comments_updated` (+ `at`). Optional tiny `svc` add of a coarse `phase` string on `agent_status`. | `app.py:589-598` (the `/status` body already returns **all** of these), `app.py:660-664` (claim sets `state:"working"`), `app.py:623-629` (hand_back sets `done`/`blocked`), `app.py:553-558` (PUT /source bumps `source_updated`), `app.py:751/771/790` (comment ops bump `comments_updated`). | **SHIP (Tier-1).** Every signal the timeline needs is already in the body the viewer polls every 2s (`viewer.html:686`). No new API. |
| **(B) `ping_working` carries a status string** | the agent prompt instructs `ping_working(message="reading comments")` etc.; the banner shows it. | `mcp_server.py:453-456` (`ping_working` **already** forwards `message`), `app.py:661` (the claim/renew write **already** persists `message` into `agent_status`), `viewer.html:243/279` (the banner already reads `agent_status` but does **not** surface `.message` in the working arm). | **PARTIAL, opportunistic.** The plumbing already exists end-to-end; the only gap is the viewer not displaying `agent_status.message` in the working state. Tier-1 **surfaces this message when present** as a free enrichment of the derived timeline, but does **not** depend on it (agent-dependent: it must call ping with a message, costing tokens/latency, and most prompts won't). It decorates, never gates. |
| **(C) Wrapper parses `claude -p --output-format stream-json`** | switch `watch.py`'s `Popen` to capture **stdout**, parse the NDJSON event stream (`tool_use`/`text`/`result`) in a reader thread, POST each to a **new** `/api/reviews/{id}/events` endpoint with a **new persisted event store**; the viewer streams/polls and renders. | `claude --help` **confirms** `--output-format stream-json` is real ("realtime streaming", requires `--print` + `--verbose`). `watch.py:504` currently spawns `Popen(argv, stderr=errf)` and **does not touch stdout** — so the stream is available but unparsed today. | **DEFER (Tier-2, out of this epic).** Technically feasible and maps to *actual* tool calls, but costs a new persisted store (violates the prefer-no-new-meta-key constraint), a new event API, a real protocol parser in the credentialed spawner, and a fragile coupling to Claude's event schema. YAGNI: (A) already gives the owner the asked-for "is it working or hung" answer. Pinned as a follow-on the epic explicitly does not build. |

**`claude stream-json` is real** — `claude --help` lists `--output-format` choices `text | json |
stream-json` with stream-json described as "realtime streaming" and only valid with `--print`
(`-p`); the help also notes streaming output "only works with --output-format=stream-json" and
pairs with `--verbose`. So (C) is not blocked by a missing feature; it is deferred on cost/value,
not feasibility.

### The four signals → timeline steps (the Tier-1 mapping)

The viewer reduces the `/status` body to an ordered step list. The mapping, every cell verified
against `app.py`:

| Timeline step | Derived from | `app.py` evidence |
|---------------|--------------|-------------------|
| **Sent / waiting for pickup** | `turn=="agent"` AND `agent_status==null`, within `PICKUP_GRACE_S` | already rendered by MR-062/066 (`viewer.html:249-257`) — keep |
| **No agent picked this up** | `turn=="agent"` AND `agent_status==null`, past `PICKUP_GRACE_S` | already rendered by MR-066 (`viewer.html:253-254`) — keep |
| **Connected — reading your comments** | `agent_status.state=="working"` first observed (the lease claim). "Reading" is the **resting label** of this step — it is NOT independently derivable (a read is a GET that bumps nothing), so it is **merged into claimed**, not shown as its own timed step. | `app.py:660-664` writes `state:"working"` on a granted claim; no `/status` signal marks "reading" |
| **Editing the draft** | `source_updated` increased since the turn began (`> turn_updated`) | `app.py:553-558` bumps `source_updated` on PUT /source |
| **Updating comments** (signal-honest label; NOT "Resolving") | `comments_updated` increased since the turn began (`> turn_updated`) — covers reply/resolve/reopen/create/delete, not resolve alone | `app.py:751,771,790` bump `comments_updated` on **create/delete/reply/resolve/reopen** |
| **Resolved comments** (only when finished) | the **Updating-comments** step is relabelled "Resolved comments" **only** if the terminal state is `done`; on `blocked` ("Agent needs you") it stays "Updating comments" | terminal `state=="done"` (`app.py:623-629`) is the only honest "resolved" signal |
| **(optional) live status line** | `agent_status.message` non-empty (option B decoration) | `app.py:661` persists `message`; `mcp_server.py:454-456` forwards it |
| **Live elapsed timer** | `turn=="agent"` AND `state=="working"`: `elapsed = now - turn_updated` | `app.py:636` sets `turn_updated` on the reviewer→agent flip (the Send time) |
| **Final revision duration** | on `done`: `now_observed_done - firstSeenAgentAt` (client-captured start; see timer note) | start NOT recoverable from `/status` — `app.py:629` re-bumps `turn_updated` on hand_back |
| **Done — draft updated** | `turn=="reviewer"` AND `agent_status.state=="done"` | already rendered by MR-052 (`viewer.html:265`) — keep |
| **Agent run stopped** | `state=="blocked"` AND message starts `"agent process exited"` | already rendered by MR-068 (`viewer.html:269-270`) — keep |
| **Agent needs you** | `state=="blocked"`, other message | already rendered (`viewer.html:272`) — keep |
| **May have stopped (stale lease)** | `agent_status.at` older than `STALE_S` | already rendered by MR-066 (`viewer.html:259`) — keep |

The new work is the **middle three rows** (connected-reading / editing / updating-comments) and
assembling all rows into a *cumulative, ordered, live* timeline rather than one mutually-exclusive
line. Two signal-honesty rules are load-bearing and called out above: (1) `comments_updated` is
**not** resolve-specific — it bumps on reply/reopen/create/delete too (`app.py:751/771/790`) — so the
step is labelled "Updating comments", and the literal word "Resolved" appears **only** on terminal
`done`, never on a turn where the agent merely posted a clarifying reply then handed back `blocked`;
(2) "reading" has **no** derivable signal (a read is a GET that bumps nothing), so it is the resting
label of the claimed step, not a fake timed step. The first/last
rows are MR-062/066/067/068 behaviour the timeline **wraps and preserves**, never re-implements.

### Service (`app.py`)

- **Tier-1 needs no service change.** Every field is already in the `/status` body (`app.py:589-598`).
  This is the central, deliberate outcome of resolving the fork toward (A).
- **One optional, small, default-safe `svc` add (MR-074, may be dropped at G2 if judged unneeded):**
  a coarse `phase` hint on the working-state `agent_status` so the agent *can* (but need not) label
  its current step richer than the derived guess. Shape: reuse the **existing** `message` field —
  it already round-trips through `ping_working` → `app.py:661` → `/status` — so **no new meta key is
  added**. The service change, if any, is only to *document and lightly validate* that `message` is a
  short status string and to ensure it is returned in the working arm (it already is). Persistence:
  none beyond the existing `agent_status` object in `meta.json` (overwritten each ping, never
  appended — correct for a "current step" hint, no history needed). If review concludes the derived
  timeline (A) plus the already-surfaced `message` (B) suffice with zero `svc` edits, **MR-074 is
  cut** and the epic is UI-only. Default assumption: cut it; see Assumptions.

### UI (`viewer.html`)

- **Extend `renderBanner(st)` (`viewer.html:241`) into a timeline renderer**, riding the **same 2s
  poll** (`viewer.html:679-696`) that already calls it. The banner element (`#turnbanner` /
  `#turntext`, `viewer.html:177`) gains a child timeline container (`#turnsteps`) holding an ordered
  list of step nodes; `renderBanner` computes which steps are *done*, which is *active* (the live
  one), and which are *pending*, from the signal mapping above. Steps, in order: **Connected — reading
  your comments** → **Editing the draft** → **Updating comments** → terminal.
- **Signal-honest labels (load-bearing).** Two labels must not over-claim their signal:
  - The comment-activity step is labelled **"Updating comments"** (or "Commenting"), **not
    "Resolving"** — because `comments_updated` bumps on reply/reopen/create/delete as well as resolve
    (`app.py:751/771/790`). It is relabelled **"Resolved comments"** *only* when the terminal state is
    `done` (the agent actually finished). On the `blocked` / "Agent needs you" path — e.g. the agent
    posts a clarifying **reply** then hand_backs `blocked` — the step stays "Updating comments" and the
    word "resolved" must **never** appear (nothing was resolved that turn).
  - **"Reading" is a resting label, not a signal.** A read is a GET that bumps nothing in `/status`,
    so there is no derivable "reading" event. It is folded into the post-claim step as its resting
    text ("Connected — reading your comments"), representing the brief's *reading* stage without
    inventing a fake signal or a separately-timed step.
- **Track per-turn baselines in module state.** On a `turn_updated` change (a new turn began), capture
  the baseline `source_updated`/`comments_updated` so the "editing"/"updating comments" steps fire on
  an increase *within this turn*, not a stale bump from a prior round. This mirrors the existing `lastSrc`/`lastCmt`
  module vars (`viewer.html:221-222`) — reuse that pattern; add `turnBaseSrc`/`turnBaseCmt`/`turnStart`.
- **Liveness without a new animation.** The active step reuses the **existing** `.loading` spinner
  CSS (`viewer.html:87-89`) — already reduced-motion-safe (`@media (prefers-reduced-motion:reduce)`
  shows a static ring). Completed steps get a static check/marker; the warn/error states reuse the
  **existing** `.warn` treatment (`viewer.html:93`). No new `@keyframes`, so reduced-motion safety is
  inherited, not re-derived.
- **Surface `agent_status.message` (option B decoration)** as the active step's detail line when
  present and non-empty, set via `textContent` (the existing XSS-safe path, `viewer.html:240`).
- **Timer (folded into this ticket).** A `#turntimer` span in/near the banner.
  - **Live elapsed (while working):** while `turn=="agent"` AND `state=="working"`, show `now -
    turn_updated` formatted `M:SS` ("Agent is working… 0:47"). `turn_updated` is the Send/flip time
    (`app.py:636`). To make the *digit* tick every second (not only on the 2s poll), add a **cheap 1s
    `setInterval`** that re-renders only the timer text from the **last `/status` body already in
    module state** — it issues **no extra fetch** (it reuses the cached `turn`/`turn_updated`/`state`),
    so it is purely a local clock tick, not new polling load. Stop/no-op the tick when not in the
    working state. Reduced-motion: a 1s text update is not a CSS animation, so it is unaffected by
    `prefers-reduced-motion` (and a per-second digit is gentle, not a strobe).
  - **Final duration (on completion):** capture the start **client-side** — a module var
    `firstSeenAgentAt[reviewId]` (or a single var, one review per page) set the first poll where this
    page observes `turn=="agent"` for the review; on the poll where it observes `state=="done"`,
    compute `Date.now() - firstSeenAgentAt` and show "Agent revised in M:SS. Your turn." Chosen over a
    server-recorded duration on the YAGNI ladder: **no service change, no new persistence**, and it
    exactly fits the live-watching case the owner described (watching the run to completion).
    **Documented limitation:** a page **loaded *after* `done`** never saw `turn=="agent"`, so it has
    no start and shows the plain "Agent updated the draft. Your turn." (today's text) with **no**
    duration — acceptable, because the timer is for the person *watching* the run. The live elapsed
    timer always works regardless. A robust server-recorded duration (record elapsed at the hand_back
    arm, `app.py:623-629`) is a small additive `svc` follow-on **explicitly not taken here**; noted as
    a deferred option, not in scope.
- **Pane adaptivity is inherited** — the banner already uses `var(--*)` tokens that flip under
  `@media (prefers-color-scheme: dark)` (`viewer.html:11`). The timeline uses the same tokens; the
  validation captures **both panes** via `prefers-color-scheme` emulation (never `--force-dark-mode`).
- **Do not regress** the doc live-reload / "Draft updated by AI" toast (`viewer.html:687`) or the
  comment live-reload (`viewer.html:688`); the timeline reads the same `/status` body and must not
  change when those branches run.

## Rollout phases

Each phase is independently shippable; the epic ships Phase 1 (and possibly the trivial Phase 0
`svc` decoration). Phase 2 is named and deferred.

### Phase 1 — Tier-1 derived live timeline + timer (the headline; UI-only)
- Extend `renderBanner` into the ordered, cumulative timeline driven by the four derived signals,
  riding the existing 2s poll. Wraps and preserves MR-062/066/067/068. Surfaces `agent_status.message`
  when present. Adds the **live elapsed timer** (`now - turn_updated` while working, ticking on a cheap
  fetch-free 1s interval) and the **client-captured final revision duration** on `done`. This single
  phase fixes the "looks frozen" problem the epic was raised for and answers "how long did that take?".

### Phase 0 (optional, may be cut) — `svc` status-message contract
- If review wants the agent to be able to push a richer step label, formalise (document + light
  validate) the existing `agent_status.message` as a short status hint and confirm it is returned in
  the working arm. No new key, no new endpoint, no new persistence. Sequenced *before* Phase 1 only if
  kept (so the UI can rely on the documented contract). Default: cut.

### Phase 2 — Tier-2 real stream-json events (DEFERRED, out of this epic)
- `watch.py` captures child stdout, parses `claude -p --output-format stream-json --verbose` NDJSON
  (`tool_use`/`text`/`result`), POSTs events to a new `/api/reviews/{id}/events` store; the viewer
  renders the real tool-call stream. Named here for traceability; **not built in sprint-26**. Spun out
  to the backlog as a follow-on, gated on a measured need that Phase 1 does not already meet.

## Non-goals

- **The handoff diff (#19/#21 — "review the agent's changes" green/red).** A separate feature; the
  brief's part 3 (streamed, non-jerky `update_source`) rides on it and is explicitly out of scope here.
- **Streamed / token-level / incremental-`update_source` document rendering** (brief part 3, spectrum
  b/c). Out of scope; the timeline is about *progress visibility*, not *smoother doc swaps*.
- **Re-doing MR-062 (spinner), MR-066 (pickup cue), MR-067/068 (crash signal + watcher logging).**
  The timeline **wraps** these; it does not re-implement or alter them.
- **Tier-2 stream-json events (C).** Deferred to Phase 2 / backlog, not shipped this epic.
- **Making the agent self-report (B) a hard dependency.** The `message` is decoration, never required.
- **Aggregating timelines across reviews / any dashboard rollup.** Per-review only; no new cross-review
  exposure on the no-auth, id-only-tenancy service.

## Key constraints

Hard rules, made specific to this epic:

- **stdlib-only, zero pip.** Tier-1 adds no dependency (pure JS in `viewer.html` + CSS reuse). The
  spinner/warn CSS already exists; no new vendored asset, so **no `Dockerfile COPY` change** is
  needed (the timeline lives inside the already-copied `viewer.html`, `Dockerfile:8`). If Phase 0
  ships, it is `app.py`-only and stdlib.
- **No new persisted `meta.json` key for Tier-1.** The derived timeline is computed client-side; the
  optional Phase 0 reuses the **existing** `agent_status.message` (overwrite-based, no history),
  honouring the brief's "a progress event store must justify its persistence/shape" — Tier-1 needs no
  store at all, and that is the point.
- **Back-compat of `meta.json` / `/status`.** A legacy review with no `agent_status` (`null`) must
  render exactly as today (the existing waiting/working/parked arms). `renderBanner` already defaults
  `turn` to `"reviewer"` and treats `agent_status` null as parked (`viewer.html:242-243`); the
  timeline must keep those defaults.
- **Single-file regex router under `_lock`.** If Phase 0 touches `app.py`, it edits the existing
  `/status` GET arm (`app.py:583-598`) or the handoff lease arm (`app.py:637-664`) — it adds **no new
  route**, so there is no route-ordering/shadowing concern. Cite the line edited in the ticket.
- **JS-rendered, time-dependent surface.** A 200 is not a render, and `render-smoke.sh` **cannot**
  drive a time-dependent, signal-sequenced JS state (its flat selector matcher reads a static DOM
  once). Validation is a **node-CDP eval driver** in the `agent_smoke.py` pattern that *advances the
  review through the lifecycle and asserts the live steps over time*. See Verification.
- **Both panes via `prefers-color-scheme` emulation, never `--force-dark-mode`.** Bare headless
  Chrome resolves dark by default; capture light with `--blink-settings=preferredColorScheme=1` and
  dark with `=0` (or CDP `Emulation.setEmulatedMedia`). A no-flag "light" + `--force-dark-mode` "dark"
  proof is vacuous.
- **Reduced-motion respected.** The active-step spinner reuses the existing `.loading` rule whose
  `@media (prefers-reduced-motion:reduce)` already stops the animation; validation asserts the
  animation is suppressed under emulated reduced-motion (CDP `Emulation.setEmulatedMedia`
  `prefers-reduced-motion: reduce`, then read `getComputedStyle(...).animationName === 'none'`).
- **Header checks use GET, not HEAD.** Any AC that inspects a response header uses `curl -sD - -o
  /dev/null <url>` (a GET header-dump), never `curl -sI` (HEAD → 501 on this server). Tier-1 has no
  new served file, so this mostly bites only if Phase 2 ever lands.
- **render-smoke selectors are flat.** Where a render-smoke is used at all (first-paint of the banner
  container), assert `#turnbanner`, `#turnsteps`, and `#turntimer` as **separate** selectors, never
  `#turnbanner #turnsteps` (a space is rejected, exit 2). The *live* behaviour (step sequence, ticking
  digit, final duration) is the CDP driver's job, not render-smoke's.
- **Europe/London dates; `Co-Authored-By: Claude` trailer; `python3 -m py_compile app.py watch.py`
  gate** (watch.py compiled because Phase 2 would touch it; Tier-1 still compiles both as a cheap
  guard). UI tickets additionally owe the CDP drive.
- **Never the live `mdreview` container on :8139.** All builds/smokes run on throwaway container
  names + ports; throwaway `MDREVIEW_DATA` dirs and temp scripts go in the gitignored `.scratch/`.

## Preferred execution order

1. **MR-073 (ui, Phase 1)** — the derived live timeline + elapsed/duration timer in `renderBanner`.
   The headline; standalone, depends on nothing new. Ships the epic's value.
2. **MR-074 (svc, Phase 0, optional)** — formalise/return `agent_status.message` as a status hint.
   Only if review wants the agent-pushable label; sequence it *before* MR-073's message-decoration if
   kept, else cut at G2. Default: cut.
3. **MR-075 (docs)** — sweep `CLAUDE.md` / `README.md` / `AGENTS.md` for the new timeline behaviour
   (and, if MR-074 ships, the `message`-as-status-hint contract). Same-sprint docs-sweep; must be
   `done` before sprint-26 closes (G7).

If MR-074 is cut, the epic is MR-073 + MR-075 (a UI feature + its docs sweep).

## Ticket breakdown

Create in `tickets/` only after G1. IDs continue from MR-072 → MR-073+. Sprint: sprint-26.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-073 | Live progress timeline + elapsed/duration timer in the working banner (derived from `/status` signals) | ui | 1 |
| MR-074 | (optional) `agent_status.message` status-hint contract, returned + documented | svc | 0 |
| MR-075 | Docs sweep: timeline behaviour + (if shipped) status-hint contract | docs | 1 |

Deferred (backlog, not sprint-26): **Tier-2 stream-json events** — `watch.py` stdout parse + new
`/api/reviews/{id}/events` API + viewer event rendering (Phase 2).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| **"Editing"/"updating comments" misfires from a *stale* `source_updated`/`comments_updated` bump** carried over from a prior round (the timeline shows "editing" before the agent has edited). | Medium | Baseline `source_updated`/`comments_updated` against `turn_updated` at turn start (the per-turn-baseline state); only an increase **after** the current turn began counts. Verified in the CDP drive by asserting "editing" is absent until the PUT and present after. |
| **The comment step over-claims "Resolved" when nothing was resolved** — `comments_updated` bumps on reply/reopen/create/delete too (`app.py:751/771/790`), so an agent that posts a clarifying reply then hand_backs `blocked` ("Agent needs you") would falsely read as "resolved". | Medium | Label the step **"Updating comments"**, never "Resolving", off the raw `comments_updated` bump; show the word "Resolved" **only** when the terminal state is `done`. The CDP drive includes a **reply-then-`blocked`** path asserting the step never claims "resolved" on that turn. |
| **Steps fire out of order / one tick skips a step** (agent edits and comments between two 2s polls, so "editing" and "updating comments" both first appear on the same tick). | Medium | Design the timeline as **cumulative** (a step, once its signal has fired this turn, stays "done") rather than a single current-step pointer — so a skipped intermediate poll still shows both steps reached, not a lost one. The CDP drive asserts cumulative presence, not exact tick timing. |
| **Regressing MR-062/066/067/068** by rewriting `renderBanner`. | Medium | The timeline **wraps** the existing arms (the same `turn`/`as.state`/`at`/`turn_updated` conditions, table above), not replaces them. The CDP drive re-asserts each shipped state (pickup-timeout, stale-lease, run-stopped, agent-needs-you) still renders. |
| **Liveness invisible in a backgrounded/headless tab** (CSS animation frozen → can't prove "live"). | Medium | Per the project memory, prove liveness via computed `animationName`/`currentTime` and CDP reduced-motion stepping, **not** by screenshot/eye. The CDP driver reads `getComputedStyle(activeStep).animationName` and asserts it is the spin keyframe in the active step and `'none'` under emulated reduced-motion. |
| **Over-building toward Tier-2.** | Low (pinned) | (C) is explicitly deferred; the plan ships only derived signals. The fork is resolved on record, so the implementer does not re-litigate it. |
| **`agent_status.message` could carry agent-controlled text into the banner.** | Low | Already mitigated: the banner sets it via `textContent` (`viewer.html:240` convention), which cannot inject HTML. The timeline keeps `textContent`. No-auth/id-only tenancy is unchanged (per-review, no aggregation). |
| **Final duration lost on a page reopened after `done`** (client-captured start never observed). | Medium (accepted) | By design: the timer serves the *watcher*. A post-`done` load shows today's "draft updated" text with no duration — never a wrong number. Documented limitation, signed off in the CDP drive (assert the page-reopened-after-done case shows no bogus duration). A server-recorded duration is a deferred `svc` option, not in scope. |
| **The 1s timer interval double-polls or leaks** (a stray `setInterval` issuing fetches, or never cleared). | Low | The tick re-renders the timer text from the **cached** last `/status` body only — **no fetch** — and is a single interval guarded to no-op outside the working state. The CDP drive asserts the elapsed digit advances between two reads taken ~1s apart with the poll suppressed, proving the local clock ticks without new polling. |

## Verification

Every ticket gates on `python3 -m py_compile app.py watch.py`. The headline verification is a
**node-CDP eval driver** (the `agent_smoke.py` pattern, `agent_smoke.py:112-148`) against a **rebuilt
throwaway container** (never :8139), because the timeline is a time-dependent, signal-sequenced JS
state that `render-smoke.sh` cannot drive.

**MR-073 (ui) — the lifecycle CDP drive (new sibling, e.g. `timeline_smoke.py`):**
1. Build a throwaway image, run it on a throwaway name/port with a throwaway `MDREVIEW_DATA`
   (`.scratch/`), `curl /healthz` + `/api/reviews` green.
2. `create_review`, open `/review/{id}` in headless Chrome over CDP. Then walk the lifecycle by
   POSTing to the real `/api/reviews/{id}/handoff` + `/source` + `/comments` endpoints between CDP
   reads, asserting the live DOM after each step:
   - **Send** (`POST /handoff {to:agent}`) → assert the banner shows "waiting for pickup" / sent.
   - **Claim** (`POST /handoff {state:working,owner:...}`) → assert the **"Connected — reading your
     comments"** step is present and active (the merged claimed+reading step), AND the **live timer**
     (`#turntimer`) shows a `M:SS` value.
   - **Timer ticks** → with the 2s poll **suppressed** (do not feed a new `/status`), read `#turntimer`,
     wait ~1.2s, read again; assert the elapsed value **advanced** (proves the fetch-free 1s clock tick,
     not just a poll refresh) — per the hidden-tab memo, read the rendered text, not a screenshot.
   - **Edit** (`PUT /source`) → assert an **"editing"** step appears and is now marked done/active;
     assert it was **absent** before this step (the baseline guard).
   - **Updating comments** (create + `POST /comments/{cid}/resolve`) → assert an **"Updating comments"**
     step appears.
   - **Hand back done** (`POST /handoff {to:reviewer,state:done,message:"…"}`) → assert a **"done —
     draft updated"** terminal state with the message; assert the comment step is now relabelled
     **"Resolved comments"** (allowed only because terminal state is `done`); AND a **final revision
     duration** ("Agent revised in M:SS") computed from the client-captured start (the page watched the
     whole run, so it has one).
   - **Signal-honesty path — reply-then-`blocked`** (separate review: claim, create a comment, `POST
     /comments/{cid}/reply` (NO resolve), then `POST /handoff {to:reviewer,state:blocked,message:"need
     a decision"}`) → assert the comment step shows **"Updating comments"** (or "Commenting") and the
     word **"Resolved" NEVER appears** (nothing was resolved this turn), and the terminal banner is the
     "Agent needs you" state — proving the label is signal-honest, not over-claiming `comments_updated`.
   - **Reopen-after-done guard** (same review, fresh CDP page load AFTER the hand_back) → assert the
     banner shows the plain done text with **no** duration (the documented limitation: a page that
     never observed `turn=="agent"` shows no bogus number).
   - **Crash path** (separate review: claim, then `POST /handoff {to:reviewer,state:blocked,
     message:"agent process exited 1 without finishing"}`) → assert the **"agent run stopped"** warn
     state renders (MR-068 not regressed).
   - **Pickup-timeout path** (Send, never claim, advance past `PICKUP_GRACE_S`) → assert the **"no
     agent picked this up"** warn state (MR-066 not regressed).
3. **Both panes:** run steps 2's key reads under `--blink-settings=preferredColorScheme=1` (light) and
   `=0` (dark) — never `--force-dark-mode` — and assert the banner/timeline renders legibly (the
   `var(--*)` tokens resolve) in each.
4. **Reduced-motion:** CDP `Emulation.setEmulatedMedia` `prefers-reduced-motion: reduce`, then assert
   the active step's `getComputedStyle(...).animationName === 'none'`; without it, assert it is the
   `turnspin` keyframe (proving liveness, per the hidden-tab memo — computed style, not screenshot).
5. **First-paint render-smoke** (cheap complement, not the proof): `scripts/render-smoke.sh
   <review-url> '#turnbanner' '#turnsteps' '#turntimer'` — **separate** flat selectors — asserts the
   container nodes paint. This does **not** assert the live sequence or the ticking (that is the CDP
   drive's job).
6. **Regression guard:** the same drive re-asserts the "Draft updated by AI" doc-reload toast and
   comment live-reload still fire (the timeline reads the same `/status` body and must not break them).

Example `/status` body the timeline reduces (confirming the fields exist, `app.py:589-598`):
```json
{"source_updated": 1719250000.0, "comments_updated": 1719250010.0,
 "turn": "agent", "turn_updated": 1719249990.0,
 "agent_status": {"state": "working", "message": "editing the rename", "owner": "watch-…", "at": 1719250012.0}}
```
Reduction: `turn=="agent"` + `state=="working"` + `at` fresh → "Connected — reading your comments"
(claimed); `source_updated > turn_updated` → "Editing the draft" reached; `comments_updated >
turn_updated` → "Updating comments" reached (NOT "Resolved" — that word appears only on terminal
`done`); `message` present → show "editing the rename" on the active step.

**MR-074 (svc, if shipped):** `python3 -m py_compile app.py`; `curl -s -X POST .../handoff -d
'{"state":"working","owner":"x","message":"reading 2 comments"}'` then `curl -s .../status` and
assert `agent_status.message == "reading 2 comments"` is returned in the working arm. Header checks
(none expected) would use `curl -sD - -o /dev/null`, never `curl -sI`.

**MR-075 (docs):** prose-only; `py_compile` unaffected; confirm `CLAUDE.md`/`README.md`/`AGENTS.md`
describe the timeline and (if MR-074 shipped) the `message`-as-status-hint contract.

## Assumptions & open questions

Proceeding autonomously on the stated assumptions; none rises to a BLOCKER-FOR-HUMAN (no product
fork that could waste a sprint — the cuttable item, MR-074, is a small additive `svc` formalisation,
not a design fork).

- **(load-bearing) Tier scope: ship (A) only; defer (C).** Assumption: the derived timeline fixes the
  "looks frozen" problem the epic was raised for, so (C)'s new event API + persisted store + stream
  parser is not worth its cost this epic. Justification: the trigger was *visibility of a healthy
  long run*, which (A) delivers from existing signals; (C) buys finer-grained *real tool calls* the
  owner did not ask for. If the owner specifically wants the literal tool-call stream (not just
  step-level progress), that flips (C) into scope — flagged as the question below.
- **(load-bearing) MR-074 default: CUT.** Assumption: the derived timeline (A) plus the
  already-surfaced `agent_status.message` (B, free) suffice, so no `svc` change ships and the epic is
  UI + docs only. Justification: the `message` plumbing already exists end-to-end (`mcp_server.py:454`
  → `app.py:661` → `/status`); the only gap is the viewer displaying it, which is MR-073's job. Keep
  MR-074 only if review wants a *documented contract* obliging the agent to push step labels.
- **(minor) Timeline is cumulative, not a single current-step pointer.** Assumption: once a step's
  signal fires this turn it stays "done", so a skipped poll never loses a step. Justification: robust
  to the 2s-poll granularity vs sub-2s agent actions (the risk table).
- **(minor) `turn_updated` is the per-turn baseline anchor** for "edit/resolve happened *this* turn".
  Justification: `app.py:629/636` bump `turn_updated` exactly on a hand-back and a reviewer→agent
  flip — the turn boundaries — so a bump strictly after it is in-turn.
- **(load-bearing) Final-duration start is captured CLIENT-side, not server-recorded.** Assumption:
  the timer serves the person watching the run, so client capture (no service change, no persistence)
  is the right rung of the ladder; the limitation (a page opened *after* `done` shows no duration) is
  acceptable. Justification: the owner's framing is watching the agent revise to completion. Trade-off
  documented; the server-recorded alternative (record elapsed at the `app.py:623-629` hand_back arm) is
  a small additive `svc` follow-on left out of scope. If the owner wants a durable duration that
  survives a post-`done` reload (e.g. for an audit/history view), that flips the `svc` add into scope.
- **(load-bearing) The comment step is labelled by its honest signal, not "Resolved".** Decision (not
  an open assumption): `comments_updated` is not resolve-specific (`app.py:751/771/790` bump it on
  reply/reopen/create/delete too), so the step reads "Updating comments" and only says "Resolved" on
  terminal `done`. This prevents the reply-then-`blocked` path falsely claiming a resolution.
- **(decision) "Reading" is merged into the claimed step, not a separate timed step.** There is **no**
  derivable "reading" signal — a read is a GET that bumps nothing — so the brief's *reading* stage is
  represented as the resting label of the claimed step ("Connected — reading your comments"). No fake
  signal is invented. This is a pinned decision, not an open question.

**Open question — RESOLVED at G1 (owner picked step-level).** The owner confirmed **step-level
stages** (claimed/reading → editing → updating comments → done), **not** the literal agent tool-call
stream. So Tier-1 (A) ships as-is and the raw-event stream (C)/stream-json stays deferred to the
backlog — no scope expansion.

## Relationships

- **GH #27** — this epic (parts 1+2: the live timeline + finer error surfacing). Part 3 (streamed
  non-jerky doc updates) is out of scope (rides #19/#21).
- **#26 (done, MR-067/068)** — the crash signal + watcher logging this timeline **wraps**; not redone.
- **#19/#21 (handoff diff)** — out of scope; the vehicle for #27 part 3, a separate feature.
- **MR-062/066** — the spinner + pickup cue this timeline wraps; not redone.

## Review resolutions

### 2026-06-24 — product-owner amendment: add an elapsed/duration timer (pre-G1)
Folded the timer into **MR-073** (no new tier, no new ticket — it rides the same derived-`/status`
Tier-1 and the same UI surface). Changes:
- **Live elapsed timer:** `now - turn_updated` while `turn=="agent"` and `state=="working"`
  (`turn_updated` = the Send/flip time, `app.py:636`), ticking on a **cheap, fetch-free 1s
  `setInterval`** that re-renders only the timer text from the cached last `/status` body (no extra
  polling). Added to the signal table, the UI timer design note, Phase 1, and the goal/intro.
- **Final revision duration:** resolved the called-out subtlety that **`turn_updated` is re-bumped on
  hand_back** (`app.py:629`), so the start is gone from `/status` at completion. Pinned the
  **client-side capture** (remember first-seen `turn=="agent"`, delta on `done`) — no service change,
  no persistence — with its documented limitation (a page opened *after* `done` shows no duration) and
  the server-recorded alternative explicitly deferred. Captured as a load-bearing assumption.
- **Validation:** the node-CDP drive now asserts (a) the live timer shows on claim, (b) the digit
  **advances ~1s with the poll suppressed** (proves the local clock, not a poll refresh), (c) the
  **final duration** renders on `done`, and (d) a **page reopened after `done`** shows no bogus
  duration. Added a `#turntimer` selector to the render-smoke first-paint check and two timer risks.
- **Source reference:** the brief's 2026-06-24 **Amendments** entry is now noted in the
  source-requirement line; `source:` frontmatter unchanged (same file).

### 2026-06-24 — G1 verdict GO-WITH-NITS: two signal-honesty nits folded into MR-073
The critic verified every code claim (derived timeline, client-side timer, MR-074-cut all confirmed
sound) and the owner picked **step-level stages** (not the literal tool-call stream), so Tier-1 ships
as-is and (C)/stream-json stays deferred — no scope expansion. Two worth-fixing nits folded into
MR-073:
- **Nit 1 — "resolving" over-claimed its signal.** `comments_updated` bumps on
  reply/reopen/create/delete too (`app.py:751/771/790`), not just resolve, so an agent that posts a
  clarifying reply then hand_backs `blocked` ("Agent needs you") would have falsely lit "resolving".
  **Fix:** the step is now labelled **"Updating comments"** off the raw bump, and the word "Resolved"
  appears **only** when the terminal state is `done`. Updated the signal table (split into
  "Updating comments" + a `done`-gated "Resolved comments" row), the post-table signal-honesty rules,
  the UI labels bullet, a new dedicated risk row, the per-turn-baseline note, and **added a node-CDP
  reply-then-`blocked` assertion** that the word "Resolved" never appears that turn.
- **Nit 2 — no derivable "reading" signal.** A read is a GET that bumps nothing in `/status`, so
  "reading" cannot be a separate timed step. **Fix:** made the decision explicit — "reading" is folded
  into the post-claim step as its **resting label** ("Connected — reading your comments"), representing
  the brief's *reading* stage without inventing a fake signal. Updated the signal table, the
  post-table rules, the UI section, the ordered-steps list, the CDP claim assertion, and added it as a
  pinned decision in Assumptions. No "reading" event/endpoint is invented.
- **Open question closed:** the owner's step-level choice is recorded in Assumptions; (C) stays
  backlog-deferred. Everything else pinned: step-level derived timeline, the timer, MR-074 default-cut,
  MR-075 docs sweep.
