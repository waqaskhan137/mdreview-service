---
retro_of: feature-cycle run — theme-awareness epic (sprint-07 / MR-027)
agent: cycle-retrospective
timestamp: 2026-06-18
subject: the RUN (plan → G1 → tickets → sprint → implement → G7 → PR), not the feature
---

# Cycle retrospective — theme-awareness

## Verdict

**Smooth run, one real catch.** A 9-line CSS epic that the G1 critic caught overclaiming
(symmetric fix), forcing one honest re-scope round before tickets spawned; then a clean first-pass
G7. Friction was minimal and the two carried footguns from the previous cycle visibly paid off.

## What went well (load-bearing)

- **The G1 critic earned its keep, the high-value way.** The plan claimed a *symmetric* fix
  ("and the inverse for a dark-authored figure"); the critic **measured** the regression
  (white-on-transparent figure luminance spread 238 → 5 on the mat) and forced a re-scope to a
  named non-goal, *shown* on the dark screenshot for sign-off rather than discovered post-ship
  (`theme-awareness-plan-review-2026-06-18.md`, BLOCKER). This is the gate doing exactly its job.
- **Footguns 10-11 (added by last cycle's retro) worked.** The plan/ACs used two flat selectors
  `'img' '#article' '.mermaid'` (never `'#article img'`) and the GET-header-dump note for any
  incidental `Content-Type` check — the two sprint-06 mistakes the previous retro flagged.
  **Evidence that retro → footgun-list is an effective feedback loop**: a named past failure did
  not recur. (`epics/theme-awareness-plan.md` Key constraints; `MR-027` Notes.)

## Top suggestions (prioritized)

### 1. Promote "measure both directions before claiming symmetry" to a planner method step `[agent]`
The planner measured one boundary rigorously (host `color-scheme` does not reach `<img>` SVGs —
correctly killing option (b)) but asserted the mat's *inverse* effect from prose, and got it
wrong: it claimed symmetry the critic then disproved by measurement (238 → 5). The planner had the
exact tool (a headless screenshot + luminance sample) it used on (b) and simply did not point it at
the mat's dark-authored case. Generalizable habit for `mdreview-planner.md`: **"When a fix is
asymmetric by nature (a surface/color/theme choice that helps one input class and may hurt another),
measure BOTH directions with the same rigor before claiming a symmetric benefit; an unmeasured
'and vice-versa' is a red flag."** This is the single change most likely to prevent a recurring
class of G1 BLOCKER (overclaim caught by the critic's measurement).

### 2. Make empirical-measurement-in-planning an explicit planner step `[agent]`
Twice now a measurement settled a design fork that prose argument would have gotten wrong: the
`color-scheme` boundary (planner, pre-G1) and the mat regression (critic, at G1). It is currently
an emergent habit of this planner, not a documented method. Add to the planner's process: **"For any
design fork that turns on observable browser/render behavior, settle it with a throwaway-container
screenshot or DOM dump and put the result table in the plan, not a prose argument."** Pairs with
suggestion 1 (which says *which* directions to measure); this says *measure, don't argue*. Both
target the same root: the plan is strongest exactly where it measured.

### 3. Add a lightweight scope-check ritual for the stale-local-`main` trap `[process]` or `[skill]`
The G7 critic's `git diff main...dev --stat` showed all of sprint-06 (app.py +132, mcp_server,
KaTeX) because local `main` was behind `origin/main`; the critic had to fall back to the impl commit
`f541bbf` to get a clean scope check (`sprint-07-close-review-2026-06-18.md`, NIT-1). Harmless this
run, but it recurs every cycle where the standing `dev → main` PR has not merged. Cheap fix: the G7
step should **scope-check against `origin/main` (or the impl commit range), not local `main`** — e.g.
`git fetch && git diff origin/main...dev --stat`, or diff the sprint's commit range directly. A
one-line instruction in the skill's G7 step prevents the critic re-deriving this each time.

### 4. Decide a policy on the `.histdoc`-arm screenshot gap, don't re-litigate it each cycle `[process]`
The `.histdoc img` (history-modal) arm is not render-smokeable at first paint (modal closed in a
`--dump-dom` load). The r2 G1 review asked for a manual modal shot "if cheap" at G7; the G7 critic
tried via CDP, couldn't run page JS in scope, and accepted the arm on CSS-semantics + render-path
inspection (`sprint-07-close-review...md`, SHOULD-1). The reasoning is sound (single shared
declaration block; `showRound()` guarantees the node) but this exact "should we screenshot the modal"
debate will resurface every time `.histdoc` is touched. Either (a) write a one-line standing rule —
*"a shared CSS declaration proven on one arm is accepted for sibling arms that aren't first-paint
renderable; no separate screenshot required"* — or (b) add a `render-smoke.sh` mode that can click
to open a modal. (a) is the cheaper, proportionate call.

### 5. Don't add a lighter gate path for tiny single-ticket epics — but note the real overhead `[process]`
Balanced take, since the run invites the question. For a 9-line CSS change the machinery (G0–G8, two
G1 rounds, a G7 close review, four screenshots) was *heavy in proportion to LOC* — but it was **not**
wasted: the G1 round caught a real overclaim, and the both-pane screenshots were the only thing that
could prove a theme-specific bug (a 200 is genuinely not a render here). The overhead that bought
nothing was procedural bookkeeping (board reconciles, frontmatter flips), not the gates. **Recommend
against a separate "tiny epic" path:** a second path is a second thing to keep correct, the
consistency of one process is worth more than the saved minutes, and "tiny" is exactly where an
unmeasured overclaim hides (this run proves it). If anything is trimmed, trim *ceremony* (collapse
the pre-G7 board-reconcile commit into the close commit), not *gates*.

## Metrics

- **G1 rounds:** 2 (PASS-WITH-CONDITIONS → PASS). Round 2 found **no new** issues — it narrowly
  confirmed the BLOCKER + 3 SHOULDs were resolved. Churn was convergent, not repeated-class.
- **G7 rounds:** 1 (first-pass PASS; 0 blockers, 1 SHOULD, 2 NITs — all informational/accepted).
- **Tickets:** 1 shipped (MR-027), 0 carried. One carry-*note* (the `.histdoc` modal-shot gap).
- **Parks:** none.
- **Wrong load-bearing assumptions:** 1 — the symmetric-fix claim, overturned by the critic's
  measurement at G1 (re-scoped to a named non-goal, ticket count unchanged).
- **Carried-footgun payoff:** 2/2 — footguns 10 (HEAD→501 / GET header-dump) and 11
  (`render-smoke` flat-matcher, two selectors) both observed; neither past mistake recurred.
