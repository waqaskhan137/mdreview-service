---
id: MR-024
title: MCP attach_asset + list_assets tools
status: done
layer: svc
priority: P0
sprint: sprint-06
epic: rich-rendering
depends_on: [MR-023]
branch: dev
created: 2026-06-18
updated: 2026-06-18
---

## Goal

An agent driving mdreview **over MCP** can attach and list a review's assets without leaving the
protocol or rewriting the draft. Surfaces the MR-023 HTTP capability as two MCP tools, in the
existing thin-wrapper style (no new state). This is what makes "serve local images" usable from the
MCP path the brief was driven through.

## Acceptance criteria

- [x] **`attach_asset`** tool: args `{id (req), name (req), content_b64 (req)}` → maps to
      `POST /api/reviews/{id}/assets`, returns the asset JSON (`name`, `stored`, `url`, `bytes`,
      `ctype`). **No `path` arg** (the server-side local-read form is cut — S5). The tool
      description states base64 is the transport and that attaching under the exact draft `src`
      string lets the viewer match it.
- [x] **`list_assets`** tool: args `{id (req)}` → maps to `GET /api/reviews/{id}/assets`, returns
      `{assets:[...]}`.
- [x] Both are added to the `TOOLS` schema and the `route()`/dispatch mapping the same way the
      existing tools are (`create_review`, `get_feedback`, `update_source`, …) — name → (method,
      path, body), no new state in `mcp_server.py`.
- [x] The `mcp_server.py` module docstring tool list is updated to include the two new tools.
- [x] **GATING (mcp_smoke):** `mcp_smoke.py` (extended if it enumerates tools) shows `tools/list`
      includes `attach_asset` + `list_assets`; `tools/call attach_asset {id,name,content_b64}`
      returns the asset JSON (with `stored` + `url`); `tools/call list_assets {id}` lists it.
- [x] Local validation passes: `python3 -m py_compile app.py` **and**
      `python3 -m py_compile mcp_server.py`; `python3 mcp_smoke.py` (against a running service) green.

## Notes / context

- Epic plan: `epics/rich-rendering-plan.md` — MCP section, Verification (MR-024 block). Two tools,
  not a `register_asset_dir` (dir registration was the cut `path` form, S5).
- Mirror the existing tool wiring in `mcp_server.py` (TOOLS schema entry + dispatch branch) and the
  smoke style in `mcp_smoke.py`. The brief's shape was `attach_asset(review_id, bytes|path, name)`;
  we ship `bytes` (base64) only.
- Depends on MR-023 (the HTTP endpoints it wraps must exist).

## Work log

- `2026-06-18` — **mcp_server.py:** added two `TOOLS` entries — `attach_asset {id, name,
  content_b64}` and `list_assets {id}` — and the matching `route()` branches (`POST
  /api/reviews/{id}/assets` with `{name, content_b64}`; `GET /api/reviews/{id}/assets`). No `path`
  arg (S5 cut). Updated the module docstring (`...10 schemas`) and the `# The 10 tools` comment.
  No new state — thin 1:1 wrapper, same style as the existing 8 tools.
- `2026-06-18` — **mcp_smoke.py:** expanded the expected tool set to 10 (added `attach_asset`,
  `list_assets`) and the label; added an `attach_asset` → `list_assets` round-trip (attach a 1×1
  PNG, assert the returned `stored` is present, then assert `list_assets` includes it).
- Files: `mcp_server.py`, `mcp_smoke.py`.

## Validation

- `2026-06-18` — `python3 -m py_compile app.py mcp_server.py mcp_smoke.py` OK.
- `2026-06-18` — `MDREVIEW_BASE=http://localhost:8138 python3 mcp_smoke.py` against the rebuilt
  container: **all 13 assertions PASS**, including "tools/list returns exactly the 10 tools",
  "attach_asset -> stored sha1+ext, isError false", and "list_assets -> includes the attached
  asset's stored name".

## Follow-ups

- `path` arg on `attach_asset` — deferred with the cut local-read form (S5).
