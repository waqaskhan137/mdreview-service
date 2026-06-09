---
id: MR-018
title: Docs — MCP wrapper in README/AGENTS, future-mcp.md to shipped, client config + exposure
status: done
layer: docs
priority: P2
sprint: sprint-04
epic: mcp-wrapper
depends_on: [MR-015, MR-016, MR-017]
branch: dev (docs)
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Document the shipped wrapper so an agent operator can run and wire it up.

## Acceptance criteria

- [ ] **Service unchanged** for `app.py`/UI/Docker (this is a `docs` ticket; it may edit
      `README.md`/`AGENTS.md`/`docs/future-mcp.md`, not product code).
- [ ] `README.md` + `AGENTS.md`: how to run (`MDREVIEW_BASE=… python3 mcp_server.py`), the 8 tools,
      an example MCP client config (e.g. a `mcpServers` stdio entry), and the `list_reviews`/`/`
      cross-review exposure note (trusted-network posture).
- [ ] `docs/future-mcp.md` updated from "**not built**" to **shipped**, pointing at `mcp_server.py`
      + `mcp_smoke.py`; the deferred-sketch framing replaced with the real run/usage.
- [ ] **`MDREVIEW_PUBLIC_BASE` guidance:** instruct operators to set `MDREVIEW_PUBLIC_BASE` on the
      **service** to a host reachable by whoever the agent hands the `review_url` to (else the
      returned URL is a `Host`-derived `localhost`/internal host — `app.py:34`, `app.py:177-179`).
- [ ] Local validation: read-diff; docs match the shipped tool names + run command.

## Notes / context

Plan: `epics/mcp-wrapper-plan.md` (Phase 4; Per-ticket AC — MR-018). DoD allows this trailing docs
sweep within the sprint (the deferring code tickets name it here); G7 will not pass with it
undone (it is not eligible for carry-over).

## Work log

- `2026-06-09` — `README.md`: new "MCP server (optional)" section — run command, `mcp_smoke.py`,
  an example `mcpServers` stdio client config, the 8 tools, the `isError`/`-32602` behavior, the
  `MDREVIEW_PUBLIC_BASE`-for-reachable-`review_url` guidance, and the `list_reviews` exposure note.
  `AGENTS.md` + `CLAUDE.md`: a "Calling it over MCP" section. `docs/future-mcp.md`: flipped from
  "not built" to **SHIPPED**, pointing at `mcp_server.py`/`mcp_smoke.py`.

## Validation

- `2026-06-09` — read-diff. README covers run/config/tools/public_base/exposure; AGENTS + CLAUDE
  carry the MCP section; future-mcp marked SHIPPED. Service-unchanged diff (app.py/UI/Docker/compose)
  empty — only docs touched.

## Follow-ups

None.
