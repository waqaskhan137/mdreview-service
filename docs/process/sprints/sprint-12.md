---
id: sprint-12
name: mcp-agent-effectiveness
status: closed
start: 2026-06-19
end: 2026-06-19
goal: Make the mdreview MCP self-serve for agents and PROVE it — a code-derived staleness signal (tools_hash + server_info + --print-version), a stdlib agent-loop render-proof harness, discoverability locked under test, and the two already-shipped viewer fixes retro-ticketed.
close_review: reviews/sprint-12-close-review-2026-06-19.md
---

## Goal

By the end of the sprint a stale MCP server is **detectable** (the `server_info` tool surfaces the
running wrapper's `tools_hash`/version; a human/CI compares it to `--print-version`; remedy =
reconnect), and the canonical image-embed loop is **proven to render unaided** by `agent_smoke.py`
(create → reference image → `attach_asset(path=…)` → asset served → `<img>` repointed → `naturalWidth>0`)
— no operator curl. Discoverability stays load-bearing under test. The two viewer fixes already shipped
this session (table CSS, lightbox) are retro-ticketed so the board is honest. No `app.py`/viewer code
change beyond what already shipped.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-038 | Retro: GFM table CSS in the viewer (done-on-arrival, `dae815e`) | ui | P2 | done |
| MR-039 | Retro: click-to-zoom lightbox in the viewer (done-on-arrival, `2ed9593`) | ui | P2 | done |
| MR-040 | MCP staleness signal — `tools_hash` + `server_info` tool + `--print-version` | svc | P1 | done |
| MR-041 | `agent_smoke.py` — agent-loop render-proof (create→path-attach→repoint→naturalWidth>0) | svc | P1 | done |
| MR-042 | `mcp_smoke.py` — assert `server_info` + the discoverability contract | svc | P1 | done |
| MR-043 | Docs sweep — `server_info`/16-tool count + reconnect-on-stale guidance | docs | P2 | done |

## Preferred execution order

1. **MR-038 / MR-039** — already `done`; reconcile the board first (honest tracker before new work).
2. **MR-040** — `tools_hash` + `server_info` + `--print-version` (foundation; Phases 2–3 assert it).
3. **MR-041** — `agent_smoke.py` (the headline render-proof). Depends on MR-040.
4. **MR-042** — `mcp_smoke.py` discoverability + `server_info` assertions. Depends on MR-040.
5. **MR-043** — docs sweep (must close in-sprint; not carry-over-eligible). Depends on MR-040.

## Notes / retro

- `2026-06-19` — **Closed at G7 (staff-critic PASS, 0 BLOCKER/0 SHOULD/1 NIT accepted-no-change).**
  The process critique landed structurally: the headline `agent_smoke.py` proves the agent loop renders
  unaided (create → `attach_asset(path=…)` → asset served → `<img>` repointed → `naturalWidth>0`, zero
  human curl, exit 0), and a stale MCP server is now *detectable* (`server_info` surfaces the running
  `tools_hash`; a human/CI compares to `--print-version`; remedy = reconnect). The critic independently
  re-ran both harnesses: `agent_smoke` PASS, `mcp_smoke` 34/34, `server_info` local with `BASE` on a
  dead port, three-way hash identity `e6843ee24b2c`, `app.py` untouched.
- **G1 conditions confirmed shipped:** honest staleness scoping (no surface claims the agent
  self-detects — the only "self-detect" string is a negation); the Node built-in-`WebSocket` CDP render
  check (no bespoke RFC6455 client).
- **Carry-overs:** none. The two retro-tickets (MR-038/039) documented already-merged commits
  (`dae815e`/`2ed9593`); the critic verified the `viewer.html` delta is exactly those, not new work.
- **Backlog/non-goal spun off:** option (b) — the HTTP service publishing the *expected* wrapper hash
  as an MCP-reachable comparand so an agent could self-detect — named a future option, not built.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-038–043 all `done`;
      no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-12-close-review-2026-06-19.md`, verifying shipped work against each ticket's
      acceptance criteria, **including `agent_smoke.py` PASS** + a render-smoke of `viewer.html` — **PASS**,
      1 NIT accepted-no-change;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
