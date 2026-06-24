---
review_of: epics/watcher-observability-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: epic done — smooth run, G1 1 round / G7 1 round, 0 parks, 0 carries, 0 wrong load-bearing assumptions; one AC-clause gap (F1) slipped G4
status: resolved
---

# Cycle Retrospective — watcher-observability (sprint-24, GH #26)

Reviews the RUN, not the feature. Persisted to disk so the learnings survive the session. The epic
shipped pickup-timeout + crash-surfacing in three dependency-ordered tickets (MR-066 viewer `.warn`
cue → MR-067 watcher capture+signal → MR-068 viewer crash render); G1 GO-WITH-NITS in one round,
G7 PASS first-pass on an independent rebuilt-container re-drive; epic closed `done`.

## Verdict

Smooth run. The planner pre-resolved both "pin it" forks against the code and the critic verified
both pivotal correctness questions against the source, so G1 cleared in one round with no NO-GO.
The one real friction is not in this cycle's conduct but in the process *not learning*: the
node-CDP validation wall was hit and named for the **third** cycle running, and the fixes two prior
retros proposed for it still do not exist.

## What went well (load-bearing)

- **G1 was a real verification gate, not a rubber stamp.** The critic's highest-value catch — the
  crash-AFTER-`hand_back` false positive (a child that POSTs `done` then exits non-zero in teardown
  would be stomped by an unconditional crash signal) — became a MANDATORY `/status` re-check plus a
  dedicated false-positive stub test, and that guard then passed both G4 and G7 end-to-end against a
  real watcher run. A design-time catch that held all the way through is the gate working.
- **Both load-bearing pins were verified, not argued.** "Does the client-elapsed cue fire without a
  `/status` change?" (`viewer.html:668` re-invokes `renderBanner` every poll) and "does the existing
  `hand_back{state:blocked}` arm suffice?" (`app.py:623-629`) were both confirmed against source
  before G1 passed — so "no `app.py` change" held and scope stayed clean (commits touched only
  `viewer.html`, `watch.py`, `README.md`).
- **G7 independently re-drove against a REBUILT container** (scratch port 8182) with a fresh CDP
  driver and real watcher stub runs, not a re-read of the implementer's G4 — and caught F1 that G4
  missed.

## Prioritized suggestions (SUGGEST-ONLY — not applied)

1. **[process]/[skill] Write the node-CDP rule into the process — this is a THRICE-NAMED, un-actioned
   recurrence and the single highest-value fix.** The sprint-23 retro proposed adding a one-paragraph
   rule to `docs/process/README.md` ("`render-smoke.sh` verifies first-paint / non-modal nodes only;
   any time-dependent or click/JS-gated viewer state is verified by the node-CDP `Runtime.evaluate`
   driver, `agent_smoke.py:112-148`"); the sprint-22 retro named the same wall. Verified today: that
   rule is **still absent** from the process README, and sprint-24 re-derived a `.scratch/cdp_banner.js`
   from scratch under the same constraint, then the sprint file had to (again) spell the recipe out
   across ~12 lines of its own G7 scope note. Promote that prose to the README validation-gate /
   G4+G7 rows once so the next JS-DOM ticket inherits it instead of rediscovering it. A previously
   named, un-actioned fix recurring a third time is the highest-value class to close.

2. **[feature] Promote the node-CDP driver from a per-ticket `.scratch/` script to a checked-in
   `scripts/cdp-eval.sh` (sprint-23 retro suggestion #2, also un-actioned).** Both the MR-066/068
   implementer and the G7 critic again wrote their own open+poll+read-back CDP plumbing this cycle.
   The scaffold is identical every time; only the assertions differ. A thin checked-in helper next to
   `render-smoke.sh` lets the AC author write only the assertions and still lets G7 re-drive
   independently with a different assertion set. Backlog `feature` ticket; pairs with #1.

3. **[process] Add an AC-completeness (field-by-field) check to G4 — motivated by F1.** F1 (the crash
   record omitted the resolved argv the AC explicitly names: "review id, exit code, **the resolved
   argv**, and the captured stderr tail") is an AC-clause-vs-implementation gap that neither the
   implementer's self-check nor G4 caught — only the independent G7 did. The headline goal
   (diagnosability) was met, which is exactly why a prose-level self-review glides past it. A G4 rule
   — when an AC enumerates the fields of a structured output, check the artifact carries *each named
   field*, not just that the behavior works — would have caught it one gate earlier and cheaper.

4. **[skill]/[process] Codify the from-source-G4 / container-at-G7 split as an explicit, bounded
   pattern (it worked here, but only by the implementer's judgment).** G4 validated against a
   working-tree service on a scratch port (rationale: `viewer.html` is served from disk and `watch.py`
   is non-containerized, so a rebuild proves nothing G4 needs), and G7 independently re-drove against
   a rebuilt container — and that container re-drive is what surfaced F1. The split is sound *for this
   layer shape*, but it currently rests on an undocumented judgment call. Write it down: for `ui`
   (disk-served `viewer.html`) and `watch.py` (non-containerized) tickets, G4-from-source is
   acceptable **provided G7 re-drives against a rebuilt container**; for any `infra`/Dockerfile/COPY
   change the rebuild is owed at G4. This keeps the corner from being closed too early (a needless
   per-ticket rebuild) without leaving it to memory each cycle.

5. **[feature] Close the F4 server-side TOCTOU when it stops being hypothetical.** G7's F4 noted the
   server's blocked hand-back arm (`app.py:623-629`) is unconditional, so the watcher's client-side
   `/status` re-check is the *sole* guard against stomping a `done`, with a tiny single-watcher TOCTOU
   window. Correctly accepted as the safe direction for v1 (a missed signal self-heals; a rare false
   "stopped" only offers a non-destructive "Take back the turn"). Capture as a backlog `feature` with
   the recorded revisit trigger: a server-side guard on the blocked arm, or real multi-watcher
   contention on one review. Not this cycle's work — a tracked deferral so it is not silently lost.

## Metrics

G1 rounds: 1 (GO-WITH-NITS, five nits folded into ACs, no re-review). G7 rounds: 1 (PASS first-pass;
F1 worth-fixing resolved post-review on dev, F2/F3/F4 accepted non-blocking). Tickets shipped: 3
(MR-066/067/068); carried: 0. Parks: 0. Wrong load-bearing assumptions: 0 (both "pin it" forks
verified correct against source at plan time and held through G7). Recurring friction: node-CDP
validation wall (3rd cycle: sprints 22, 23, 24) — un-actioned process/helper fix.

## Resolution log

- 2026-06-24 — Retro produced at epic close (sprint-24). Suggestions are advisory; none applied
  (cycle-retrospective never edits process/skill/agents). Suggestion #1 (node-CDP rule into the
  process README) is a flagged third-time recurrence and the strongest candidate for a follow-up
  `docs`/`process` ticket; #2 (`scripts/cdp-eval.sh`) pairs with it as the `feature` half.
