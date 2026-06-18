# TRACKER — the board

At-a-glance view of every ticket grouped by status. The ticket frontmatter is the source of
truth; move a row here whenever a ticket's `status` changes.

Last updated: 2026-06-18. sprint-06 (rich-rendering) **closed at G7 (staff-critic PASS) and merged to main (PR #5)** — math (KaTeX) + asset attach/serve live on `main`. sprint-05 (landing-page) merged to main (PR #4); page LIVE at https://mdreview.waqasrana.space/ (HTTPS enforced).

## Active sprint

_none active_ — sprint-06 merged to main (PR #5); `dev` and `main` aligned.

**sprint-06 — rich-rendering** (`closed`, 2026-06-18; merged to main, PR #5). Epic: `rich-rendering` (G1 passed 2 rounds; G7 PASS). Shipped the two P0s: math rendering (KaTeX marked-extension) + per-review asset attach/serve over HTTP & MCP + viewer `<img>` rewrite. MR-022–026 all `done`; local-dir `path` read form cut to backlog (S5).

**sprint-05 — landing-page** (`closed`, 2026-06-09; merged to main, PR #4). Epic: `landing-page`. G7 PASS; MR-019 done, MR-020 done (carry-over discharged: DNS added, cert issued, HTTPS enforced, README URL recorded). MR-021 (GIF demo) remains backlog.
sprint-01/02/03/04/05/06 shipped to main (PR #1, #2, #3, #4, #5).

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
| MR-019 | Author buildless landing page (site/index.html) with dashboard tokens, static demo, CNAME | ui | P1 | sprint-05 |
| MR-020 | Publish to GitHub Pages — gh-pages pipeline, runbook, README URL (live at mdreview.waqasrana.space, HTTPS enforced) | infra | P1 | sprint-05 |
| MR-022 | KaTeX math render (marked-extension; binary `_read_bytes` + static content-types) | ui | P0 | sprint-06 |
| MR-023 | Per-review asset storage + manifest + `POST/GET /assets`, `GET /asset/{stored}` (base64) | svc | P0 | sprint-06 |
| MR-024 | MCP `attach_asset` + `list_assets` tools | svc | P0 | sprint-06 |
| MR-025 | Viewer rewrites local/relative/site-root `<img src>` to served asset URLs | ui | P0 | sprint-06 |
| MR-026 | Docs sweep: README API table, CLAUDE.md contract, AGENTS.md + MCP docstring (math + assets) | docs | P1 | sprint-06 |

## blocked

_none_

## backlog

| ID | Title | Layer | Pri | Sprint |
|----|-------|-------|-----|--------|
| MR-021 | Replace static demo with animated GIF of the review loop (drop-in) and re-publish | ui | P2 | — (next cycle) |

## Epics

| Epic | Status | Gate | Sprint |
|------|--------|------|--------|
| review-dashboard | done (merged to main 2026-06-08, PR #1) | G1 passed 2026-06-08 | sprint-01 |
| process-hardening | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-08 (2 rounds) | sprint-02 |
| process-hardening-2 | done (merged to main 2026-06-08, PR #2) | G1 passed 2026-06-09 (2 rounds) | sprint-03 |
| mcp-wrapper | done (merged to main 2026-06-09, PR #3) | G1 passed 2026-06-09 (2 rounds) | sprint-04 |
| landing-page | done (merged to main 2026-06-09, PR #4; live at mdreview.waqasrana.space; MR-021 GIF demo in backlog) | G1 passed 2026-06-09 (2 rounds) | sprint-05 |
| rich-rendering | done (merged to main 2026-06-18, PR #5) | G1 passed 2026-06-18 (2 rounds) | sprint-06 |
