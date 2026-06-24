---
review_of: epics/agent-watcher-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: smooth — C1's top fix held (scaffold-before-dispatch), per-chunk G1 caught a real backwards model (B1); only new friction was an external human commit landing mid-cycle
status: resolved
---

# Cycle Retrospective — agent-watcher Chunk 2 (sprint-18, MR-056 + MR-057)

Reviews the RUN, not the feature. **Deliberately short: only what is NEW or changed vs the C1 retro**
(`docs/process/reviews/agent-watcher-c1-cycle-retro-2026-06-24.md`) — C1's findings are not repeated.
C2 shipped the watcher core (`watch.py`: fail-closed credentialed spawner + claim-before-spawn loop).
G1 PASS-WITH-NITS (own focused review, B1 + WC-1..5 folded, no second round), G7 PASS first-pass
(critic re-ran the security crux + crash model on a scratch-port instance), 2 trivial nits applied
post-G7, **0 parks, 0 carry-overs.**

## What changed since C1 (load-bearing)

- **C1's #1 fix worked.** The orchestrator committed the full planning scaffold — both tickets, the
  sprint, the G1 review, the expanded plan (6 files, `8a43de7`, 01:40) — to `dev` **before** the first
  implementation subagent committed (`5ed6e93`, 01:44). The C1 failure mode (scaffold stranded
  *between* the two ticket merges, reconstructed after MR-054 was already merged) **did not recur.**
  Subagents committed only their own ticket; the orchestrator merged from `dev`. This was the run's
  single biggest friction last cycle and it is gone. Confirms the C1 suggestion was the right call —
  worth promoting from advisory to a written skill rule (suggestion 1).

- **Giving a security-bearing chunk its OWN G1 paid off directly.** Under the one-epic-many-chunks
  shape, C2 could have ridden the epic's original G1. Instead it got a focused G1 because it introduces
  the credentialed spawner — and that review's **B1** was a genuine correctness reframe, not a nit:
  the plan claimed a crashed child gets "re-claimed and re-spawned" bounded by the hourly cap, but
  `turn_updated` bumps only on a real reviewer→agent flip (`app.py:630-634`), so a crashed child
  **strands the baton at `turn==agent` forever** under the default seed — fail-safe under-spawn, the
  *opposite* of the plan's relaunch-storm. The stated cap rationale was backwards and was rewritten;
  G7 then independently reproduced the stranded-baton (`turn_updated` byte-identical across ~14s of
  ticks) and the backlog-only relaunch. A shared epic G1 would likely have skated past this.

## Prioritized suggestions (SUGGEST-ONLY — not applied)

1. **[skill] Promote C1's "scaffold-before-dispatch" from advisory to a written feature-cycle rule —
   it is now proven, not hypothetical.** C1 *suggested* it; C2 *did* it by hand and the friction
   vanished. Close the loop: pin in the skill that the orchestrator commits all planning artifacts
   (plan, G1 review, sprint, all tickets, TRACKER) to `dev` before dispatching any implementation
   subagent, subagents commit only their own ticket on a branch, and merges come from `dev` never a
   ticket branch. This is the one suggestion most de-risked by evidence this cycle.

2. **[skill] Make "a security/credential-bearing chunk gets its own focused G1, even within a
   one-epic-many-chunks epic" an explicit skill heuristic.** C2 proved the value: the dedicated G1
   surfaced B1 (a backwards safety model that would otherwise have been asserted at close). Pin the
   trigger — a chunk that introduces a new trust boundary, spawner, credential flow, or fail-closed
   control re-runs G1 on its expanded section rather than inheriting the epic's plan-gate. Cheap
   insurance against a load-bearing security claim shipping wrong.

3. **[process] Note that an autonomous cycle can run concurrently with the human's own local commits,
   and the standing PR will carry them.** New this run: a stale `.git/index.lock`/`HEAD.lock` blocked
   a commit; the cause was the **user's own** `e451969` ("feat(site): redesign landing page",
   author `waqas`) landing on `dev` mid-cycle — an external parallel commit, not a subagent. The
   orchestrator correctly verified no cross-contamination and proceeded, but the `main..dev` range
   (the standing PR) now bundles the C2 watcher work **and** the unrelated site redesign. Add one
   line to the process: on a lock-contention or unexpected `dev` HEAD during a cycle, check
   `git log --author` to distinguish a subagent race from a human commit, and flag to the user when
   the cycle's PR has picked up commits the cycle did not author (so the PR scope is honest).

4. **[process] The `reviews/` directory split (4th-time recurrence) held trivially this cycle because
   C2 has no render evidence — but it is STILL unratified.** Gate `.md` (the C2 G1 and sprint-18
   close) went under `docs/process/reviews/` and no bulky evidence dir was produced (no product page
   to render). So the convention was not stressed, but it remains unwritten — see C1 retro #2 for the
   full case. One README Layout line still closes it permanently. Lower priority *this* cycle only
   because nothing could go wrong with no evidence to misplace; the standing recommendation is
   unchanged.

## Metrics

G1 rounds: 1 (own focused C2 review; PASS-WITH-NITS, B1 + WC-1..5 folded into MR-056/MR-057, no second
round). G7 rounds: 1 (PASS first-pass; 1 worth-considering + 2 cosmetic nits, applied post-close in
`8abc9b2`, 0 blocking). Tickets shipped: 2 (MR-056, MR-057); carried: 0. Parks: 0. Wrong load-bearing
assumptions: **1** — the plan's crash-loop bound (B1), backwards (stranded baton, not relaunch storm),
caught at the dedicated G1 and rewritten before code, re-verified at G7. New friction: 1 (external
human commit `e451969` on `dev` mid-cycle → lock contention + PR now carries an unrelated site change).
C1's top friction (stranded scaffold): **resolved this cycle.**

## Resolution log

- 2026-06-24 — Retro produced at C2 sprint close (sprint-18). SUGGEST-ONLY; none applied
  (cycle-retrospective never edits process/skill/agents). Headline: C1's #1 fix worked in practice
  (suggestion 1 promotes it to a written rule); the dedicated per-chunk G1 caught the backwards B1
  crash model (suggestion 2); the only new friction was a concurrent human commit on `dev`
  (suggestion 3). The `reviews/` split (suggestion 4) is a 4th recurrence, untested this cycle.
