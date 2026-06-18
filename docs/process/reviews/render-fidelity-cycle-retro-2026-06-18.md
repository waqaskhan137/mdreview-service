---
retro_of: cycle/render-fidelity (sprint-08)
kind: cycle-retrospective
author: cycle-retrospective
timestamp: 2026-06-18
scope: the RUN (plan→G1→tickets→sprint→implement→G7→close), not the feature
---

# Cycle retrospective — render-fidelity (sprint-08)

**Verdict: smooth.** A clean 3-ticket UI cycle, shipped same-day, zero parks, zero carry-overs,
one real defect — caught and fixed at the gate that exists to catch it. The cycle's headline is that
the accumulated planner Method bullets are now *demonstrably* paying off across cycles, and the one
defect they missed points at a precise, generalizable gate gap.

## What went well (load-bearing)

- **The measurement habit pre-empted the recurring browser-global trap.** The exact gap that broke
  the math epic — UMD globals not composing with vendored `marked` — was reproduced in headless
  Chrome by the planner *and independently re-reproduced by the G1 critic* (`render-fidelity-plan-review-2026-06-18.md`
  "Reproduction"), pinning that `window.markedHighlight` is a namespace object whose `.markedHighlight`
  is the factory. The feature shipped first-try as a result. This is the *third* cycle of the
  measurement habit and the second to show it catching a real trap before code — the
  retro→planner-method→next-cycle loop is working, not coincidence.
- **Pinned-upstream vendoring was clean; only the hand-derived asset regressed.** The 3 pinned deps
  (marked-footnote, highlight.js common, marked-highlight) reproduced clean at both gates. The single
  hand-curated `hljs-github.css` was the only thing that broke. A sharp signal (see Suggestion 2).

## Top suggestions

1. **[skill] Add a computed-style/contrast check to render evidence for theme/color work — not just a
   screenshot.** The G7 SHOULD (`sprint-08-close-review-2026-06-18.md` finding 1) was invisible to
   both-pane screenshots *and* to `render-smoke.sh` (which only counts nodes — verified, the script
   has no color logic): the `.hljs-doctag` span was present in the DOM and rendered, but
   `getComputedStyle().color` was `rgb(0,0,0)` on the dark pane. Only the critic's manual
   `getComputedStyle` caught it. For any ticket that ships color/theme CSS, the G4/G7 render evidence
   should include a `getComputedStyle().color` assertion on the highest-risk token(s) on the dark
   pane, not just a PNG. This prevents a *recurring class* (silent color regressions that paint
   "correctly enough" to pass a screenshot). Highest value — it's the one thing the otherwise-strong
   measurement habit structurally could not see.

2. **[agent] Planner Method bullet: a hand-derived asset deserves its own before/after verification,
   distinct from the approach it implements.** The planner measured the *theme approach* (M4
   screenshots of github-dark on the pre mat) and it was sound — but the *implementer's* hand-edited
   strip regex orphaned `pre codecode` and the M4 evidence said nothing about it, because M4 validated
   the design, not the transform. The generalizable lesson (the sprint retro itself reaches for it):
   when a step *hand-derives* an asset from a vendored one (stripping/concatenating CSS, trimming a
   build), that derivation is a separate failure surface and the plan should call for verifying the
   *derived artifact's* observable output, not just the upstream choice. Pairs with Suggestion 1 but
   is the more general rule.

3. **[process] State a vendoring preference: pin-and-include upstream over hand-curate, and when you
   must hand-curate, isolate the edit.** Clean data point this cycle: 3 pinned-upstream assets shipped
   defect-free; the 1 hand-built file regressed (`MR-029` Work log "stripped **all** `.hljs{…}` base
   rules" — the strip was the bug). A one-line note in the README vendoring guidance ("prefer the
   pinned upstream file unedited; if a transform is unavoidable, keep it minimal and verify the
   *output*, not the recipe") would bias the next theme/asset cycle away from the one move that broke
   here.

## Lower-priority

4. **[skill] Add a standalone sync-`marked.parse` assertion to the UI smoke.** G7 NIT 2 notes the only
   guard that all three extensions stayed synchronous is "the article rendered at all" — a future
   `async:true` regression would surface as a *blank article*, not a clear failure. A one-line
   `typeof marked.parse(probe) === 'string'` check in the render evidence makes that failure legible.
   Low value (the real guard holds), but cheap and removes a latent silent-failure mode.

## Metrics

- **G1 rounds:** 2 (PASS-WITH-CONDITIONS → PASS). Round-2 found *no new* issues — a clean re-check of
  4 SHOULD + 1 NIT, all ticket-level, no redesign. Not churn; the second round was confirmation.
- **G7 rounds:** 1 (PASS-WITH-CONDITIONS, 1 SHOULD fixed pre-close, 2 NITs accepted).
- **Tickets shipped vs carried:** 3 shipped (MR-028/029/030), 0 carried, 0 blocked, 0 parks.
- **Wrong load-bearing assumptions:** 0. The single load-bearing assumption (A1, parse-time
  highlighting) held; A2–A5 minor assumptions all held. G1's SHOULDs were plan *typos/omissions* (wrong
  `/r/` URL, throwing snippet, missing `.sr-only` rule, unrecorded peer-range), not overturned
  assumptions.
- **Defects reaching G7:** 1 (hand-edited CSS strip → `.hljs-doctag` invisible on dark) — not
  foreseeable from the plan's measurements, which validated the approach but not the implementer's
  hand-transform. This is the seam Suggestions 1–2 target.
- **Single-session / 3-cycles-back-to-back drift:** none observed. `origin/main` is current
  (`9fff69f`, PR #6 merged); no local-main staleness recurred. Diff scope stayed exactly on-plan
  (`viewer.html` + 4 `static/` + 3 docs; no `app.py`/`Dockerfile` drift — G7 confirmed). No scope
  creep, no debt smuggled in.
