---
slug: process-hardening-2
captured: 2026-06-09
source: cycle retrospective reviews/process-hardening-cycle-retro-2026-06-09.md (second-cycle meta-review)
related_epic: epics/process-hardening-2-plan.md
---

# Process hardening 2 (from the process-hardening retrospective)

Verbatim suggestions from the `process-hardening` cycle retrospective. Do not edit; append dated
notes under Amendments if the requirement changes. These tighten the process/skill/agent so a
recurring class of friction (rules in prose instead of the enforcing gate row; stale line-number
anchors) stops recurring. No product behavior changes.

1. **Planner must place each new rule in the enforcing gate pass-condition row, and treat any
   DoD/prose/G5 restatement as non-enforcing.** `[agent]` (mdreview-planner) / `[process]`. All
   five G1 blockers last cycle collapsed to one class: "new rules land in prose / DoD / G5, never
   in the gate pass-condition row that enforces them." One standing instruction ("name the
   enforcing gate row for every new rule; prose is a pointer, not the enforcement") pre-empts that
   whole class.

2. **Adopt cite-the-gate-row-by-name as the standing convention; stop emitting line-number
   anchors into process docs.** `[process]` + `[agent]` (mdreview-planner). Line-number anchors
   went stale in BOTH cycles (off by ~7 here after the README grew). Reserve line numbers for code
   citations; cite gates/sections by name in process docs and plans.

3. **Add an orchestrator close-step rail: reconcile ticket statuses, sprint checkboxes, and
   `close_review` BEFORE invoking the G7 critic.** `[skill]` (.claude/skills/feature-cycle). Last
   cycle the sprint still listed tickets `ready` and `close_review` empty when the G7 reviewer
   arrived; the critic caught bookkeeping the close step should have done.

4. **(minor) Scope the G7 screenshot clause to product-page changes explicitly.** `[process]`. A
   docs/infra sprint touches no product page; G7 correctly reduced "render smoke of touched pages"
   to exercising `render-smoke.sh`. The G7 row should state the screenshot requirement is
   conditional on a product page being touched, so such a sprint is not read as non-compliant.

## Amendments

(none yet)
