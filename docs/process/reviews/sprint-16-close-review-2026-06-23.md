---
review_of: sprints/sprint-16.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: PASS
status: resolved
---

# Sprint-16 close review (G7) — agent-handoff-baton Chunk 3 (MR-053)

Independent G7 sprint-close review. The reviewer is not the implementer. This is the final chunk of
the `agent-handoff-baton` epic; on PASS the epic is `done`. Scope under review: MR-053 only
(`svc`/`docs`) — the `hand_back` + `ping_working` MCP tools over the `POST /handoff` route, the
`mcp_smoke.py` coverage, and the doc consolidation (tool count 18→20 + the `CLAUDE.md` agent
contract). No product page (`viewer.html`/`dashboard.html`/`static/**`) was touched, so per the G7
pass-condition this sprint owes the container/process smoke (`py_compile` + `curl /healthz` +
`/api/reviews` + an `mcp_smoke.py` run) but **not** a per-page DOM assertion or screenshot.

**Verdict: PASS.** Every MR-053 acceptance criterion is met in the code that shipped on `dev`
(commit `4496879`), and an independent smoke on a throwaway instance (port 8155) reproduces the
claimed behavior end to end, including the 409 foreign-owner back-off over both HTTP and the MCP
stdio transport. No blockers. The epic closes.

## AC verification (against shipped code, commit 4496879 on dev)

**AC-1 — `hand_back(document_id, message, state?)` → `POST /handoff {to:"reviewer", state, message}`,
state default `"done"`. PASS.**
`TOOLS` entry at `mcp_server.py:262-282` (adjacent to the comment tools); `route()` arm at
`mcp_server.py:450-452`:
`return "POST", "/api/reviews/%s/handoff" % args["document_id"], {"to": "reviewer", "state": args.get("state", "done"), "message": args["message"]}`.
The `state` default is `args.get("state", "done")` — correct. `message` is required in the input
schema; `state` is an enum `["done","blocked"]`.

**AC-2 — lease-ping tool named `ping_working` (NOT `take_turn`), → `POST /handoff
{state:"working", owner, message?}`, description states the 409 foreign-owner back-off. PASS.**
`TOOLS` entry at `mcp_server.py:283-302`; the name is `ping_working` (G1 NIT-2 honored — not
`take_turn`). `route()` arm at `mcp_server.py:453-457` builds `{"state":"working","owner":...}` and
only adds `message` when non-None. The description (`mcp_server.py:285-291`) states: "a review already
leased by a DIFFERENT owner returns an error (HTTP 409) — back off and skip it" and "Does NOT change
whose turn it is." `message` is optional (`required: ["document_id","owner"]`).

**AC-3 — `get_status` passthrough, no code change. PASS.**
`route()` arm at `mcp_server.py:406-407`: `return "GET", "/api/reviews/%s/status" % args["id"], None`
— unchanged, proxies `/status` verbatim. The new `turn`/`turn_updated`/`handoff`/`agent_status`
fields flow through with no code change (so the passthrough needs no reconnect; the two NEW tools
do). Confirmed live in the smoke: the e2e round-trip reads `turn`/`agent_status` straight off
`GET /status`.

**AC-4 — `mcp_smoke.py` covers exactly 20 tools, `tool_count == 20`, and a hand_back/ping_working
round-trip. PASS.**
`mcp_smoke.py:60-68` asserts `tools/list` equals the exact 20-name set (the expected set now includes
`hand_back`, `ping_working`); `mcp_smoke.py:128-129` asserts `server_info` `tool_count == 20`;
`mcp_smoke.py:161-189` drives `ping_working` (→ `agent_status.owner == "ci-agent"`, `isError` false)
then `hand_back` (→ `turn == "reviewer"`, `agent_status.state == "done"`, `isError` false). Two
description checks (`mcp_smoke.py:79-85`) assert `hand_back` mentions reviewer + done/blocked and
`ping_working` mentions a lease + 409/back-off.

