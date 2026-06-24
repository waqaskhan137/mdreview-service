---
epic: watcher-launch-fix
status: active
created: 2026-06-24
source: requirements/watcher-launch-fix.md   # verbatim critic-gated proposal (mdreview 05ff768234, two staff-critic rounds, verdict GO)
gate: passed 2026-06-24   # G1 PASS-WITH-NITS, scaffolding findings folded; ticket unblocked
review: reviews/watcher-launch-fix-plan-review-2026-06-24.md
related_sprints: [sprint-20]
related_tickets: [MR-060]
---

# Watcher Launch Fix Plan

The shipped `agent-watcher` watcher (`watch.py`, MR-054–MR-059) ships a runnable `DEFAULT_LAUNCH_CMD`
(`claude -p …`) that **silently no-ops headless**: a `claude -p` with no permission stance routes
MCP tool use (the agent's entire toolset: `ping_working` / `update_source` / `resolve_comment` /
`hand_back`) to an interactive approval prompt; with no TTY to answer it, the agent claims the lease
and hands back without doing the work. The two safe fixes pull in opposite directions: the default
must not silently no-op (the defect), and it must not be silently dangerous either (baking
`--dangerously-skip-permissions` into the default punches a hole through the C3 arming path — an
armed review on a public base becomes a fully autonomous agent executing attacker-authored comment
content). **Option B is decided** (recommended and confirmed across both critic rounds): make the
default an **inert must-configure stub** that makes the watcher **refuse to start** with guidance
when `WATCH_LAUNCH_CMD` is unset, and move the permission posture into runbook recipes. This is a
small, 1-ticket `svc`(+same-change `docs`) follow-up to the now-done `agent-watcher` epic.

**Source requirement:** [`requirements/watcher-launch-fix.md`](../requirements/watcher-launch-fix.md)
— the original critic-gated brief, kept verbatim.

## Product goal

An operator who runs `python3 watch.py` either gets a **working** agent loop or a **clear refusal
with guidance** — never a watcher that claims the lease and silently does nothing. The watcher's
identity as a *generic, fail-closed credentialed spawner* is preserved: the agent command and its
permission posture are an explicit one-time operator choice, documented with the injection trade-off
spelled out, not a Claude-specific default baked into the loop.

## Core design principle

**A credentialed spawner with no safe default refuses to start; it never claims a lease it cannot
honour.** The watcher is a *mechanism*; the agent + permission posture is *operator policy*. When
policy is unconfigured, the only honest behaviour is to exit at **startup** with guidance — not to
start, claim a review's lease, and then die per-review (which would strand the review at
`turn==agent` under the B1 no-relaunch model).

## Recommended approach

This epic does **not** touch `app.py` or the `Dockerfile`. The entire change is in `watch.py` and
two docs files. Split below by area.

### Service (`watch.py`)

The fix is a **startup-time configuration gate**, deliberately placed where the other fail-closed
checks live (`main()`, before `run()`), never inside the per-review spawn path.

1. **Turn `DEFAULT_LAUNCH_CMD` into an inert sentinel.** Today it is a runnable argv
   (`watch.py:83-89`): `["claude", "-p", "<prompt>"]`. Replace it with a value that is **not a
   runnable command** and is unambiguously detectable as "unconfigured" — e.g. a module-level
   sentinel `DEFAULT_LAUNCH_CMD = None` (with the old prompt text removed), so the only Claude
   string left in the file is in the runbook-pointing guidance message, not an executable default.
   The current docstring claim that this constant is "the ONLY Claude-specific knowledge in this
   file" (`watch.py:80-82`) becomes false and must be rewritten.

2. **Add a `launch_configured()` check and gate it at startup in `main()`.** Mirror the existing
   `arming_configured()` predicate (`watch.py:105-108`): a tiny function that returns
   `bool(os.environ.get("WATCH_LAUNCH_CMD"))` — i.e. true iff the operator set a launch command. In
   `main()` (`watch.py:491-498`), **before** `run()` and alongside `require_trusted_base_or_exit` /
   `_arming_startup_notice`, call a `require_launch_configured_or_exit()` that, when unset, writes a
   guidance message to `stderr` and `sys.exit(2)`. Recommended ordering: run it **after**
   `require_trusted_base_or_exit(BASE)` (keep the trusted-base refusal as the first gate — it is the
   security crux) but **before** `_arming_startup_notice()` and `run()`. The guidance message must:
   - name `WATCH_LAUNCH_CMD`;
   - state that the value must include the agent command **and its permission stance**;
   - point to the README **"Watcher (optional) — operator runbook"** section for the recipes;
   - exit with code **2** (consistent with the existing `require_trusted_base_or_exit` refusal).

