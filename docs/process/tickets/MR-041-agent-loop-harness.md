---
id: MR-041
title: "agent_smoke.py — agent-loop render-proof (create→path-attach→repoint→naturalWidth>0)"
status: done
layer: svc
priority: P1
sprint: sprint-12
epic: mcp-agent-effectiveness
depends_on: [MR-040]
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

The headline proof the MCP is self-serve: a stdlib harness that drives `mcp_server.py` over stdio **as
an agent would** and proves the canonical image-embed loop **renders** with zero human curl — turning
"an operator attached it by hand" into a repeatable gate.

## Acceptance criteria

- [ ] **New sibling `agent_smoke.py`** (not bolted onto the fast `mcp_smoke.py`). Drives stdio
      initialize → `create_review` (markdown referencing `/assets/<fig>.png`) → write a real PNG to a
      temp file → `attach_asset(id, name="/assets/<fig>.png", path=<tmp>)` (exercises the **path** branch,
      no base64 in context) → assert `stored` returned, `isError` false → `delete_review` cleanup.
- [ ] **Layer (i) always-on gate (stdlib only, no Chrome/Node):** `GET {base}/api/reviews/{id}/asset/
      {stored}` via `urllib` → `200` + `Content-Type` starts `image/` (header-dump, never `curl -sI`);
      **and** headless Chrome `--dump-dom` of `/review/{id}` + stdlib HTML parse → the rendered `<img src>`
      is the served asset URL (the **repoint** proof).
- [ ] **Layer (ii) render proof ("a 200 is not a render"):** the `<img>` actually **loaded**
      (`naturalWidth > 0`) AND `src == {asset url}` — via the repo's **Node built-in-`WebSocket` CDP**
      pattern (`Runtime.evaluate` of `naturalWidth` on `#article img`). **No bespoke stdlib RFC6455 WS
      client** (SHOULD-2).
- [ ] **Fail-loud skip.** If **Chrome OR Node** is absent, layer (ii) prints `SKIPPED` and exits with a
      distinct non-pass code (3, matching `render-smoke.sh`); layer (i) still ran. Never a silent pass.
      Exit `0` all pass; `1` real failure (asset not served / not repointed / not loaded).
- [ ] Calls `server_info`, prints the proved `tools_hash`, asserts the 16-tool count.
- [ ] Local validation: `python3 -m py_compile agent_smoke.py`; `MDREVIEW_BASE=<throwaway> python3
      agent_smoke.py` → PASS (Chrome+Node present) on a non-:8139 throwaway container.

## Notes / context

- Epic: `epics/mcp-agent-effectiveness-plan.md` — Decision 2, Verification → MR-041 (the measured
  sequence: `stored`/`url`, asset 200 `image/png`, `--dump-dom` repoint, CDP `naturalWidth=1`).
- Reuse `mcp_smoke.py`'s `drive()` stdio pattern + the repo's Node-CDP pattern (sprint-09
  render-evidence README; sprint-11 close). Launch Chrome with the URL as argv; pick the `type=="page"`
  target from `GET /json` (`/json/new?url=` is disabled in new headless).
- Depends on MR-040 (asserts `server_info` / the 16-tool count).

## Work log

- `2026-06-19` — new `agent_smoke.py` (stdlib). Drives `mcp_server.py` over stdio (`drive()`/`call()`):
  `server_info` → `create_review` (markdown referencing `/assets/plot.png`) → write a real 1×1 PNG to a
  temp file → `attach_asset(path=…)` (the path branch, no base64 in context) → `delete_review` cleanup.
  Layer (i) stdlib gate: asset `200`+`image/*` (urllib) + `<img>` repoint via headless `--dump-dom` +
  `html.parser`. Layer (ii) render proof: `naturalWidth>0` via an embedded **Node built-in-`WebSocket`
  CDP** check (`node_render`), gated by `node_with_websocket()` (Node ≥21 global WebSocket) +
  `find_chrome()`; **fail-loud skip exit 3** if Chrome or Node absent. No bespoke WS client.

## Validation

- `2026-06-19` — `python3 -m py_compile agent_smoke.py` OK. Against a throwaway `:8155` container:
  **PASS (exit 0)** — `server_info` 16 tools `tools_hash=e6843ee24b2c`; create → path-attach → asset
  `200 image/png` → `<img>` repointed (`--dump-dom`) → **`#article img naturalWidth>0` (nw=1) AND
  src==asset**. Zero human curl. **Fail-loud skip verified:** with Node hidden (`PATH=/usr/bin:/bin`),
  the gate still passes, the render half prints `SKIPPED`, exit **3** (never a silent pass).

## Follow-ups

- Pure-no-Node fallback (if ever mandated): `--dump-dom` repoint gate + a manual G7 `naturalWidth`
  spot-check — never a new WS client.
