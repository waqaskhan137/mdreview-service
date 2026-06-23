---
id: sprint-16
name: agent-handoff-baton — Chunk 3 (agent surface: MCP tools + contract)
status: active         # planning | active | closed
start: 2026-06-23
end: 2026-06-24
goal: Ship the agent-facing surface (MR-053) — hand_back + ping_working MCP tools over the /handoff route + the CLAUDE.md agent contract — completing the agent-handoff-baton epic (Chunks 1-3 all shipped).
close_review:          # reviews/sprint-16-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Land the **final chunk** of the agent-handoff-baton epic: give a looping agent a first-class way to
use the baton over MCP, and document the contract. `hand_back` (agent returns the turn) and
`ping_working` (claim/renew the lease) wrap the `POST /handoff` route MR-051 ships; the `CLAUDE.md`
note documents the find-work loop, the lease heartbeat, the blocked-via-comment-reply convention, and
the reconnect requirement. **Deliberately widened** (see MR-053 Work log) to keep the epic's docs
consistent at close: the tool count 18→20 across `README.md` / `AGENTS.md` / `CLAUDE.md` /
`docs/future-mcp.md` + `mcp_smoke.py`, and the `POST /handoff` route added to the README API table.
On close, the **epic is `done`** (all 3 chunks shipped on `dev`).

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-053 | Agent surface — `hand_back` + `ping_working` MCP tools + `CLAUDE.md` contract | svc | P2 | done |

## Preferred execution order

1. MR-053 — the MCP tools + contract (depends on MR-051, shipped in sprint-14).

## Notes / retro

_Filled in as the sprint runs and at close._

- Chunk 3 of 3 (final). Depends on MR-051 (`done`). Closing this sprint completes the epic.
- **Reconnect note:** adding tools to `mcp_server.py` changes `tools_hash`; a human/CI must reconnect
  the MCP client to pick up `hand_back`/`ping_working` (pure HTTP/render changes — MR-051/MR-052 —
  needed no reconnect). The `mcp_smoke.py` run against a fresh process exercises the new tools without
  a client reconnect.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] MR-053 is `done`;
- [ ] a **staff-critic sprint-close review** exists at `reviews/sprint-16-close-review-YYYY-MM-DD.md`,
      verifying MR-053 against its acceptance criteria, including the container rebuild + `curl
      /healthz` + `/api/reviews` smoke + a `mcp_smoke.py` run (no product page touched this sprint —
      `svc`/`docs` — so no per-page DOM assertion/screenshot is owed);
- [ ] retro + carry-overs recorded above, and `close_review:` set in frontmatter;
- [ ] on close, the `agent-handoff-baton` **epic** frontmatter is set `status: done`.