3. **Make `_launch_argv()` defensive, not the gate.** `_launch_argv()` (`watch.py:333-351`) returns
   `list(DEFAULT_LAUNCH_CMD)` when `WATCH_LAUNCH_CMD` is unset. With the sentinel `None` this would
   become `list(None)` and raise. Because the startup gate guarantees `WATCH_LAUNCH_CMD` is set by
   the time `_launch_argv()` is ever reached, the clean shape is: the unset branch of `_launch_argv()`
   should not be the user-facing failure — it should not be reachable in normal operation. Keep a
   single source of truth: have `_launch_argv()` raise a clear internal error (or assert) if it is
   somehow called with no `WATCH_LAUNCH_CMD`, rather than re-implementing the guidance there. **The
   exit-2-with-guidance lives only in `main()`**, never in `_launch_argv()`/`_spawn()`.

**Why the startup gate, not a spawn-time exit (load-bearing).** `_spawn()` (`watch.py:355-372`) runs
**only after** `handle()` (`watch.py:376-393`) has POSTed `/handoff {state:working, owner}` and won
the lease on a `200`. The server bumps `turn_updated` only on a real reviewer→agent flip, **not** on
a `{state:working}` lease write (documented at `watch.py:18-23` and `app.py:629-636`). So a check
that exited inside `_spawn()`/`_launch_argv()` would: claim the lease → die → strand the review at
`turn==agent` with no re-surfacing (the edge-triggered `/wait?since=cursor` never re-emits it). The
startup gate means the watcher **refuses to start at all** — it never reaches a `/wait` poll, never
claims a lease — which is the only failure mode that does not strand a review.

### UI (`viewer.html` / `dashboard.html` / `static/`)

**None.** No browser-rendered surface changes, so no render-smoke is owed. (`watch.py` is a
standalone operator process, not served by the container.)

### Docs (`README.md`, `CLAUDE.md`, and the `watch.py` docstring/comments — same change)

The recipes move into the runbook, and **every "default Claude headless" assertion is swept** to the
new must-configure-stub truth. Exact spots found on `dev` (the ticket enumerates these; verify each
still reads as found at implementation time):

| File | Location | Current text (wrong under B) | Becomes |
|------|----------|------------------------------|---------|
| `watch.py` | module docstring, `:8` ("default Claude headless") | "spawns the operator's configured launch command (default Claude headless)" | "spawns the operator's configured launch command; with `WATCH_LAUNCH_CMD` unset it **refuses to start** (exit 2 with guidance) — there is no runnable default" |
| `watch.py` | config comment, `:42` | "Unset => DEFAULT_LAUNCH_CMD (Claude headless)." | "Required; unset => the watcher exits 2 at startup with guidance (must-configure stub)." |
| `watch.py` | `DEFAULT_LAUNCH_CMD` block comment + value, `:80-89` | "Default launch command … Claude headless … the ONLY Claude-specific knowledge in this file" | inert sentinel + comment explaining it is a must-configure stub, no runnable default, no Claude command in the loop |
| `README.md` | "Watcher" intro, `:185` | "spawns the operator's configured agent command **(default Claude headless)**" | "spawns the operator's **required** `WATCH_LAUNCH_CMD`; unset ⇒ refuses to start with guidance" |
| `README.md` | example block, `:190-195` | "default launch command (Claude headless)" comment + a `WATCH_LAUNCH_CMD='["claude","-p","..."]'` only on the non-loopback example | both examples set `WATCH_LAUNCH_CMD`; comment names the must-configure stub; add the **scoped recipe** (`--permission-mode dontAsk` + `--allowedTools "mcp__mdreview__*"`) and the **full-autonomy recipe** (`--dangerously-skip-permissions`, trusted/localhost only) |
| `README.md` | "Generic launch template" para, `:209` | "Unset, it falls back to a named `DEFAULT_LAUNCH_CMD` (Claude headless)." | "Unset, the watcher **refuses to start** (exit 2) with guidance to set `WATCH_LAUNCH_CMD` incl. its permission stance — there is no runnable default." |
| `README.md` | env-var table, `:270` | `\| WATCH_LAUNCH_CMD \| DEFAULT_LAUNCH_CMD (Claude headless) \| …` | default cell ⇒ **"required — unset exits 2 at startup"**; meaning cell notes the permission stance must be included |
| `CLAUDE.md` | watcher para, `:132` | "spawns a configured agent command **(default Claude headless)**" | "spawns the operator's **required** launch command; unset ⇒ the watcher refuses to start" |

