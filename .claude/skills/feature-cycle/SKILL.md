---
name: feature-cycle
description: >-
  Drive a feature brief through the mdreview-service delivery cycle end-to-end: capture brief ->
  plan (via the mdreview-planner agent) -> independent staff-critic critique + fix loop (G1) ->
  create and groom tickets (G2) -> open a sprint (G6) -> implement (G3/G4/G5) -> render-smoke
  staff-critic sprint-close review (G7) -> fix -> close -> push dev -> update the standing PR to
  main (G8) -> auto cycle-retrospective. Use when the user gives a feature brief and says run the
  full cycle / take this through plan->tickets->sprint->PR, or says "feature-cycle" / "run the
  delivery cycle" / "resume the cycle". A thin orchestrator over docs/process/ (the gates are
  defined there; this skill drives them). Runs autonomously to the PR; the only human stop is the
  G8 merge.
---

# feature-cycle — orchestrator

You are driving this repo's **own** delivery process (`docs/process/README.md`, gates **G0-G8**).
This skill does **not** redefine the gates — it executes them. Read `docs/process/README.md` once
at start; it is the source of truth for every gate's pass condition. Keep this SKILL.md in
context and **open the matching reference file for the phase you are in** (progressive
disclosure):

- Phases 0-2 (capture, plan, G1 critique loop) -> `references/01-plan-and-critique.md`
- Phases 3-4 (tickets, sprint) -> `references/02-groom-and-open.md`
- Phase 5 (implement) -> `references/03-implement.md`
- Phases 6-10 (render-smoke + G7 review, fix, close, push, PR, auto retro) -> `references/04-close-and-ship.md`

## Autonomy posture

Runs **autonomously to the PR.** The independent staff-critic PASS (or product-owner sign-off)
stands in for a separate human G1 gate; the only human stop is **G8** (the standing `dev -> main`
PR is opened/updated, the user decides the merge). Flags can restore earlier stops (below). Do
not edit `docs/process/README.md` to reconcile autonomy with the written gate — if the user wants
the README changed, it goes through a normal reviewed `docs` ticket.

## Invocation

- `/feature-cycle <brief text | path-to-brief>` — start a new cycle from a brief.
- `/feature-cycle resume <epic-slug>` — detect state for that epic and continue.
- Flags: `--gate-at-plan` (stop for human sign-off after G1), `--ask` (stop and ask the planner's
  clarifying questions instead of assuming), `--plan-only` (stop after G1), `--name <slug>`.

## ALWAYS step 1 — slug-scoped state detection

Never trust `TRACKER.md` prose for counts or "the current sprint" (it is hand-maintained and goes
stale). Read **frontmatter + filenames + git** for the named epic slug and map to a phase:

| Observed (for THIS slug) | Phase to run |
|---|---|
| starting from a brief, no `requirements/<slug>.md` and no epic | 0 — capture |
| requirement exists, no `epics/<slug>-plan.md` | 1 — plan |
| epic plan exists, `gate:` not passed | 2 — critique loop |
| epic `gate: passed`, no tickets reference this epic | 3 — tickets |
| this epic's tickets are `ready`, none in an active sprint yet | 4 — sprint open |
| this epic's sprint is `active` and any committed ticket is not `done` | 5 — implement |
| all this epic's sprint tickets `done`, no close review file | 6 — close review |
| close review `status: open` | 7-8 — fix + re-review |
| close review `resolved`, sprint not `closed` / not pushed / PR not updated | 9 — ship |

**Rails (hard):**
- An explicit **epic slug is required for every phase past 0.** `resume` with no slug is a
  **hard error**: list the candidate epics and stop. Do not pick one.
- **"active" is not "outstanding."** A sprint can be `active` but parked-pending-close after
  shipping. Before implementing, confirm committed tickets are genuinely undone.
- On **resume**, frontmatter + git are the source of truth (the in-session task list is gone).

Announce: `Phase N (gate G#) for <slug>; next action: ...`, then open the matching reference file.
Use `TaskCreate`/`TaskUpdate` to track phases in-session (convenience only).

## Invariants (assert at every step)

