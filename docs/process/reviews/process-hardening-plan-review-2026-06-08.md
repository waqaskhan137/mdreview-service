---
review_of: epics/process-hardening-plan.md
gate: G1
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-08
verdict: PASS (round 2)
status: resolved
---

# G1 plan review — process-hardening epic (round 1)

Independent review by `staff-critic` (not the author `mdreview-planner`). This review IS the
deliberate exercise of the G1 planner<->critic loop that the first cycle never ran (brief
suggestion 3), so it was reviewed for real. It found substantive blockers.

Anchors spot-checked (~15 `path:line` refs): all land on the claimed content; the
host-8137 -> container-8080 port mapping is correctly reasoned; ticket slicing and the single
`depends_on` are correct; coverage of all 6 suggestions is complete and suggestion 3's "no ticket"
is legitimate (this review discharges it).

## BLOCKER

**B1 — New rules land in prose / DoD / G5, never in the gate pass-condition row that enforces
them.** One defect in three places:
- *B1a (suggestion 4):* the plan leans on "G7 does not pass with stale docs" but amends only the
  DoD (`README.md:130-134`) and the G5 row (`:156`) — the **G7 pass condition (`:158`) has no
  docs-currency clause**. The named enforcement does not exist in the named gate. Add the clause
  to the G7 row.
- *B1b (carry-over loophole):* G7 passes with tickets "explicitly carried over." Nothing forbids a
  docs-sweep ticket from being carried over, so docs debt can cross the sprint boundary — exactly
  what "bounded same-sprint" was meant to prevent. State that a docs-sweep ticket is
  **ineligible for carry-over**.
- *B1c (suggestion 1+2 / G4):* render-smoke is put in dev-flow step 5 narrative with "mirror into
  G4 if needed". The G4 pass condition (`:155`) is `py_compile`+`docker build`+self-check — no
  render-smoke. If it's not in the G4 row, a `ui` ticket passes the gate without it. Put it in the
  G4 row (referencing the README rule once).

**B2 — `render-smoke.sh` contract has false-pass / false-fail modes (the exact failures it
exists to prevent).**
- *B2a:* the contract oscillates to `chrome --dump-dom | grep -q <selector>`. A CSS selector is
  not a grep pattern, and the inline CSS/JS source contains the strings `gcard`/`cmt`, so grep
  passes even if zero elements rendered. The contract must **evaluate the selector against the
  DOM** (count matched elements), not substring-grep the dump.
- *B2b:* no wait-for-render. Per `sprint-01-close-review-2026-06-08.md:62`, the working assertion
  used `--dump-dom` after a virtual-time advance because the page renders via `setTimeout`
  fallbacks + async mermaid. The contract must mandate a render-wait (virtual-time budget) before
  asserting; cite that evidence.

## SHOULD-FIX
- Scope drift: the "both gate rails now exercised" note (suggestion-3 artifact) is bundled into
  the suggestion-1+2 render-smoke rewrite ticket. Unbundle or drop it (the G1 review file is the
  durable evidence).

## NIT
- DoD anchor off by one: plan cites `README.md:131-135`; it's `130-134` (135 is blank).
- Remove the "mirror into G4 if needed" hedge once B1c is fixed.

## Verdict: PASS-WITH-FIXES
Design sound; fails only on enforcement wiring and script-contract completeness. Required fixes
(routed back to the author `mdreview-planner`):
1. B1a — docs-currency clause in the **G7 row (`:158`)**.
2. B1b — docs-sweep ticket **ineligible for carry-over**.
3. B1c — render-smoke in the **G4 row (`:155`)**; drop the "if needed" hedge.
4. B2a — DOM selector evaluation, not substring-grep.
5. B2b — mandate render-wait/virtual-time in the script contract; cite `:62`.
6. SHOULD-FIX — unbundle the rails-exercised note.
7. NIT — fix the DoD anchor to `:130-134`.

## Resolution log
- 2026-06-08 — round 1 recorded; routed to the author for revision. status: open.
- 2026-06-08 — author (`mdreview-planner`) revised the plan; **round-2 re-review: PASS**. All five
  blockers, the should-fix, and the nit confirmed genuinely resolved and wired into the named gate
  rows (G4 `:155`, G7 `:158`, DoD `:130-134`), anchors accurate, no new inconsistency introduced.
  G1 gate **cleared**; tickets may be created. Non-blocking note carried into the suggestion-1+2
  docs ticket: the G4-row wording should scope the render-smoke to `ui` tickets explicitly.
  status: resolved.
