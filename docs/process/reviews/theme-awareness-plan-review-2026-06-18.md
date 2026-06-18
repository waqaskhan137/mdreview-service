---
review_of: epics/theme-awareness-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS-WITH-CONDITIONS
status: resolved
---

# G1 review — theme-awareness plan (independent)

The (b)-rejection is empirically sound and reproduces exactly; the CSS-only blast radius and
mermaid/katex exclusion are correct. But the plan's central claim — that the white mat fixes a
**symmetric** bug ("and the inverse for a dark-authored figure") — is false: a measured
reproduction shows the `#fafaf9` mat renders a dark-authored / white-on-transparent figure
**invisible** on a dark pane, and that figure is **legible today**. The mat fixes one direction and
*regresses* the other. The design is still shippable as a one-ticket UI change, but only after the
plan is made honest about which half it fixes and the regression is bounded. Conditions below.

## Findings

### [BLOCKER] The mat regresses dark-authored / transparent-bg figures; the plan claims it fixes them

The **Product goal** and the epic intro both assert the fix is symmetric: *"a dark-authored figure
is never a blinding rectangle on a light pane"* and *"the inverse for a dark-authored figure on a
light pane."* That framing is not what the shipped rule does, and one sub-case is an outright
regression versus today.

Reproduced on this machine (Chrome, `--screenshot`, luminance-sampled), a figure with white
text/strokes on a **transparent** background — the common shape of a dark-authored screenshot or a
white-line diagram — behaves as follows:

- **Today (no mat), dark pane (`#111`):** luminance spread across the figure region = **238**. The
  white strokes are clearly legible on the dark pane.
- **With the `#fafaf9` mat, dark pane:** luminance spread = **5**. White-on-`#fafaf9`. The figure is
  **effectively invisible** — the mat erases a figure that renders fine today.

So the mat does not merely "leave the other half unfixed"; for transparent-background dark-authored
figures it **introduces a new breakage on the dark pane**, the exact pane the epic exists to
protect. The plan's own **Risks** table does not list this; **Assumptions #4** frames the only cost
as the cosmetic "light card seam," not a legibility regression.

This is the finding the brief's "(and vice-versa)" was pointing at, and the plan answers it with a
claim that measurement contradicts.

Direction to resolve (any one is acceptable for G1, pick and state it):
1. **Re-scope the goal honestly.** State plainly that the mat fixes *light-authored figures on a
   dark pane* (the reported site bug, P1), and that *dark-authored transparent-bg figures* are
   **out of scope** and may regress on the dark pane — then move that case to the named backlog
   follow-up (luminance heuristic). The brief's "vice-versa" then becomes an explicit non-goal, not
   a claimed deliverable. This keeps the one-ticket scope and is probably the right call.
2. **Or** seed the verification doc (step 2) with a real white-on-transparent SVG and show the dark
   screenshot, so the regression is on the record for the product owner to accept at G1/G7 — not
   discovered after ship. The current step-2 fixtures are all light-authored (white-bg SVG, light
   raster), so the run as written **cannot surface this regression** and would green-light a plan
   whose stated symmetric goal is unmet.

Either way the gap must be named before tickets spawn; the verdict is contingent on it.

### [SHOULD] Verification fixtures only exercise the half that works — they can't catch the BLOCKER

Verification **step 2** seeds a light raster and a **white-fill** SVG (`fill="white"` rect, black
text). Both are light-authored. The dark screenshot (step 4) will therefore show the *success* case
and nothing else, and the plan asserts the run proves "images legible in both." It does not — it
proves the light-authored case is legible in both. Add a third fixture: an SVG with
`fill="white"`/`stroke="white"` text on **no background** (transparent). The dark screenshot must
include it. If condition (1) above is taken (declare the case out of scope), this fixture should
still be shown so the regression is *visible and accepted*, not hidden.

### [SHOULD] "every embedded image" overreaches — the history modal is outside `#article`

The epic intro and Product goal say a reviewer "sees **every** embedded image ... legibly." The
selector `#article img` does not cover the **version-history** view: `showRound()`
(`viewer.html:481-484`) renders a past draft via `marked.parse(...)` into `.histdoc`, which lives in
`#histbox` — a **sibling of `.wrap`**, not inside `#article` (`viewer.html:103` vs `:121`). Images in
a historical draft viewed on a dark pane will still smear. This is fine to leave unfixed, but the
plan should say "images in the live `#article` render," not "every embedded image," so the scope
claim matches the selector. (The gutter note cards are safe: `renderComments()` injects note text via
`esc()` only — `viewer.html:433` — so a note can never emit an `<img>`. That part of the scoping
holds.)

### [NIT] `render-smoke` default-dark claim is build-dependent; state it as observed, not guaranteed

