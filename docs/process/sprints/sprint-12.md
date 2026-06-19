---
id: sprint-12
name: mcp-agent-effectiveness
status: active
start: 2026-06-19
end: 2026-06-19
goal: Make the mdreview MCP self-serve for agents and PROVE it — a code-derived staleness signal (tools_hash + server_info + --print-version), a stdlib agent-loop render-proof harness, discoverability locked under test, and the two already-shipped viewer fixes retro-ticketed.
close_review:
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
| MR-040 | MCP staleness signal — `tools_hash` + `server_info` tool + `--print-version` | svc | P1 | ready |
| MR-041 | `agent_smoke.py` — agent-loop render-proof (create→path-attach→repoint→naturalWidth>0) | svc | P1 | ready |
| MR-042 | `mcp_smoke.py` — assert `server_info` + the discoverability contract | svc | P1 | ready |
| MR-043 | Docs sweep — `server_info`/16-tool count + reconnect-on-stale guidance | docs | P2 | ready |

## Preferred execution order

1. **MR-038 / MR-039** — already `done`; reconcile the board first (honest tracker before new work).
2. **MR-040** — `tools_hash` + `server_info` + `--print-version` (foundation; Phases 2–3 assert it).
3. **MR-041** — `agent_smoke.py` (the headline render-proof). Depends on MR-040.
4. **MR-042** — `mcp_smoke.py` discoverability + `server_info` assertions. Depends on MR-040.
5. **MR-043** — docs sweep (must close in-sprint; not carry-over-eligible). Depends on MR-040.

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-12-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      acceptance criteria, **including `agent_smoke.py` PASS** (the epic's headline proof) and a
      render-smoke of `viewer.html` (the retro-tickets), and its findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
