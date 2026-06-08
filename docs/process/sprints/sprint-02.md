---
id: sprint-02
name: Process hardening
status: active
start: 2026-06-08
end: 2026-06-15
goal: Apply the 6 first-cycle retro suggestions to the process, skill, and planner agent (MR-008..011).
close_review:
---

## Goal

Harden the delivery process itself so the next product cycle inherits a tighter validation bar
and a sharper planner: a canonical render-smoke that asserts rendered DOM nodes (wired into the
G4 gate row), a planner that specifies fit-based layout + remembers the Dockerfile-COPY footgun,
and a DoD/G7 reconciliation that blesses a bounded same-sprint docs-sweep. No product behavior
changes. Suggestion 3 (exercise the G1 staff-critic loop) was already discharged by this epic's
own 2-round G1 review.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-008 | Planner agent — fit-based-layout rule + Dockerfile-COPY footgun | docs | P2 | ready |
| MR-009 | Add `scripts/render-smoke.sh` (DOM-node assertion against a served URL) | infra | P1 | ready |
| MR-010 | README + skill — render-smoke as the `ui` validation bar (G4 row) | docs | P1 | ready |
| MR-011 | README — reconcile DoD with a bounded same-sprint docs-sweep (G7 row clause) | docs | P2 | ready |

## Preferred execution order

1. MR-008 — planner edits (no deps; sharpens future plans immediately)
2. MR-009 — `scripts/render-smoke.sh` (the canonical command must exist first)
3. MR-010 — README + skill `ui` validation bar (depends on MR-009)
4. MR-011 — DoD / docs-sweep wording (independent; any time after MR-008)

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

- [ ] every committed ticket is `done` or explicitly carried over (docs-sweep tickets are not
      eligible for carry-over once that wording lands);
- [ ] an independent `staff-critic` close review at
      `reviews/sprint-02-close-review-YYYY-MM-DD.md` verifies shipped work against each ticket's
      AC. For this docs/infra sprint the "render smoke of touched pages" reduces to: the new
      `scripts/render-smoke.sh` is exercised (present/absent/missing-Chrome cases) and the README
      gate-row wording is checked against the cited anchors;
- [ ] retro + carry-overs recorded, `close_review:` set.