Verification step 3 asserts `render-smoke.sh` "defaults to headless dark
(`prefers-color-scheme: dark`, confirmed)." `render-smoke.sh` passes **no** scheme flag
(`--dump-dom` only), so the default is whatever the local Chrome resolves. On this machine it does
resolve dark (reproduced: a bare `@media (prefers-color-scheme: dark)` page renders blue headless) —
but that is an observed property of this Chrome build, not a guarantee, and the smoke only counts
DOM nodes anyway (scheme is irrelevant to it). Drop the "defaults to dark" assertion from the smoke
step; it is load-bearing nowhere and invites a future false "confirmed."

### [NIT] Minor citation drift

The plan cites mermaid's inline SVG at `viewer.html:157,:34`. `:157` is `renderMermaid()` (the JS),
`:34` is the `.mermaid` div rule; the actual `.mermaid svg` CSS rule is `:35`. Harmless, but per the
repo's citation convention tighten to `:35` (rule) / `:157` (render fn) so the reviewer-of-record
isn't chasing an off-by-one. KaTeX (`:175`,`:180`) and the existing `#article img` (`:29`) cites are
correct.

## What's sound (load-bearing, so noted)

- **The (b)-rejection reproduces exactly.** Built the `<img>`-loaded SVG with an internal
  `@media (prefers-color-scheme: dark)` rule, screenshotted under `preferredColorScheme=0/1` with and
  without `html{color-scheme:light dark}`: the rect followed `preferredColorScheme` in both rows;
  host `color-scheme` made **zero** difference. The plan's table and its conclusion (host
  `color-scheme` does not cross the `<img>` boundary) are correct, and `preferredColorScheme` is the
  right emulation — `--force-dark-mode` (correctly rejected in the plan) is Chrome's auto-invert, a
  different mechanism. The dead-end is genuinely closed by evidence.
- **Blast radius is one HTML file.** No `app.py`/route/`meta.json`/MCP touch; `Dockerfile:8` already
  copies `viewer.html`; the footgun-9 "no new served file" reasoning holds.
- **Mermaid/KaTeX exclusion is correct by construction.** Mermaid output is `.mermaid svg` (inline
  `<svg>`, `viewer.html:157`), KaTeX is `.katex` spans; `#article img` matches neither.
- **One `ui` ticket (MR-027) is right-sized** and MR-027 is the correct next ID. Keeping the docs
  note inside it avoids a docs-sweep carry-over; no G7 carry-over risk for a single CSS rule.

## Open questions for the author

- On the dark-pane seam (Assumptions #4): is "light mat on a dark pane is acceptable" a call you want
  to default-yes autonomously, or gate at G1? I'd accept default-yes for the *cosmetic* seam — but
  the **legibility regression** in the BLOCKER is a different question and should not be auto-defaulted;
  it changes a "legible today" figure to "invisible." Which way do you want the dark-authored case to
  fall — out of scope (regression accepted, backlog follow-up) or in scope (then this is more than one
  CSS rule)?
- If `#fafaf9` is chosen over `#fff`: have you confirmed a light-authored figure that *itself* assumes
  pure `#fff` (e.g. a screenshot with a white chrome bar) doesn't show a visible `#fafaf9` halo seam
  around its own white? Minor, screenshot-tunable, but worth an eyeball in step 4.

## Resolution log

Author response 2026-06-18 (Europe/London). Plan edited; frontmatter/verdict unchanged (reviewer
sets those at re-review). Full detail in the plan's **Review resolutions** section.

- **[BLOCKER] mat regresses dark-authored / transparent figures.** Resolved by honest re-scope
  (option 1, not a re-plan): symmetric claim removed from the epic intro, Product goal, and Core
  principle; the dark-authored / white-on-transparent case is now a **named non-goal** with the
  measured 238 → 5 regression recorded in a new design-fork subsection and a dedicated Risks row;
  per-image luminance heuristic named as its backlog fix. One ticket unchanged.
- **[SHOULD-1] fixtures all light-authored.** Resolved: Verification step 2 adds a
  white-on-transparent SVG fixture; step 4's dark screenshot must show both a light-authored figure
  (legible — the fix) and the transparent figure (invisible — the named non-goal), so the
  regression is visible and signed-off.
- **[SHOULD-2] `.histdoc` images uncovered.** Resolved with **option (a)**: selector extended to
  `#article img, .histdoc img` (cheap, consistent; scoping history out was rejected). Rationale in a
  new "Selector scope" subsection; gutter note path confirmed `<img>`-free via `esc()`
  (`viewer.html:433`); noted `.histdoc img` is not render-smokeable at first paint.
- **[SHOULD-3 / NIT-1] `render-smoke` "defaults to dark".** Resolved: claim dropped from
  Verification step 3; smoke stated as node-count-only and scheme-irrelevant.
- **[NIT-2] `.mermaid svg` cite `:34` → `:35`.** Fixed at every occurrence.
- **Open questions** (dark-pane seam direction; `#fff` halo) answered in Assumptions 4-5 and Risks.
