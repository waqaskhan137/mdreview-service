---
review_of: the review-dashboard cycle (sprint-01)
gate: retro (Phase 10)
reviewer: cycle-retrospective (agent)
independent: true
timestamp: 2026-06-08
verdict: smooth-validated-run
status: open
---

# Cycle Retrospective — review-dashboard (sprint-01), 2026-06-08

**Verdict:** Smooth, validated run — all 7 tickets shipped to `dev` in dependency order; the G7
render-smoke earned its keep by catching a real container-packaging bug. First-cycle adoption of
the ported process worked, but it exercised only half the new machinery (G7's critic, not G1's).

## What went well
- **G7 render-smoke caught a real shipping bug that py_compile/curl could not:** the Dockerfile
  omitted `COPY dashboard.html`, so the rebuilt container served an empty `200` at `/` (fixed in
  `1326462`). The "a 200 is not a render" rail paid off on its first outing.
- **Independence held where it ran:** G7 was an independent `staff-critic` pass (reviewer !=
  implementer), PASS-WITH-FIXES with no blockers; both SHOULD-FIX resolved in-place, no re-review.
- **Clean decomposition + sequencing:** service endpoints (MR-001/002/003/005) landed before the
  UI that consumes them (MR-004/006); per-ticket commits, work logs, and validation all present.

## Top suggestions (prioritized; suggest-only — user decides what becomes a ticket)

1. **Make `ui` validation serve from the rebuilt image, not a local file.** `[process]`/`[skill]`
   (G4/G5). The Dockerfile-COPY gap was invisible through MR-004's local headless-Chrome smoke
   and only surfaced three tickets later at G7's container smoke (`1326462`). Requiring
   `docker compose up -d --build` + render against the published port as part of `ui`-ticket
   validation surfaces packaging gaps at the ticket, not at sprint close.

2. **Standardize a DOM-node assertion as the render-smoke bar for JS pages.** `[process]`/`[skill]`.
   G7 SHOULD-FIX #2: a screenshot proves first-paint only. Make Chrome `--dump-dom` asserting the
   expected nodes exist (e.g. `.gcard`/`mark.cmt`) the standing requirement for every JS-rendered
   page — "a screenshot is not proof of the dynamic path."

3. **Deliberately exercise the G1 staff-critic loop next cycle.** `[process]`/`[skill]`. G1 here
   was cleared by product-owner viewer review; the SKILL's Phase-2 planner<->critic loop
   (<=3 rounds -> park) was never run on a real plan. Run the planner + staff-critic G1 path on
   the next epic before the process relies on it.

4. **Reconcile the same-change-docs DoD with the docs-sweep ticket pattern.** `[process]`. MR-001
   defers its field docs to MR-007 ("deliberate deferral"), but the DoD says durable behavior
   docs ship "in the same change." Either bless a trailing docs-sweep within the same sprint, or
   make sweep-tickets the documented exception.

5. **Give the planner a fit-based-layout rule instead of hard-coded breakpoints.** `[agent]`
   (mdreview-planner). The epic's `~820px` collapse threshold was wrong on geometry (a 284px
   gutter cannot fit at 820px), reconciled at G7 (SHOULD-FIX #1). The planner should specify
   responsive *behavior* ("show the gutter only when it physically fits"), not a pixel value.

6. **Add a Dockerfile-COPY footgun to the planner.** `[agent]` (mdreview-planner). A new
   root-level served file needs a `Dockerfile COPY` edit, and the `ui` ticket that adds the asset
   must carry that infra change. Plan-time complement to suggestion #1.

## Metrics
- **G1 rounds:** 4 (product-owner viewer rounds, not staff-critic churn; the SKILL's <=3-round
  park cap is written for the critic loop — whether it governs the product-owner path is
  unspecified, and it ran 4).
- **G7 rounds:** 1 (single close review, PASS-WITH-FIXES; both SHOULD-FIX resolved in-place).
- **Tickets:** 7 shipped / 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0 overturned; 1 minor (the `~820px` breakpoint, reconciled
  to fit-based geometry — design held, only the threshold wording changed). The Dockerfile gap
  was a gate-caught bug, not a stated plan assumption.

## Disposition
Suggestions are proposals only. None applied automatically. The user decides which become
backlog tickets; #1, #2, and #3 are the highest-leverage for hardening the newly-adopted process
before the next cycle.
