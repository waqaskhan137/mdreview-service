# TRACKER — the board

At-a-glance view of every ticket grouped by status. The ticket frontmatter is the source of
truth; move a row here whenever a ticket's `status` changes.

Last updated: 2026-06-08. Epic review-dashboard shipped to main (PR #1).

## Active sprint

**sprint-01 — Review dashboard** (`closed`, 2026-06-08). Epic: `review-dashboard`. G7 passed.
Progress: 7/7 done — all committed tickets complete; sprint pending G7 close.

## ready

_none_

## in-progress

_none_

## review

_none_

## done

| ID | Title | Layer | Pri | Sprint |
|----|-------|-------|-----|--------|
| MR-001 | Persist provenance (project/source_path/session) on POST + meta | svc | P1 | sprint-01 |
| MR-002 | summary() + list_reviews() + GET /api/reviews | svc | P1 | sprint-01 |
| MR-003 | Serve dashboard at /; move JSON descriptor to /api | svc | P1 | sprint-01 |
| MR-005 | History snapshots on PUT + /history routes | svc | P2 | sprint-01 |
| MR-004 | dashboard.html — Project>Session grouping, status pills, open/delete, revision badge | ui | P1 | sprint-01 |
| MR-006 | viewer.html — Google-Docs gutter comments + minimal history view | ui | P1 | sprint-01 |
| MR-007 | Docs — provenance/list/history fields + docs/future-mcp.md | docs | P2 | sprint-01 |

## blocked

_none_

## Epics

| Epic | Status | Gate | Sprint |
|------|--------|------|--------|
| review-dashboard | done (merged to main 2026-06-08, PR #1) | G1 passed 2026-06-08 | sprint-01 |
