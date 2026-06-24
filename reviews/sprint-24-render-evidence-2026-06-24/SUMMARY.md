# sprint-24 render evidence — watcher-observability (#26)

Date: 2026-06-24. Validation of MR-066 / MR-067 / MR-068 (G4).

## Method (and why from-source)

Validated against the service run **from the working tree** on scratch port **8181**
(`PORT=8181 MDREVIEW_DATA=.scratch/s24data python3 app.py`), with the watcher (`watch.py`) run on the
host against it. This is behaviorally identical to a container for these changes and was preferred for
fast, direct iteration:

- `viewer.html` is served **from disk at request time** (`app.py:812` `_read(os.path.join(HERE,
  "viewer.html"))`) — the running service serves the *edited* file; there is **no Dockerfile change**
  and `viewer.html` is already `COPY`ed, so a container rebuild would serve the identical bytes.
- `watch.py` is **not containerized** at all (the non-containerized sibling) — it only ever runs on
  the host, exactly as tested.

The container rebuild + both-pane/reduced-motion CDP screenshots are re-driven independently at **G7**
(staff-critic) and the final **mdreview-qc** pass. All temp/stubs/data under `.scratch/`.

## MR-066 — pickup-timeout `.warn` cue (viewer)

Fixture: review `99d80db34c`, `turn=agent`, `agent_status=null`, `turn_updated` back-dated 120s
(> `PICKUP_GRACE_S=60`). Browser-rendered banner read back via `getComputedStyle`:

```json
{ "className": "turnbanner show warn", "hasWarn": true, "hasLoading": false,
  "text": "No agent has picked this up — is a watcher running? Take back the turn.",
  "beforeAnimationName": "none", "beforeContent": "none", "PICKUP_GRACE_S": 60 }
```

No-regression — **within grace** (review `d068762d53`, `turn_updated`=now) still spins:

```json
{ "className": "turnbanner show loading", "hasLoading": true, "hasWarn": false,
  "text": "Sent — waiting for an agent to pick this up.",
  "beforeAnimationName": "turnspin", "beforeContentSet": true }
```

PASS — past grace → non-spinning `.warn` cue; within grace → `.loading` spinner. Reduced-motion-safe
by construction (`.warn` has no `::before`, so no animation to suppress). Screenshot: amber
left-bordered banner with a "Take back the turn" button, no spinner.

## MR-067 — watcher stderr capture + log + guarded crash signal (watch.py)

Three host runs of `watch.py` against the throwaway service, `WATCH_LOG_FILE` set, stub launch
commands (see `watch-*.log`):

- **Crash** (`watch-crash.log`): child exits 1 without hand_back. Log captured the exit code **and**
  the stderr marker (`BOOM-CRASH-MARKER`); `/status` re-check saw `turn=agent` → POSTed the signal.
  Result `/status`: `turn=reviewer`, `agent_status={state:blocked, message:"agent process exited 1
  without finishing"}`. PASS.
- **False-positive guard** (`watch-falsepos.log`): child hands back `done` **then** exits 1. Log:
  *"crash-signal: review … already handed back (turn=reviewer state=done) — no false 'stopped'"*.
  `/status` stayed `turn=reviewer`, `agent_status.state=done`. **No false "stopped" written.** PASS —
  this is the conflation guard the G1 critic flagged.
- **Happy path** (`watch-happy.log`): child hands back `done`, exits 0 → exit-0 branch, no signal.
  `/status` stayed `done`. PASS.

`python3 -m py_compile watch.py` + `py_compile app.py` pass. Unconfigured watcher still exits 2.

## MR-068 — render the "agent run stopped" crash signal (viewer)

Fixture: review `310fec7735` left `blocked` by the MR-067 crash run above (true end-to-end —
watcher → service → viewer). Browser-rendered banner:

```json
{ "className": "turnbanner show warn", "hasWarn": true, "hasLoading": false,
  "text": "Agent run stopped: agent process exited 1 without finishing. Your turn.",
  "beforeAnimationName": "none" }
```

No-regression — a **deliberate agent question** (`96f35fcf16`, `state=blocked`, message "Do you mean X
or Y here?") still reads as a question, not a crash:

```json
{ "className": "turnbanner show", "hasWarn": false, "hasLoading": false,
  "text": "Agent needs you: Do you mean X or Y here?." }
```

PASS — the watcher crash signal renders as the distinct `.warn` "Agent run stopped" banner (no
spinner; Send re-enabled since the turn is already back with the reviewer), and a genuine question is
NOT mistaken for a crash. (The trailing `?.` double-period on the question is a pre-existing cosmetic
nit in the original blocked arm, unchanged here.)

## Verdict

MR-066 / MR-067 / MR-068 all PASS at G4 (behavioral, against a running service). The headline live
bug (Send with no watcher → forever spin) is fixed by MR-066 alone; the crash-surfacing (MR-067/068)
is proven end-to-end including the false-positive guard.
