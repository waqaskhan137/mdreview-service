# TRACKER — the board

At-a-glance view of every ticket grouped by status. The ticket frontmatter is the source of
truth; move a row here whenever a ticket's `status` changes.

Last updated: 2026-06-09. mcp-wrapper (sprint-04) groomed, G1 passed (2 rounds); implementing. 3 epics on main.

## Active sprint

**sprint-04 — MCP wrapper** (`active`, 2026-06-09). Epic: `mcp-wrapper`. G1 passed (2 rounds); 4 tickets ready.
sprint-01/02/03 all shipped to main (PR #1, #2).
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
| MR-008 | Planner agent — fit-based-layout rule + Dockerfile-COPY footgun | docs | P2 | sprint-02 |
| MR-009 | Add scripts/render-smoke.sh (DOM-node assertion) | infra | P1 | sprint-02 |
| MR-010 | README + skill — render-smoke as the ui validation bar (G4 row) | docs | P1 | sprint-02 |
| MR-011 | README — reconcile DoD with bounded same-sprint docs-sweep (G7 row) | docs | P2 | sprint-02 |
| MR-012 | Planner agent — wire-enforcement-into-row + cite-by-name rules | docs | P1 | sprint-03 |
| MR-013 | README — citation-by-name convention + scope G7 render clause | docs | P2 | sprint-03 |
| MR-014 | Skill — pre-G7 board-reconciliation rail + SKILL.md invariant | docs | P2 | sprint-03 |
| MR-015 | mcp_server.py — stdio JSON-RPC core | svc | P1 | sprint-04 |
| MR-016 | tools/call dispatch → HTTP | svc | P1 | sprint-04 |
| MR-017 | mcp_smoke.py — stdlib smoke harness | svc | P1 | sprint-04 |
| MR-018 | Docs — MCP wrapper | docs | P2 | sprint-04 |

## blocked

_none_

## Epics

| Epic | Status | Gate | Sprint |
|------|--------|------|--------|
| review-dashboard | done (merged to main 2026-06-08, PR #1) | G1 passed 2026-06-08 | sprint-01 |
| process-hardening | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-08 (2 rounds) | sprint-02 |
| process-hardening-2 | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-09 (2 rounds) | sprint-03 |
| mcp-wrapper | active | G1 passed 2026-06-09 (2 rounds) | sprint-04 |
