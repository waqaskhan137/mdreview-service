---
review_of: epics/dashboard-density-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS-WITH-CONDITIONS
status: resolved
---

# G1 independent review — dashboard-density plan

The two forks are sound: `auto-fit` is the right mechanism for the row-fill complaint, fork-1's
option (c) is correctly chosen over (b) (which would re-create the gutter), and cap-2000 is a
defensible reconciliation of edge-to-edge vs legibility. The plan does not pass clean, though: the
`:has()` rule keys on the **per-session** grid, not the per-project unit the prose assumes, and the
**verification recipe asserts the wrong target widths** — numbers carried over from the cap-2200
exploration table that don't hold under the shipped cap-2000/gap-8. Fix the recipe and add a
multi-session seed; the design itself ships. No BLOCKER.

## Findings

### [SHOULD] Verification asserts cap-2200 numbers against a cap-2000 build (`dashboard-density-plan.md:274-276`)
The CDP assertions at 2560px are stale relative to the design they verify. The plan ships
`max-width:2000px` and `gap:8px`, but the asserted targets are the figures from the **fork-2
exploration table** (which used cap 2200 and gap 10):
- pairproj 2-card "each ≈1071px" — `1071 = (2200-48-10)/2`. Under the shipped config the content
  width is `2000-48 = 1952`, gap 8, so two cards are `(1952-8)/2 ≈ **972px**`, not 1071.
- bigproj 6-card "each ≈350px" — `350` is the cap-2200/gap-10 number. Under cap-2000/gap-8 it is
  `(1952 - 5×8)/6 ≈ **319px**`, ~30px off the asserted target.

A verifier following the recipe literally either fails a correct implementation or has to widen the
tolerance until the assertion proves nothing. Recompute the expected widths for the **actual**
cap-2000/gap-8 values (≈972 for 2-card, ≈319 for 6-card) before this becomes the binding G7 proof.
The lone-card 560 and `.wrap`=2000 assertions are correct and unaffected.

### [SHOULD] The `:has(.card:only-child)` rule keys on the per-session grid, but the plan frames it per-project (`dashboard.html:177-178`; plan Core design principle + Fork 1)
Verified the render structure: `.card` is a direct child of `.grid` (good — `:only-child`
structurally matches), but the grid is emitted **per session**, not per project:
`section.project > div.group-body > div.session > div.grid > .card[]` (lines 177-178). The plan's
language throughout ("a project with 1 card", "a 2-card project splits the row evenly") conflates
project with the row-fill unit, which is the session grid.

Consequence the plan never addresses: a project with one card in each of several sessions renders as
several single-card grids, **each** matching `:only-child` and **each** capped to 560px — so a
"6-card project" spread one-per-session shows six narrow 560px rows, not a filled row. This is
arguably *correct* (a session row with one card genuinely is a lone card), so it's not a defect in
the mechanism — but it isn't what the prose claims, and the verification seeds **only single-session
projects** (`run-1` for all of agit/pairproj/bigproj, lines 252-255), so the recipe never observes
the multi-session case at all. Fix both: (1) state in the plan that the fill/cap unit is the session
grid, and confirm per-session lone-card capping is the intended read; (2) add a seed of one project
with two sessions (one card each) and capture it, so the screenshot shows what a multi-session
project actually looks like under the rule.

### [NIT] `:only-child` ignores `.is-hidden`; a filtered-to-one grid goes wide, not capped (`dashboard.html:196-202`)
The brief asked this to be noted; the plan omits it. `applyFilter()` hides cards with `.is-hidden`
(`display:none`), not removal, so a grid filtered down to one visible card still has >1 element
child → `:only-child` is false → no 560 cap. Because a `display:none` grid item generates no track,
that one visible card then sizes to the full available width (the opposite of the brief's guess that
it "stays narrow"). Either way it's a transient filter state, acceptable, but the plan should name
the interaction rather than leave it for the close review to discover.

### [NIT] Confirm the `preferredColorScheme` enum direction live, don't trust the comment (`dashboard-density-plan.md:199-202`)
The dark-via-scheme-emulation guidance is correct and the `--force-dark-mode` ban is right (it's
auto-invert and never sets `prefers-color-scheme`, so it would test the wrong path against the
`@media (prefers-color-scheme: dark)` rules at `dashboard.html:9,56`). But the `0=dark / 1=light`
enum ordering is non-obvious and has bitten people; the plan claims it verified (`body bg
rgb(17,17,17)` under `=0`). Keep that as a *live re-check* in the close review (assert the dark pane's
computed `body` bg is the dark token), not an assumption inherited from the plan comment.

## What's good (load-bearing)
- Fork-1 (b)-vs-(c) reasoning is the crux and it's right: (b) caps the lone card by reintroducing the
  exact 2-card gutter the user complained about; (c) is the only option that fixes the lone case
  without regressing the headline fix. The measurement-driven elimination of (b) is the strongest
  part of the plan.
- Cap-2000 is a sound, honestly-bounded call. (The review prompt's "560px dead margin at 2560" is
  itself off — it's `(2560-2000)/2 = 280px` each side, a reading-width, not a stranded column. The
  plan's weakest screen is true 4K, which it correctly names and offers no-cap as a one-line
  follow-up. Gating full-bleed behind a user preference rather than guessing is the right move.)
- `:has()` support claim is accurate (Firefox 121 / Dec 2023 was the last major; fine for a 2026
  internal dashboard), and the degradation-to-full-span is genuinely benign.
- The CSS-only ⇒ behavior-preserved-by-construction argument holds: no JS path is touched, and the
  preserve-functionality re-check is correctly retained rather than waved through on that basis.

## Resolution log

Resolved by the plan author (mdreview-planner) 2026-06-19 in
`epics/dashboard-density-plan.md` (see its "Review resolutions" section for the full text).
Verdict/frontmatter unchanged; plan stays `gate: G1 not passed` / `status: draft`. Still one
ticket (MR-032).

- **[SHOULD] stale cap-2200 verification widths** — FIXED. Recomputed the CDP assertions against the
  shipped cap-2000/gap-8 config: content width `2000−48=1952`, each card `(1952−(N−1)×8)/N`, giving
  2-card **≈972px** (was 1071) and 6-card **≈319px** (was 350); added the formula + a result table to
  the Verification section. Lone-card 560 and `.wrap`=2000 left as-is (already correct). The cap-2200
  numbers remain only in the Fork-1 candidate table, now explicitly labeled exploration.
- **[SHOULD] `:has()` keys per-session, prose framed per-project; multi-session unseeded** — FIXED.
  Reworded Core design principle, Fork 1, the summary and product goal to state the fill/cap unit is
  the **per-session grid** (`dashboard.html:177-178`), confirmed per-session lone-card capping is
  intended, added the multi-session consequence note, and seeded + asserted + screenshotted a
  two-session single-card project ("multisess"). render-smoke counts bumped accordingly.
- **[NIT] `:only-child` ignores `.is-hidden` (filtered-to-one goes wide)** — ACTIONED. Named the
  filter interaction in Fork 1 (`applyFilter()` uses `display:none`, not removal, so `:only-child` is
  false and the lone visible card sizes full-width); flagged as an acceptable transient state.
- **[NIT] confirm `preferredColorScheme` enum direction live** — ACTIONED. The dark-pane constraint
  now mandates a live re-check (assert computed dark-pane `body` bg = dark token) instead of inheriting
  the plan comment's `rgb(17,17,17)` claim.

