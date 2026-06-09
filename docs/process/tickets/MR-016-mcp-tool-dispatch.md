---
id: MR-016
title: tools/call dispatch → HTTP (8 tools, provenance pass-through, error mapping)
status: done
layer: svc
priority: P1
sprint: sprint-04
epic: mcp-wrapper
depends_on: [MR-015]
branch: dev (mcp_server.py)
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Implement `tools/call`: map each tool name + args onto its `urllib` request against
`MDREVIEW_BASE` (default `http://localhost:8137`), relay the HTTP response as a `tools/call`
result, with a clean protocol-vs-tool error split. Requires a running service.

## Acceptance criteria

- [ ] **Service unchanged:** same base-relative empty-diff check as MR-015.
- [ ] **Happy-path envelope (pinned):** a successful call returns
      `{content:[{type:"text", text:<json-string of the HTTP body>}]}` (no `isError` / `isError:false`).
      Harness asserts `content[0].type == "text"` and `content[0].text` parses as JSON.
- [ ] **Tool error → result, not protocol error:** a service `404` / connection-refused / any
      non-2xx returns `{content:[{type:"text", text:<detail>}], isError:true}` — a normal result,
      stream stays valid.
- [ ] **Unknown tool name → JSON-RPC `error` `-32602`** (invalid params), NOT an `isError` result.
      Smoke asserts `code == -32602`.
- [ ] **Provenance pass-through:** `create_review` forwards `project`/`session`/`source_path`
      verbatim; omitting them behaves as today (optional service fields, `app.py:228-230`).
- [ ] All 8 tools dispatch to the correct verb/endpoint per the plan's tool table; `get_history`
      selects `/history` vs `/history/{round}` by the optional `round` arg.
- [ ] Local validation: `python3 -m py_compile mcp_server.py`; against a running container, a
      `create_review` → `update_source` round-trip returns sane results.

## Notes / context

Plan: `epics/mcp-wrapper-plan.md` (Tool surface table with `app.py` anchors; Per-ticket AC — MR-016).

## Work log

- `2026-06-09` — `mcp_server.py`: added `tools/call` dispatch. A `urllib` client (`http()`) calls
  `MDREVIEW_BASE`; `route()` maps each of the 8 tools to verb+path+body (create_review passes
  provenance through; get_history selects list vs `/history/{round}` by the optional `round`).
  Success -> `{content:[{type:text,text:<body>}], isError:false}`; any non-2xx / unreachable ->
  `isError:true` result (stream stays valid); unknown tool name -> JSON-RPC `-32602`; missing
  required arg -> `-32602`. No app.py/UI/Docker change.

## Validation

- `2026-06-09` — `py_compile` OK. Against the running container (`MDREVIEW_BASE=:8137`), driving the
  server over stdio: `create_review` -> id + review_url (isError:false); `update_source` -> revision
  1; `get_history` -> rounds [0]; `get_review` bad id -> isError:true with "HTTP 404"; unknown tool
  -> JSON-RPC error `-32602`. Service-unchanged diff empty.

## Follow-ups

None.
