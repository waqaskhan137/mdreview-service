# TRACKER — the board

At-a-glance view of every ticket grouped by status. The ticket frontmatter is the source of
truth; move a row here whenever a ticket's `status` changes.

Last updated: 2026-06-19. **sprint-12 (mcp-agent-effectiveness) CLOSED at G7 (staff-critic PASS, 0 BLOCKER/0 SHOULD/1 NIT)** — the MCP is now provably self-serve: `agent_smoke.py` drives the wrapper as an agent and proves create → `attach_asset(path=…)` → `<img>` renders (`naturalWidth>0`) with zero human curl, and a stale server is detectable (`server_info` `tools_hash` + `--print-version` + reconnect). G1 passed 2 rounds. **Awaiting the standing dev→main PR.** **sprint-11 (comment-resolution) + sprint-10 (dashboard) merged to main via PR #9.** sprint-09 (dashboard-redesign) merged to main (PR #8). sprint-08 (render-fidelity) merged to main (PR #7). sprint-07 (theme-awareness) merged to main (PR #6). sprint-06 (rich-rendering) merged to main (PR #5). sprint-05 (landing-page) merged to main (PR #4); page LIVE at https://mdreview.waqasrana.space/ (HTTPS enforced).

## Active sprint

_none active_ — **sprint-12 (mcp-agent-effectiveness) closed at G7** (staff-critic PASS,
`reviews/sprint-12-close-review-2026-06-19.md`). All 6 tickets `done` on `dev`; no carry-overs.
The headline `agent_smoke.py` proves the agent loop renders unaided. Pending the standing
`dev → main` PR (G8).

