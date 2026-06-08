---
id: sprint-02
name: Process hardening
status: closed
start: 2026-06-08
end: 2026-06-15
goal: Apply the 6 first-cycle retro suggestions to the process, skill, and planner agent (MR-008..011).
close_review: reviews/sprint-02-close-review-2026-06-09.md
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
| MR-008 | Planner agent — fit-based-layout rule + Dockerfile-COPY footgun | docs | P2 | done |
| MR-009 | Add `scripts/render-smoke.sh` (DOM-node assertion against a served URL) | infra | P1 | done |
| MR-010 | README + skill — render-smoke as the `ui` validation bar (G4 row) | docs | P1 | done |
| MR-011 | README — reconcile DoD with a bounded same-sprint docs-sweep (G7 row clause) | docs | P2 | done |

## Preferred execution order

1. MR-008 — planner edits (no deps; sharpens future plans immediately)
2. MR-009 — `scripts/render-smoke.sh` (the canonical command must exist first)
3. MR-010 — README + skill `ui` validation bar (depends on MR-009)
4. MR-011 — DoD / docs-sweep wording (independent; any time after MR-008)

## Notes / retro

- All 4 tickets `done`, no carry-overs. Docs/infra sprint — no product code changed.
- The G1 loop on this epic's own plan (2 rounds) caught real blockers before any ticket existed,
  discharging retro suggestion 3 by exercising the planner<->critic rail for the first time.
- Independent `staff-critic` G7 close review: **PASS-WITH-FIXES**, no blockers; it re-ran
  `render-smoke.sh` live (including a render-wait ablation) and found 5 SHOULD-FIX, all resolved in
  Phase 7 (selector validation; evidence completeness; anchor de-brittling; close-step
  reconciliation). See `reviews/sprint-02-close-review-2026-06-09.md`.
- **Dogfooding note:** the new render-smoke bar (MR-009/010) was itself used to validate the
  sprint at G7 — the process change validated by the process it changed.
- **Carry-overs:** none.

## Close gate (G7)

- [x] every committed ticket is `done` (no carry-overs; docs-sweep tickets are not eligible for
      carry-over per the new wording, n/a here);
- [x] an independent `staff-critic` close review at
      `reviews/sprint-02-close-review-2026-06-09.md` verified shipped work against each ticket's
      AC. The "render smoke of touched pages" reduced to: `scripts/render-smoke.sh` exercised
      (present / anti-grep / fail-loud / async exit-0 / render-wait ablation / unsupported-reject)
      in `reviews/sprint-02-render-evidence-2026-06-09/`, and the README gate-row wording checked
      against the rows;
- [x] retro + carry-overs recorded, `close_review:` set.
