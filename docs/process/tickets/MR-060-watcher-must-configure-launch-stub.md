---
id: MR-060
title: "Watcher must-configure launch stub — refuse-to-start at startup when `WATCH_LAUNCH_CMD` unset + runbook recipes + injection caveat (`docs`)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs  (svc; carries its same-change docs sweep per the C1/C2/C3 precedent)
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-20
epic: watcher-launch-fix
depends_on: []
branch: MR-060-watcher-must-configure-launch-stub
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The shipped `agent-watcher` watcher ships a runnable `DEFAULT_LAUNCH_CMD` (`claude -p …`) that
**silently no-ops headless**: a `claude -p` with no permission stance routes the agent's MCP tool use
to an interactive approval prompt; with no TTY to answer it, the agent claims the lease and hands back
without doing the work. Baking `--dangerously-skip-permissions` into the default is the opposite, equally
unsafe failure (it punches a hole through the C3 arming path). Option B (decided across both critic
rounds): make the default an **inert must-configure stub** so the watcher **refuses to start at startup**
with guidance when `WATCH_LAUNCH_CMD` is unset, and move the permission posture into runbook recipes. An
operator who runs `python3 watch.py` then gets either a working agent loop or a clear, guided refusal —
never a watcher that claims a lease and silently does nothing. One `svc` ticket carrying its same-change
docs sweep. No `app.py` / Dockerfile / UI change.

## Acceptance criteria

- [ ] **Inert default.** `DEFAULT_LAUNCH_CMD` is no longer a runnable command — it becomes an inert
      sentinel (e.g. `DEFAULT_LAUNCH_CMD = None`, with the old `claude -p` prompt text removed). No
      executable Claude command remains in `watch.py`'s loop; the only Claude string left in the file is
      in the guidance message, not an executable default.
- [ ] **`launch_configured()` predicate.** A tiny function mirroring the existing `arming_configured()`
      pattern (`watch.py:105-108`) returning `bool(os.environ.get("WATCH_LAUNCH_CMD"))` — true iff the
      operator set a launch command.
- [ ] **Startup gate in `main()` — `require_launch_configured_or_exit()`.** Called in `main()`
      (`watch.py:491-498`) **AFTER** `require_trusted_base_or_exit(BASE)` (keep the trusted-base refusal
      first — it is the security crux) and **BEFORE** `_arming_startup_notice()` / `run()`. When
      `WATCH_LAUNCH_CMD` is unset it writes guidance to `stderr` and `sys.exit(2)`. The guidance must:
      name `WATCH_LAUNCH_CMD`; state the value must include the agent command **and its permission
      stance**; point to the README "Watcher (optional) — operator runbook" section for the recipes; and
      exit with code **2** (matching the existing `require_trusted_base_or_exit` refusal convention).
- [ ] **Startup-not-spawn-time (load-bearing rationale).** The exit must live in `main()` at **startup**,
      **NOT** inside `_spawn()` / `_launch_argv()`. A spawn-time exit would claim the lease then die,
      stranding the review at `turn==agent`: `_spawn()` (`watch.py:355-372`) runs only after `handle()`
      (`watch.py:376-393`) POSTed `/handoff {state:working}` and won the lease on a `200`, and the server
      bumps `turn_updated` only on a real reviewer→agent flip, **not** on a `{state:working}` lease write
      (`app.py:629-636`), so the edge-triggered `/wait?since=cursor` never re-surfaces it. The startup gate
      means the watcher refuses to start at all — never reaches a `/wait` poll, never claims a lease — the
      only failure mode that does not strand a review.
- [ ] **`_launch_argv()` defensive, not the gate.** `_launch_argv()` (`watch.py:333-351`) returns
      `list(DEFAULT_LAUNCH_CMD)` when `WATCH_LAUNCH_CMD` is unset; with the `None` sentinel that would be
      `list(None)` and raise an opaque `TypeError`. Keep a single source of truth: the user-facing
      exit-2-with-guidance lives **only** in `main()`. Make `_launch_argv()`'s unset branch raise a clear
      internal error / assert (it is unreachable in normal operation because the startup gate guarantees
      `WATCH_LAUNCH_CMD` is set), so a future refactor that drops the gate fails loud, not with an opaque
      `TypeError`.
- [ ] **Trusted-base gate still first.** The trusted-base refusal (C2) still fires first and unchanged for
      an untrusted base; the new launch gate is additive and independent — it runs after the trusted-base
      gate and does not alter the C2/C3 decision table.