**New runbook content** (in the README "Watcher" section, with the trade-off spelled out):

- **Scoped / recommended recipe (headless, mdreview-tools-only):**
  `WATCH_LAUNCH_CMD='["claude","-p","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","…"]'`.
  State explicitly that **`--allowedTools` alone is not robustly headless** — an unlisted tool the
  agent reaches for (`Read`/`Bash`/`TodoWrite`/a web fetch) falls through to the no-TTY permission
  prompt and stalls (a narrowed reprise of the defect); **`--permission-mode dontAsk` converts that
  fall-through into a clean deny** (listed tools approved, everything else denied outright, no
  prompt). State the **anchoring rule**: the MCP server segment must be glob-free — `mcp__mdreview__*`
  is valid; `mcp__*` / `*` are ignored with a startup warning.
- **Full-autonomy recipe (only if you accept it, trusted/localhost only):**
  `WATCH_LAUNCH_CMD='["claude","--dangerously-skip-permissions","-p","…"]'`.
- **Injection caveat (load-bearing, an explicit AC — see below).**

## Rollout phases

### Phase 1 — the fix (single phase, single ticket)

This is one shippable slice: the `watch.py` startup gate + the same-change docs sweep + the runbook
recipes + the injection caveat. There is no foundation-then-build sequencing to split; the docs
changes are wrong-until-the-code-lands and the code is undocumented-until-the-docs-land, so they
must ship together (the C1/C2/C3 precedent: `svc` ticket carries its same-change docs).

## Non-goals

- **Reworking the trusted-base / arming model.** C2 (`require_trusted_base_or_exit`,
  `check_trusted_base`) and C3 (arming allowlist) are unchanged. The new launch gate is **additive
  and independent** — it runs after the trusted-base gate and does not alter its decision table.
- **Bundling or shipping a specific agent runtime.** `WATCH_LAUNCH_CMD` stays a generic,
  operator-configured argv template. Option B makes the watcher *more* agent-agnostic (it removes
  the one runnable Claude default from the loop), not less.
- **Auto-relaunch / crash recovery (B1).** Out of scope and unchanged. The B1 no-relaunch model is
  exactly *why* the gate must be at startup, but this epic does not modify reaping/recovery.
- **`app.py` / `Dockerfile` / container changes.** `watch.py` is not served, not containerized, not
  imported by `app.py`. No `COPY` change, no route change, no UI change.
- **Validating that a *real* Claude agent completes the work.** The end-to-end self-check uses a
  **stub** launch command (the loop is generic by design). Proving the recommended `dontAsk` +
  `allowedTools` recipe drives a real model is an operator-runbook claim, verified by the critic's
  manual repro recorded in the requirement, not re-run in this ticket's automated self-check.

## Key constraints

- **Startup exit, never spawn-time exit.** The unconfigured refusal must happen in `main()` before
  `run()` (before any `/wait` poll, before any lease claim). A per-review exit inside
  `_spawn()`/`_launch_argv()` would strand the review at `turn==agent` (B1: `turn_updated` is not
  re-bumped by a lease write, so `/wait` never re-surfaces it). This is the load-bearing constraint.
- **Exit code 2**, matching the existing `require_trusted_base_or_exit` refusal — so an operator (and
  the self-check) can assert one refusal convention.
- **Stdlib-only, zero pip.** `watch.py` is a stdlib sibling of `mcp_server.py`. The fix adds no
  import and no dependency.
- **Additive / default-safe to the existing fail-closed gates.** The new gate composes with — does
  not replace or reorder the *meaning* of — `require_trusted_base_or_exit` and `_arming_startup_notice`.
