---
retro_of: viewer-transparency (epic, GH #27, sprint-26)
kind: cycle-retrospective
author: cycle-retrospective
date: 2026-06-25
related_epic: epics/viewer-transparency-plan.md
related_sprint: sprints/sprint-26.md
g1_review: reviews/viewer-transparency-plan-review-2026-06-24.md
g7_review: reviews/sprint-26-close-review-2026-06-24.md
---

# Cycle retro — viewer-transparency (#27, sprint-26)

**Verdict:** Smooth run. Both gates passed in one round, zero parks, zero carry-overs. The only
real friction was *outside* the gated flow: a post-G4 live-testing confusion loop driven by a
partial-smoke screenshot read as a deployed bug. The one durable defect is an artifact-placement
slip (G7 render-evidence written to the wrong `reviews/`).

## What went well (load-bearing)

- **Read-the-code-first design collapsed scope correctly.** The planner verified every "verified
  against" cell against `app.py`/`mcp_server.py`/`watch.py` and found the `ping_working.message`
  plumbing already round-trips end-to-end (`mcp_server.py:454` → `app.py:661` → `/status`). That
  turned a "show what the agent is doing" ask into a UI-only, no-new-API, no-agent-instrumentation
  change and **cut MR-074** before it cost a ticket. This is the pattern to keep: resolve the
  load-bearing fork against the real code, on the record, so the implementer never re-litigates it.
- **The independent G7 CDP re-drive earned its keep.** W1 (the timer baselined on Send, so it
  included pickup lag, not just agent work time) was a real semantic defect the implementer's own
  G4 smoke missed and the independent gate caught — exactly the leak G7 exists to stop. A 6-line
  fix (`9029762`) followed.

## Top suggestions (prioritized)

### 1. Fix where G7 render-evidence is written — it landed at repo-root `reviews/`, not `docs/process/reviews/`. `[process]`
The G7 review and the sprint file both cite `reviews/sprint-26-render-evidence-2026-06-24/`, but the
directory was actually created at **`<repo-root>/reviews/`**, while the README's Layout + Reviews
sections put all gate evidence under **`docs/process/reviews/`**. Read relative to the citing review
file (which *is* in `docs/process/reviews/`), the cited path resolves to a directory that does not
exist — a future session following the link hits a dead end. This is **recurring**: the same stray
`reviews/sprint-12-render-evidence-2026-06-19/` sits untracked at repo-root (the session-start git
status). Either the skill/agent should write evidence under `docs/process/reviews/...` to match the
README, or the README should bless a repo-root `reviews/` and the citations should be made
unambiguous. Pick one and make the path-convention explicit so the citation always resolves.

### 2. Don't share a partial-smoke screenshot as if it were the deployed state; and close the "not live until redeployed" gap. `[process]`
The highest-friction moment was post-G4 and *outside* the gates: the owner reacted to a screenshot
of a **partial** smoke (a `done` state, no comment resolved — the "1:12" value now frozen in
MR-073's Validation log) as a deployed bug ("timer stuck at 1:12, never checked updating comments"),
and the feature was not even on their live `:8139` yet. Resolving it cost a redeploy + a
comment-path re-smoke. Two durable lessons: (a) any screenshot handed to the owner mid-cycle should
be **labelled** with what lifecycle stage it captured and whether it is from a throwaway smoke vs a
live deploy, so a partial proof is never mistaken for the shipped state; (b) the recurring "a deploy
isn't live until the container is recreated / the page is hard-refreshed" gap keeps biting (it ties
to the deferred #27 part-3 stream work and the auto-reload idea). Worth a short process note on the
deploy-and-verify handoff, and worth weighing a viewer auto-reload-on-new-version as a `[feature]`
backlog item.

### 3. Keep the "default + flag the one load-bearing fork" pattern — surfacing the step-level vs tool-call-stream fork to the owner at G1 was the right call. `[agent]`
The planner correctly identified that the A-vs-C fork (step-level stages vs the literal tool-call
stream) was the *one* choice that could waste a sprint, set a default (ship A, defer C), and flagged
exactly that as the open question — which the owner closed at G1 via AskUserQuestion, keeping the
epic UI-only. Everything cuttable (MR-074) was handled as an autonomous assumption, not escalated.
This is the calibration the planner agent should keep: escalate the product fork, decide the
engineering trade-offs. No change needed — recording it so the pattern is reinforced, not eroded.

### 4. Generalize the "node-CDP drive, not render-smoke, for time-dependent JS" rail into the skill's UI-validation guidance. `[skill]`
This epic correctly recognized that `render-smoke.sh` cannot drive a signal-sequenced, ticking JS
state and specified a node-CDP lifecycle driver — but that recognition lived in the *plan's*
prose, re-derived for this feature. Several past epics (working-banner, watcher-observability) hit
the same wall. A standing rule in the feature-cycle skill — "a UI ticket whose deliverable is
*time-dependent or signal-sequenced* owes a CDP drive; render-smoke is first-paint only" — would
stop each UI epic re-deriving it and prevent a future one from shipping a thin screenshot proof.

## Metrics

- **G1 rounds:** 1 (GO-WITH-NITS; 2 worth-fixing nits folded, both signal-honesty labels).
- **G7 rounds:** 1 (PASS, independent node-CDP re-drive; 1 worth-fixing W1 fixed post-pass, 2 nits accepted).
- **Tickets shipped vs carried:** 2 shipped (MR-073, MR-075), 0 carried. MR-074 cut at plan time (sound).
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0 overturned. W1 was a spec-as-written semantic mismatch
  (timer counted from Send, not claim) the independent gate flagged — the design assumptions
  (derived-signal timeline, client-captured duration, MR-074-cut) all held under drive.
- **Mid-cycle changes absorbed cleanly:** 1 requirement amendment (elapsed/duration timer, folded
  via the planner with the brief preserved + a dated Amendment) and 1 owner fork resolved at G1.
