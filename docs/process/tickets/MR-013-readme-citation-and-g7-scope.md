---
id: MR-013
title: README — citation-by-name convention + scope G7 render clause to product-page changes
status: done
layer: docs
priority: P2
sprint: sprint-03
epic: process-hardening-2
depends_on: []
branch: dev (small/solo change)
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Make the cite-by-name convention visible in the process docs (not only the planner's prompt), and
stop a docs/infra-only sprint reading as G7-non-compliant for shipping no page screenshots.
(Retro suggestion 2 process half + suggestion 4.)

## Acceptance criteria

- [ ] `README.md` **Reviews (gate evidence)** section gains a one-line convention: cite gates and
      sections **by name** in process docs, reviews, and plans; **reserve line numbers for code
      citations** (process docs grow and numeric anchors drift).
- [ ] The **G7 — Sprint close** pass-condition row render clause is reworded so the per-page
      `scripts/render-smoke.sh` DOM assertion **+ screenshot** are **conditional on a product page
      (`viewer.html`/`dashboard.html`/`static/**`) being touched this sprint**, while the
      **container rebuild + `curl /healthz` + `/api/reviews` smoke stays unconditional every
      sprint**. A docs/infra-only sprint that touches no product page is explicitly **not
      non-compliant** for lacking the per-page DOM assertion + screenshot.
- [ ] Every other G7 clause (done-or-carried-over, docs-sweep carry-over ineligibility,
      independent staff-critic review, retro) is byte-for-byte unchanged. Gate set + lifecycle
      unchanged.
- [ ] Render bar NOT weakened: when a product page IS touched, the full render-smoke + screenshot
      is still owed.
- [ ] Validation: read-diff (exact before/after wording in the plan's Process section).

## Notes / context

Plan: `epics/process-hardening-2-plan.md` (Process section — has the verbatim before/after). Must
stay consistent with `.claude/skills/feature-cycle/references/04-close-and-ship.md` Phase 6, which
runs rebuild + curl unconditionally. G1 review B1: `reviews/process-hardening-2-plan-review-2026-06-09.md`.

## Work log

- `2026-06-09` — `README.md`: added a **Citation convention** line to the Reviews (gate evidence)
  section (cite gates/sections by name; reserve line numbers for code). Reworded the **G7** row's
  render clause so rebuild + `curl /healthz` + `/api/reviews` stay **unconditional**, and only the
  per-page `render-smoke.sh` DOM assertion + screenshot are conditional on a product page
  (`viewer.html`/`dashboard.html`/`static/**`) being touched; a docs/infra-only sprint is
  explicitly not non-compliant. Every other G7 clause unchanged.

## Validation

- `2026-06-09` — read-diff. Citation convention present; G7 keeps the curl smoke unconditional
  with the per-page assertion gated; docs-sweep carry-over + retro clauses intact; consistent with
  `04-close-and-ship.md` Phase 6 (which runs rebuild + curl unconditionally).

## Follow-ups

None.