_(sprint-11 comment-resolution + sprint-10 dashboard already merged to main via PR #9.)_

**sprint-10 — dashboard-density** (`closed` out-of-cycle, 2026-06-19). Epic: `dashboard-density` (G1 passed 2 rounds; **G7 waived by user exception**). Shipped MR-032's density CSS **within a direct flat continuous-grid redesign** (commit `0f44c1b`): one packed grid (newest-first, project-as-inline-tag, zero gutters) is now the default, with a "Group by project" toggle to the grouped sections (which keep the MR-032 density). `dashboard.html` only. Render-validated via CDP; not independently G7-reviewed.

**sprint-09 — dashboard-redesign** (`closed`, 2026-06-19; merged to main, PR #8). Epic: `dashboard-redesign` (G1 passed 2 rounds; G7 PASS). Shipped MR-031: `dashboard.html` rewritten into a dense, full-width (capped 1600px), searchable grid of collapsed click-to-expand cards with collapsible project groups; open/delete/version/notes + pane-adaptive theme preserved (CDP-verified). `dashboard.html` only.

**sprint-08 — render-fidelity** (`closed`, 2026-06-18; merged to main, PR #7). Epic: `render-fidelity` (G1 passed 2 rounds; G7 PASS-WITH-CONDITIONS, resolved). Shipped MR-028 (GFM footnotes, vendored marked-footnote), MR-029 (syntax highlighting, vendored highlight.js common + marked-highlight, dual-scheme theme, mermaid skipped), MR-030 (docs). Viewer + vendored `static/` only.

**sprint-07 — theme-awareness** (`closed`, 2026-06-18; merged to main, PR #6). Epic: `theme-awareness` (G1 passed 2 rounds; G7 PASS). Shipped MR-027: a near-white mat behind `#article img` + `.histdoc img` so light-authored figures stay legible on a dark review pane (excludes mermaid/katex; CSS-only). Inverse case (dark-authored/white-on-transparent figures) is an accepted non-goal (luminance heuristic backlog).

**sprint-06 — rich-rendering** (`closed`, 2026-06-18; merged to main, PR #5). Epic: `rich-rendering` (G1 passed 2 rounds; G7 PASS). Shipped the two P0s: math rendering (KaTeX marked-extension) + per-review asset attach/serve over HTTP & MCP + viewer `<img>` rewrite. MR-022–026 all `done`; local-dir `path` read form cut to backlog (S5).

**sprint-05 — landing-page** (`closed`, 2026-06-09; merged to main, PR #4). Epic: `landing-page`. G7 PASS; MR-019 done, MR-020 done (carry-over discharged: DNS added, cert issued, HTTPS enforced, README URL recorded). MR-021 (GIF demo) remains backlog.
sprint-01/02/03/04/05/06/07/08/09 shipped to main (PR #1, #2, #3, #4, #5, #6, #7, #8).

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
| MR-027 | Viewer — neutral light mat behind `#article img` + `.histdoc img` (theme-safe images) | ui | P1 | sprint-07 |
| MR-028 | GFM footnotes in the viewer (vendored marked-footnote; refs + back-ref section) | ui | P2 | sprint-08 |
| MR-029 | Syntax highlighting in the viewer (vendored highlight.js + marked-highlight; dual-scheme, skips mermaid) | ui | P2 | sprint-08 |
| MR-030 | Docs — footnotes + syntax highlighting render in the viewer | docs | P2 | sprint-08 |
| MR-031 | Redesign `dashboard.html` — dense grid, collapsible cards, sticky search, collapsible groups (preserve open/delete/version/notes) | ui | P1 | sprint-09 |
| MR-032 | Dashboard density → shipped within a direct flat continuous-grid redesign + group-by toggle (out-of-cycle; G7 waived) | ui | P1 | sprint-10 |
| MR-033 | Comment store (`comments.json`) + `POST/GET /comments` + `GET /comments/{cid}` + `comments_updated` + comment-aware `GET /feedback`/`summary()` | svc | P1 | sprint-11 |
| MR-034 | Comment state machine — reply/resolve/reopen routes, `status_history`, 409 on illegal transitions | svc | P1 | sprint-11 |
| MR-035 | MCP tools `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` + descriptions + `mcp_smoke` round-trip (14 tools) | svc | P1 | sprint-11 |
| MR-036 | Viewer — threaded `comment_id`-keyed gutter cards, authoring → `POST /comments`, retire legacy author surfaces, Resolved panel + reopen, live-reload | ui | P1 | sprint-11 |
| MR-037 | Docs sweep — README/CLAUDE/AGENTS/future-mcp + MCP docstring 10→14 + comment-aware feedback/dashboard | docs | P2 | sprint-11 |
| MR-038 | Retro: GFM table CSS in the viewer (done-on-arrival, `dae815e`) | ui | P2 | sprint-12 |
| MR-039 | Retro: click-to-zoom lightbox in the viewer (done-on-arrival, `2ed9593`) | ui | P2 | sprint-12 |
| MR-040 | MCP staleness signal — `tools_hash` + `server_info` tool + `--print-version` | svc | P1 | sprint-12 |
| MR-041 | `agent_smoke.py` — agent-loop render-proof (create→path-attach→repoint→naturalWidth>0) | svc | P1 | sprint-12 |
| MR-042 | `mcp_smoke.py` — assert `server_info` + the discoverability contract | svc | P1 | sprint-12 |
| MR-043 | Docs sweep — `server_info`/16-tool count + reconnect-on-stale guidance | docs | P2 | sprint-12 |
| MR-044 | `create_comment` MCP tool + viewer anchor-by-quoted-text (agents author review comments; 17 tools) | svc | P1 | — (out-of-cycle) |

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
| theme-awareness | done (merged to main 2026-06-18, PR #6) | G1 passed 2026-06-18 (2 rounds) | sprint-07 |
| render-fidelity | done (merged to main 2026-06-18, PR #7) | G1 passed 2026-06-18 (2 rounds) | sprint-08 |
| dashboard-redesign | done (merged to main 2026-06-19, PR #8) | G1 passed 2026-06-19 (2 rounds) | sprint-09 |
| dashboard-density | active (G1 cleared; MR-032 ready) | G1 passed 2026-06-19 (2 rounds) | sprint-10 |
| comment-resolution | done (merged to main 2026-06-19, PR #9) | G1 passed 2026-06-19 (2 rounds) | sprint-11 |
| mcp-agent-effectiveness | done on `dev` (G7 PASS; pending dev→main PR) | G1 passed 2026-06-19 (2 rounds) | sprint-12 |