- **Independence (G1/G7):** the `mdreview-planner` agent authors AND revises the plan; the
  `staff-critic` agent (or the product owner) reviews; the orchestrator (you) implements +
  renders. Author != reviewer, always. You never edit the plan you will implement, and the critic
  never reviews its own edits.
- **Commit hygiene:** every commit references the ticket ID. Conventional-commit subject
  (`feat(svc): ... (MR-###)`). This repo **keeps** the `Co-Authored-By: Claude` trailer (see
  README divergences).
- **Validation is the gate:** `python3 -m py_compile app.py` must pass before any commit; for
  `infra` changes, `docker build` must pass; for `ui` changes, a curl smoke + a browser open of
  the touched page.
- **Dates** are `Europe/London`.
- **Reconcile the board before the G7 critic:** all committed tickets `done`, the sprint's
  checkboxes/table updated, and `TRACKER.md` rows moved — done in Phase 6 *before* spawning
  `staff-critic`, so the reviewer spends its budget on substance, not bookkeeping. `close_review`
  and `status: closed` are set post-review in Phase 8 (the critic produces the review file).
- **No fabrication:** verify paths/IDs/state against disk before acting; on a genuine product
  fork with no safe default, **stop and ask** rather than guess. Never invent a review verdict.

## The phases (detail lives in the reference files)

| # | Phase | Gate | Actor | Human stop? |
|---|---|---|---|---|
| 0 | Capture brief verbatim -> `requirements/<slug>.md` | G0 | you | no |
| 1 | Plan + clarifying-Qs/assumptions | — | **mdreview-planner** | only `--ask`/`--gate-at-plan` |
| 2 | Critique + fix loop until PASS (<=3 rounds -> park) | **G1** | **staff-critic** + planner | only `--gate-at-plan` |
| 3 | Create + groom tickets (safe ID allocation) | G2 | you | no |
| 4 | Open sprint (safe sprint-NN allocation) | G6 | you | no |
| 5 | Implement per dev-flow; py_compile + smoke evidence before `done` | G3/4/5 | you | no |
| 6 | Render-smoke touched pages -> evidence; critic reviews evidence + ACs | **G7** | you + **staff-critic** | park if smoke fails |
| 7 | Fix findings | — | you | no |
| 8 | Second critic pass until resolved/carried; close sprint, write retro | G7 | **staff-critic** | no |
| 9 | Push `dev`; update-or-open the standing PR dev->main | **G8** | you | **STOP — never merge** |
| 10 | Cycle retrospective (**automatic**, every run incl. parks) | — | **cycle-retrospective** | no |

## Hard rails (autonomous mode)

- Explicit slug required; **fail loud** on any ticket-ID / sprint-number / file collision — never
  silently overwrite or reuse.
- `python3 -m py_compile app.py` must pass before any commit. For a running container, rebuild
  with `docker compose up -d --build` and smoke `curl localhost:8137/healthz`.
- **Phase 6 render-smoke must succeed** (every touched page opens and renders) or the cycle
  **parks** — it does not pass G7.
- **Parking is discoverable:** on any park (critique exceeded rounds, smoke failed, collision,
  blocker), write a `## BLOCKED` note into the epic plan and the sprint file stating the blocker,
  and open/update a **draft PR** titled `[BLOCKED] <slug>: <reason>`. **Arm the retro gate** (drop
  `.claude/.feature-cycle-pending-retro` containing the slug) and run Phase 10 before stopping.
- **Phase 10 is hook-enforced.** A `Stop` hook (`.claude/hooks/enforce-cycle-retro.sh`, wired in
  `.claude/settings.json`) blocks the session from ending while the marker exists. The marker is
  armed entering Phase 9 / on park and cleared only by Phase 10. The hook fails open if `jq` is
  missing; the manual unstick is `rm .claude/.feature-cycle-pending-retro`. Do not delete it by
  hand to escape — run the retro.

When you reach Phase 9 and the PR is open/updated (or the run parks earlier), **Phase 10 runs
automatically** — spawn `cycle-retrospective` to meta-review the run before you finish. Then
**report the PR URL plus the retro's top suggestions, and stop.** Merging `dev -> main` is the
user's G8 decision and is never automated; retro suggestions are proposed, never auto-applied.
