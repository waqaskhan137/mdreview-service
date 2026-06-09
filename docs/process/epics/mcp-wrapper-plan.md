---
epic: mcp-wrapper
status: active
created: 2026-06-09
source: requirements/mcp-wrapper.md
gate: passed 2026-06-09
review: reviews/mcp-wrapper-plan-review-2026-06-09.md
related_sprints: [sprint-04]
related_tickets: [MR-015, MR-016, MR-017, MR-018]
---

# MCP wrapper for mdreview-service

mdreview-service is already a small, stable HTTP API. This epic adds a thin **stdio MCP server**
(`mcp_server.py`) that exposes the existing endpoints as first-class MCP tools, so an agent runtime
that speaks MCP can call the review service with schemas and discovery instead of hand-rolling
`curl`/HTTP. The wrapper is a **separate process** that proxies HTTP and holds no state of its own.
This is the first epic in this repo that ships running code through the hardened gates; the
overriding rule is that the HTTP service's behavior does **not** change.

**Source requirement:** [`requirements/mcp-wrapper.md`](../requirements/mcp-wrapper.md) — the
original ask, kept verbatim. Design input: [`docs/future-mcp.md`](../../future-mcp.md) (sketched in
MR-007).

## Product goal

An agent runtime configures one MCP server. It then discovers 8 tools
(`create_review`, `list_reviews`, `get_review`, `get_feedback`, `get_status`, `update_source`,
`get_history`, `delete_review`) and round-trips a real review — create a draft, hand the human the
URL, poll status, read feedback, push applied edits — entirely through tool calls. Provenance
(`project`/`session`/`source_path`) flows through `create_review` unchanged. The running HTTP
service and its on-disk storage are byte-for-byte unaffected; the wrapper is additive and optional.

## Core design principle

**Thin proxy; the HTTP service is the source of truth.** The MCP server adds protocol framing and
tool schemas and does nothing else: every `tools/call` is a single HTTP request to an existing
endpoint, and the HTTP response (or error) is relayed back. It re-implements **no** review logic,
holds **no** state, and touches **no** file the service owns. It is a standalone script run on the
agent host, never baked into the service image — which is what makes "the HTTP service stays
exactly as it is" provably true and keeps the **stdlib-only / zero-pip** posture intact on both
sides (`urllib.request` + `json` are stdlib; MCP framing is hand-written, no SDK).

## Recommended approach

### Service (`app.py`)
- **No change.** `app.py`, `viewer.html`, `dashboard.html`, `static/**`, `Dockerfile`, and
  `docker-compose.yml` are untouched by this epic. The wrapper is a new sibling component, not an
  edit to the service. This is the load-bearing non-goal, restated under Non-goals and Key
  constraints and enforced by the per-ticket base-relative `git diff` AC.

### New component — `mcp_server.py` (layer: `svc`, separate process)

A new file at repo root. It is `svc`-adjacent (it is server code that speaks a protocol) but runs as
its **own process on the agent host**, not inside the service container. We tag its tickets `svc`
because the layer table has no closer fit and the work is server-side Python; the plan flags the
"separate process / not in the image" distinction explicitly so the implementer does not COPY it
into the `Dockerfile` (that would be an `infra` change and is an out-of-epic follow-up, see Risks).

**Transport & framing (ASSUMPTION — verify at build time against the official MCP spec/SDK).**
MCP is **JSON-RPC 2.0 over stdio**. Messages are **newline-delimited JSON** on stdin/stdout (one
JSON object per line) — *not* LSP-style `Content-Length:` framed. This newline-vs-header choice is
the classic hand-rolled-MCP footgun and is the single most important thing for the implementer to
confirm against the spec before writing the read loop, because it determines both the server's
parser and the verification harness's input format. If the target runtime requires `Content-Length`
framing, the read/write loop changes but nothing else in this plan does.

**Minimal method set to implement (ASSUMPTION — verify shapes against the MCP spec/SDK reference):**

| JSON-RPC method | Server responds with (planned shape) |
|-----------------|--------------------------------------|
| `initialize` | `{protocolVersion:"2025-06-18", capabilities:{tools:{}}, serverInfo:{name:"mdreview-mcp", version}}` (the `protocolVersion` is pinned in the MR-015 AC; confirm the value at build time) |
| `notifications/initialized` | notification (no `id`); acknowledge silently, send no response |
| `tools/list` | `{tools:[{name, description, inputSchema /* JSON Schema */}, …]}` — all 8, **static** |
| `tools/call` | `{content:[{type:"text", text:<json-string of HTTP response>}], isError?:bool}` |