- [ ] **Docs swept — 8 spots.** Every spot in the epic plan's docs-sweep table is updated; no "default
      Claude headless" / "falls back to `DEFAULT_LAUNCH_CMD`" assertion survives in `README.md`,
      `CLAUDE.md`, or `watch.py`. The 8 spots: `watch.py` module docstring (`:8`), config comment (`:42`),
      `DEFAULT_LAUNCH_CMD` block comment + value (`:80-89`); `README.md` "Watcher" intro (`:185`), example
      block (`:190-195`), "Generic launch template" para (`:209`), env-var table (`:270`); `CLAUDE.md`
      watcher para (`:132`). Verified by the **loose single-term, case-insensitive grep** of `headless` /
      `DEFAULT_LAUNCH_CMD` / `WATCH_LAUNCH_CMD` across `watch.py README.md CLAUDE.md` (a narrow
      `"default Claude headless"` regex misses the 4 spots lacking the adjacent "default" word and would
      false-clear) — every returned line must be new-behavior-consistent (describes the must-configure
      stub / runbook recipe / exit-2 behavior).
- [ ] **Runbook recipes present.** The README "Watcher" section documents the **scoped / recommended
      recipe** (`--permission-mode dontAsk` **plus** `--allowedTools "mcp__mdreview__*"`) with the
      rationale that **`--allowedTools` alone is not robustly headless** (an unlisted tool the agent
      reaches for falls through to the no-TTY prompt and stalls — a narrowed reprise of the defect) and
      `--permission-mode dontAsk` converts that fall-through into a clean deny; plus the **glob-free
      anchoring rule** (the MCP server segment must be glob-free — `mcp__mdreview__*` valid; `mcp__*` / `*`
      ignored with a startup warning). And the **full-autonomy recipe**
      (`--dangerously-skip-permissions`, trusted/localhost only).
- [ ] **Injection caveat (explicit AC, not a soft bullet).** The runbook states that on a public/armed
      base the launched agent **executes instructions embedded in reviewer comments** (prompt injection),
      so the `WATCH_LAUNCH_CMD` permission posture bounds the blast radius — use the scoped posture,
      **not** `--dangerously-skip-permissions`, on any base where comments aren't fully trusted.
- [ ] **Local validation passes:** `python3 -m py_compile watch.py`, plus the **2-arm stub-launch
      end-to-end** self-check against a **localhost throwaway** mdreview service on a scratch port (e.g.
      8151 — never the live 8139, never `docker compose up`/8137), all scratch artifacts under
      `.scratch/` (gitignored):
  - [ ] **Arm A — unconfigured exits 2 at STARTUP.** Against a *trusted/loopback* base (trusted-base gate
        passes) with `WATCH_LAUNCH_CMD` **unset**, `python3 watch.py` exits **2** in `main()` printing
        guidance naming `WATCH_LAUNCH_CMD`, **before any `/wait` poll and before any lease claim** (the
        `run()` banner / `cursor=` line is **absent** in this arm — proof it never reached `run()`).
  - [ ] **Arm B — configured runs the full loop.** With `WATCH_LAUNCH_CMD` set to a stub argv, a review
        flipped to `turn==agent` drives the full loop: `/wait` → claim (`/handoff {state:working}` 200) →
        spawn the stub → reap → the stub hands back ⇒ `turn` flips back to `reviewer`. Uses the corrected
        `/handoff` schemas (`/handoff` dispatches on `to`/`by`/`state`, `app.py:611-643`): the
        **flip-to-agent** body is `{"to":"agent"}` (`app.py:628`) and the **stub hand-back** body is
        `{"to":"reviewer","state":"done",…}` (`app.py:625`) — NOT a bare `{"state":…}`.

## Notes / context

- Epic plan: `docs/process/epics/watcher-launch-fix-plan.md` — §"Recommended approach / Service
  (`watch.py`)" (the 3-step fix), §"Docs … (same change)" (the 8-spot sweep table + new runbook content),
  §"Key constraints" (startup-not-spawn-time, exit code 2, stdlib-only, in-project `.scratch/`),
  §"Verification" (the compile gate, the loose-grep sweep, the 2-arm stub self-check), the §"MR-060
  acceptance criteria" list, and §"Review resolutions" (the folded G1 fixes: corrected `/handoff` schemas
  + the loose single-term grep).
- `watch.py` line refs (verify they still read as found at implementation time): inert default at
  `watch.py:83-89` + the "ONLY Claude-specific knowledge" docstring claim at `watch.py:80-82` (becomes
  false, must be rewritten); the `arming_configured()` predicate to mirror at `watch.py:105-108`; `main()`
  at `watch.py:491-498`; `_launch_argv()` at `watch.py:333-351`; `_spawn()` at `watch.py:355-372`;
  `handle()` at `watch.py:376-393`; the `run()` banner at `watch.py:408-409`.
- `app.py` line refs (verify before relying): `/handoff` router at `app.py:611-643` (flip arm
  `to == "agent"` at `:628`; hand-back `to == "reviewer" and state in ("done","blocked")` at `:625`;
  lease claim `state == "working"` at `:635-636`); `turn_updated` semantics at `app.py:629-636`.