- **Sweep ALL "default Claude headless" assertions** (the table above): a stale "falls back to a
  Claude default" line anywhere is a correctness bug post-B, since the behaviour is now "exits with
  guidance."
- **Validation gate is `python3 -m py_compile watch.py`** (no test framework). The end-to-end is a
  single runnable self-check script (below). No `docker build` (no infra change); no render-smoke
  (no UI change).
- **In-project scratch.** All smokes, throwaway service data dirs, and temp scripts go in the
  gitignored **`.scratch/`** (`.gitignore:10`), never `/tmp` or an external scratchpad. Use a
  **scratch port** for the throwaway service (e.g. `8151`), **avoiding the live `8139` and the
  compose `8137`**, and **never `docker compose up`** (the live instance is the compose service).

## Preferred execution order

1. `watch.py`: add `launch_configured()` + `require_launch_configured_or_exit()`, wire into `main()`,
   turn `DEFAULT_LAUNCH_CMD` into the inert sentinel, make `_launch_argv()` defensive.
2. Sweep the `watch.py` docstring + config comments (the three `watch.py` rows in the table).
3. Sweep `README.md` (intro, example block + new recipes, generic-template para, env-var table) and
   `CLAUDE.md` (watcher para); add the injection caveat.
4. `python3 -m py_compile watch.py`; run the end-to-end stub self-check (both arms below).
5. Commit (conventional subject with `MR-060`, `Co-Authored-By: Claude` trailer).

## Ticket breakdown

One ticket. `svc` layer, carrying its same-change docs (the C1/C2/C3 precedent: a `watch.py` change
ships with the runbook/docstring docs it invalidates). MR-060 is the next ID after MR-059 (verified
against `docs/process/tickets/`).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-060 | Watcher must-configure launch stub: refuse-to-start at startup when `WATCH_LAUNCH_CMD` unset + runbook recipes + injection caveat (svc + same-change docs) | svc | 1 |

### MR-060 acceptance criteria (for the ticket author to formalize)

1. **Inert default.** `DEFAULT_LAUNCH_CMD` is no longer a runnable command (an inert sentinel); no
   executable Claude command remains in `watch.py`'s loop.
2. **Startup refusal.** With `WATCH_LAUNCH_CMD` unset, `python3 watch.py` (against a *trusted/loopback*
   base, so the trusted-base gate passes) **exits 2 in `main()` before `run()`**, printing guidance
   that names `WATCH_LAUNCH_CMD`, says the value must include the permission stance, and points to the
   README "Watcher" runbook. The exit happens **before any `/wait` poll and before any lease claim**.
3. **Configured loop intact.** With a `WATCH_LAUNCH_CMD` set to a stub argv, the full loop runs:
   `/wait` → claim (`/handoff {state:working}` 200) → spawn the stub → reap → (stub `hand_back`s).
4. **Trusted-base gate still first.** The trusted-base refusal (C2) still fires first and unchanged
   for an untrusted base; the new launch gate does not alter the C2/C3 decision table.
5. **Docs swept.** Every spot in the table above is updated; no "default Claude headless" / "falls
   back to `DEFAULT_LAUNCH_CMD`" assertion survives in `README.md`, `CLAUDE.md`, or `watch.py`.
   Verified by the **loose single-term grep** (Verification step 2: `headless` /
   `DEFAULT_LAUNCH_CMD` / `WATCH_LAUNCH_CMD`, case-insensitive, across the three files) returning
   only new-behavior-consistent lines — a narrow `"default Claude headless"` regex misses the 4
   spots that lack the adjacent "default" word and would false-clear.
