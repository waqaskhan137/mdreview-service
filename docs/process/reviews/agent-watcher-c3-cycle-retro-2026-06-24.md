---
review_of: epics/agent-watcher-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: gates clean (per-chunk G1 caught a real pre-impl pending-set loop), but a subagent wrote scratch OUTSIDE the repo and hung ~7-8h on the permission hook — the run's only friction, and a recurrence
status: resolved
---

# Cycle Retrospective — agent-watcher Chunk 3 (sprint-19, MR-058 + MR-059) — EPIC CLOSE

Reviews the RUN, not the feature. **Deliberately short: only what is NEW vs the C1 and C2 retros**
(`agent-watcher-c1-cycle-retro-2026-06-24.md`, `agent-watcher-c2-cycle-retro-2026-06-24.md`) — their
findings are not repeated. C3 shipped MR-058 (local arming relaxing C2's fail-closed Step-0) +
MR-059 (per-review attempt cap + the full operator runbook), closing the 3-chunk `agent-watcher`
epic. Own focused G1 PASS-WITH-NITS, G7 PASS-WITH-NITS first-pass, **0 parks, 0 carry-overs.**

## What changed since C2 (load-bearing)

- **The per-chunk G1 caught a real pre-implementation bug against shipped code, not a plan nit.** C3's
  W1: the plan's literal "skip un-armed reviews without a claim" (an early `return False` in
  `handle()`) would have landed un-armed reviews in the `_at_capacity()`-keyed `pending` set whenever
  the watcher was at capacity, then `_drain_pending` retries them **forever** — `run()` keys pending
  membership on `_at_capacity()`, not on *why* `handle()` returned False (`watch.py:302-304` at review
  time). Fixed before code by gating in `run()` with a `continue` **before** `handle()`
  (`watch.py:443-447`), leaving `handle()`/`pending` byte-for-byte C2; G7 reproduced it under
  `MAX_CONCURRENT=0` (test B2: un-armed Y logged once, never claimed, never in `pending`). This is the
  C1/C2 "per-chunk G1 earns its keep" pattern, but sharper: the catch was an interaction with
  *already-shipped* C1/C2 code the plan would otherwise have carried into the implementer's hands.

## Prioritized suggestions (SUGGEST-ONLY — not applied)

1. **[skill] Mandate in-project `.scratch/` (and non-8139/8137 ports) in EVERY implementation/smoke
   subagent prompt — this run's worst friction, and a recurrence.** An MR-058 subagent wrote
   throwaway-service data dirs to `/tmp` and the external scratchpad (outside the repo), tripping the
   user's "stay in project" permission hook repeatedly; one subagent **hung ~7-8 HOURS** on the
   prompts before the user intervened ("do not create files outside the project … idiot"). This recurs
   against the existing `temp-files-in-project-not-scratchpad` memory, which already said to keep temp
   files in-project. The mid-cycle fix (gitignored `.scratch/`, commit `75a9798`, landed *between* the
   two ticket merges; G7 then used `.scratch/` port 8156) worked — make it a standing skill rail, not a
   per-run rediscovery. The orchestrator **cannot see or approve a subagent's file writes**, so a single
   out-of-project write stalls the whole run on a hook the orchestrator can't clear — the highest-cost,
   lowest-visibility failure mode in the autonomous loop. Every dispatched subagent prompt must pin:
   scratch under `./.scratch/`, throwaway service ports avoiding 8139/8137, clean up after.

2. **[process] When a chunk gates a relaxation of a prior chunk's safety control, make the no-regression
   the explicit G1+G7 crux.** C3 relaxed C2's fail-closed Step-0 EXIT; both gates correctly treated
   "C2 EXIT preserved byte-for-byte when arming unconfigured" as *the* load-bearing claim (G1 read
   `check_trusted_base`; G7 test A re-ran the un-vouched+no-arming EXIT). This worked by good judgment,
   not by a written rule. Pin it: a chunk that loosens an earlier fail-closed/security control owes an
   explicit "the old refusal still fires on the old inputs" assertion at both gates. Generalizes C2's
   "security chunk gets its own G1" (already suggested) to the relaxation case.

3. **[process] The `reviews/` directory split held a 5TH time but is still unwritten.** Gate `.md` (C3
   G1 + sprint-19 close) again went under `docs/process/reviews/`; the render-evidence dir convention
   was unstressed (C3 touches no product page — G7 correctly ruled the smoke's absence COMPLIANT, not a
   gap). Fifth recurrence across retros; the one-line README Layout fix from the C1 retro (#2) still
   closes it. Noted, not re-argued.

## Epic-level wrap (agent-watcher now `done`)

The **one-epic-many-sprints, per-chunk-focused-G1** structure worked well across C1→C2→C3 and is worth
keeping as the default for a multi-chunk security feature. Splitting the epic plan into three chunks
each with its **own** G1 on its expanded section (rather than one upfront epic G1) caught a distinct,
load-bearing, against-shipped-code issue *every* chunk — C2's backwards crash-loop bound (B1, fail-safe
under-spawn), C3's `pending`-set retry loop (W1) — that a single front-loaded plan-gate would almost
certainly have skated past, because each chunk's hazard only became concrete once the prior chunk's code
existed to interact with. Cost was low: each chunk was 2 tickets, 1 G1 round, 1 G7 round, 0 parks, 0
carry-overs across all three sprints. The structure's real win is that the gate's depth tracked the
code's actual surface as it grew, instead of reviewing an abstraction of it once.

## Metrics

G1 rounds: 1 (own focused C3 review; PASS-WITH-NITS, W1-W4 + N1-N2 folded into MR-058/MR-059, no second
round). G7 rounds: 1 (PASS-WITH-NITS first-pass; 1 worth-considering doc nit + 1 accepted log-noise nit,
0 blocking; nit fixed in `947f5ef`). Tickets shipped: 2 (MR-058, MR-059); carried: 0. Parks: 0. Wrong
load-bearing assumptions: **0** at plan level — W1 was a plan *mechanism* bug (literal early-return),
caught at the dedicated G1 and re-specced to the `run()`-side gate before code, not a wrong assumption.
New friction: **1, severe** — a subagent wrote scratch outside the repo and hung ~7-8h on the
"stay in project" hook (recurrence of `temp-files-in-project-not-scratchpad`); fixed mid-cycle with
gitignored `.scratch/` (`75a9798`). Recurrence flagged: the `reviews/` directory split (5th retro).
Epic: `agent-watcher` **DONE** (C1+C2+C3; 6 tickets MR-054..MR-059; 3 sprints; 0 parks total).

## Resolution log

- 2026-06-24 — Retro produced at C3 sprint close (sprint-19), which also closes the agent-watcher epic.
  SUGGEST-ONLY; none applied (cycle-retrospective never edits process/skill/agents). Headline: the gates
  were clean (per-chunk G1's W1 caught a real pre-impl pending-set loop), but a subagent's out-of-project
  scratch write hung the run ~7-8h on the permission hook — suggestion #1 (mandate in-project `.scratch/`
  in subagent prompts) is the run's top fix and a recurrence. Epic-level: the per-chunk-G1 structure
  caught a load-bearing issue every chunk and is worth keeping.
