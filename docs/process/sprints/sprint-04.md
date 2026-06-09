---
id: sprint-04
name: MCP wrapper
status: closed
start: 2026-06-09
end: 2026-06-16
goal: Ship a stdlib stdio MCP server wrapping the HTTP API (MR-015..018), with the HTTP service unchanged.
close_review: reviews/sprint-04-close-review-2026-06-09.md
---

## Goal

Deliver the `mcp-wrapper` epic: a new standalone `mcp_server.py` (stdlib JSON-RPC over stdio)
exposing the 8 review tools, a stdlib smoke harness, and docs — without changing `app.py` or any
product page. Success: an MCP client can `initialize`, `tools/list` the 8 tools, and round-trip
`create_review` → `update_source` against a running container.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-015 | mcp_server.py — stdio JSON-RPC core (initialize/tools-list) | svc | P1 | done |
| MR-016 | tools/call dispatch → HTTP (8 tools, error mapping) | svc | P1 | done |
| MR-017 | mcp_smoke.py — stdlib smoke harness + container round-trip | svc | P1 | done |
| MR-018 | Docs — wrapper in README/AGENTS, future-mcp.md to shipped | docs | P2 | done |

## Preferred execution order

1. MR-015 — protocol core (no service needed; proves the surface in isolation)
2. MR-016 — tool dispatch → HTTP (depends MR-015; needs a running container)
3. MR-017 — smoke harness (depends MR-016; becomes the close evidence)
4. MR-018 — docs sweep (depends MR-015..017; docs-sweep ticket, ineligible for carry-over)

## Notes / retro

- All 4 tickets `done`, no carry-overs. First product-code sprint: shipped `mcp_server.py` +
  `mcp_smoke.py` (stdlib MCP wrapper) + docs, with the HTTP service provably unchanged.
- **The hardened gates paid off on real code:** G1 caught the planner violating its own MR-012 rule
  (service-unchanged enforced in prose, not a ticket AC); G7 independently re-ran the diff and the
  spec cross-check and reproduced the smoke. Verdict PASS (only 2 cosmetic NITs, both fixed).
- **Dogfooded + extended the pre-G7 rail:** it reconciled the board AND ran+recorded the
  unconditional smoke (process-hardening-2 retro suggestion 1) — see
  `reviews/sprint-04-render-evidence-2026-06-09/smoke.txt`.
- **Carry-overs:** none.

## Close gate (G7)

- [x] every committed ticket is `done` (MR-018 is a docs-sweep ticket — NOT eligible for
      carry-over; must be `done` before close);
- [x] an independent `staff-critic` close review at `reviews/sprint-04-close-review-YYYY-MM-DD.md`
      verifies shipped work against each ticket's AC. No product page is touched, so per the G7
      pass-condition row the per-page render-smoke/screenshot are not owed — but the
      **unconditional** rebuild + `curl /healthz` + `/api/reviews` smoke IS owed and must be run +
      recorded (carrying process-hardening-2 retro suggestion 1). The wrapper's own evidence is the
      `mcp_smoke.py` run output;
- [x] retro + carry-overs recorded, `close_review:` set.

## Carry-over note

Per `requirements/mcp-wrapper.md`, this sprint's close applies process-hardening-2 retro
suggestion 1: the pre-G7 board rail must **run + record the unconditional smoke** (not just
reconcile the board). Done at close; consider grooming the rail change into the process backlog.
