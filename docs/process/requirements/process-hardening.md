---
slug: process-hardening
captured: 2026-06-08
source: cycle retrospective reviews/review-dashboard-cycle-retro-2026-06-08.md (first-cycle meta-review)
related_epic: epics/process-hardening-plan.md
---

# Process hardening (from the first-cycle retrospective)

Verbatim suggestions from the `review-dashboard` cycle retrospective. Do not edit; append dated
notes under Amendments if the requirement changes. These are improvements to the delivery
process / skill / agents themselves, not to the mdreview product.

1. **Make `ui` validation serve from the rebuilt image, not a local file.** `[process]`/`[skill]`
   (G4/G5). The Dockerfile-COPY gap was invisible through MR-004's local headless-Chrome smoke
   and only surfaced three tickets later at G7's container smoke (commit 1326462). Requiring
   `docker compose up -d --build` + render against the published port as part of `ui`-ticket
   validation surfaces packaging gaps at the ticket, not at sprint close.

2. **Standardize a DOM-node assertion as the render-smoke bar for JS pages.** `[process]`/`[skill]`.
   A screenshot proves first-paint only; the setTimeout fallbacks would make a broken recompute
   path look identical. Make Chrome `--dump-dom` asserting the expected nodes exist (e.g.
   `.gcard`/`mark.cmt`) the standing requirement for every JS-rendered page.

3. **Deliberately exercise the G1 staff-critic loop next cycle.** `[process]`/`[skill]`. G1 on the
   first cycle was cleared by product-owner review; the SKILL's Phase-2 planner<->critic loop
   (<=3 rounds -> park) was never run on a real plan. Run the planner + staff-critic G1 path so
   the novel rail is exercised before the process relies on it.

4. **Reconcile the same-change-docs DoD with the docs-sweep ticket pattern.** `[process]`. MR-001
   deferred its field docs to MR-007 ("deliberate deferral"), but the DoD says durable behavior
   docs ship "in the same change." Either bless a trailing docs-sweep within the same sprint, or
   make sweep-tickets the documented exception.

5. **Give the planner a fit-based-layout rule instead of hard-coded breakpoints.** `[agent]`
   (mdreview-planner). The epic's ~820px collapse threshold was wrong on geometry and was
   reconciled to a fit-based test at G7. The planner should specify responsive behavior ("show
   the gutter only when it physically fits"), not a pixel value it has not computed.

6. **Add a Dockerfile-COPY footgun to the planner.** `[agent]` (mdreview-planner). A new
   root-level served file needs a `Dockerfile COPY` edit, and the `ui` ticket that adds the asset
   must carry that infra change. Plan-time complement to suggestion #1.

## Amendments

(none yet)
