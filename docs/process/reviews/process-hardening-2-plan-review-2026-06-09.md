---
review_of: epics/process-hardening-2-plan.md
gate: G1
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-09
verdict: PASS (round 2)
status: resolved
---

# G1 plan review — process-hardening-2 epic (round 1)

Independent review by `staff-critic` (not the author `mdreview-planner`). Structure sound: all 4
suggestions covered, 3-ticket slicing right and genuinely independent, **dogfooding clean** (zero
process-doc line-number anchors; every gate cited by row name — the plan obeys the rule it
proposes). Suggestion-3's scoping (the planner's "least sure" call) is confirmed CORRECT: a
pre-G7 rail cannot reconcile `close_review` because that names the file the critic produces, so it
correctly reconciles board-reality only and leaves `close_review`/`status: closed`/retro in
Phase 8 — which is what last cycle actually did.

## BLOCKER

**B1 — Suggestion-4 G7 replacement wording over-scopes the conditional and self-contradicts.**
The replacement prepends "only if a product page was touched this sprint" to the *entire* render
parenthetical — which includes `rebuild` + `curl /healthz` + `/api/reviews`, the `render-smoke.sh`
DOM assertion, AND the screenshot. But (a) the brief only asked to scope the **screenshot** clause;
(b) the plan's own Risks section claims the wording "retains the container-rebuild + curl smoke for
every sprint" — directly contradicted by the wording; (c) it introduces a README/skill
inconsistency — `04-close-and-ship.md` Phase 6 runs rebuild + `curl /healthz` + `/api/reviews`
**unconditionally**, gating only the per-page open/screenshot.
**Required:** gate ONLY `render-smoke.sh against the touched page + the screenshot` on a product
page being touched; keep `rebuild` + `curl /healthz` + `/api/reviews` unconditional. Then the
Risks sentence becomes true and the skill agrees.

## SHOULD-FIX

**S1 — Suggestion-1 rule enforces citation, not wiring.** The recurring defect was rules whose
enforcement lived only in prose/DoD/G5. The proposed planner rule says "**name** the enforcing
gate row" — but a planner can cite "G5" next to a prose-only rule and satisfy the letter while
reproducing the defect. Tighten to: the enforcement must be **placed in (added to) the named
row's pass-condition text**, not merely that a row is cited. "Wire it into the row," not "point at
a row."

## NIT
- **N1 — "all five G1 blockers" overstates the retro.** The retro says the suggestion pre-empts
  **three of five** (B1a/B1b/B1c are the same defect three times). The plan repeats "all five" in
  three places; soften to "three of five."
- **N2 — the rail's first checklist item ("every committed ticket `done`") restates Phase 6's
  existing precondition.** The genuinely new reconciliation is sprint checkboxes + TRACKER rows;
  worth noting that's the added value.

## Verdict: PASS-WITH-FIXES
Required to clear G1 (routed to the author `mdreview-planner`):
1. B1 — rewrite the suggestion-4 G7 replacement so only `render-smoke.sh` + screenshot are
   product-page-conditional; keep rebuild + curl smoke unconditional; reconcile the Risks
   sentence.
2. S1 — tighten suggestion-1 from "name the row" to "place enforcement in the named row's
   pass-condition text."
3. N1 — correct "all five" -> "three of five".

## Resolution log
- 2026-06-09 — round 1 recorded; routed to the author for revision. status: open.
- 2026-06-09 — author revised; **round-2 re-review: PASS**. B1 resolved (G7 replacement keeps
  rebuild + curl smoke unconditional, gates only render-smoke + screenshot on a product page;
  before-quote matches the G7 row verbatim; Risks sentence now true and consistent with skill
  Phase 6). S1 resolved (rule is now "place enforcement in the named row's pass-condition text",
  citation-alone explicitly insufficient, in all four locations). N1 resolved (three of five).
  Dogfooding still clean (zero process-doc line anchors). No new inconsistency. G1 **cleared**;
  tickets may be created. status: resolved.
