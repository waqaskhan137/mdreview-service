---
review_of: epics/agent-handoff-baton-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-23
verdict: epic done — smooth, 0 parks, 0 wrong load-bearing assumptions across 3 chunks
status: resolved
---

# Cycle Retrospective — agent-handoff-baton (3-chunk epic, sprints 14/15/16)

Reviews the RUN, not the feature. Persisted to disk so the learnings survive the session (a prior
retro's own suggestion). The epic shipped a turn-based handoff baton in 3 dependency-ordered chunks
(MR-051 server contract → MR-052 viewer UI → MR-053 agent surface), each G1 PASS-WITH-NITS and G7
PASS first-pass; epic closed `done`, in standing PR #17.

## What went well (load-bearing)

- **The G1 plan held across all 3 chunks.** Every footgun the critic verified (unlocked `bump()`,
  route non-shadowing, `/status` additivity, the 409 convention) proved correct in implementation.
  Zero wrong load-bearing assumptions epic-wide.
- **Chunk boundaries were right.** MR-051 shipped invisibly/additive; MR-052 and MR-053 built on it
  independently; each G7-PASS first-pass. Chunked delivery worked.
- **The reconnect caveat was surfaced** (ticket / sprint / PR / CLAUDE.md) with the `tools_hash`
  change `f265447b5a8c`→`a97fb4f09e7c` as the human/CI signal.

## Prioritized suggestions (SUGGEST-ONLY — not applied)

1. **[process] A new `svc` route must add its README API-table row in the same change.** MR-051
   shipped `POST /handoff` but its ACs owed no API-table entry; the row was backfilled 3 chunks later
   by MR-053. A route that "ships invisibly" still ships a public HTTP contract. Add to the DoD/G5:
   a new `svc` route updates the README API table same-change (same rule as AGENTS/CLAUDE).
2. **[process] Ratify the `reviews/` directory split — this is a RECURRENCE** of the
   `legacy-feedback-retire` retro's #2. Gate-review `.md` lives under `docs/process/reviews/`, but
   bulky render-evidence has gone to repo-root `reviews/` in some sprints and `docs/process/reviews/`
   in others; the G7 row says `reviews/sprint-NN-render-evidence-*` with no tree prefix. One line in
   the README Layout resolves it permanently (e.g. gate `.md` → `docs/process/reviews/`; bulky
   evidence → repo-root `reviews/`). A previously-named, un-actioned fix recurring is the
   highest-value class to close.
3. **[skill] Document multi-chunk epic-close mechanics in `04-close-and-ship.md`.** Marking the epic
   `done`, accumulating `related_sprints`, and retitling the standing PR across chunks worked here by
   attentiveness, not by the skill. Add an "if this is the epic's final chunk" sub-step to Phase 8.
4. **[skill] Phase 9 should emit a post-merge callout when `mcp_server.py` `TOOLS`/`tools_hash`
   changed** ("After merge: reconnect the MCP client — tools_hash changed X→Y"), so the human doing
   the G8 merge knows the merge isn't the last step.
5. **[process] Tighten scope-widen vs docs-sweep.** MR-053's same-change update of 4 doc files for a
   tool-count bump was correctly recorded per the blocking rule and is DoD-compliant (mechanical,
   low-risk). Heuristic worth writing into the DoD: a multi-file count/enumeration bump is fine
   same-change; anything needing *new prose* across files is better a named same-sprint docs-sweep
   ticket (gets its own G2 grooming).

## Metrics

G1 rounds: 1 (PASS-WITH-NITS, folded into ACs, no re-review). G7 rounds: 1 per sprint (all PASS
first-pass; 14: 2 NITs, 15: 3 NITs, 16: 1 NIT). Shipped: 3 tickets (MR-051/052/053); carried: 0.
Parks: 0. Wrong load-bearing assumptions: 0. Deferred: concurrent co-editing (OT/CRDT) — issue #16.

## Resolution log

- 2026-06-23 — Retro produced at epic close (final chunk, sprint-16). Suggestions are advisory; none
  applied (the cycle-retrospective never edits process/skill/agents). Suggestion #2 (`reviews/` split)
  is a flagged recurrence and the strongest candidate for a follow-up `docs` ticket.