**AC-5 — `CLAUDE.md` agent-contract note. PASS.**
The "The turn baton (working with the human live)" section (`CLAUDE.md:100-125`) documents all four
required pieces: the find-work loop (step 1: poll `list_reviews`/`get_status` for owned reviews with
`turn == "agent"`); the lease heartbeat (step 2: `ping_working` right away then periodically); the
blocked convention (step 3: `hand_back(state="blocked")` + a comment **reply**, "never `reopen`
(that's the reviewer's UI action, deliberately not an MCP tool)"); and the reconnect requirement
(`CLAUDE.md:123-125`).

**AC-6 — doc consistency: tool count 20 everywhere; README API table has the `POST /handoff` row.
PASS.**
Tool count is `20` in every live surface: `CLAUDE.md:178`, `README.md:148`, `AGENTS.md:89`,
`docs/future-mcp.md:49`, the in-code comment `mcp_server.py:66`, and `mcp_smoke.py:68`. `tool_count`
is computed (`len(TOOLS)`, `mcp_server.py:336`), not hardcoded, and `tools_hash` is derived over the
TOOLS schema + INSTRUCTIONS (`mcp_server.py:318-323`). A repo-wide grep found **no** stray "18 tools"
outside the historical `docs/process/` tickets. Both new tools are enumerated (not merely counted)
in `CLAUDE.md:182-183`, `README.md:154`, `AGENTS.md:93`. README API table:
`README.md:53` is the `POST /api/reviews/{id}/handoff` row with all four body forms; `README.md:52`
adds the new `/status` fields (`turn, turn_updated, handoff, agent_status`).

**AC-7 — scope: `mcp_server.py` + docs only; no Non-goal leak. PASS.**
`git show 4496879 --stat`: AGENTS.md, CLAUDE.md, README.md, docs/future-mcp.md,
docs/process/tickets/MR-053-*, mcp_server.py, mcp_smoke.py. **No `app.py`, no `viewer.html`.** Both
tools are thin wrappers onto the existing MR-051 route — no new server logic, no daemon, no new
storage file, no auth, no new dependency. No locked Non-goal is touched.

## Smoke transcript (independent, throwaway instance)

Environment: `MDREVIEW_DATA=$(mktemp -d) PORT=8155 python3 app.py` (NOT the live 8139 / compose
8137). Port 8155 verified free via `lsof -iTCP:8155 -sTCP:LISTEN` before launch and free again after
teardown.

```
$ python3 -m py_compile mcp_server.py mcp_smoke.py app.py
PY_COMPILE_OK

$ python3 mcp_server.py --print-version
{"version": "0.1.0", "tools_hash": "a97fb4f09e7c"}        # non-empty; matches the ticket's recorded value
# pre-MR-053 (4496879~1) tools_hash = f265447b5a8c  -> CHANGED (expected: two new tools; client reconnect required)

$ curl -s http://localhost:8155/healthz
{"ok": true}
$ curl -s http://localhost:8155/api/reviews   # -> reviews key present, count 0

$ MDREVIEW_BASE=http://localhost:8155 python3 mcp_smoke.py
... (44 assertions)
  ok   tools/list returns exactly the 20 tools
  ok   hand_back description: returns the turn to the reviewer (done/blocked)
  ok   ping_working description: a lease that backs off on a foreign owner (409)
  ok   server_info tool reports tool_count == 20 (local dispatch, no service touched)
  ok   three-way tools_hash identity (serverInfo == server_info tool == --print-version)
  ok   ping_working -> lease claimed (agent_status.owner set), isError false
  ok   hand_back -> turn=reviewer, agent_status.state=done, isError false
PASS: all MCP smoke assertions hold
EXIT_CODE=0

# Independent end-to-end baton drive (HTTP):
1. initial:           turn=reviewer  agent_status=None          # legacy default path
2. {to:agent}:        turn=agent
3. ping_working A:    agent_status.owner=sess-A  state=working
4. foreign owner B:   HTTP=409  body={"error":"lease held","owner":"sess-A"}   owner still=sess-A
5. hand_back done:    turn=reviewer  agent_status.state=done
6. GET /api/reviews:  turns in list: ['reviewer']               # turn flows through the list endpoint

# Independent end-to-end over the MCP stdio transport (foreign-owner ping_working):
  isError= True
  text= HTTP 409 from POST /api/reviews/ab1dc424a4/handoff: {"error": "lease held", "owner": "owner-1"}
  # -> the 409 surfaces as a ToolError the agent treats as "skip this review" (AC-2, confirmed end to end)

# Teardown: kill <pid>; port 8155 free; temp data dir removed.
```

## Findings

No BLOCKER. No SHOULD. Two NITs, neither gating:

- **NIT-1 (doc nicety, non-gating).** The `ping_working` round-trip in `mcp_smoke.py:161-175` does not
  also assert the 409 foreign-owner back-off through the MCP tool path; that case is exercised only by
  the MR-051 HTTP smoke and (now) by this review's independent stdio drive. The smoke proves the happy
  path and the descriptions; the back-off is structurally guaranteed by `http()` raising `ToolError`
  on non-2xx (`mcp_server.py:342-344`). Worth a one-line addition next time the smoke is touched, not
  worth a revision.
- **NIT-2 (process, non-gating).** The deliberate scope-widening to the docs is well recorded in the
  MR-053 Work log (per the blocking rule) and the sprint goal, so this is not a phantom — noting only
  that the widen pulled four doc files into a `svc`-tagged ticket. The DoD permits same-change doc
  updates, so this is compliant; flagged purely for visibility.

## Resolution log

- `2026-06-23` — Independent G7 review complete. All seven MR-053 ACs verified against shipped code
  (`4496879`). Independent smoke on throwaway port 8155: `py_compile` OK; `mcp_smoke.py` 44/44, exit
  0 (20 tools, `tool_count == 20`, three-way `tools_hash` identity, baton round-trip); `--print-version`
  `tools_hash a97fb4f09e7c` (changed vs pre-053 `f265447b5a8c`, reconnect required for the new tools);
  `/healthz` + `/api/reviews` respond; e2e baton drive over HTTP and MCP stdio confirms the 409
  foreign-owner back-off and the `turn` flips. No blockers; two non-gating NITs recorded. **Verdict
  PASS; status resolved.** Sprint-16 may close and the `agent-handoff-baton` epic is `done`.
