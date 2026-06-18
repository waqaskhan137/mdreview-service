---
review_of: epics/theme-awareness-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS
status: resolved
---

# G1 re-review (round 2) — theme-awareness plan (independent)

Round-1 was PASS-WITH-CONDITIONS (1 BLOCKER, 3 SHOULD, 2 NIT). This round verifies narrowly that
the BLOCKER and the three SHOULDs are genuinely resolved in the revised plan. They are. No new
blocker introduced. **G1 passes.**

## Confirmation per round-1 finding

### [BLOCKER] Symmetric overclaim + dark-authored/transparent regression — RESOLVED
The symmetric claim is gone everywhere it lived and replaced with an honest asymmetry. The epic
intro ("One direction, stated honestly", lines 24-29), Product goal ("the honest boundary",
lines 43-47), and Core design principle ("an **asymmetric** choice with an honest cost",
lines 59-66) all now state the fix is for light-authored figures on a dark pane (the majority) and
that the dark-authored / white-on-transparent inverse is unfixed and in one sub-case **regresses**.
The measured 238 → 5 luminance result is recorded in a new design-fork subsection (lines 111-127),
Non-goals names the inverse as an accepted regression with the per-image luminance heuristic as its
backlog fix (lines 241-248), and Risks gains a dedicated row (line 327). Ticket count is still one
(line 314) — this is re-framing, not added build. No residual overclaim found.

### [SHOULD-1] Verification fixtures couldn't surface the regression — RESOLVED
Verification step 2 now seeds four fixtures including a **white-on-transparent SVG** (white text/
stroke, no background) as the explicit regression fixture (lines 383-385), and step 4 requires the
**dark screenshot to show both** the light-authored figures legible on the mat (the fix) and the
transparent figure invisible (the named non-goal), lines 443-453. The G4/G7 evidence summary
(lines 481-485) and execution order (step 5, lines 300-302) carry the same requirement. The
tradeoff is now shown for sign-off, not hidden.

### [SHOULD-2] History modal outside `#article` — RESOLVED, decision consistent
Option (a) chosen: selector extended to `#article img, .histdoc img` (lines 142-148). Spot-checked
against `viewer.html`: `.histdoc` is rendered by `showRound()` at `:482-484` into `#histbox`, a
sibling of `.wrap` (`.wrap` closes `:104`, `#histmodal`/`#histbox` opens `:121`) — outside
`#article`, so a bare `#article img` would miss it. The extended selector is cited consistently in
the design fork, UI approach (lines 199-201), Key constraints (line 264), Risks (line 330), ticket
title (line 314), and execution order. The weaker-evidence caveat is stated correctly and is
acceptable: the `.histdoc` arm is not render-smokeable at first paint (modal hidden until clicked,
so `showRound()` never runs in a headless `--dump-dom` load), verified instead by the CSS rule + the
`showRound()` render path, with an explicit caution against adding a `.histdoc` smoke selector that
would never match (lines 276-281). That arm carries genuinely weaker evidence than the `#article`
arm, but the caveat is honest, the risk is cosmetic (a mat behind a history-modal image), and the
render path is short and inspected — acceptable for G1.

### [SHOULD-3 + NITs] — RESOLVED
- SHOULD-3 / NIT-1 (`render-smoke` "defaults to dark"): the assertion is dropped; step 3 now states
  the smoke counts DOM nodes only and is scheme-irrelevant, theme proven by the step-4 screenshots
  (lines 405-409). Correct.
- NIT-2 (`.mermaid svg` cite `:34` → `:35`): fixed at every occurrence. Verified `:35` is the
  `.mermaid svg` rule and `:34` is the `.mermaid` div rule, so the correction is accurate.
- Open questions (`#fff` halo; dark-authored direction) answered in the considered-refinement
  paragraph + Risks row (lines 170-181, 329) and Assumptions items 4-5 (lines 507-521).

## Code spot-check (read-only, against `viewer.html`)
All cited lines verify: `:29` (`#article img`), `:35` (`.mermaid svg`, inline `<svg>` not `<img>`),
`:104`/`:121` (`.wrap` vs `#histmodal` sibling boundary), `:152`/`:154`/`:157` (mermaid theming +
render fn), `:433` (gutter notes through `esc()` only — no `<img>` emittable), `:482-484`
(`showRound()` → `.histdoc`). The plan's `:104` for the `.wrap` close is more accurate than round-1's
`:103`.

## Residual non-gating notes
- The `.histdoc img` arm rests on inspection + rule-existence, not a render smoke. Not a gate issue,
  but at G7 the dark screenshot should ideally include one history-modal image opened manually if it
  is cheap — otherwise the inspection-only evidence stands as the plan states.
- Mat hex (`#fafaf9` vs `#fff`) and the `#fff`-halo eyeball remain implementer screenshot calls, as
  the plan scopes them. No action needed at G1.

## New blockers
None. The revision resolved by re-framing the same single CSS rule; it added no route, no DOM
wrapping, no build step, and no new served file. Blast radius is unchanged (one HTML file).

## Resolution log
Round-2 re-review 2026-06-18 (staff-critic, independent). Verified the BLOCKER and three SHOULDs
against the revised plan and spot-checked all load-bearing `viewer.html` cites read-only.

- **[BLOCKER]** RESOLVED — symmetric overclaim removed from intro/Product goal/Core principle;
  asymmetry stated honestly; 238 → 5 regression on record in design fork + Non-goals + Risks; inverse
  named non-goal with luminance-heuristic backlog fix. One ticket.
- **[SHOULD-1]** RESOLVED — white-on-transparent fixture added (step 2); dark screenshot must show
  both fix and non-goal (step 4); evidence summary + execution order updated.
- **[SHOULD-2]** RESOLVED — selector extended to `#article img, .histdoc img`, cited consistently;
  weaker-evidence caveat for the `.histdoc` arm stated and accepted.
- **[SHOULD-3 + NITs]** RESOLVED — `render-smoke` dark claim dropped; `:34`→`:35` fixed; open
  questions answered.

**Verdict: PASS. G1 passes — tickets (MR-027, sprint-07) may spawn.**
