---
id: MR-047
title: Docs sweep — "human is done" → comments_updated (CLAUDE/AGENTS), drop POST /feedback from README, fix future-mcp.md
status: ready
layer: docs
priority: P2
sprint: sprint-13
epic: legacy-feedback-retire
depends_on: [MR-046]
branch:
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Land the documented-contract change that must accompany MR-046's write retirement, so no doc
advertises a write surface that now returns 410 or tells agents to poll a signal that nothing
bumps. This is the same-sprint docs-sweep for MR-046 (not carry-over eligible — must be `done`
before sprint-13 closes).

## Acceptance criteria

- [ ] `CLAUDE.md` and `AGENTS.md` "Detecting the human is done" section (`CLAUDE.md:80–87`,
      `AGENTS.md:36–43`) rewritten to tell agents to watch **`comments_updated`** (the live signal
      the viewer bumps), not the dead `feedback_updated` write. The "or tell the human to reply
      'done'" option is kept.
- [ ] `README.md` API table: the `POST /api/reviews/{id}/feedback` write row (`README.md:52`) is
      removed; the `GET /feedback` row (`:51`) and the `status` row (`:53`) are kept exactly.
- [ ] `docs/future-mcp.md:61` — the line "The 'human is done' heuristic in `AGENTS.md` is
      unchanged." is dropped or repointed (Phase 2 changes exactly that heuristic, so the sentence
      becomes false). `docs/future-mcp.md:36`'s `get_status` table row stays (the field is still
      emitted).
- [ ] **No `mcp_server.py` change** — its `get_status` description (`mcp_server.py:108–109`)
      already leads with "Watch comments_updated for new/changed comment threads" and only *lists*
      `feedback_updated` as one of three still-emitted timestamps (factually true). Confirm and
      leave it; therefore **no MCP-client reconnect is owed** by this epic.
- [ ] The read-shape status comment in the contract snippets (`CLAUDE.md:24`, `AGENTS.md:24`,
      `# {"source_updated":…, "feedback_updated":…}`) stays accurate (the field is still emitted) —
      may optionally add `comments_updated` for clarity, but not required.
- [ ] Inspection checks pass: `grep -n "feedback_updated" CLAUDE.md AGENTS.md` shows the
      "human is done" bullet now says `comments_updated` in both; `grep` for the POST `/feedback`
      row in `README.md` is empty; `grep -n "unchanged" docs/future-mcp.md` no longer asserts the
      old heuristic. (Docs layer — no `py_compile`/render-smoke owed.)

## Notes / context

- Depends on **MR-046** landing first (svc-before-docs) so docs never describe a route whose
  behaviour hasn't changed yet.
- Epic: [`epics/legacy-feedback-retire-plan.md`](../epics/legacy-feedback-retire-plan.md) — see
  "Docs" section and the "MCP edit — right-sized to no change" decision. The dropped third (MCP)
  ticket and the reconnect ceremony are deliberately out of scope per G1.
- **Frozen historical records are NOT retro-edited:** `epics/mcp-wrapper-plan.md:110`,
  `epics/dashboard-redesign-plan.md:39`, `tickets/MR-002-list-and-summary.md:23` mention
  `feedback_updated` but are shipped artifacts — leave them (per the README's never-edit-history
  ethos). Only `docs/future-mcp.md` is a live design-record doc and is edited.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- AGENTS.md/CLAUDE.md full dedup (audit finding 2) — backlog, out of this epic.
