---
review_of: the process-hardening cycle (sprint-02)
gate: retro (Phase 10)
reviewer: cycle-retrospective (agent)
independent: true
timestamp: 2026-06-09
verdict: smooth-run
status: open
---

# Cycle Retrospective — process-hardening (sprint-02)

**Verdict:** Smooth. The first real G1 planner<->critic loop earned its keep (caught 5 substantive
blockers before any ticket existed), all 4 tickets shipped on `dev`, G7 passed with no blockers.
The only friction is a *recurring* one: README line-number anchors drifted again, in both cycles.

## What went well
- **The G1 loop, run for real for the first time, paid off immediately.** Round 1 was
  PASS-WITH-FIXES with 5 blockers found *before any ticket was created* — the planner<->critic
  rail was both exercised (discharging retro suggestion 3) and validated in one move. Without it,
  three wrong-enforcement defects would have shipped into tickets.
- **Dogfooding closed the loop cleanly.** `scripts/render-smoke.sh` (MR-009) was used at this
  sprint's own G7 to validate the sprint that shipped it — including a live render-wait ablation
  (`RENDER_SMOKE_VTB=1` -> nodes drop to 0). The process change was validated by the process it
  changed.

## Top suggestions (prioritized; suggest-only — user decides what becomes a ticket)

1. **Planner must place each new rule in the enforcing gate pass-condition row, and treat any
   DoD/prose/G5 restatement as non-enforcing.** `[agent]` (mdreview-planner) / `[process]`.
   Highest-value: all five G1 blockers collapse to one class — "new rules land in prose / DoD / G5,
   never in the gate pass-condition row that enforces them." B1a/B1b/B1c are the same defect three
   times. One standing instruction ("name the enforcing gate row for every new rule; prose is a
   pointer, not the enforcement") pre-empts three of five blockers next cycle.

2. **Adopt cite-the-gate-row-by-name as the standing convention; stop emitting line-number
   anchors into process docs.** `[process]` + `[agent]` (mdreview-planner). This is the
   cross-cycle recurrence: cycle-1 and cycle-2 both produced stale `README.md:NNN` anchors (here
   off by ~7 after the README grew). The fix is already proven — G7 improvised it (MR-010/011 now
   cite gate rows by name). Make row-name citation the convention; reserve line numbers for code.

3. **Add an orchestrator close-step rail: reconcile ticket statuses, sprint checkboxes, and
   `close_review` BEFORE invoking the G7 critic.** `[skill]` (.claude/skills/feature-cycle).
   G7 SHOULD-FIX #5: the sprint still listed tickets `ready` and `close_review` empty when the
   reviewer arrived — the critic caught bookkeeping the close step should have done. A pre-G7
   reconciliation step keeps the critic on substance.

4. **(minor) Scope the G7 screenshot clause to product-page changes explicitly.** `[process]`.
   A docs/infra sprint touches no product page, and G7 correctly reduced "render smoke of touched
   pages" to exercising `render-smoke.sh`. The G7 row could state the screenshot requirement is
   conditional on a product page being touched, so such a sprint isn't read as non-compliant.

## Metrics
- **G1 rounds:** 2 (round 1 PASS-WITH-FIXES, 5 blockers + 1 should-fix + 1 nit; round 2 PASS).
- **G7 rounds:** 1 (PASS-WITH-FIXES, 0 blockers, 5 SHOULD-FIX all resolved inline).
- **Tickets:** 4 shipped (MR-008..MR-011) / 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0 overturned. The "least sure" bounded-sweep decision was
  refined (carry-over ineligibility added at G1), not reversed. The 5 G1 blockers were
  enforcement-wiring defects, not wrong premises.
- **PR:** #2 (`dev` -> `main`) open, not merged (awaits G8).

## Disposition
Suggestions are proposals only; none applied automatically. #1 and #2 are the highest-leverage and
target a recurring class — natural candidates for a follow-up `mdreview-planner` tweak or a small
process-hardening-2 increment when the user chooses.
