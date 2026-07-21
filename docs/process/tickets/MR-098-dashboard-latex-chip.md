---
id: MR-098
title: Dashboard: LATEX chip + kind-aware statusOf
status: ready
layer: ui
priority: P2
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-093]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Make latex reviews recognizable on the dashboard and stop the baton-centric status from showing a
permanent misleading "Your turn" on no-baton reviews.

## Acceptance criteria

- [ ] `LATEX` chip in the card crumb row when `r.kind == "latex"` (guard = field presence; the
      field only exists on latex reviews).
- [ ] `statusOf(r)`: kind=="latex" branch shows open-comment count instead of the baton badge.
- [ ] Markdown review cards render byte-identically to today (kind-guarded changes only).
- [ ] Card link stays `/review/{id}` for both kinds.
- [ ] Dashboard render-smoke passes from a rebuilt image.
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

card() and statusOf() in web/app/dashboard.html (statusOf at dashboard.html:169-177, link at
:202). The only core UI file this epic touches.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

