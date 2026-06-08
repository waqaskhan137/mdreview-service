# Phases 0-2 — capture, plan, G1 critique loop

## Phase 0 — capture the brief (G0)

If `requirements/<slug>.md` does not exist, create it from the brief **verbatim**. Do not groom,
reword, or "improve" it. Add frontmatter:

```yaml
---
slug: <slug>
captured: YYYY-MM-DD            # Europe/London
source: <where it came from>    # this session, a message, a meeting
related_epic: epics/<slug>-plan.md
---
```

Then a verbatim body, and an `## Amendments` section for any later dated changes. Never edit the
text above an amendment. G0 passes once the file exists and is unedited.

## Phase 1 — plan (mdreview-planner authors)

Spawn the **`mdreview-planner`** agent with the requirement path. It explores the codebase,
surfaces clarifying questions + explicit assumptions, and writes `epics/<slug>-plan.md` strictly
to `templates/epic-plan.md`. The planner is the **author**; you do not edit the plan you will
implement (that would break G1 independence).

- With `--ask`: relay the planner's blocker questions to the user and stop. Otherwise the planner
  records assumptions and proceeds.
- The epic starts `status: draft`, `gate: G1 not passed`.

## Phase 2 — critique + fix loop (G1)

G1 requires a recorded **independent** review (reviewer != author). Two valid reviewers:

- the **`staff-critic`** agent (global), or
- the **product owner** (the user) — e.g. notes left in the mdreview viewer itself.

Loop (max 3 rounds, then park):

1. Spawn `staff-critic` on `epics/<slug>-plan.md`. It writes
   `reviews/<slug>-plan-review-YYYY-MM-DD.md` (round suffix `-r2`, `-r3`) with frontmatter
   `review_of`, `gate: G1`, `reviewer`, `independent: true`, `verdict`, `status: open`, and a
   findings list + Resolution log.
2. If PASS with no blockers -> set the review `status: resolved`, set the epic
   `gate: passed YYYY-MM-DD`, `status: active`, link `review:`. G1 cleared.
3. If blockers -> spawn **`mdreview-planner`** again to REVISE its own plan (it stays the author,
   preserving independence), update the Resolution log, re-review. Repeat.
4. 3 rounds without PASS -> **park** (see SKILL hard rails): `## BLOCKED` note, draft PR, arm the
   retro marker, run Phase 10.

**Recording a real human review honestly:** if the product owner reviewed the plan (e.g. in the
viewer), record what actually happened — their notes as findings, their sign-off as the verdict,
`reviewer: product-owner (<name>)`, `independent: true`. Never synthesize a `staff-critic` verdict
that did not run.

Only after G1 passes do you proceed to Phase 3 (tickets). Do not create tickets for a `draft`
epic.
