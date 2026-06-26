---
review_of: sprints/sprint-20.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-20 close review (G7) — epic `watcher-launch-fix`, MR-060

Independent staff-critic review. I did not implement MR-060. I read the shipped `watch.py`,
the `README.md` "Watcher" section, and the `CLAUDE.md` watcher pointer on `dev`, verified them
against the ticket ACs, and re-exercised the load-bearing behavior against a throwaway service
in `.scratch/` (port 8153; live 8139 / compose 8137 untouched; no `docker compose up`).

## Verdict

**PASS.** Every shipped AC is met. The startup gate is in the correct place in `main()`
(after `require_trusted_base_or_exit`, before `_arming_startup_notice`/`run`), exits 2 at
startup before any `/wait` poll or lease claim, and the configured path still runs the full
loop. The 8-spot docs sweep is complete with no surviving contradictory "default Claude
headless / falls back" claim. Scope is compliant: MR-060 touched only `watch.py`, `README.md`,
`CLAUDE.md` — no `app.py`/Dockerfile/UI change, so no render-smoke is owed.

## What I re-ran (with results)

1. **Arm A — unconfigured exits 2 at STARTUP.** `env -u WATCH_LAUNCH_CMD
   MDREVIEW_BASE=http://localhost:8153 python3 watch.py` → **exit 2**; stderr guidance names
   `WATCH_LAUNCH_CMD` and points to the README "Watcher (optional) — operator runbook"; the
   `run()` banner (`owner=… base=… cursor=…`) was **ABSENT** from stdout; the service review
   list stayed empty (no review flipped/claimed). Confirmed it exits before `run()`, the whole
   point of the gate.
2. **Arm B — configured runs the full loop.** Stub `WATCH_LAUNCH_CMD='["bash",".scratch/stub.sh"]'`
   (POSTs `/handoff {state:working,owner}` then `/handoff {to:reviewer,state:done,owner,message}`).
   Created a review, flipped it `{to:agent}` (`turn==agent`), ran `python3 -u watch.py --backlog`:
   banner present (`cursor=0.000 (backlog=True)`) → `spawned child …` → stub ran with the
   `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` env contract → claimed lease (200) → handed back
   → final `turn==reviewer`, `agent_status.state==done`. Baton returned in ~1s. The gate does
   not break the normal path.
3. **Sentinel safety.** `_launch_argv()` on unset `WATCH_LAUNCH_CMD` raises **`RuntimeError`**
   (clear "should have been caught at startup" message), **not** a `list(None)` `TypeError`.
   `launch_configured()` returns `False` for unset AND for empty-string `WATCH_LAUNCH_CMD`, and
   an empty-string value also exits 2 at startup (no `run()` banner) — consistent with
   `_launch_argv()`'s `if not raw` branch (no `shlex.split("")==[]` spawn-nothing edge).
   `DEFAULT_LAUNCH_CMD = None` is referenced only at its definition and in docstrings — no code
   reads it, so the sentinel breaks no reader.
4. **Gate ordering (load-bearing).** Untrusted base + unset launch → the **trusted-base**
   refusal fires first and exits 2; the launch-gate guidance is absent in that run, proving the
   launch gate is genuinely additive and second (the security crux stays first).
5. **Docs sweep + scope.** Loose grep of `headless|DEFAULT_LAUNCH_CMD|WATCH_LAUNCH_CMD` across
   `watch.py README.md CLAUDE.md`: every hit is must-configure-consistent. Every `headless`
   occurrence is a recipe descriptor ("robustly headless") or the negated defect ("silently
   no-ops headless"); zero affirmative "default/falls back to Claude" claim survives. README
   runbook carries the scoped recipe (`--permission-mode dontAsk` **plus**
   `--allowedTools "mcp__mdreview__*"`, with the "allowedTools alone stalls" rationale + glob-free
   anchoring rule), the full-autonomy recipe, and the explicit prompt-injection caveat. MR-060
   commit `7b1dc06` touched only `watch.py`/`README.md`/`CLAUDE.md`; app.py last changed in MR-055
   (the 180-line app.py delta vs `main` is pre-existing dev drift from prior merged sprints, not
   this ticket). Live instance on 8139 returned `{"ok": true}` throughout.

## Findings

### Blocking

None.

### Worth considering

- **(worth-considering) `claude -p` literal appears inside the guidance and recipes.** This is
  intentional per the AC ("the only Claude string left … is in the guidance message"), and it is
  correct here. Flagging only so a future reader does not mistake the guidance-message `claude`
  for a resurrected runnable default — it is inside an `sys.stderr.write` string and an example
  argv, never assigned to `DEFAULT_LAUNCH_CMD` or passed to `Popen`. No change needed.

### Nits

- **(nit) `_launch_argv()` non-array JSON falls through to `shlex.split(raw)`.** If a future
  operator sets `WATCH_LAUNCH_CMD='"claude -p"'` (a bare JSON string), it is `shlex`-split with a
  stderr note. That is pre-existing behavior (untouched by MR-060) and reasonable; noting it only
  because the new must-configure framing makes `WATCH_LAUNCH_CMD` the single load-bearing knob, so
  its parse edges are now more operator-facing. Not in scope for this sprint.

## Resolution log

- 2026-06-24 — staff-critic — Independent G7 review. Verdict **PASS**. Re-ran Arm A (exit 2 at
  startup, no banner, no claim), Arm B (configured full loop, baton returned to reviewer),
  sentinel safety (RuntimeError not TypeError; empty-string == unset), gate ordering
  (trusted-base first), and the docs sweep (no surviving contradictory claim). Scope compliant
  (no app.py/Dockerfile/UI change → no render-smoke owed); live 8139 healthy. All scratch
  artifacts under `.scratch/` and removed after the run. No blocking findings; one
  worth-considering and one nit, both non-blocking and out of scope for MR-060.

## Resolution log

- 2026-06-24 — Independent G7 review (1-ticket sprint). Verdict PASS, no blockers. The critic re-ran
  Arm A (unset WATCH_LAUNCH_CMD → exit 2 at startup, run() banner absent, no lease claimed), Arm B
  (configured stub → claim → spawn → hand-back), sentinel safety (_launch_argv raises; empty-string
  treated as unset; None has no other reader), gate ordering (trusted-base refusal first), and the
  docs sweep (no surviving "default Claude headless" claim; recipes + injection caveat present) against
  a .scratch/ throwaway service. Two no-change observations. Review status: resolved; sprint-20 closed
  at G7; the watcher-launch-fix epic marked done (single ticket).
