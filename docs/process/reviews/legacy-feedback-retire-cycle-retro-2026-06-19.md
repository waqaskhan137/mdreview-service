---
review_of: cycle/legacy-feedback-retire (sprint-13)
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-19
verdict: smooth run; friction concentrated in recurring non-feature places
status: suggestions-only
---

# Cycle Retrospective — `legacy-feedback-retire` (sprint-13)

**Verdict:** Smooth run on a small change — one G1 round of churn, clean G7 first-try, no parks.
The friction was concentrated in two recurring, non-feature places: a **path/location footgun**
(plan + G1 review + this retro all misfiled or mis-targeted at `reviews/` vs
`docs/process/reviews/`) and a **planner asserting verification it hadn't fully done** (the
`summary()` case table). Both have happened before.

**What went well (load-bearing):**
- The live-volume discipline (memory `legacy-notes-feedback-load-bearing`) held: 31 empty reviews
  stayed `awaiting`, 61 notes/feedback files untouched. The implementer rebuilt against a
  `docker cp` of the `:8139` volume and the critic independently re-derived `summary()` and
  byte-compared every reader region against `e091509^` — the right depth for a read-path-preserving
  cut, and it paid off.
- G1 round 1 caught a genuinely load-bearing defect (wrong design-fork table → vacuous safety AC)
  *before* it became a wrong ticket AC. The gate doing its highest-value job.
- The cycle right-sized itself down (dropped the planned 3rd MCP ticket) instead of shipping a
  no-op edit + a reconnect ceremony.

## Top suggestions (highest-leverage first)

1. **Hard-code the canonical artifact paths into the planner/skill so the planner stops misfiling
   at repo-root `epics/`/`reviews/`.** `[skill]` (primary) / `[agent]` mdreview-planner. This run
   the planner wrote *both* the epic and its G1 review to repo-root `epics/`/`reviews/`; the
   orchestrator had to `git mv` and the critic flagged it. **Recurring.** Fix is a one-line rule in
   the skill ("epics → `docs/process/epics/`, gate reviews → `docs/process/reviews/`; never
   repo-root") and the planner's prompt, not a per-run catch.

2. **Resolve the `reviews/` directory split — it caused all three location misfires this run.**
   `[process]`. The README Layout names `docs/process/reviews/` as canonical, but gate-review `.md`
   files live there while **render-evidence dirs, smoke `.txt`, and the source audit live in
   repo-root `reviews/`** — and this retro was *requested* at repo-root `reviews/` while every prior
   retro is in `docs/process/reviews/` (written there to match convention). Pick one: (a) ratify the
   split in the README ("reviews `.md` → `docs/process/reviews/`; bulky evidence/smoke/audits →
   repo-root `reviews/`"), or (b) collapse to one tree. Until written down, every cycle re-litigates
   it.

3. **Add a planner standing-instruction: when you claim to have "traced" code, paste the
   derivation, don't assert the conclusion.** `[agent]` mdreview-planner. The plan stated "I traced
   the status derivation in `summary()` … for every population that actually exists" — yet the case
   table was wrong in two independent ways (credited the guard with protecting the 12 `fu>0`
   reviews; it actually protects the 31 Pop-B reviews, and the tested Pop-C state has 0 live
   instances). Requiring the planner to *show* the per-population truth table (KEEP vs DELETE, with
   live counts) rather than assert "I traced it" would have surfaced the error in round 0.

4. **Reconcile the TRACKER against git at sprint close, not by hand.** `[process]` / `[skill]`. The
   board still says sprint-12 is "pending dev→main PR" but its commits + close-review are already on
   `origin/main` (merge `72c6522`). A close-step check (`git log origin/main..dev` to derive
   merged/pending state) beats trusting the prose. Low effort, recurring payoff.

5. **For pre-hardened briefs, have the skill state up front what the cycle is *adding* vs
   *re-certifying*.** `[skill]`. This brief arrived already corrected twice in-session before the
   cycle started, then captured verbatim (the right G0 call). But the planner partly re-walked
   covered ground, and the one place it diverged from the audit (the `summary()` guard) is exactly
   where it got it wrong by re-deriving loosely. A one-line "what's already verified upstream / what
   this cycle re-checks" framing would stop confident re-assertion of upstream facts only skimmed.

**Honest note on ceremony:** for a 16-line `app.py` change + ~20 doc lines, the overhead (570-line
plan, two G1 rounds, 214 + 114 lines of G1 review, 143-line G7 review) is heavy relative to the
diff. It was **not** wasted — G1 caught a real wrong-AC defect and the read-path verification was
genuine — but the value came from the *guard analysis* and the *reader sweep*, not the volume of
prose. The planner's habit of restating each decision 3-4 times (the MCP no-change decision appears
in ~8 places) is the avoidable part.

**Metrics:** G1 rounds: **2** (r1 CHANGES-REQUESTED → r2 PASS). G7 rounds: **1** (PASS first try,
0 BLOCKER / 0 SHOULD / 2 NIT, both close-step hygiene). Tickets shipped: **2/2**; carried: **0**.
Parks: **0**. Wrong load-bearing assumptions: **1** (the `summary()` design-fork table / vacuous
Pop-C safety AC — caught at G1, decision survived). Scope: right-sized *down* (3rd MCP ticket
dropped at G1, correctly).

## The 2-3 highest-leverage calls

1. **Hard-code canonical artifact paths in the skill/planner** (#1) and **write down the `reviews/`
   split** (#2) — together they kill the recurring location footgun that hit three artifacts this
   run.
2. **Planner must paste derivations, not assert "I traced it"** (#3) — directly targets the one
   wrong load-bearing assumption and a repeating planner pattern.

_Suggestions only — the cycle-retrospective agent edits nothing; these are for the user to apply._