The plan **pins** the target `protocolVersion` to `"2025-06-18"` (current MCP spec revision) and the
exact `capabilities:{tools:{}}` / `serverInfo` / `content` field names in the MR-015/MR-016 ACs, so
the harness asserts concrete values rather than a vague "confirm against spec." Because no MCP code
or spec is vendored in this repo, the implementer still **confirms the pinned `protocolVersion` and
field names at build time** against the official MCP specification/SDK reference and corrects them
there if the spec has moved. Treat any mismatch as a build-time correction, not a re-plan.

**Error mapping (specify precisely — getting this wrong is a real bug):**
- **Protocol errors → JSON-RPC `error` object.** Malformed JSON → `-32700` (parse error); unknown
  method → `-32601` (method not found); **unknown tool name in `tools/call` → `-32602` (invalid
  params)** — a *decided* choice (see MR-016 ACs): naming a non-existent tool is a malformed request,
  not a tool that ran and failed, so it is a protocol error, not an `isError` result.
- **Tool/transport errors → a normal `tools/call` result with `isError:true`**, not a JSON-RPC
  error. A `404` from the service (bad/expired id), a connection refused (service down), or a non-2xx
  status is surfaced as `{content:[{type:"text", text:<error detail>}], isError:true}`. The agent
  sees a tool failure it can reason about, and the protocol stream stays valid.

**Config.** `MDREVIEW_BASE` env var, default `http://localhost:8137` (the published compose port;
the in-container `PORT` is 8080 — the wrapper talks to the *published* base). All HTTP via
`urllib.request` with a short timeout; JSON via `json`.

### Tool surface (8 tools, 1:1 with the HTTP API)

