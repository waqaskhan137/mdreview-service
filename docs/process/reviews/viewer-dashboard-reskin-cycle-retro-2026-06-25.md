---
retro_of: epics/viewer-dashboard-reskin-plan.md
cycle: sprint-28
reviewer: cycle-retrospective
timestamp: 2026-06-25
scope: the RUN (plan -> G1 -> tickets -> sprint -> implement -> G7 -> PR), not the feature
---

# Cycle retrospective — viewer-dashboard-reskin (sprint-28)

**Verdict:** Smooth run, no parks, zero wiring regressions. The only real friction was
**self-inflicted G7 churn from a planner estimate baked into a ticket AC as a hard number**
(`~1180px`), plus two ad-hoc-but-load-bearing verification steps (side-by-side mockup
comparison, dark-pane computed-style) that the process did not require — it got them because the
implementer chose to, not because a gate asked.

## What went well (load-bearing)

- **The planner's footgun map held.** Every load-bearing constraint the plan surfaced (STALE_S
  single-mirror, `layoutComments` fit-test-not-pixel, legacy back-compat, "200 is not a render")
  survived implementation with zero wiring regressions — the G7 review confirms each contract by
  live check. A re-skin touching ~600 lines of load-bearing inline JS shipping with no functional
  regression is the plan doing its job.
- **G1 caught the highest-risk gap before tickets existed.** C1 (the `.gcard`-presence-proves-
  nothing wide-mode gap) was found at plan review and folded into a mandatory ticket AC r1 — that
  is exactly where it should be caught, not at G7.

## Top suggestions (prioritized)

### 1. Stop baking planner/critic point-estimates into ACs as hard numbers `[skill]`/`[agent]`
The single MAJOR at G7 (F1) was not a defect: MR-089's C1 AC demanded `body.gutter-on` at
`~1180px`, but the (unchanged, pre-existing) 720+320 geometry only engages wide mode at `~1315px`.
The `~1180px` was a *planning estimate* the critic wrote into the C1 condition and the orchestrator
carried verbatim into the ticket; G7 then spent a MAJOR finding + a fix commit (`3f85c50`)
reconciling the AC to measured reality. **The geometry was never regressed** (`git diff 8d4227c^`
proves it). Fix: when a planner/critic asserts a *measured* threshold (pixel boundary, byte size,
timing) it should be tagged as an estimate-to-verify ("measure during implementation; pin the AC to
the measured value"), never frozen as a pass/fail number the implementer must hit. An AC that was
"never satisfiable with the existing geometry" (G7's words) is a spec defect the planner can avoid.
This is the highest-value fix: it is a *recurring class* (any baked-in number invites the same
churn).

### 2. Make the side-by-side mockup comparison + dark-pane computed-style check a required G4/G7 step for visual-spec work `[process]`
This run's *real* fidelity bugs (project-only crumb, hairline divider, status dot) were caught by a
live side-by-side mockup capture the **user asked for mid-run**, and dark-pane legibility was proven
by a computed-style contrast read — neither is in the G4/G7 gate text. The gate requires DOM-node
assertions + screenshots, but "a node exists" and "a screenshot rendered" do not prove *fidelity to
a visual spec* or *legibility on the dark pane*. For any epic whose design source is a visual-spec
mockup, add a gate step: (a) a side-by-side capture vs the mockup at the target width, (b) a
dark-pane `getComputedStyle` contrast read on palette-sensitive nodes. The evidence dir already did
both well (its README is a good template) — codify it so the next visual-spec run does not depend on
the user remembering to ask.

### 3. Teach the cycle to handle a run on an intermediate feature branch `[skill]`
The cycle ran on `feat/ui-updates` (cut from `dev`, user-created), not on `dev`. This broke two
process assumptions: Phase 9's "push dev / standing dev->main PR" did not cleanly apply, and "no
service change" tripped a false alarm (G7 F3: `app.py` differs from `origin/main` because
`feat/ui-updates` carries an un-merged MR-064 from `dev`). The run had to stop and ask the human the
PR target. Fix: the skill should (a) detect at start when the working branch is not `dev`, record
the branch and its merge-base in the sprint/ticket frontmatter (the tickets *do* carry
`branch: feat/ui-updates` — good), and (b) compute "this sprint's changes" against the **merge-base
of the working branch**, not `origin/main`, so a "no svc change" claim is checked against
sprint-authored commits (`git diff 8d4227c^ HEAD`), not branch-provenance noise.

### 4. Add a "dead code from removed affordances" self-check before G4 `[process]`/`[skill]`
Two NIT G7 findings (F4 orphan `.watcher` CSS, F5 unreachable `"Ungrouped"` fallback) were dead code
left when affordances were removed — and MR-087's own AC explicitly said "no dead selector / no
orphaned handler", yet both slipped the implementer's self-check into G7. When a ticket *removes* an
affordance, the self-check should grep the removed selector/identifier names to prove they are gone
from both markup and CSS/JS. Minor individually, but it is a *pattern* (re-skins routinely strip old
affordances) and the AC already promises it — the gap is a missing mechanical check, not a missing
rule.

### 5. Sweep evidence claims for self-referential grep traps `[skill]` (minor)
G7 F2 caught `grep -c STALE_S dashboard.html -> 0` claimed in evidence while the actual count is 2
(both explanatory comments). The substantive constraint held; the *literal* claim was false. The AC
was corrected to a code-specific grep, **but the same false `grep -c STALE_S -> 0` still sits
uncorrected in MR-087's Validation log (line 101)** — the fix landed in the AC and evidence README
but not the ticket's own validation note. Lesson: a grep used as proof must match *code*, not
comments-about-the-code, and when a finding corrects a claim, fix *every* copy of it. Low stakes,
but it is a literal falsehood left in the durable record.

## Metrics

- **G1 rounds:** 1 (PASS-with-conditions; 4 conditions C1/C2/M1/N1 folded r1, no re-review needed).
- **G7 rounds:** 1 (PASS-with-conditions; 5 findings — 1 MAJOR + 2 MINOR + 2 NIT — all resolved in
  one fix commit `3f85c50`; 0 blockers).
- **Tickets shipped vs carried:** 4 shipped (MR-087/088/089/090), 0 carried. Docs-sweep (MR-090)
  closed in-sprint (not carry-over-eligible).
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0. All 6 plan assumptions held; the IA-replacement and
  dark-mode-preserved load-bearing calls were both confirmed correct at G7. The only "wrong number"
  was a non-assumption planning *estimate* (the ~1180px AC), and a plan-scope miss: the docs-sweep
  grep targeted README + CLAUDE only, but the implementer correctly also swept **AGENTS.md** (which
  carries the same curl-comment IA text) — the plan's Phase-3 grep list was incomplete by one file.
