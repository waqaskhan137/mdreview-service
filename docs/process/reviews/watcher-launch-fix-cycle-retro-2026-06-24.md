---
review_of: epics/watcher-launch-fix-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: Smooth — clean 1-ticket fix on a pre-gated brief; 0 parks, 0 carry-overs; the two prior-retro lessons held.
status: resolved
---

# Cycle Retrospective — watcher-launch-fix (sprint-20, MR-060)

Subject is the **run**, not the feature. This was a single-ticket fix with an unusual,
already-critic-gated origin. It ran clean.

## One-line verdict

Smooth. A pre-gated brief turned G1 into a fast confirm; both prior-retro process lessons were
applied and held; 0 parks, 0 carry-overs. One trivial `.scratch/` friction.

## What went well (load-bearing)

- **Pre-gated brief → feature-cycle path worked.** The Option-B design was settled in mdreview
  (`05ff768234`, two staff-critic rounds, verdict GO) + GH #23 **before** G0, so G1 explicitly
  did not re-litigate the design (`watcher-launch-fix-plan-review-2026-06-24.md:13-17`) and instead
  gated only implementability. Result: a single G1 round, PASS-WITH-NITS, both nits in the
  *self-check scaffolding* (wrong `/handoff` schema; over-narrow sweep-grep), not the fix. No
  re-litigation, no design churn.
- **Both agent-watcher retro lessons held.** (1) The scaffold landed on `dev` before the impl
  subagent was dispatched (commit `4e35b2c` scaffold precedes `7b1dc06` feat) — no stranded-scaffold
  tangle. (2) Impl + G7 smokes ran entirely in `.scratch/` (port 8153; live 8139 / compose 8137
  untouched — `sprint-20-close-review-2026-06-24.md:14-16`) — no `/tmp` writes, no permission-hook
  trips.

## Top suggestions (prioritized, suggest-only)

1. **Promote the two held lessons from advisory to written rails.** [process] Both fixes worked
   *because the orchestrator remembered prior retros*, not because anything enforces them — neither
   "commit scaffold to `dev` before dispatching the impl subagent" nor "all smokes go in `.scratch/`,
   never `/tmp`" appears in `docs/process/README.md` (grep: 0 hits) or the skill
   (`.claude/skills/feature-cycle/`: 0 hits). They have now held across consecutive cycles; that is
   the threshold to write them into the Working Agreement / Development flow so they survive a
   future orchestrator that hasn't read the retros.

2. **Add a one-line "don't `rmdir` `.scratch/`, only its contents" rule to the smoke rail.**
   [skill] The only friction this run: a subagent's cleanup removed the `.scratch/` **directory**,
   which broke a later orchestrator `>` redirect into it (the PR-body update); a one-line recreate
   fixed it. When suggestion #1 writes the `.scratch/` rail, pair it with "clean files, leave the
   dir" so concurrent/later writers don't lose their target. Cheap, prevents a recurring class.

3. **Document the "pre-gated brief" path as a first-class entry mode.** [process] This brief
   entered already critic-gated (review-workflow, two rounds, GO) and G1 correctly degraded to a
   confirm. That is a genuinely good shape worth naming in `docs/process/README.md` "Starting things"
   — when a brief carries a resolved mdreview design review, G1 gates implementability only and
   should not re-open the design. Names the path so the next pre-gated brief isn't accidentally
   re-litigated.

4. **Backlog the `_launch_argv()` non-array parse edge.** [feature] G7 nit
   (`sprint-20-close-review-2026-06-24.md:79-83`): a bare-JSON-string `WATCH_LAUNCH_CMD` (e.g.
   `'"claude -p"'`) falls through to `shlex.split`. Pre-existing and out of MR-060 scope, but the
   new must-configure framing makes `WATCH_LAUNCH_CMD` the single load-bearing knob, so its parse
   edges are now more operator-facing. Low priority; capture it so it isn't rediscovered live.

## Metrics

- **G1 rounds:** 1 (PASS-WITH-NITS; both nits in self-check scaffolding, folded at ticket-authoring, no second round).
- **G7 rounds:** 1 (PASS; critic re-ran both arms + sentinel + gate-ordering + docs sweep).
- **Tickets:** 1 shipped (MR-060), 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0 (G1 verified all load-bearing claims against `watch.py`/`app.py`; none overturned).
- **Note (not new):** the `reviews/` directory-split convention (gate `.md` under `docs/process/reviews/`) held again — its 6th recurrence; tracked, no action.