Each tool maps to exactly one existing route. Endpoint citations are `app.py` line numbers (code
citations, per the Citation convention's "reserve line numbers for code").

| Tool | Args (JSON Schema) | HTTP call | `app.py` |
|------|--------------------|-----------|----------|
| `create_review` | `markdown` (req), `title?`, `project?`, `session?`, `source_path?` | `POST /api/reviews` → `{id, review_url, feedback_url, source_url, status_url}` | `app.py:226-238` |
| `list_reviews` | *(none)* | `GET /api/reviews` → `{reviews:[summary…]}` | `app.py:223-224` |
| `get_review` | `id` (req) | `GET /api/reviews/{id}` → meta | `app.py:240-246` |
| `get_feedback` | `id` (req) | `GET /api/reviews/{id}/feedback` → `{markdown, notes[], …meta}` | `app.py:267-276` |
| `get_status` | `id` (req) | `GET /api/reviews/{id}/status` → `{source_updated, feedback_updated}` | `app.py:285-294` |
| `update_source` | `id` (req), `markdown` (req) | `PUT /api/reviews/{id}/source` → meta (snapshots a history round, live-reloads viewer) | `app.py:251-265` |
| `get_history` | `id` (req), `round?` (int) | `round` absent → `GET /api/reviews/{id}/history` → `{rounds[]}`; `round` present → `GET /api/reviews/{id}/history/{n}` → one past draft + its feedback | `app.py:296-309` (list), `app.py:311-323` (one) |
| `delete_review` | `id` (req) | `DELETE /api/reviews/{id}` → `{deleted}` | `app.py:240-249` |

Notes:
- `create_review` carries provenance straight through: the `POST` handler already reads
  `project`/`source_path`/`session` from the body (`app.py:228-230`) and `create_review()` writes
  them to `meta.json` (`app.py:130-144`). No service change needed — they are optional fields.
- `get_history` is **one tool, two endpoints** selected by the presence of the optional `round`
  arg. `round` is the integer round number `N` matching `/history/(\d+)` (`app.py:311`).
- **Polling stays the agent's job.** `get_status` is the cheap signal; `get_feedback` returns the
  notes. The wrapper does not poll or block — it relays a single request per call, preserving the
  AGENTS.md "human is done" heuristic.

## Rollout phases

Each phase is independently shippable and smoke-testable.

### Phase 1 — protocol core (no service required)
The stdio read/write loop, JSON-RPC envelope handling, `initialize`, `notifications/initialized`,
and `tools/list` returning all 8 static tool schemas. Verifiable by piping newline-delimited
`initialize` + `tools/list` into the server **with no HTTP service running** — the schemas are
static, so this proves the protocol surface in isolation.

### Phase 2 — tool dispatch → HTTP
`tools/call` dispatch: map each tool name + args onto its `urllib` request against `MDREVIEW_BASE`,
relay the HTTP response as a `tools/call` result, and apply the error mapping (protocol vs tool
error). Requires a running service. Verifiable by a `create_review` → `update_source` round-trip
against a running container.

### Phase 3 — verification harness
A small **stdlib-Python** harness, `mcp_smoke.py` (using `json` + `subprocess`), that feeds the
handcrafted JSON-RPC sequence into the server, parses the responses, and asserts them — plus the
container round-trip. It is deliberately **not** a bash script: the round-trip extracts an `id` and
parses `content[0].text`, which in bash would need `jq` (not stdlib, not guaranteed present) and
would quietly reintroduce a dependency, contradicting the zero-pip spine of this plan. A
`json`/`subprocess` harness keeps "dependency-free" literally true. This becomes the wrapper's
repeatable smoke (analogous to `scripts/render-smoke.sh` for UI) and the evidence an implementer
attaches at G4/G7.

### Phase 4 — docs
Document the wrapper in `README.md` / `AGENTS.md` and update `docs/future-mcp.md` from "not built"
to shipped: how to run it (`MDREVIEW_BASE python3 mcp_server.py`), the 8 tools, the example MCP
client config, and the explicit note that it is optional and does not change the HTTP service.

## Non-goals

- **No change to the HTTP service.** `app.py`, `viewer.html`, `dashboard.html`, `static/**`, the
  `Dockerfile`, `docker-compose.yml`, and the storage format are untouched. This is the epic's
  defining boundary (enforced by the per-ticket base-relative `git diff` AC, not by prose).
- **MCP tools only — no resources, no prompts.** This wrapper implements the MCP **tools** feature
  and nothing else; the `initialize` capabilities advertise only `{tools:{}}`. No `resources/*` or
  `prompts/*` methods are implemented, which forecloses that scope drift up front.
- **Not baking the wrapper into the service image.** It is a standalone host-side script; COPYing it
  into the `Dockerfile` is an out-of-epic `infra` follow-up, not this epic.
- **No auth in the wrapper.** It inherits the service's trust-the-network, id-only posture; it adds
  no tokens, no tenancy, no access control.
- **Not re-implementing review logic.** No note-counting, no history snapshotting, no status
  derivation in the wrapper — the service owns all of it; the wrapper relays.
- **No new transport.** stdio only; no SSE/HTTP MCP transport, no streaming, no long-poll.
- **No SDK / pip dependency.** Hand-written JSON-RPC over `urllib` + `json`; no `mcp` or `anthropic`
  package (see Key constraints).

## Key constraints

Hard rules the implementation must not violate.

- **Stdlib-only, zero pip (footgun 1, the load-bearing one).** The wrapper uses only `sys`,
  `json`, `os`, `urllib.request` from the stdlib. **No `mcp`/`anthropic`/any pip package.** MCP is
  JSON-RPC 2.0 over stdio — small enough to hand-implement — so the SDK buys little and would break
  the "no installs" spirit the service is built on. Trade-off, stated: we hand-maintain the MCP
  framing and must track spec changes ourselves, versus depending on a maturing SDK that would do
  the framing but add a dependency and a moving-target version. We choose stdlib (see the
  load-bearing decision in the summary); the SDK path remains a documented fallback if the
  hand-rolled framing proves to diverge from the spec.
- **HTTP service unchanged (back-compat by construction).** Because the wrapper only *calls* the
  HTTP API, the service's behavior, routes, and on-disk format are preserved automatically. No
  `meta.json` key is added; no route is added or reordered in `route()`. The id regex
  `[A-Za-z0-9]{4,40}` (`app.py:38`) is not touched — the wrapper passes ids through verbatim and
  lets the service reject malformed ones.
- **Tool args are optional where the API is optional.** `create_review`'s `title`/`project`/
  `session`/`source_path` are optional in the schema, matching the service (`app.py:228-230`), so a
  caller that omits provenance behaves exactly as today.
- **Exposure note (footgun 5).** `list_reviews` (→ `GET /api/reviews`) aggregates across **all**
  reviews regardless of who created them — id-only tenancy means it widens visibility to anything on
  the targeted service. The wrapper inherits, and must document, the trust-the-network posture; it
  adds no isolation. Call this out in the docs ticket.
- **Validation gate.** `python3 -m py_compile mcp_server.py` (and the harness if it is Python) is the
  G4 compile check — the analogue of `py_compile app.py`. There is no test framework; the JSON-RPC
  smoke harness is the functional check. No `infra` change ⇒ no `docker build` is required *for the
  wrapper*, though the round-trip smoke does rebuild/run the service container.
- **No JS-rendered surface.** This epic ships no product page, so the G7 per-page
  `scripts/render-smoke.sh` DOM-assertion + screenshot requirement does **not** apply (per the G7
  pass-condition row: the per-page assertion is owed "only if a product page … was touched"). The
  unconditional container rebuild + `curl /healthz` + `/api/reviews` smoke is still owed at G7.

## Preferred execution order

1. **MR-015** (protocol core: stdio loop + `initialize` + `tools/list` static schemas) — provable
   with no service running.
2. **MR-016** (tool dispatch → HTTP via `urllib`) — depends on MR-015's dispatch table existing.
3. **MR-017** (verification harness) — depends on MR-016 so the round-trip is exercisable; the
   `tools/list` half can be drafted alongside MR-015.
4. **MR-018** (docs sweep: `README.md` / `AGENTS.md` / `docs/future-mcp.md`) — last, once the tool
   surface and run command are final. Per the Definition of Done, durable docs land in-sprint; this
   is the sprint's docs ticket and (per G7) is **not** eligible for carry-over.

Protocol surface precedes dispatch precedes the harness that exercises both; docs close.

## Ticket breakdown

Create these in `tickets/` only after G1 passes, then link them in the frontmatter.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-015 | `mcp_server.py`: stdio JSON-RPC core — `initialize`, `notifications/initialized`, `tools/list` (8 static schemas) | svc | 1 |
| MR-016 | `tools/call` dispatch → HTTP via `urllib` (8 tools, provenance pass-through, protocol-vs-tool error mapping) | svc | 2 |
| MR-017 | `mcp_smoke.py` (stdlib `json`+`subprocess`, no jq): handcrafted JSON-RPC sequence + container `create_review`→`update_source` round-trip | svc | 3 |
| MR-018 | Docs: wrapper in `README.md`/`AGENTS.md`, update `docs/future-mcp.md` to shipped, client config + exposure note | docs | 4 |

**Layer-tag note (N1).** MR-015–MR-017 are tagged `svc` because the work is server-side Python and
the layer table has no closer fit — yet these tickets are **forbidden from touching `app.py`**. The
tension is deliberate and pragmatic: the `svc` tag is what drives the right validation gate
(`py_compile`, no `docker build`), while the per-ticket "service unchanged" AC below keeps the
forbidden files inviolate.

### Per-ticket acceptance criteria

These are the AC-level requirements the implementer self-checks at **G4 (Implementation Gate)**
(under its "author self-checked the acceptance criteria" clause). Routine `py_compile` is owed by
every code ticket and is not repeated per row.

**MR-015 (protocol core) ACs:**
- **Service-unchanged (defining non-goal).** The base-relative diff
  `git diff --stat "$(git merge-base origin/main HEAD)"...HEAD -- app.py viewer.html dashboard.html static Dockerfile docker-compose.yml`
  is **empty**.
- **Pinned protocol contract (build-time-verified).** `initialize` returns
  `{protocolVersion:"2025-06-18", capabilities:{tools:{}}, serverInfo:{name:"mdreview-mcp", version:<str>}}`.
  `"2025-06-18"` is the target MCP `protocolVersion` planned against (current MCP spec revision); the
  implementer **confirms this exact string against the official MCP spec/SDK at build time** and
  corrects it there if the spec has moved — the AC pins a concrete value to assert, not a vague
  "confirm against spec."
- **Capabilities advertise tools only** — `capabilities == {tools:{}}` (no `resources`, no `prompts`).
- **`notifications/initialized`** (an `id`-less notification) is acknowledged silently — the server
  sends **no** response line for it.
- **`tools/list`** returns `{tools:[…]}` whose `.name` set is exactly the 8 tool names, each object
  carrying a `description` and an `inputSchema` (JSON Schema object).
- **Stream hygiene (S4 — the pipe-smoke depends on it).** The server **flushes stdout after each
  response** and **exits cleanly on stdin EOF**, so a piped (`printf … | python3 mcp_server.py`)
  smoke completes instead of hanging.

**MR-016 (tool dispatch → HTTP) ACs:**
- **Service-unchanged.** Same base-relative empty-diff check as MR-015.
- **`tools/call` envelope (pinned).** A successful call returns
  `{content:[{type:"text", text:<json-string of the HTTP response body>}]}` (no `isError`, or
  `isError:false`). The harness asserts `content[0].type == "text"` and that `content[0].text`
  parses as JSON.
- **Tool error → result, not protocol error.** A service `404` (bad/expired id), connection refused,
  or any non-2xx is returned as `{content:[{type:"text", text:<error detail>}], isError:true}` — a
  normal `tools/call` result, leaving the JSON-RPC stream valid.
- **Unknown tool name → JSON-RPC `error` `-32602` (invalid params).** *Decision (resolving the
  review's open question):* an unrecognized `name` in `tools/call` is a malformed request, so it
  returns a JSON-RPC `error` object with code **`-32602`** (invalid params) — **not** an
  `isError:true` result. This keeps "the tool ran and failed" (`isError`) cleanly separate from "you
  named a tool that does not exist" (protocol error). MR-016's smoke asserts a JSON-RPC `error`
  with `code == -32602` for an unknown tool name.
- **Provenance pass-through.** `create_review` forwards `project`/`session`/`source_path` verbatim in
  the `POST` body; omitting them behaves exactly as today (they are optional service fields,
  `app.py:228-230`).

**MR-017 (verification harness) ACs:**
- **Service-unchanged.** Same base-relative empty-diff check as MR-015.
- **Stdlib only.** `mcp_smoke.py` uses only `json` + `subprocess` (+ `os`/`sys`); **no `jq`, no pip**.
- It encodes assertions for: the MR-015 protocol surface (8 tools, pinned `initialize` shape), the
  MR-016 happy-path envelope, the `isError:true` 404 path, and the `-32602` unknown-tool path, plus
  the container `create_review`→`update_source` round-trip.

**MR-018 (docs) ACs:**
- Documents the run command, the 8 tools, an example MCP client config, and the `list_reviews`
  exposure note (footgun 5).
- **`MDREVIEW_PUBLIC_BASE` guidance (resolving the review's open question).** The `review_url` the
  wrapper relays is derived by the service from the request `Host` header unless `MDREVIEW_PUBLIC_BASE`
  is set (`app.py:34`, `app.py:177-179`). The docs ticket must instruct operators to set
  `MDREVIEW_PUBLIC_BASE` on the **service** to a URL reachable by whoever the agent hands the link to
  (a human browser), so the returned `review_url` is not an unreachable `localhost`/internal host.

## Risks and mitigations

- **MCP protocol shape unverifiable from this repo.** No MCP code/spec is vendored here, so the
  `initialize` handshake, `protocolVersion`, framing, and `content` envelope are *assumptions*.
  Mitigation: they are explicitly labelled as build-time-verify assumptions throughout; MR-015's
  acceptance criteria must include "confirmed against the official MCP spec/SDK reference," and the
  harness asserts the actual on-wire shapes once confirmed. If the runtime needs `Content-Length`
  framing instead of newline-delimited, only the read/write loop changes.
- **Newline vs `Content-Length` framing** (the hand-rolled-MCP footgun). Mitigation: plan for
  newline-delimited JSON, isolate framing behind a `read_message`/`write_message` pair so swapping
  it is a one-function change, and verify against the spec first.
- **Error-mapping confusion** (protocol error vs tool error). Mitigation: the mapping is specified
  above and decided in the MR-016 ACs — JSON-RPC `error` for malformed input, unknown method
  (`-32601`), and unknown tool name (`-32602`); `isError:true` results for HTTP 4xx/5xx and
  connection failures. MR-016's smoke hits a happy path, a `404`/bad-id path (→ `isError`), and an
  unknown-tool path (→ `-32602`), asserting the right channel for each.
- **Scope creep into the service.** Any temptation to "just add a key" or a route to make a tool
  cleaner violates the defining non-goal. Mitigation: each of MR-015–MR-017 carries a **per-ticket
  acceptance criterion** (see "Per-ticket acceptance criteria" below) requiring a base-relative
  `git diff` to show **no change** to `app.py`/`viewer.html`/`dashboard.html`/`static/**`/
  `Dockerfile`/`docker-compose.yml`. That AC rides **G4 (Implementation Gate)**'s existing "author
  self-checked the acceptance criteria" clause — the enforcement lives in a real ticket AC, not in a
  free-floating claim about the gate row (per **MR-012**: citing a gate row alone is insufficient;
  the check must be wired into a mechanism the gate already runs).
- **`MDREVIEW_BASE` mismatch.** The wrapper defaults to the *published* `http://localhost:8137`, not
  the in-container `8080`. Mitigation: documented default + env override; the harness sets it
  explicitly.
- **Bundling the wrapper into the image later.** Out of scope here; noted as an `infra` follow-up so
  it is tracked, not smuggled into this epic.

## Out-of-epic follow-ups (acknowledged debt, not in scope)

- Optionally COPY `mcp_server.py` into the image / publish a runnable container target (`infra`).
- Optional `mcp` SDK variant as a separately-installable component (would carry a pip dependency;
  only if the hand-rolled framing proves to diverge from the evolving spec).

## Process carry-over (this cycle's open — not part of the feature)

Per the source brief's carry-over note and the **process-hardening-2 retrospective, suggestion 1**:
the **pre-G7 board rail** should not only reconcile the board but also **run and record the
unconditional rebuild + `curl /healthz` + `/api/reviews` smoke** as G7 evidence. This is a
`[skill]` process tweak, **out of this epic's scope**, to be applied **when closing this cycle's
sprint** (run + record the smoke in the G7 evidence) and groomed into the process backlog rather
than riding only as a memory. Recorded here so the sprint-close step does not forget it.

## Verification

No test framework; verification is `py_compile` + a runnable JSON-RPC smoke + a container
round-trip. All commands are concrete and dependency-free (the harness is stdlib Python — no `jq`).
The `printf`-pipe examples below are the human-readable illustration; `mcp_smoke.py` (MR-017)
encodes the same assertions.

**1. Compile (G4 gate for every code ticket):**
```bash
python3 -m py_compile mcp_server.py        # + the harness if it is Python
```

**2. Protocol surface, no service running (proves Phase 1 / MR-015).**
Pipe newline-delimited JSON-RPC into the server; assert it answers `initialize` and lists 8 tools:
```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 mcp_server.py
# Expect: line 1 -> result with serverInfo + capabilities.tools
#         (notification produces no response line)
#         line 2 -> result.tools is an array of 8 objects whose .name set ==
#         {create_review,list_reviews,get_review,get_feedback,get_status,
#          update_source,get_history,delete_review}, each with an inputSchema.
```
(Exact `initialize` result fields are build-time-verified against the MCP spec; the harness encodes
the confirmed shape.)

**3. Tool dispatch round-trip against a running container (proves Phase 2 / MR-016).**
```bash
docker compose up -d --build           # service on localhost:8137
export MDREVIEW_BASE=http://localhost:8137

# create_review via tools/call, then update_source on the returned id, then verify over plain HTTP.
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"create_review","arguments":{"markdown":"# Hi","title":"smoke","project":"mcp","session":"s1","source_path":"x.md"}}}' \
  | python3 mcp_server.py
# Expect: the create_review result.content[0].text parses to JSON containing "id" + the four urls.

# Extract the id from that result, then:
#   tools/call update_source {id, markdown:"# Hi v2"}  -> result is meta with bumped source_updated
# Confirm the service actually reflects it (proves real proxying, not a stub):
curl -s "$MDREVIEW_BASE/api/reviews/<id>/source"     # -> "# Hi v2"
curl -s "$MDREVIEW_BASE/api/reviews/<id>/history"    # -> {"rounds":[{"round":0,...}]}  (update_source snapshotted a round)
```

**4. Error-channel check (proves the error mapping, MR-016):**
```bash
# tools/call get_review {id:"doesnotexist0"} against a running service
# Expect: a tools/call RESULT with isError:true (the service's 404 relayed), NOT a JSON-RPC error object.
# tools/call with an unknown tool name
# Expect: a JSON-RPC error object with code -32602 (invalid params) — the decided convention
#         (an unknown tool name is a malformed request, not an isError result).
```

**5. Service-unchanged check (per-ticket AC on MR-015–MR-017, enforces the defining non-goal).**
Use a **base-relative** diff — a bare `git diff --stat <paths>` compares working tree to index and
false-passes once the edit is committed, so it must be anchored to the branch base:
```bash
git diff --stat "$(git merge-base origin/main HEAD)"...HEAD -- \
  app.py viewer.html dashboard.html static Dockerfile docker-compose.yml
# Expect: empty — this epic adds files (mcp_server.py, mcp_smoke.py, docs), it edits none of these.
```
This is the runnable form of the per-ticket AC; the author self-checks it at **G4 (Implementation
Gate)** under the gate's existing "author self-checked the acceptance criteria" clause.

**6. Sprint close (G7).** Independent `staff-critic` close review; the unconditional smoke —
rebuild the container, `curl /healthz` + `/api/reviews` — is run and recorded (also satisfying the
carry-over above). No product page is touched, so per the G7 pass-condition row the per-page
`scripts/render-smoke.sh` DOM assertion + screenshot are **not** owed.

## Review resolutions

Round 1 — review `reviews/mcp-wrapper-plan-review-2026-06-09.md` (G1, PASS-WITH-FIXES). Applied by
the author 2026-06-09; the 4-ticket breakdown (MR-015–MR-018) is unchanged.

- **B1 (BLOCKER) — "HTTP service unchanged" enforced only in prose, citing a non-existent G4
  condition (the MR-012 defect class).** Made "base-relative `git diff` shows no change to
  `app.py`/`viewer.html`/`dashboard.html`/`static/**`/`Dockerfile`/`docker-compose.yml`" an explicit
  **per-ticket acceptance criterion** on MR-015, MR-016, and MR-017 (new "Per-ticket acceptance
  criteria" subsection after the ticket table), so it rides **G4 (Implementation Gate)**'s existing
  "author self-checked the acceptance criteria" clause. Deleted the free-floating "G4 asserts
  `git diff`" claim from the Risks bullet and rewrote the Verification §5 prose to point at the
  per-ticket AC instead of asserting a gate-row condition.
- **S1 — diff command false-passes after commit.** Replaced every
  `git diff --stat <paths>` with the base-relative form
  `git diff --stat "$(git merge-base origin/main HEAD)"...HEAD -- …` (Verification §5 and the
  per-ticket ACs). Added `docker-compose.yml` to the watched-paths set everywhere it is listed
  (Non-goals, the `Service (app.py)` subsection, Risks, the per-ticket ACs, and Verification §5).
- **S2 — "confirm against the MCP spec" not testable.** Pinned `protocolVersion` to `"2025-06-18"`
  (current MCP spec revision; implementer confirms at build time) in the method-set table, the
  MR-015/MR-016 ACs, and both `printf` smoke examples. The ACs now assert the exact `initialize`
  fields (`capabilities:{tools:{}}`, `serverInfo`) and the `tools/call` envelope
  (`content[0].type=="text"`, `content[0].text` parses as JSON, `isError` semantics).
- **S3 — tools-only non-goal.** Added a Non-goal: the wrapper implements MCP **tools only** — no
  resources, no prompts; `initialize` advertises only `{tools:{}}`.
- **S4 — pipe-smoke hang.** Added an MR-015 AC: the server flushes stdout after each response and
  exits cleanly on stdin EOF, so the pipe-based smoke completes instead of hanging.
- **N1 (nit) — `svc`-tag tension.** Added a one-line "Layer-tag note" under the ticket table naming
  why MR-015–MR-017 are tagged `svc` yet forbidden from touching `app.py` (the tag drives
  `py_compile` / no `docker build`; the per-ticket AC keeps the forbidden files inviolate).
- **Open question (a) — unknown tool name.** Decided: an unknown `name` in `tools/call` returns a
  JSON-RPC `error` with code **`-32602`** (invalid params), not an `isError` result. Recorded in the
  error-mapping prose, the MR-016 AC, the Risks bullet, and the Verification §4 assertion.
- **Open question (b) — `MDREVIEW_PUBLIC_BASE`.** Decided: the docs ticket (MR-018) must instruct
  operators to set `MDREVIEW_PUBLIC_BASE` on the **service** to a browser-reachable URL so the
  `review_url` the wrapper relays is reachable (the service derives it from the `Host` header unless
  the env var is set — `app.py:34`, `app.py:177-179`). Added as an MR-018 AC.