6. **Runbook recipes present.** The README "Watcher" section documents the scoped recipe
   (`--permission-mode dontAsk` + `--allowedTools "mcp__mdreview__*"`, with the "allowedTools alone
   stalls" rationale and the glob-free anchoring rule) and the full-autonomy recipe.
7. **Injection caveat (explicit AC, not a soft bullet).** The runbook states that on a public/armed
   base the launched agent **executes instructions embedded in reviewer comments** (prompt
   injection), so the `WATCH_LAUNCH_CMD` permission posture bounds the blast radius — use the scoped
   posture, **not** `--dangerously-skip-permissions`, on any base where comments aren't fully trusted.
8. **Validation:** `python3 -m py_compile watch.py` passes; the end-to-end self-check (below) passes
   both arms.

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Implementer puts the exit in `_spawn()`/`_launch_argv()` (the "obvious" place), stranding a review at `turn==agent`. | Constraint + AC #2 make the *startup* placement and "before any lease claim" explicit; the self-check asserts the exit happens before any `/wait` poll (no review is ever flipped/claimed in the unconfigured arm). |
| `_launch_argv()` `list(None)` crash if the startup gate is bypassed or reordered. | Make `_launch_argv()` defensive (raise a clear internal error if reached unset) so a future refactor that drops the gate fails loud, not with an opaque `TypeError`. |
| A "default Claude headless" assertion is missed in the sweep, leaving docs lying. | The table enumerates every spot found on `dev` (3 in `watch.py`, 4 in `README.md`, 1 in `CLAUDE.md`); AC #5 requires zero survivors; the **loose single-term grep** (`headless` / `DEFAULT_LAUNCH_CMD` / `WATCH_LAUNCH_CMD`, case-insensitive) surfaces every survivor for eyeball — a narrow `"default Claude headless"` regex misses the 4 spots lacking the adjacent "default" word and would false-clear. |
| Scoped recipe documented but wrong (e.g. `acceptEdits` reprises the no-op). | The requirement already verified `acceptEdits` does NOT clear the MCP gate; the runbook ships `dontAsk` + `allowedTools` (the functional posture) and explains why `allowedTools` alone stalls. Not re-verified against a live model in this ticket (a non-goal). |
| Operator confusion: "why won't it start?" | The guidance message names the env var and points to the runbook; the README example block now sets `WATCH_LAUNCH_CMD` in *both* examples so copy-paste works. |

## Verification

All commands run from the repo root; **all scratch artifacts under `.scratch/`** (gitignored), a
**scratch service port (e.g. `8151`)** avoiding `8139`/`8137`, and **never `docker compose up`**.

**1. Compile gate.**
```bash
python3 -m py_compile watch.py
```

**2. Docs-sweep grep (loose single-term; eyeball every hit reflects the inert stub).** A narrow
regex on "default Claude headless" misses 4 of the 8 spots (the ones that say "(Claude headless)"
without an adjacent "default", e.g. `watch.py:42/80`, `README.md:190/270`). Use the **loose
single-term** form the risk table names — grep case-insensitively for each surviving keyword across
the three files and **read every hit**: the sweep is verified iff every line returned is
new-behavior-consistent (no surviving "default Claude headless" / "falls back to a Claude default"
claim; remaining hits only describe the must-configure stub / runbook recipe / exit-2 behavior).
```bash
# Loose sweep: surface EVERY surviving mention, then eyeball each line is new-behavior-consistent.
grep -rn -i -e "headless" -e "DEFAULT_LAUNCH_CMD" -e "WATCH_LAUNCH_CMD" \
  watch.py README.md CLAUDE.md
# Expect the new truth to be present:
grep -rn -i -e "must-configure" -e "refuses to start" README.md
grep -rn -e "mcp__mdreview__\*" -e "dontAsk" README.md     # scoped recipe present
```

**3. End-to-end stub self-check (the runnable proof, both arms).** Stand up a throwaway service on a
scratch port, then exercise both arms. Sketch (the ticket ships the concrete script in `.scratch/`):

```bash
mkdir -p .scratch
PORT=8151
DATA=.scratch/watcher-launch-data
rm -rf "$DATA" && mkdir -p "$DATA"
# Throwaway service (NOT docker compose; a plain python3 run on the scratch port + data dir):
MDREVIEW_DATA="$DATA" PORT=$PORT python3 app.py >.scratch/svc.log 2>&1 &
SVC=$!
trap 'kill $SVC 2>/dev/null' EXIT
# wait for /healthz (GET, not -I — no do_HEAD):
until curl -s -o /dev/null "http://localhost:$PORT/healthz"; do sleep 0.2; done
BASE="http://localhost:$PORT"

# --- Arm A: UNCONFIGURED -> exit 2 at STARTUP, before any /wait poll ---
# loopback base => trusted-base gate passes; WATCH_LAUNCH_CMD UNSET => launch gate must fire.
MDREVIEW_BASE="$BASE" python3 watch.py >.scratch/unconf.out 2>.scratch/unconf.err
test $? -eq 2 || { echo "FAIL: expected exit 2"; exit 1; }
grep -q "WATCH_LAUNCH_CMD" .scratch/unconf.err || { echo "FAIL: no guidance"; exit 1; }
# Prove it exited BEFORE polling: the watcher prints its run() banner ("owner=… base=… cursor=")
# only inside run(); it must be ABSENT in the unconfigured arm.
grep -q "cursor=" .scratch/unconf.out && { echo "FAIL: reached run()/poll loop"; exit 1; }

# --- Arm B: CONFIGURED -> full loop (claim -> spawn stub -> hand back) ---
# stub launch command: a tiny script that reads $REVIEW_ID/$MDREVIEW_BASE/$MDREVIEW_OWNER and
# hands back under the SAME owner, then exits 0. /handoff dispatches on to/by/state (app.py:611-643),
# NOT on a bare `state` value: hand-back is `to == "reviewer" and state in ("done","blocked")`
# (app.py:625), so the body is {"to":"reviewer","state":"done",...} — NOT {"state":"reviewer"}.
cat > .scratch/stub-agent.sh <<'SH'
#!/usr/bin/env bash
curl -s -X POST "$MDREVIEW_BASE/api/reviews/$REVIEW_ID/handoff" \
  -H 'Content-Type: application/json' \
  -d "{\"to\":\"reviewer\",\"state\":\"done\",\"owner\":\"$MDREVIEW_OWNER\",\"message\":\"stub done\"}" >/dev/null
SH
chmod +x .scratch/stub-agent.sh
# create a review and flip it to turn==agent (Send to agent), then run the watcher with --backlog:
rid=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"t","markdown":"# t\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
# flip to agent (the viewer "Send to agent" path; reviewer->agent so turn_updated bumps).
# The flip arm is `to == "agent"` (app.py:628), NOT `state == "agent"`: body is {"to":"agent"}.
curl -s -X POST "$BASE/api/reviews/$rid/handoff" -H 'Content-Type: application/json' \
  -d '{"to":"agent"}' >/dev/null
# run the watcher briefly with the stub; --backlog so it sees the existing agent-turn flip:
timeout 15 env MDREVIEW_BASE="$BASE" \
  WATCH_LAUNCH_CMD="[\"$PWD/.scratch/stub-agent.sh\"]" \
  python3 watch.py --backlog >.scratch/conf.out 2>&1
grep -q "spawned child for review $rid" .scratch/conf.out || { echo "FAIL: never spawned"; exit 1; }
# the stub handed back => turn flips back to reviewer:
turn=$(curl -s "$BASE/api/reviews/$rid/status" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("turn"))')
test "$turn" = "reviewer" || { echo "FAIL: turn not handed back (got $turn)"; exit 1; }
echo "PASS: unconfigured exits 2 at startup; configured runs the full loop"
```

Notes the ticket must honour in the script:
- The exact `/handoff` request/response shape, the `turn` field name on `/status`, and the run()
  banner string are **verified against the code at implementation time** (the sketch cites
  `app.py:629-636` for the `turn_updated` semantics and `watch.py:408-409` for the banner; confirm
  before relying on them).
- Header/MIME checks (none needed here) would use `curl -sD - -o /dev/null` (GET header-dump), never
  `curl -sI` (no `do_HEAD` ⇒ 501). The `/healthz` readiness loop uses GET, not `-I`.
- Kill the throwaway service on exit; leave nothing outside `.scratch/`.

## Assumptions and open questions

All are recorded-and-proceed; none blocks G1 (Option B is decided and the mechanism is constrained
by the B1 model). No BLOCKER-FOR-HUMAN.

1. **(minor) Sentinel shape.** Assuming `DEFAULT_LAUNCH_CMD = None` as the inert sentinel, detected
   by a `launch_configured()` predicate on `WATCH_LAUNCH_CMD`. Justification: simplest detectable
   "unset," mirrors the existing `arming_configured()` pattern; any equally-inert sentinel (an empty
   list, a `_UNSET` object) is acceptable as long as `_launch_argv()` cannot run it.
2. **(minor) Gate ordering in `main()`.** Assuming order: trusted-base refusal → launch-configured
   refusal → arming notice → `run()`. Justification: keep the security-crux gate (trusted base)
   first; the launch gate is a config gate, fine to run second; the arming notice is informational.
   Any ordering that keeps **both** refusals before `run()` satisfies the constraint.
3. **(minor) Exit code.** Assuming **2**, matching `require_trusted_base_or_exit`. Justification: one
   refusal convention for operators and the self-check.
4. **(load-bearing, but defaulted safely) Scoped recipe content is the requirement's, not
   re-derived.** Assuming the runbook ships `--permission-mode dontAsk` + `--allowedTools
   "mcp__mdreview__*"` verbatim from the requirement (which the critic verified against the Claude
   permission docs), and does **not** re-test it against a live model in this ticket (a non-goal).
   Justification: B-vs-C is decided; the recipe is runbook content, and the requirement records the
   manual verification. If an operator later finds the recipe stalls, that is a docs follow-up, not
   this ticket's automated scope.
5. **(minor) Stub hand-back path.** The self-check stub hands back via `POST /handoff`. `/handoff`
   dispatches on `to`/`by`/`state` (verified `app.py:611-643`), **not** on a bare `state` value, so
   the bodies are: flip-to-agent `{"to":"agent"}` (`app.py:628`), hand-back
   `{"to":"reviewer","state":"done",…}` (`app.py:625`), and the watcher's own lease claim
   `{"state":"working","owner":…}` (`app.py:635-636`). The sketch uses these verified shapes; still
   re-confirm against `app.py` at implementation time.

## Review resolutions

**2026-06-24 — G1 staff-critic review** (`reviews/watcher-launch-fix-plan-review-2026-06-24.md`,
verdict PASS-WITH-NITS; core Option-B fix approved, both worth-considering items are in the plan's
deferred-verification scaffolding).

- **worth-considering #1 — self-check `/handoff` bodies use the wrong schema.** `/handoff` dispatches
  on `to`/`by`/`state` (`app.py:611-643`), not a bare `state`. Corrected the two hand-authored bodies
  in the Arm B self-check: the **flip-to-agent** is now `{"to":"agent"}` (was `{"state":"agent",…}`;
  flip arm is `to == "agent"`, `app.py:628`) and the **stub hand-back** is now
  `{"to":"reviewer","state":"done",…}` (was `{"state":"reviewer",…}`; hand-back is
  `to == "reviewer" and state in ("done","blocked")`, `app.py:625`). The watcher's own lease claim
  `{"state":"working","owner":…}` was already correct (matches `elif state == "working"`,
  `app.py:635-636`) and is unchanged. Updated assumption #5 to record the verified shapes. Arm B now
  flips and hands back with shapes that actually match the router, so it would pass.
- **worth-considering #2 — "zero survivors" sweep grep over-narrowed (caught 4 of 8).** Replaced the
  narrow `"default Claude headless"` / `"falls back to .*DEFAULT_LAUNCH_CMD"` regex with the **loose
  single-term** form already named in the risk table: grep case-insensitively for `headless`,
  `DEFAULT_LAUNCH_CMD`, and `WATCH_LAUNCH_CMD` across `watch.py README.md CLAUDE.md` and eyeball that
  every hit is new-behavior-consistent (the sweep is verified iff the grep returns only lines that
  describe the inert must-configure stub / runbook / exit-2 behavior, with no surviving "default
  Claude headless" claim). Updated Verification step 2, AC #5, and the risk-table row to point at the
  loose grep. The docs-sweep **table is unchanged** (the critic independently confirmed it lists
  exactly the 8 spots).
- **nit #3 — confirmed.** Kept the `_launch_argv()` defensive raise/assert on the unset branch; the
  critic confirmed it is a good belt (fails loud if a future refactor drops the startup gate), not
  dead code. The user-facing exit-2-with-guidance stays solely in `main()`.
- **nit #4 — confirmed.** Kept the scoped runbook recipe as `--permission-mode dontAsk` **plus**
  `--allowedTools "mcp__mdreview__*"` (not allowedTools-alone), with the "allowedTools alone stalls"
  rationale and the glob-free anchoring rule; the critic confirmed it documents the full posture
  correctly.
