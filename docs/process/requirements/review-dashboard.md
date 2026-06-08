---
slug: review-dashboard
captured: 2026-06-08
source: user session 2026-06-08 (waqas), interactive planning + viewer review
related_epic: epics/review-dashboard-plan.md
---

# Review dashboard, provenance, history, sessions, and Google-Docs comments

Verbatim asks as supplied during the session. Do not edit. If the requirement changes, append a
dated note under Amendments rather than altering the text above.

- "the feature where it keeps track of the feedback and actual md files and have a dashboard
  showing files and relevant sessions or projects the mdreview files came from?"
- "What happens when an agent wants to see the review file from past. Is there any history
  tracking?"
- "Can this be an MCP?"
- "This service should be able to handle multiple files from same or multiple agent sessions. Is
  it doing it now?"
- "the note or comment should be visible like google docs comment style."

## Amendments

- 2026-06-08: scope decisions gathered during interactive grooming are recorded in the epic plan,
  not here. Summary of the decisions: provenance via optional `project` + `source_path` +
  `session` fields on POST; dashboard at `/` with list + open + delete, grouped Project > Session
  > files; lightweight append-only history snapshots (one round per agent revision); Google-Docs
  style margin comments with exact-span highlight, collapsing to the existing panel below ~820px;
  MCP wrapper deferred to a follow-up (documented in `docs/future-mcp.md`, not built in this
  epic).
