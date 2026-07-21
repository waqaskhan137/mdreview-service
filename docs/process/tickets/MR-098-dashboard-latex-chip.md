---
id: MR-098
title: Dashboard: LATEX chip + kind-aware statusOf
status: done
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

- [x] `LATEX` chip in the card crumb row when `r.kind == "latex"` (guard = field presence).
- [x] `statusOf(r)`: kind=="latex" branch -> "latex" badge showing the open-comment count
      (countLabel) instead of the baton badge.
- [x] Markdown review cards render unchanged (all new paths kind-guarded).
- [x] Card link stays `/review/{id}` for both kinds.
- [x] Dashboard render-smoke passes (local; G7 re-runs from the image).
- [x] Local validation passes: `python3 -m py_compile ...`

## Notes / context

card() and statusOf() in web/app/dashboard.html (statusOf at dashboard.html:169-177, link at
:202). The only core UI file this epic touches.

## Work log

- `2026-07-21` — `web/app/dashboard.html`: `.badge.latex` + `.kindchip` CSS; `statusOf` latex
  branch; `card()` renders the LATEX chip in the crumb and a countLabel badge for latex; markdown
  path untouched.

## Validation

- `2026-07-21` — py_compile green. render-smoke on `/` with one latex + one markdown review:
  `.card` (2), `.kindchip` (1), `.badge.latex` (1), `.badge.your-turn` (1) -> exit 0 (markdown
  baton badge intact, latex card chipped + count badge). Screenshot dashboard-latex-chip.png
  under sprint-29-render-evidence-2026-07-21. The dashboard.html byte change vs baseline is purely
  the additive kind-guarded chip/badge (`git diff` verified); a markdown-only dashboard renders
  identically, so the flag-off contract holds (the golden oracle excludes the dashboard page).

## Follow-ups