- No `app.py` / Dockerfile / UI change (the plan's non-goals); `watch.py` is not served, not
  containerized, not imported by `app.py`. No render-smoke owed (no product page touched; footgun #9 does
  not bite). Stdlib-only, zero pip (footgun #1) — the fix adds no import. Header/MIME checks (none here)
  would use `curl -sD - -o /dev/null`, never `curl -sI` (no `do_HEAD` ⇒ 501); the `/healthz` readiness
  loop uses GET, not `-I`.

## Work log

- `2026-06-24` — Implemented Option B in `watch.py`:
  - `DEFAULT_LAUNCH_CMD = None` (inert sentinel; removed the runnable `claude -p` argv and its
    prompt). No executable Claude command left in the loop.
  - Added `launch_configured()` (mirrors `arming_configured()`): `bool(os.environ.get("WATCH_LAUNCH_CMD"))`.
  - Added `require_launch_configured_or_exit()`; wired into `main()` AFTER
    `require_trusted_base_or_exit(BASE)` and BEFORE `_arming_startup_notice()` / `run()`. On unset
    `WATCH_LAUNCH_CMD` it writes guidance to stderr (names the var, says the value must include the
    permission stance, points to the README "Watcher" runbook) and `sys.exit(2)`. Comment records
    the startup-not-spawn-time rationale (a spawn-time exit strands `turn==agent`).
  - Made `_launch_argv()` defensive: the unset branch now `raise RuntimeError(...)` ("should have
    been caught at startup") instead of `list(None)`.
  - Docs sweep, all 8 spots: 3 in `watch.py` (module docstring, config comment, the
    `DEFAULT_LAUNCH_CMD` block comment incl. the now-removed "ONLY Claude-specific knowledge"
    claim); 4 in `README.md` ("Watcher" intro, example block, generic-template para, env-var table
    row); 1 in `CLAUDE.md` (watcher para). Every "default Claude headless" / "falls back to
    `DEFAULT_LAUNCH_CMD`" assertion flipped to the must-configure-stub truth.
  - Added the README "Watcher" runbook recipes: scoped/recommended (`--permission-mode dontAsk` +
    `--allowedTools "mcp__mdreview__*"`, with the "allowedTools alone stalls via the no-TTY
    fall-through" rationale and the glob-free anchoring rule) and full-autonomy
    (`--dangerously-skip-permissions`, trusted/localhost only), plus the explicit prompt-injection
    caveat.
- Files touched: `watch.py`, `README.md`, `CLAUDE.md` (committed `7b1dc06`). No `app.py` / Dockerfile
  / UI change.

## Validation

- `2026-06-24` — `python3 -m py_compile watch.py` → PASS (`PY_COMPILE OK`).
- Throwaway service: `MDREVIEW_DATA=.scratch/mr060-svc PORT=8151 python3 app.py` (scratch port,
  never 8139/8137; no `docker compose up`). `/healthz` → `{"ok": true}`.
- **Arm A (unconfigured exits 2 at STARTUP):** `env -u WATCH_LAUNCH_CMD
  MDREVIEW_BASE=http://localhost:8151 python3 watch.py` →
  - exit code **2**;
  - stderr guidance present, naming `WATCH_LAUNCH_CMD` and pointing to the README "Watcher" runbook;
  - the `run()` banner (`owner=… base=… cursor=…`) was **ABSENT** from stdout → it exited at startup,
    before any `/wait` poll and before any lease claim (no review was flipped/claimed in this arm).
- **Arm B (configured runs the full loop):** stub `WATCH_LAUNCH_CMD='["bash",".scratch/stub.sh"]'`
  (the stub POSTs lease-renew `{"state":"working","owner":…}` then hand-back
  `{"to":"reviewer","state":"done",…}`). Created a review, flipped it with `{"to":"agent"}`
  (`turn==agent`), ran `python3 -u watch.py --backlog` →
  - banner present (`watch.py: owner=… base=http://localhost:8151 cursor=0.000 (backlog=True)`);
  - `spawned child for review 5220d731ce …` → claimed the lease (200) and spawned the stub;
  - final `turn` flipped back to **reviewer** → the stub handed back; the gate does not break the
    normal path.
- Sweep grep (`grep -rin headless|DEFAULT_LAUNCH_CMD|WATCH_LAUNCH_CMD watch.py README.md CLAUDE.md`):
  every hit is new-behavior-consistent (must-configure stub / exit-2 / runbook recipe); no surviving
  "default Claude headless" / "falls back to `DEFAULT_LAUNCH_CMD`" claim. Positive checks confirm
  "refuses to start", `dontAsk`, and `mcp__mdreview__*` are present in the README.
- `.scratch/` artifacts cleaned up after the run.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
