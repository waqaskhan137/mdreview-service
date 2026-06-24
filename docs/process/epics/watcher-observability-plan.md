---
epic: watcher-observability
status: active
created: 2026-06-24
source: docs/process/requirements/watcher-observability.md
gate: passed 2026-06-24
review: reviews/watcher-observability-plan-review-2026-06-24.md
related_sprints: [sprint-24]
related_tickets: [MR-066, MR-067, MR-068]
---

# Watcher Observability Plan

When a watcher-spawned agent fails — or when no watcher is running at all — the reviewer sees an
indefinite spinning "working" banner with no cue, and a failed run leaves almost no trace. This
epic makes a stuck or crashed agent run **visible and diagnosable**: the viewer times out the
"waiting-for-pickup" state into a distinct non-spinning warning, and the watcher captures the
child's exit code + stderr to a documented log *and* signals the crashed run back so the banner
shows "agent run stopped" instead of a frozen spinner. This is purely about **visibility**, not
retry — the deliberate fail-safe under-spawn (no auto-relaunch) stays.

**Source requirement:** [`requirements/watcher-observability.md`](../requirements/watcher-observability.md)
— the original brief (GH #26 + the live-instance bug), kept verbatim.

## Product goal

A reviewer who pressed **Send to agent** can always tell, within ~a minute, which of three things
is true and what to do about it:

1. **Pre-grace waiting / working** — a spinner, "give it a moment."
2. **No agent picked it up** (no watcher running, or nothing claimed the lease within the grace
   window) — a distinct non-spinning warning: *"no agent has picked this up — is a watcher running?
   Take back the turn."*
3. **The agent run stopped/crashed** — a distinct non-spinning warning: *"agent run stopped — Take
   back the turn,"* driven by an explicit signal the watcher writes when its child exits without
   finishing.

And an **operator** can diagnose a failed run from a documented, timestamped log holding the child's
exit code and captured stderr — not a single buried stdout line.

The epic is **done** when: (Half 1) the viewer distinguishes those three states and respects
reduced-motion; (Half 2) `watch.py` captures the crashed child's exit code + stderr to a documented
log and POSTs a "stopped" signal that the viewer renders as a distinct non-spinning warning;
auto-relaunch is **not** added.

## Core design principle

**Surface the truth client-side first; signal explicitly only when the watcher knows more than the
clock.** Half 1 needs no server or watcher change — the viewer already polls `turn`, `agent_status`,
and `turn_updated`, so a pure client-side timeout turns "parked forever" into an actionable warning
and covers the *no-watcher-at-all* case the clock can detect on its own. Half 2 reuses the
**existing** `hand_back{to:reviewer, state:blocked, message}` arm — the watcher already knows its
child crashed, so it tells the server, which already flips the turn back and which the viewer already
renders. **No new `agent_status` state, no new `/handoff` arm, no new persisted meta key.** The two
halves share one visual treatment (non-spinning warning banner) so they reinforce rather than fight.

## Recommended approach

### Service (`app.py`)

**No change.** Verified against the code:

- `GET /status` already returns `turn`, `turn_updated`, and `agent_status` (`app.py:594-597`), so
  Half 1's client-side timeout has every field it needs.
- The hand-back arm already exists: `POST /api/reviews/{id}/handoff` with
  `{to:"reviewer", state:"blocked", message:"…"}` writes
  `agent_status={state:"blocked", message, owner, at}`, flips `turn` to `reviewer`, bumps
  `turn_updated`, and `notify_all()`s `/wait` waiters — all under `_lock` (`app.py:623-629,
  667-672`). This is exactly the signal Half 2 needs. The viewer already renders the blocked state
  (`viewer.html:248`). So Half 2 rides the existing surface; `app.py` is untouched.

This is the pinned decision from the brief's "pin it" instruction: **the existing
`hand_back{state:blocked,message}` suffices — no `svc` change.** (See the measurement table below.)

### UI (`viewer.html`)

All UI work lives in `renderBanner` (`viewer.html:232-255`) and the turn-baton banner CSS
(`viewer.html:80-89`). Two additions, both client-side:

- **Grace-window timeout for the parked arm.** The parked arm is the `if(!as){…}` branch
  (`viewer.html:240`) which today unconditionally sets the spinner. Split it on
  `Date.now()/1000 - turn_updated`:
  - `turn==='agent'` AND `!agent_status` AND elapsed **≤ grace** → keep today's
    "Sent — waiting for an agent to pick this up." **with** the spinner (`.loading`).
  - `turn==='agent'` AND `!agent_status` AND elapsed **> grace** → a **non-spinning warning**:
    "No agent has picked this up — is a watcher running? Take back the turn." (`.loading` NOT added;
    a new `.warn` class for the warning treatment.)
  - `turn_updated` is already in the `/status` body (`app.py:595`) and the viewer's poll body, so
    **no server call is added.** The banner re-renders on the existing ~2s poll (`viewer.html:668`),
    so the state flips on its own as the clock crosses the grace boundary, even with no `/status`
    *change* — the same property the existing `STALE_S` working-state check relies on.
- **"Agent run stopped" treatment for the blocked hand-back.** The reviewer-turn `state==='blocked'`
  arm (`viewer.html:248`) already shows "Agent needs you: <message>." Keep that for a deliberate
  agent-asked-a-question block, but give the **watcher's crash signal** its own message via the
  message text the watcher sends ("agent process exited N without finishing"), and apply the same
  **non-spinning warning `.warn`** treatment so it reads as a stopped/failed state, not a normal
  "your turn." (Reviewer-turn arms never add `.loading`, so they are already non-spinning; the new
  `.warn` class gives them the warning *style* — see Distinguishability below.)

**Distinguishability (the three agent-turn states + the stopped state).** A single new `.warn` CSS
class carries the warning treatment (a warning accent: a left border / icon tint using an existing
token, no spinner). The decision table the implementer encodes:

| Condition (`turn`, `agent_status`, elapsed) | Banner text | Spinner | Class |
|---|---|---|---|
| `agent`, null, ≤ grace | Sent — waiting for an agent to pick this up. | yes | `.loading` |
| `agent`, null, > grace | No agent has picked this up — is a watcher running? Take back the turn. | no | `.warn` |
| `agent`, working, age ≤ `STALE_S` | Agent is working on your feedback… | yes | `.loading` |
| `agent`, working, age > `STALE_S` | Agent may have stopped — Take back the turn? | no | (unchanged today; may adopt `.warn`) |
| `reviewer`, blocked (watcher crash msg) | Agent run stopped: <reason>. Take back the turn. | no | `.warn` |
| `reviewer`, blocked (agent question) | Agent needs you: <message>. | no | (today's style) |
| `reviewer`, done / none | Your turn… | no | (today's style) |

The fix is: only the two genuinely-active rows spin; everything that means "nothing is coming, act"
is a non-spinning `.warn`. Reduced-motion is already handled for `.loading` (`viewer.html:89`); the
new `.warn` has no animation so it is reduced-motion-safe by construction (verify it adds none).

### Watcher (`watch.py`)

Two changes, both in the spawn/reap path, both stdlib-only:

- **Capture the child's stderr + structured logging.** Today `_spawn` (`watch.py:394-411`) passes no
  `stderr`/`stdout` to `Popen`, so the child inherits the watcher's streams and a crash trace is lost
  among `print()`s. Change the spawn to capture stderr (a per-child `subprocess.PIPE` read on reap, or
  redirect to a per-review temp; PIPE-on-reap is simplest and bounded since these are short runs) and
  emit **structured, timestamped** records via the stdlib `logging` module. On a non-zero (or
  hand_back-less) exit, log a record carrying the review id, exit code, the resolved argv, and the
  captured stderr tail. This is the operator-facing half of #26: minimal shape, `logging` to a
  documented file, **not** a framework.
  - **Migration scope (pinned, no implementer guess): MR-067 owns the FULL `print()`→`logging`
    migration** of `watch.py` (~15 call sites: the B1 reap traces at `watch.py:311,316`, the
    capacity/skip/cap lines, the cursor-seed/startup notices, the spawn line). A half-migration —
    some events going through `logging`, others still `print()` — is worse than either, because the
    operator's documented log would then be missing the very lines (capacity skips, lease 409s) that
    contextualize a crash. The migration is mechanical (`print(x)` → `log.info/warning(x)`), keeps
    every existing message string, and adds the structured crash record. No behavior changes beyond
    where the bytes go.
  - **`WATCH_LOG_FILE` default (pinned): unset ⇒ log to stderr only; set ⇒ also write that file.**
    The watcher is the non-containerized sibling — there is **no `/data` mount to default a path
    into**, so a baked-in file path would write to the operator's CWD by surprise. Default is
    therefore stderr (a `StreamHandler`), preserving today's "wherever the operator redirected"
    behavior by default; setting `WATCH_LOG_FILE=./watch.log` (or any path) adds a `FileHandler` to
    that exact path. `--verbose` raises the level (INFO→DEBUG). Document both `WATCH_LOG_FILE` and
    `--verbose` in the README **"Watcher (optional) — operator runbook"** section and in `watch.py`'s
    module docstring Config block (which already enumerates the env vars). The MR-067 validation
    must set `WATCH_LOG_FILE` to a concrete `.scratch/` path so the `grep "exited 1"` assertion has
    a real file to read.
- **Signal the crashed run back to the reviewer.** In `_reap` (`watch.py:299-318`), when a child
  exits non-zero, POST `/api/reviews/{rid}/handoff`
  `{to:"reviewer", state:"blocked", owner:OWNER, message:"agent process exited <code> without
  finishing"}` (the same `_http` helper, the same `OWNER` that won the lease). This flips the review
  back to the reviewer with the blocked signal the viewer renders. Guard the message for the no-auth
  posture: a short, fixed reason ("agent process exited N without finishing") — **never** the raw
  stderr (which can leak internals to a public viewer). The full stderr stays in the operator log
  only. This stays within the **B1 no-relaunch** model: it reaps, logs, **signals**, and moves on —
  no re-spawn.

A subtlety to encode (do not regress B1, and do not lie about a successful run): the watcher must
**re-check `/status` BEFORE it POSTs the crash signal — this is MANDATORY, not optional.** The
premise that "a child that handed back exits 0 and never reaches the non-zero branch" is **not
guaranteed**: the child is an arbitrary operator launch command (a Claude agent under a wrapper). It
can POST a successful `done` `hand_back` partway through and *then* exit non-zero for an unrelated
reason — a cleanup error, `set -e`, a SIGTERM during teardown. Unconditionally signalling on a
non-zero exit would then **stomp the just-written `done` state** with a false "agent run stopped."

So in `_reap`, on a non-zero child exit, before POSTing the blocked/stopped signal:
`GET /api/reviews/{rid}/status`, and **SKIP the signal** if `turn != "agent"` (the child already
handed the turn back) **or** `agent_status.state == "done"`. Only signal when the re-check confirms
the review is still stranded at `turn == "agent"` — which is exactly the genuine-crash case (a child
that died before `hand_back` leaves `turn=agent` with a stale `working` lease, so the re-check sees
`turn=agent` and correctly signals). The guard suppresses *only* the false positive; it never
suppresses a real crash. The `/status` read is a cheap GET; a failed read logs and skips the signal
(never crashes the loop) — the safe direction, since a missed signal still self-heals via the 180s
stale banner plus the Half-1 pickup-timeout cue.

## Measured forks (render/behavior-observable, settled against the code, not argued)

| Question | Method | Result |
|---|---|---|
| Does `/status` expose `turn_updated` for a client-side grace timer? | Read `app.py:594-597` | Yes — `turn`, `turn_updated`, `agent_status` all in the body. Half 1 is client-only. |
| Does a "stopped/failed" signal need a NEW `agent_status` state or `/handoff` arm? | Read `app.py:606-675` | No. `hand_back{to:reviewer,state:blocked,message}` already writes `agent_status.state="blocked"`, flips turn, bumps `turn_updated`, notifies waiters — all under `_lock`. |
| Does the viewer already render a blocked state? | Read `viewer.html:248` | Yes — `state==='blocked'` → "Agent needs you: <message>." Half 2 reuses it with a stopped-specific message + `.warn` style. |
| Does the banner re-render without a `/status` *change* as the grace clock crosses? | Read `viewer.html:663-668` (poll calls `renderBanner` every tick) + the existing `STALE_S` pattern relies on the same | Yes — the ~2s poll re-invokes `renderBanner`, so a pure time-based transition fires without a server event. |
| Does `_spawn` capture child stderr today? | Read `watch.py:394-411` | No — child inherits the watcher's streams; the crash trace is lost. Capture must be added. |

These resolve the brief's "pin it" asks: Half 2 mechanism = existing `hand_back` (no `svc` change);
Half 1 = client-only.

## Grace-window default

**Default 60 seconds.** Justification, relative to the two fixed clocks in the system:

- `STALE_S = 180` (`viewer.html:225`, mirroring `LEASE_TTL_S`, `app.py:58`) is the *working-state*
  staleness — an agent that *claimed* a lease then stopped heartbeating. The pickup grace is a
  *different, shorter* clock: nothing has claimed at all, so a healthy watcher should pick up within
  a long-poll cycle. The watcher's `/wait` long-poll is ~25s (`WATCH_WAIT_TIMEOUT_S`, `watch.py:68`),
  and lease claim + spawn is near-instant after a flip. 60s comfortably exceeds one long-poll cycle
  plus claim/spawn jitter, so a live watcher essentially never trips the warning, while a *no-watcher*
  case surfaces in ~1 minute instead of ~20.
- It sits well below `STALE_S=180` so the two warnings never collide, and well above the ~2s viewer
  poll so the transition is crisp, not flickery.
- Expose it as a single named constant (`PICKUP_GRACE_S = 60`) next to `STALE_S` with a comment, so
  the value is one-line tunable and self-documenting. The 45–90s band in the brief is acceptable; 60
  is the justified midpoint.

## Rollout phases

Each phase is independently shippable and leaves the service in a better state than before.

### Phase 1 — Reviewer-facing pickup timeout (Half 1, fully independent)
- Client-only `viewer.html` change: split the parked arm on the grace window, add the `.warn`
  non-spinning warning treatment, encode the three-state distinguishability. No server, no watcher,
  no dependency. Ships value immediately: the *no-watcher* live bug (the exact 20-minute spin) is
  fixed by this phase alone.

### Phase 2 — Watcher error capture + log + crash signal (Half 2)
- `watch.py`: capture child stderr, structured `logging` to a documented log location, and POST the
  `hand_back{state:blocked}` crash signal on a non-zero exit.
- The **viewer side** of Half 2 (rendering the blocked crash signal with the `.warn` stopped-state
  treatment) is the small `viewer.html` follow-on. Because it reuses the Phase-1 `.warn` class, it is
  a tiny addition — sequence it after the watcher emits the signal so the render can be verified
  against a real signal end-to-end.

## Non-goals

- **Auto-relaunch / crash-retry.** The deliberate fail-safe under-spawn (B1: a crashed child strands;
  no relaunch) stays. This epic adds *visibility*, never retry.
- **The rest of #27** — progress steps, streamed/live updates, the waiting-animation UX beyond the
  timeout cue. Out of scope.
- **Arming / caps changes.** No change to `WATCH_ARMED*`, the per-review cap, or the global caps.
- **A new `agent_status` state or `/handoff` arm.** Verified unnecessary; explicitly not added.
- **A new persisted `meta.json` key.** The blocked signal rides the existing `agent_status` write.
- **Leaking child stderr to the viewer.** The viewer gets a short fixed reason; raw stderr is
  operator-log-only (no-auth posture).

## Key constraints

- **stdlib-only, zero pip.** `watch.py` uses `subprocess`, `logging`, `urllib` — all stdlib. No
  vendored asset is added (no new served file → **no `Dockerfile COPY` change**; `viewer.html` is
  already copied at `Dockerfile:8`). `viewer.html` adds CSS + JS only, no new `<script>`/`<link>`.
- **`app.py` untouched.** No new route (so no risk of shadowing the ordered regex router or the
  `[A-Za-z0-9]{4,40}` id pattern), no new `meta.json` key, no new write path. The existing
  `/handoff` blocked arm runs under `_lock` already (`app.py:615-672`).
- **Back-compat of `meta.json`.** No new key. Older reviews lacking `turn_updated` already default to
  `0` in `meta()` (`app.py:595`); a `0` `turn_updated` means elapsed is huge → the warning shows,
  which is the safe direction for a parked review with no recorded flip time. Confirm this is
  acceptable (it is: an ancient parked review *should* warn).
- **`viewer.html` is JS-rendered — a 200 is not a render.** The timeout cue is a *time-dependent JS
  state transition*; `render-smoke.sh` (a flat one-shot DOM matcher) cannot drive the clock. Verify
  with the node-CDP `Runtime.evaluate` driver (the `agent_smoke.py` pattern, `agent_smoke.py:112-135`)
  against a rebuilt throwaway container.
- **Reduced-motion respected.** `.loading` already honors `prefers-reduced-motion` (`viewer.html:89`);
  `.warn` adds no animation, so it is safe by construction — assert it.
- **No-auth posture.** The viewer-visible crash reason is short and fixed; raw stderr never reaches
  the viewer.
- **Gates:** `python3 -m py_compile app.py` (unchanged but still run) **and**
  `python3 -m py_compile watch.py`. `ui` ticket owes a node-CDP banner-drive render proof from the
  rebuilt image. No `docker build`-gated infra change (no Dockerfile/compose edit).
- **Dates `Europe/London`; commits keep the `Co-Authored-By: Claude` trailer and reference the
  ticket ID.**
- **Header checks (if any) use a GET header-dump**, never `curl -sI` (no `do_HEAD`; HEAD → 501). The
  validation here is JSON `/status` reads and CDP DOM eval, not header MIME checks, so this is mostly
  N/A — noted so any added asset check uses `curl -sD - -o /dev/null`.

## Preferred execution order

1. **MR-066 (ui, Phase 1)** — pickup-timeout cue + `.warn` treatment + three-state distinguishability.
   Fully independent; lands first and fixes the live no-watcher bug on its own.
2. **MR-067 (watcher/svc-layer, Phase 2)** — `watch.py` stderr capture + structured log + crash
   `hand_back{state:blocked}` signal. Independent of MR-066 to *emit*; the viewer render of it
   depends on MR-066's `.warn` class.
3. **MR-068 (ui, Phase 2)** — render the watcher's blocked crash signal as the stopped-state `.warn`
   banner. `depends_on: [MR-066, MR-067]` (the `.warn` class is **defined in MR-066**, so MR-068 is
   purely a render-arm change, not a class redefine; it also needs MR-067's real signal to verify
   end-to-end). **Keep MR-068 separate from MR-066** — folding it in would lose Half-1's
   independent-ship property (MR-066 must ship without waiting on MR-067's signal), and the
   watcher→viewer end-to-end proof deserves its own gate.

## Ticket breakdown

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-066 | Viewer: pickup-timeout cue + non-spinning `.warn` state (Half 1) | ui | 1 |
| MR-067 | Watcher: capture child stderr + structured log + crash `hand_back` signal (Half 2) | svc | 2 |
| MR-068 | Viewer: render the watcher "agent run stopped" blocked signal (Half 2) | ui | 2 |

(IDs are placeholders continuing from MR-065; the orchestrator allocates real IDs. `MR-067` is tagged
`svc` per the layer table — `watch.py` is service-side server code even though it is not containerized;
note in the ticket that the file touched is `watch.py`, not `app.py`. `depends_on`: MR-066 → none;
MR-067 → none to emit; MR-068 → [MR-066, MR-067]. Sprint: **sprint-24**.)

### Per-ticket acceptance criteria + the validation each owes

**MR-066 (ui, Half 1)**
- `renderBanner` splits the parked `if(!as)` arm on `Date.now()/1000 - (turn_updated||0) > PICKUP_GRACE_S`
  (new constant `PICKUP_GRACE_S=60` next to `STALE_S`, commented).
- ≤ grace: today's "Sent — waiting…" + spinner. > grace: "No agent has picked this up — is a watcher
  running? Take back the turn." with NO spinner and a new `.warn` class.
- **MR-066 defines the `.warn` CSS class outright** (the non-spinning warning treatment — accent
  border/tint via an existing token, no animation), so MR-068 reuses it without redefining. The class
  ships in this ticket even though MR-066 only wires it onto the parked-timeout row.
- The three agent-turn states (pre-grace spinner, working spinner, timed-out warning) are visually
  distinct per the decision table; reclaim button stays available in all agent-turn rows.
- `.warn` adds no animation (reduced-motion safe); `.loading` reduced-motion behavior unchanged.
- No `app.py`/server change; no new `/status` call.
- **Validation:** `py_compile app.py` (sanity, unchanged) + node-CDP banner-drive against a **rebuilt
  throwaway container** (scratch port, never 8137/8139, never `docker compose up`): force
  `turn=agent` + `agent_status=null`, back-date `turn_updated` (or drive the client clock) so the
  grace elapses, assert the banner text changes to the "no agent" cue AND the spinner `::before`
  animation is gone / the state class flipped `loading`→`warn` (via `Runtime.evaluate` reading
  `getComputedStyle` `animation-name` on `#turntext::before` and the `#turnbanner` classList).
  Both-pane screenshots using **`prefers-color-scheme` emulation** (`Emulation.setEmulatedMedia` with
  `{name:'prefers-color-scheme',value:'dark'}` / `'light'`, or
  `--blink-settings=preferredColorScheme=0`/`=1`) — **never `--force-dark-mode`**. Reduced-motion
  respected (emulate `prefers-reduced-motion:reduce`, assert no `.warn` animation and a static ring).
  Evidence under `reviews/sprint-24-render-evidence-2026-06-24/`.

**MR-067 (svc/watcher, Half 2)**
- `_spawn` captures the child's stderr (PIPE-on-reap or per-review redirect); `_reap` reads it on a
  non-zero exit.
- **Full `print()`→`logging` migration** of `watch.py` (all ~15 call sites, including the B1 reap
  traces at `watch.py:311,316`, capacity/skip/cap lines, cursor-seed/startup notices, spawn line) —
  no half-migration. Every existing message string is preserved; only the sink changes.
- **`WATCH_LOG_FILE` default = unset ⇒ stderr only (`StreamHandler`); set ⇒ also write that exact
  file (`FileHandler`).** No baked-in path (the watcher has no `/data` mount; a default file path
  would surprise-write the operator's CWD). `--verbose` raises the level (INFO→DEBUG). Document both
  `WATCH_LOG_FILE` and `--verbose` in the README "Watcher (optional) — operator runbook" **and** in
  `watch.py`'s module-docstring Config block.
- On a non-zero exit, emit a structured, timestamped record carrying review id, exit code, resolved
  argv, and the captured stderr tail.
- **Crash signal with a MANDATORY `/status` re-check guard.** On a non-zero child exit, `_reap`
  first `GET /api/reviews/{rid}/status` and **SKIPS the signal** when `turn != "agent"` **or**
  `agent_status.state == "done"` (the child handed back before its non-zero teardown — do not stomp
  a successful `done`). Only when the re-check confirms `turn == "agent"` does it POST
  `/handoff {to:reviewer, state:blocked, owner:OWNER, message:"agent process exited <code> without
  finishing"}` — a short fixed reason, never raw stderr.
- B1 unchanged: no relaunch; the per-review/global caps untouched; the signal AND its re-check are
  best-effort (a failed read/POST logs and continues, never crashes the loop).
- **Validation:** `py_compile watch.py` + `py_compile app.py`. **Localhost throwaway runs** under
  `.scratch/` with `WATCH_LOG_FILE` set to a concrete `.scratch/watch.log` path:
  - **Crash stub** (claims the lease via the child env, writes a stderr marker, exits non-zero
    WITHOUT `hand_back`): assert (a) the log captures the exit code + the stderr marker
    (`grep "exited 1" .scratch/watch.log` and the marker); (b) `GET /status` shows `turn==reviewer`
    + `agent_status.state=="blocked"` with the stopped message.
  - **False-positive stub (the conflation guard test): hands back `done` and THEN exits NON-ZERO.**
    Assert the watcher's `/status` re-check **SKIPS** the signal — the review stays `turn==reviewer`
    + `agent_status.state=="done"`, and **no** false "agent run stopped" is written. Without this
    test the guard ships untested.
  - **Happy-path no-regression:** a stub that hands back `done` and exits 0 leaves the normal "your
    turn"/done state and the watcher emits no crash signal.
  Evidence under `reviews/sprint-24-render-evidence-2026-06-24/`. (All throwaway data + stub scripts
  under the gitignored `.scratch/`, cleaned after.)

**MR-068 (ui, Half 2)**
- The reviewer-turn `state==='blocked'` arm renders the watcher's crash message as a distinct
  **"agent run stopped — Take back the turn"** banner using the Phase-1 `.warn` treatment (no spinner,
  warning style), kept distinguishable from a deliberate "Agent needs you" question block.
- **Validation:** node-CDP drive against the **rebuilt container**: POST the blocked crash signal (or
  reproduce via the MR-067 crash-stub run end-to-end), assert the banner shows the stopped cue with
  `.warn` (no spinner animation) in both panes; reduced-motion respected. Plus the happy-path
  no-regression (`state==='done'` still shows "Agent updated the draft… Your turn."). Evidence under
  `reviews/sprint-24-render-evidence-2026-06-24/`.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| A *live* watcher trips the 60s warning during a slow pickup (false "no agent"). | 60s >> one ~25s long-poll cycle + claim/spawn; the moment the watcher claims, `agent_status` becomes `working` and the banner flips to the spinner on the next ~2s poll. The warning is non-destructive (it only offers "Take back the turn"), so a false positive costs nothing irreversible. Tune `PICKUP_GRACE_S` if field data shows slower pickups. |
| Old reviews with `turn_updated==0` show the warning immediately. | Correct/safe direction: an ancient parked review with no recorded flip *should* warn, not spin forever. Documented in the ticket. |
| The watcher's crash signal stomps a state the child already set by `hand_back` (e.g. a child that POSTs `done` then exits non-zero in teardown). | **MANDATORY `/status` re-check before the signal** (pinned in MR-067): skip when `turn != "agent"` or `agent_status.state == "done"`, so a successful `done` is never overwritten by a false "stopped." A genuine crash strands at `turn=agent` and is correctly signalled. Tested by the false-positive stub. No relaunch, so no storm. |
| Raw stderr leaks internals to a public no-auth viewer. | The viewer-visible message is a short fixed reason; raw stderr stays in the operator log only. Asserted in MR-067 validation. |
| `render-smoke.sh` can't prove a time-dependent banner. | Use the node-CDP `Runtime.evaluate` driver per the brief's Validation section; `render-smoke.sh`'s flat matcher is insufficient and is explicitly not relied on for the timeout transition. |
| MR-068 blocks on MR-067's signal shape drifting. | `depends_on` recorded; MR-067 pins the exact `message`/state contract MR-068 renders. |

## Verification (epic-level, runnable)

All against a **rebuilt throwaway container** on a scratch port (never 8137/8139, never
`docker compose up`); all temp data + scripts under the gitignored `.scratch/`, cleaned after.

1. **Compile gates.**
   `python3 -m py_compile app.py` and `python3 -m py_compile watch.py` — both pass.

2. **Half 1 — pickup-timeout banner transition (node-CDP).** Create a review, force it to
   `turn=agent`/`agent_status=null` with a back-dated `turn_updated`:
   ```bash
   BASE=http://localhost:<scratch>
   id=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
        -d '{"title":"t","markdown":"# t\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
   curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}' >/dev/null
   # back-date turn_updated past the grace by editing the throwaway meta.json under MDREVIEW_DATA,
   # OR drive Date.now in the CDP eval. Then:
   curl -s "$BASE/api/reviews/$id/status"   # expect turn=="agent", agent_status==null
   ```
   Then via the node-CDP driver (`Runtime.evaluate`): load the viewer, assert
   `#turnbanner` classList contains `warn` and NOT `loading`, `#turntext` text matches the "no agent"
   cue, and `getComputedStyle(#turntext,'::before').animationName === 'none'`. Both panes via
   `Emulation.setEmulatedMedia` (`prefers-color-scheme` dark/light) — never `--force-dark-mode`.
   Reduced-motion pane asserts no `.warn` animation.

3. **Half 2 — watcher crash capture + signal (crash-stub).** Run `watch.py` against the throwaway
   service with a crash-stub `WATCH_LAUNCH_CMD` (a tiny script that reads `REVIEW_ID`, claims via
   `ping_working`/`/handoff {state:working}`, writes to stderr, exits 1 without `hand_back`). Flip a
   review to `turn=agent`; after the watcher spawns + reaps:
   ```bash
   grep -q "exited 1" "$WATCH_LOG_FILE"            # exit code captured
   grep -q "<stderr marker>" "$WATCH_LOG_FILE"     # stderr captured
   curl -s "$BASE/api/reviews/$id/status"          # turn=="reviewer", agent_status.state=="blocked"
   ```
   Then drive the viewer (node-CDP) and assert the "agent run stopped — Take back the turn" `.warn`
   banner (no spinner).

4. **Half 2 — false-positive guard (`done`-then-non-zero).** A stub that POSTs `hand_back {state:done}`
   and *then* exits non-zero. Assert the watcher's mandatory `/status` re-check **SKIPS** the crash
   signal:
   ```bash
   curl -s "$BASE/api/reviews/$id/status"   # MUST stay turn=="reviewer", agent_status.state=="done"
   grep -L "blocked" "$WATCH_LOG_FILE"      # no "stopped/blocked" signal emitted for this review
   ```

5. **Half 2 — happy-path no-regression.** A stub that hands back `done` and exits 0 leaves
   `turn==reviewer` + `agent_status.state=="done"`; the banner shows "Agent updated the draft…
   Your turn." with no crash signal emitted.

6. **No-regression of existing banners.** Working (`agent_status.state=="working"`, fresh) still
   spins; stale-working still shows "Agent may have stopped"; reviewer/done still shows "Your turn."

Evidence committed under `reviews/sprint-24-render-evidence-2026-06-24/` (both-pane screenshots +
the CDP/log assertions), per the G7 render-evidence convention.

## Review resolutions

### 2026-06-24 — staff-critic review (GO-WITH-NITS), five items folded in

Both pivotal pins were verified correct by the critic against the code (the ~2s poll
unconditionally re-invokes `renderBanner` at `viewer.html:668`; the existing
`hand_back{state:blocked}` arm at `app.py:623-629` does everything claimed and `_reap` can call it).
The five nits are resolved:

1. **MR-067 — mandatory `/status` re-check before the crash signal.** Changed the Watcher approach
   section and the MR-067 ACs from "optionally re-check" to a **MANDATORY** guard: on a non-zero
   exit, `GET /status` and SKIP the signal if `turn != "agent"` or `agent_status.state == "done"`.
   Rationale folded in: the child is an arbitrary operator command and can POST `done` then exit
   non-zero in teardown, so the unconditional version would stomp a successful run with a false
   "stopped." The risk-table row was updated to match (was "optionally re-check").
2. **MR-067 — false-positive test added.** Added a `done`-then-non-zero stub variant to the MR-067
   ACs and to the epic-level verification (step 4), asserting the re-check SKIPS the signal (review
   stays `done`, no false "stopped"). The conflation guard no longer ships untested.
3. **MR-067 — print()→logging migration scope pinned.** Stated explicitly that MR-067 owns the
   **FULL** migration of all ~15 `watch.py` `print()` sites (B1 reap traces at `watch.py:311,316`,
   capacity/skip/cap lines, cursor-seed/startup notices, spawn line), not a half-migration; message
   strings preserved, only the sink changes.
4. **MR-067 — `WATCH_LOG_FILE` default pinned.** Pinned: unset ⇒ stderr-only (`StreamHandler`); set
   ⇒ also write that exact file (`FileHandler`). No baked-in path (the watcher has no `/data` mount).
   Documented in the README "Watcher" runbook and `watch.py`'s docstring Config block. Validation now
   sets a concrete `.scratch/watch.log` so the `grep "exited 1"` assertion has a real file.
5. **MR-066/MR-068 — `.warn` class ownership pinned.** Stated that the `.warn` class is **defined in
   MR-066** outright; MR-068 is purely a render-arm change, not a redefine. MR-068 is kept SEPARATE
   from MR-066 (preserving Half-1's independent-ship property and giving the watcher→viewer
   end-to-end proof its own gate), per the critic's confirmation. Sequencing MR-066 → MR-067 → MR-068
   stands. Grace=60s, the existing-`hand_back` mechanism, and the 3-ticket split are unchanged.
