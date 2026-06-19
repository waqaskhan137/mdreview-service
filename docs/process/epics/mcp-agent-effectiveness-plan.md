---
epic: mcp-agent-effectiveness
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-19
source: requirements/mcp-agent-effectiveness.md
gate: passed 2026-06-19  # G1 (Plan Gate): passed (round 2, staff-critic PASS) — tickets unblocked
review: reviews/mcp-agent-effectiveness-plan-review-2026-06-19.md
related_sprints: [sprint-12]
related_tickets: [MR-038, MR-039, MR-040, MR-041, MR-042, MR-043]
---

# Make the mdreview MCP genuinely self-serve for agents (and prove it) Plan

This epic turns a string of operator hot-patches into a gated, provable property: **an autonomous
agent, given only the mdreview MCP server, completes the canonical image-embed loop unaided, and a
stale MCP server is detectable.** The trigger was an agent that repeatedly failed to embed an image
because the running `mcp_server.py` process predated the `attach_asset(path=…)` / `instructions` /
`get_source` work on disk — and **nothing could detect that staleness**. The image only got attached
because an operator drove curl by hand. This epic adds (1) a code-tied version/staleness signal, (2)
a stdlib agent-loop acceptance harness that proves the loop renders with zero human curl, (3) a
verification that capability discoverability is genuinely covered, and (4) retro-tickets for two
viewer fixes already shipped this session so the board reflects reality.

**Source requirement:** [`requirements/mcp-agent-effectiveness.md`](../requirements/mcp-agent-effectiveness.md)
— the original brief, kept verbatim.

## Product goal

Given only the mdreview MCP server (no human, no curl), an autonomous agent can: create a review →
reference an image in the markdown → `attach_asset(path=…)` → and **the figure actually renders in
the viewer** (the `<img>` is repointed to the served asset URL and decodes). Separately, the running
MCP process's identity is **surfaced** so staleness is detectable: the agent can read and report the
running process's `tools_hash`/version (via the `server_info` tool); **comparing it to the on-disk
code** (to conclude "stale") is a **human/CI step with a shell** (`mcp_server.py --print-version`).
An MCP-only agent holds the running hash but has **no comparand over MCP**, so it cannot *self*-detect
a mismatch — what it can do is report its version so the human/CI (and the agent's operator) compare.
The remedy on any suspected staleness is invariant (reconnect the MCP client), regardless of who
notices. So the brief's "detectable by the agent **and** the human" is met as: **human/CI detects
the mismatch; the agent surfaces its version** as the input to that comparison. The proof is a
repeatable, stdlib, no-pip harness that is run at G7 and is honest about what it can and cannot
assert (a 200 is not a render; the server can signal its identity but cannot force a reconnect, and
an MCP-only agent cannot self-detect staleness).

## Core design principle

**Prove the agent loop with a runnable harness; signal what the server cannot fix; add nothing the
repo would have to maintain.** The MCP wrapper stays a thin, stateless stdio proxy — every addition
is either a tiny constant/derived value (a tool-set hash, a `server_info` tool) or a test artifact.
We do not invent capability-negotiation machinery, we do not try to hot-reload a running stdio
process (structurally impossible from the server side), and we do not add a runtime dependency. Where
a limitation is structural, the plan and the surfaced text say so plainly.

## The three load-bearing decisions (chosen option + why)

### Decision 1 — Staleness/version signal: **a code-derived `version` + a `server_info` tool** (option a, augmented)

**Context (verified).** `SERVER_INFO = {"name": "mdreview-mcp", "version": "0.1.0"}`
(`mcp_server.py:31`) is a hand-set string returned in `serverInfo` on `initialize`
(`mcp_server.py:330-339`). A running stdio server caches its code + `TOOLS` (`mcp_server.py:54-204`)
at process start; editing the file changes nothing until the client reconnects. The server can only
*surface* that it changed; it cannot force a reconnect. That is a client-lifecycle reality, not a bug
to fix.

**Chosen shape.**
1. Keep a human-set `version` in `SERVER_INFO`, but **add a code-derived `tools_hash`** — a stdlib
   `hashlib.sha256` over a canonical `json.dumps(TOOLS, sort_keys=True)` (and the `INSTRUCTIONS`
   text), truncated to ~12 hex chars. It changes automatically whenever the tool schema or workflow
   text changes, so it cannot silently drift from a hand-bumped string the way a manual version does.
2. Surface it in two places an agent and a human actually reach:
   - in the `initialize` `serverInfo` (so `serverInfo = {name, version, tools_hash}`), and
   - as a **new `server_info` tool** (no args) returning `{name, version, protocol_version,
     tools_hash, tool_count, tool_names}` so an agent can call it mid-session and a human can
     `tools/call server_info` to read what the *running* process actually exposes.
3. **Surface, not self-detect; signal, not auto-fix.** Be precise about who detects what:
   - The `server_info` tool lets an agent **read and report the *running* process's** `tools_hash`/
     version. That is all an MCP-only agent can do — it has the running hash but **no comparand over
     MCP**.
   - **Comparing** running-vs-on-disk (the step that concludes "stale") is a **human/CI step with a
     shell**: `python3 mcp_server.py --print-version` prints the on-disk `{version, tools_hash}` to
     stdout and exits (a tiny, isolated `argv` check that does not touch the JSON-RPC loop), and the
     human/CI compares it to the `server_info` value the agent surfaced. The remedy on a mismatch is
     invariant: **reconnect the MCP client** to pick up new code.
   - The honest contract, stated in `INSTRUCTIONS`, the `server_info` description, and the docs:
     *`server_info` reports the running server's `tools_hash`/version; a human/CI compares it to the
     repo's `--print-version` output to decide if the running process is stale; on a mismatch,
     reconnect the MCP client.* **Do not phrase this as "the agent detects staleness"** — an MCP-only
     agent cannot, because it has no on-disk comparand over MCP.
   - **Non-goal / future option (b), not built):** the HTTP service could publish the *expected*
     wrapper `tools_hash` (e.g. on a small info route) as an **MCP-reachable comparand**, which would
     turn the comparison into an all-MCP check the agent could make autonomously. This epic does not
     build it — option (a), honest scoping, is the minimum and the remedy is invariant either way.

**Why.** A tool-set hash is cheap (one stdlib call), self-maintaining (no "did you bump the version?"
discipline), and answers the exact failure: the running process exposed an old tool set. `server_info`
lets the agent **report** the running wrapper's identity; `--print-version` gives the human/CI the
on-disk comparand, and **the human/CI does the comparison** — the agent supplies one side of it, not a
verdict. A service-side `/healthz` build field as the wrapper's *own* version (option b, first form)
doesn't help — the staleness is in the **wrapper** process, not the HTTP service, and the wrapper and
service version independently. (The *other* form of option b — the service publishing the **expected
wrapper hash** as an MCP-reachable comparand so the agent could compare autonomously — is coherent but
out of scope; named a non-goal/future option above.) Doc-only (option c) is already partially in place
and does not make staleness *detectable*, only *explained*. We deliberately stop short of capability
negotiation: the action on a mismatch is always the same single thing (reconnect), so a richer
protocol buys nothing.

### Decision 2 — Agent-loop acceptance harness: **a new sibling `agent_smoke.py` + the repo's Node-CDP render-check**

**Context (verified by measurement, not argued).** I built a throwaway image (`docker build`),
ran it on `:8155`, and drove the real loop:

| Step | Command | Measured result |
|------|---------|-----------------|
| create + attach | `POST /api/reviews`, `POST …/assets` (name `/assets/plot.png`) | `stored=490e9f0db52061ac.png`, `url=http://…/api/reviews/{id}/asset/490e9f0db52061ac.png` |
| asset served | `curl -sD - -o /dev/null …/asset/{stored}` | `HTTP/1.0 200`, `Content-Type: image/png` |
| `<img>` repointed | headless Chrome `--dump-dom` of `/review/{id}` | `<img src="http://…/api/reviews/{id}/asset/490e9f0db52061ac.png" alt="plot">` |
| DOM nodes | `render-smoke.sh … 'img' '#article'` | `ok: img (2 nodes)`, `ok: #article (1 node)` |
| **image decoded** | CDP `Runtime.evaluate` of `naturalWidth` on `#article img` | `[{"src":"http://…/asset/490e9f0db52061ac.png","nw":1}]` — **nw>0 = the image actually loaded** |

So the loop works today; what's missing is the **repeatable, agent-driven proof**. Two facts the
harness design turns on, both measured above:
- `render-smoke.sh` proves the `img` element exists and (via `--dump-dom`) you can grep the repointed
  `src`, **but it cannot assert the image *decoded*** — `--dump-dom` serializes markup, not
  `naturalWidth`. The "a 200 is not a render" bar (and "a repointed src is not a loaded image") needs
  a JS eval over CDP. **Use the repo's established render-evidence toolchain — headless Chrome driven
  over CDP via Node's built-in `WebSocket`** (the sprint-09 render-evidence README documents exactly
  this "Node built-in WebSocket driver" over CDP; the sprint-11 close and this session's render
  evidence used the same), **not a bespoke stdlib RFC6455 client.** Node is already a de-facto test
  dependency here and adds **zero pip installs**. The "stdlib-only / zero pip" rule binds the
  **service runtime** (the MCP wrapper stays a thin proxy; no runtime dependency), **not** dev/CI
  test tooling — so writing a hand-rolled WebSocket client to honor a rule that does not bind here is
  over-engineering, not compliance. (Headless detail that stays in the ticket: the newer
  `/json/new?url=` endpoint is disabled; launch Chrome **with the URL as an argv** and pick the
  existing `type=="page"` target from `GET /json`.)
- Chrome **or Node** may be absent in some envs. `render-smoke.sh` already **exits 3 (fail loud)** when
  no Chrome is found. The CDP render-check must do the same for **either** missing Chrome **or**
  missing Node: **skip loudly with a distinct non-pass exit, never silently pass.** The asset-served
  HTTP assertion (steps 1–2) is Chrome-free *and* Node-free (stdlib `urllib`) and always runs.

**Chosen shape.**
- A **new `agent_smoke.py`** (sibling of `mcp_smoke.py`), not an extension. Justification: `mcp_smoke.py`
  is a *protocol-surface* smoke — 22 fast assertions, no browser, exits in seconds, run on every MCP
  change. The agent loop needs Chrome + a multi-second render wait + CDP, and must be able to **skip
  loudly** when Chrome is absent. Bolting a browser dependency onto the fast protocol smoke would slow
  and complicate the thing that should stay quick and always-runnable. Keeping them siblings lets
  `mcp_smoke.py` stay the cheap gate and `agent_smoke.py` be the heavier, browser-backed acceptance
  proof. Both stay stdlib + reuse the `drive()` stdio pattern.
- `agent_smoke.py` drives `mcp_server.py` over stdio **as an agent would** (initialize → tools/call):
  `create_review` (markdown that references `/assets/<fig>.png`) → `attach_asset(path=…)` pointing at a
  PNG the harness writes to a temp file (exercising the *path* branch, the one that tripped the agent,
  with no base64 in "context"). Verification is **two layers**:
  - **(i) Always-on, Chrome-free gate (stdlib only):** assert `GET …/asset/{stored}` is `200` + an
    `image/` content-type (stdlib `urllib`), **and** that the viewer **repoints** the `<img>` —
    headless Chrome `--dump-dom` + a stdlib HTML parse that the rendered `<img src>` is the served
    asset URL. (Repoint via `--dump-dom` is squarely in `render-smoke.sh`'s wheelhouse and needs no WS
    client.)
  - **(ii) Render assertion ("a 200 is not a render"):** the `<img>` actually **loaded**
    (`naturalWidth > 0`) **AND** its `src` is the served asset URL — via a small **Node built-in-
    `WebSocket` CDP** check (`Runtime.evaluate` of `naturalWidth` on `#article img`), the repo's
    established render-evidence pattern. **Fail-loud skip** (distinct non-pass exit, printed SKIPPED)
    if **Chrome or Node** is absent — never a silent pass.
  - Cleans up the review at the end (`delete_review`). Exit codes: `0` all pass; `1` a real failure
    (asset not served, or img not repointed/not loaded); `3` Chrome **or** Node absent → the render
    half (ii) is **skipped loudly** (printed as SKIPPED, distinct exit) while the Chrome-free gate (i)
    still ran.
- It also calls the new `server_info` tool and prints the running `tools_hash` (so a run records which
  server version it proved), and asserts the new tool count.
- **Documented fallback (no new WS client either way).** If a reviewer ever mandates *pure-no-Node*,
  the fallback is the layer-(i) `--dump-dom` repoint proof for the gate **plus a manual G7 spot-check**
  of `naturalWidth>0` — **not** a hand-rolled WebSocket client. Writing new RFC6455 protocol code to
  dodge a Node dependency the repo already relies on for exactly this is the over-engineering the
  process should catch.

**Why.** Sibling-not-extension keeps the fast gate fast and the heavy gate honest about Chrome/Node. A
CDP `naturalWidth` check is the only thing that actually proves "the figure renders" rather than "a
200 came back" or "an element exists" — and the repo already does it with Node's built-in `WebSocket`
(zero installs), so reaching for a bespoke stdlib RFC6455 client would add a fragile maintenance
surface to honor a runtime-only rule that does not bind test tooling. The fail-loud-on-no-Chrome/Node
contract matches `render-smoke.sh` so the harness can never green-wash a box without a browser.

### Decision 3 — Capability discoverability: **already satisfied by `instructions` + tool descriptions; ship a verification-only ticket, not new code**

**Context (verified).** The three things that tripped the agent are now discoverable from
`tools/list` + `initialize.instructions` **without external docs**:
- **path-attach:** `attach_asset`'s description (`mcp_server.py:124-131`) explicitly says *"PREFER
  `path`… so you never emit base64 through your context"* and `INSTRUCTIONS` (`mcp_server.py:36-47`)
  names `attach_asset` as the way to make images render.
- **get_source:** its description (`mcp_server.py:83-84`) and `INSTRUCTIONS` both say to read the draft
  when you didn't keep it in memory.
- **comment loop:** `INSTRUCTIONS` and the four comment tools' descriptions encode list-first →
  reply/resolve → never-reopen.

So there is **no missing code or doc** for discoverability — inventing a ticket here would be make-work
against the requirement's own "do not redo shipped work." What *is* missing is a **guarantee that the
discoverability text stays present** (a future refactor could quietly drop the path-attach guidance and
re-open the exact gap). The chosen deliverable is therefore a **verification-only ticket**: extend
`mcp_smoke.py` with assertions that the discoverability contract holds — `attach_asset` description
mentions `path`; `get_source` description tells you when to read it; `INSTRUCTIONS` names path-attach,
get_source, and the comment loop; and the new `server_info` tool exists. No production behavior change;
it makes the already-shipped discoverability *load-bearing under test*.

**Why.** The requirement asks to *confirm* an agent can self-discover the path — confirmation is a
test, not a feature. Honest scoping: claiming a discoverability feature when the text already exists
would be smuggling. The one real risk (regression) is closed by an assertion, cheaply.

## Recommended approach

### Service (`app.py`)
- **No change required.** Verified: `POST /api/reviews/{id}/assets` decodes base64 and stores under a
  content-hash name (`app.py:556-572`); `GET /api/reviews/{id}/asset/{stored}` serves the bytes with
  the manifest's `ctype` (`app.py:620-632`); `GET /api/reviews/{id}/source` (`app.py:464+`); `/healthz`
  (`app.py:420-421`); the viewer repoints `<img>` via `rewriteAssetImages` (`viewer.html:270-285`,
  matching full src then basename). The asset-served URL is `/api/reviews/{id}/asset/{stored}` (the
  brief's `/asset/{stored}` shorthand; the real path has the `/api/reviews/{id}` prefix). The epic
  touches **no `app.py` route**, so the single-file regex router and id regex are unchanged.

### MCP wrapper (`mcp_server.py`)
- Add `_tools_hash()` (stdlib `hashlib.sha256` over canonical `json.dumps(TOOLS, sort_keys=True)` +
  `INSTRUCTIONS`), include `tools_hash` in `SERVER_INFO`/the `initialize` `serverInfo`.
- Add a 16th tool **`server_info`** (no args) → `{name, version, protocol_version, tools_hash,
  tool_count, tool_names}`, dispatched **inside the wrapper** (it does not hit the HTTP service — it
  reports the wrapper's own identity). This is the one tool whose `route()` cannot map to an HTTP call;
  handle it as a local branch in `handle_tools_call`/a small helper before the `route()` dispatch.
- Add a `--print-version` argv short-circuit in `main()` (print `{version, tools_hash}` JSON, exit)
  for the human/CI on-disk comparand. Cite the insertion point: `main()` at `mcp_server.py:366-373`.
- Extend `INSTRUCTIONS` (and the `server_info` description) with the honestly-scoped contract:
  `server_info` reports the **running** server's `tools_hash`/version; a **human/CI** compares it to
  the repo's `--print-version` output to decide if the running process is stale; on a mismatch,
  **reconnect** the MCP client. The text must **not** imply an MCP-only agent self-detects staleness
  (it has the running hash but no on-disk comparand over MCP).

### Harnesses (stdlib service runtime; Node permitted for the render check only)
- **`agent_smoke.py`** (new): the agent-loop acceptance harness (Decision 2). Layer (i) — the
  always-on gate (asset-served + `--dump-dom` repoint) — is **stdlib only**. Layer (ii) — the
  `naturalWidth>0` render assertion — uses the repo's **Node built-in-`WebSocket` CDP** pattern (zero
  pip), **fail-loud-skip on no Chrome or no Node**. **No bespoke stdlib RFC6455 WebSocket client.**
- **`mcp_smoke.py`** (extend): assert the new `server_info` tool, the 16-tool count, `tools_hash` in
  `serverInfo`, the three-way hash identity (NIT-1), and the discoverability contract (Decision 3).
  Keep all existing 22 assertions green.

### UI (`viewer.html` / `dashboard.html` / `static/`)
- **No new code.** Two fixes already shipped to `dev` this session (`dae815e` table CSS,
  `2ed9593` lightbox) get **retro-tickets** (Phase 0) marked `done`-on-arrival, each carrying a
  render-smoke AC that confirms the *already-merged* code renders. The lightbox commit also
  introduced `#lightbox` (`viewer.html:43-44,170,548-552`) and table CSS (`viewer.html:30`).

### Docs
- A docs-sweep ticket (same sprint, **not carry-over-eligible** per the Definition of Done) folds the
  staleness/reconnect guidance and the `server_info` tool into `CLAUDE.md`, `README.md`, `AGENTS.md`,
  and `docs/future-mcp.md` (the 15→16 tool count and the "reconnect after editing `mcp_server.py`"
  remedy). The docs state the **honest staleness scoping (SHOULD-1)**: `server_info` reports the
  running server's `tools_hash`; **a human/CI** compares it to `--print-version`; an MCP-only agent
  surfaces its version but **cannot self-detect** the mismatch. No doc may say "the agent detects
  staleness."

## Rollout phases

Each phase is independently shippable; later phases build on earlier ones.

### Phase 0 — Board reconciliation (retro-tickets, done-on-arrival)
Retro-ticket the two already-shipped viewer fixes so the board reflects reality. No re-implementation;
each ticket documents the merged commit and carries a render-smoke AC proving the shipped code renders.

### Phase 1 — Staleness/version signal (foundation)
`tools_hash` + `server_info` tool + `--print-version` in `mcp_server.py`. This is a prerequisite for
the harness (Phase 2) which asserts `server_info`, and for discoverability assertions (Phase 3).

### Phase 2 — Agent-loop acceptance harness
`agent_smoke.py`: the create → reference → path-attach → repoint → render proof. Always-on stdlib gate
(asset 200 + `--dump-dom` repoint) plus the **Node-CDP** `naturalWidth` check (fail-loud-skip on no
Chrome OR no Node). The core deliverable — the repeatable proof.

### Phase 3 — Discoverability lock-in + docs sweep
Extend `mcp_smoke.py` with the discoverability + `server_info` assertions; sweep docs for the new tool
and the reconnect guidance.

## Non-goals

- **Forcing the client to reconnect / hot-reloading a running stdio server.** Structurally impossible
  from the server side; we *signal* staleness, we do not fix it. Stated honestly in tool text + docs.
- **Auth / multi-tenant identity.** Unchanged; roles stay attribution, not security.
- **Any change to `app.py` routes, the asset storage, or the viewer's render code.** The loop already
  works (measured); this epic proves and guards it, it does not re-engineer it.
- **Re-doing the shipped path/instructions/get_source/table/lightbox work.** Fold in + retro-ticket
  only.
- **A capability-negotiation protocol.** Over-built for a signal whose only remedy is "reconnect."
- **Asserting render fidelity of math/mermaid/highlight in the agent harness.** The harness proves the
  *image-embed* loop; other render surfaces have their own smokes.

## Key constraints

Hard rules the implementation must not violate (the repo's footguns, made specific):

- **Stdlib-only, zero pip — binds the SERVICE RUNTIME, not test tooling.** No runtime dependency: the
  MCP wrapper stays a thin, stateless proxy and `app.py`/`mcp_server.py` add nothing pip-installed.
  This rule does **not** bind dev/CI harnesses: the repo already drives headless Chrome over CDP via
  **Node's built-in `WebSocket`** (sprint-09 render-evidence README; sprint-11 close) with zero
  installs, so the render-check uses **that** pattern. **Do not hand-roll a stdlib RFC6455 WebSocket
  client** to satisfy a runtime rule that does not apply here — it is a fragile maintenance surface
  (framing edge cases, Chrome flag/endpoint drift) for no compliance gain. `agent_smoke.py`'s
  always-on gate stays stdlib (`urllib` + `--dump-dom` parse); only the `naturalWidth` layer uses Node.
- **A 200 is not a render; a repointed `src` is not a loaded image.** The harness's render half MUST
  assert `naturalWidth > 0` via the Node-CDP check, not stop at HTTP 200 or a `--dump-dom` `src` grep.
  (The `--dump-dom` grep proves *repoint*; it is the always-on gate, not the render proof.)
- **`render-smoke.sh` is a flat matcher** (`tag`, `.class`, `tag.class`, `#id`; no combinators/spaces —
  a space exits 2 as bad usage). To assert an `<img>` inside `#article`, pass **two selectors**
  (`'img' '#article'`), never `'#article img'`. (For the load assertion, use the CDP check, not
  render-smoke.)
- **No `do_HEAD` — HEAD requests 501.** Any header check (asset `Content-Type`) must use a **GET
  header-dump** `curl -sD - -o /dev/null <url>`, never `curl -sI` (the 501 page lies about headers).
- **Live instance is on :8139.** All tests use **throwaway containers on a different port** (e.g.
  `:8155`), never `docker compose` (compose binds :8137) and never the live :8139 container.
- **Chrome OR Node may be absent → fail/skip LOUD.** The Node-CDP render check exits with a distinct
  non-pass code and prints SKIPPED when **no Chrome or no Node** is found (matching `render-smoke.sh`
  exit 3); it never silently passes. State the Node dependency of the render half in the harness header
  so "no Node" skips loudly, exactly like "no Chrome."
  When emulating a themed pane is ever needed, use `--blink-settings=preferredColorScheme=0/1` or CDP
  `Emulation.setEmulatedMedia`, never `--force-dark-mode` (this epic's render check is theme-agnostic —
  it asserts `naturalWidth`, not colour — so no emulation flag is required).
- **Reconnect is structural.** The signal detects staleness; it cannot remediate. Say so in every
  surface (tool description, `INSTRUCTIONS`, docs).
- **`mcp_server.py` is NOT containerized** (verified: `Dockerfile:8` copies `app.py viewer.html
  dashboard.html`; it is an operator-side stdio process). So **no `Dockerfile COPY` change** is needed
  for the wrapper edits, and the new `agent_smoke.py`/the existing `mcp_smoke.py` are dev/CI scripts,
  not served files — also no `COPY`. (Stated explicitly so a reviewer doesn't flag a missing COPY.)
- **Don't break the existing 15 tools or `mcp_smoke.py`'s assertions.** Adding `server_info` makes it
  16; the existing `mcp_smoke.py` asserts *exactly 15* and an exact name set (`mcp_smoke.py:63-67`) —
  that assertion must be **updated to 16** in the same change, or `mcp_smoke.py` fails. This is a
  required edit, not optional.
- **Europe/London dates; `Co-Authored-By: Claude` trailer; conventional subject with the ticket ID.**
- **Validation gate:** `python3 -m py_compile app.py` (and `py_compile mcp_server.py agent_smoke.py
  mcp_smoke.py`). No test framework — the harnesses ARE the proof. (`agent_smoke.py`'s render layer
  shells out to Node for CDP; the Python file still py_compiles.)

## Preferred execution order

1. **MR-038 / MR-039 (Phase 0 retro-tickets)** — reconcile the board first; they're already `done`,
   so they unblock nothing but make the tracker honest before new work lands.
2. **MR-040 (Phase 1)** — `tools_hash` + `server_info` + `--print-version`. Foundation; Phases 2–3
   assert it.
3. **MR-041 (Phase 2)** — `agent_smoke.py`. Depends on MR-040 (asserts `server_info`).
4. **MR-042 (Phase 3)** — `mcp_smoke.py` discoverability + `server_info` assertions. Depends on MR-040.
5. **MR-043 (Phase 3)** — docs sweep. Depends on MR-040 (documents `server_info`/reconnect); must be
   `done` before sprint-12 closes (docs-sweep is not carry-over-eligible).

## Ticket breakdown

Create in `tickets/` after G1. IDs start at **MR-038** (highest existing is MR-037). Sprint **sprint-12**.

| ID | Title | Layer | Phase | Depends on |
|----|-------|-------|-------|-----------|
| MR-038 | Retro: GFM table CSS in the viewer (done-on-arrival, `dae815e`) | ui | 0 | — |
| MR-039 | Retro: click-to-zoom lightbox in the viewer (done-on-arrival, `2ed9593`) | ui | 0 | — |
| MR-040 | MCP staleness signal: `tools_hash` + `server_info` tool + `--print-version` | svc¹ | 1 | — |
| MR-041 | `agent_smoke.py` + Node-CDP render check: agent-loop render-proof (create→path-attach→repoint→naturalWidth>0) | svc¹ | 2 | MR-040 |
| MR-042 | `mcp_smoke.py`: assert `server_info` + the discoverability contract | svc¹ | 3 | MR-040 |
| MR-043 | Docs sweep: `server_info`/16-tool count + reconnect-on-stale guidance | docs | 3 | MR-040 |

¹ `mcp_server.py` and the smokes are not `app.py`/the HTTP service and not a served `ui` asset; the
process `layer` taxonomy (`svc | ui | infra | docs`) has no `mcp` value. These are tagged **`svc`** as
the closest fit (the service's MCP surface + its harnesses). **The G1 staff-critic confirmed this call
and that adding an `mcp`/`tooling` layer would be process scope-creep, correctly deferred (NIT-3)** —
so it is settled, not to be relitigated at G7; a layer change stays out of this epic's scope.

**Retro-ticket shape (MR-038/039):** `status: done` on arrival, `updated: 2026-06-19`, Work log naming
the merged commit + files, Validation citing the render-smoke below. One ticket each (not combined):
they are independent commits touching different features (table CSS vs lightbox), so two tickets keep
the board's commit→ticket mapping 1:1 and let each carry its own targeted render AC.

## Risks + mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| **CDP render check is fragile** (handshake/framing across Chrome versions; `/json/new` disabled in new headless). | Medium | Use the **repo's established Node built-in-`WebSocket` CDP pattern** (sprint-09 render-evidence README; sprint-11 close), **not** a bespoke stdlib RFC6455 client — the framing/handshake is the platform's, not ours to maintain. Launch Chrome with the URL as argv and pick the `type=="page"` target from `GET /json` (measured working). On any CDP error, exit fail-loud (code 3), never silent pass. Document the headless-flag + Node assumptions in the harness header. Fallback if pure-no-Node is ever mandated: `--dump-dom` repoint gate + manual G7 spot-check — never a new WS client. |
| **Chrome OR Node absent in CI / a clone** → render half can't run. | High (some envs) | Two-tier exit: the always-on gate (asset-served HTTP + `--dump-dom` repoint, **stdlib/Node-free**) always runs; the `naturalWidth` render half prints SKIPPED + a distinct exit (3) when **no Chrome or no Node** — fail-loud, matching `render-smoke.sh`. G7 runs it on the dev mac where Chrome + Node are present (verified). |
| **`tools_hash` churns on cosmetic edits** (a description typo fix changes the hash). | Medium | That's the *intended* semantics for tool/instruction text — any agent-visible change should signal "reconnect." The human-set `version` stays the coarse marker; `tools_hash` is the fine one. Document both. Don't hash internal/private constants, only `TOOLS` + `INSTRUCTIONS` (the agent-visible surface). |
| **Updating `mcp_smoke.py`'s "exactly 15 tools" assertion is forgotten** → smoke breaks. | Medium | MR-040's AC explicitly requires updating the count/name-set assertion to 16 in the same change; MR-042 re-asserts it. Called out in Key constraints. |
| **`server_info` tool's local dispatch** (it doesn't hit HTTP) breaks the uniform `route()`→`http()` flow. | Low | Handle it as an explicit branch in `handle_tools_call` *before* `route()`, returning a local JSON result; `route()` stays HTTP-only. **Hard AC (NIT-2):** MR-040's "no service running / no `MDREVIEW_BASE`" smoke (in Verification) is a **named acceptance criterion**, not optional, so a future refactor that routes `server_info` through `route()`/`http()` fails the smoke loudly. |
| **Retro-tickets get treated as new work** and re-implement shipped code. | Low | Both marked `done`-on-arrival with the commit hash; AC is "the *already-merged* code renders," verified by render-smoke, not by editing the viewer. |
| **Asymmetry**: the harness proves a *light-background* PNG renders; a white-on-transparent figure is the unsupported direction. | Low | Named a non-goal; the harness fixture is a normal PNG (the supported direction) — it does not claim the unsupported one. Matches the shipped image-mat guidance in `CLAUDE.md`. |

## Verification

Every command uses a **throwaway container on a non-:8139 port** (example `:8155`), never `docker
compose`, never the live :8139. Gate: `python3 -m py_compile` on every touched `.py`.

**Throwaway container setup (used by several tickets):**
```bash
cd mdreview-service
docker build -t mdreview-probe .                         # infra-style build check
docker rm -f mdreview-probe 2>/dev/null
docker run -d --name mdreview-probe -p 8155:8080 mdreview-probe
BASE=http://localhost:8155
# … run the per-ticket checks below …
docker rm -f mdreview-probe; docker rmi mdreview-probe    # cleanup
```

### MR-038 — Retro: table CSS
- `python3 -m py_compile app.py` (no py change, but the gate runs).
- Render-smoke from the rebuilt image, asserting a table actually renders (post a markdown table,
  then assert the `<table>` node):
```bash
md='# t\n\n| a | b |\n|---|---|\n| 1 | 2 |\n'
id=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
      -d "{\"markdown\":\"$md\",\"title\":\"tbl\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
RENDER_SMOKE_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  bash scripts/render-smoke.sh "$BASE/review/$id" 'table' '#article'
# expect: ok: table (>=1) , ok: #article (1)
```

### MR-039 — Retro: lightbox
- Render-smoke asserts the `#lightbox` overlay node and a figure `img` both exist in the rendered DOM
  (the click handler at `viewer.html:548-552` toggles `display`; node presence is the DOM proof):
```bash
# (reuse the create+attach image flow from MR-041's setup to get an #article img)
RENDER_SMOKE_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  bash scripts/render-smoke.sh "$BASE/review/$id" '#lightbox' 'img' '#article'
# expect: ok: #lightbox (1), ok: img (>=1), ok: #article (1)
```

### MR-040 — Staleness signal

**Acceptance criteria (named, not just commands):**
- `tools_hash` is computed by a single `_tools_hash()` helper over a **single canonical input** —
  `json.dumps(TOOLS, sort_keys=True)` **+** the `INSTRUCTIONS` text — and **every** surface
  (`serverInfo.tools_hash`, the `server_info` tool, and `--print-version`) returns that **same**
  helper's output, so on a fresh checkout all three are **byte-identical by construction**, not by
  luck. (NIT-1.)
- **Honest staleness scoping (SHOULD-1).** The `server_info` tool **reports the running process's**
  `tools_hash`/version; the tool description, `INSTRUCTIONS`, and MR-043's docs state plainly that
  **comparison-to-on-disk is a human/CI step (`--print-version`)** and that an **MCP-only agent
  cannot self-detect staleness** (no on-disk comparand over MCP) — it surfaces its version for the
  human/CI to compare; the remedy is invariant (**reconnect**). No surface may phrase this as "the
  agent detects staleness."
- The `server_info` tool **dispatches locally in the wrapper** and returns **with no service
  running** (it reports the wrapper, not HTTP) — a hard AC (see NIT-2 below).

**Commands:**
- `python3 -m py_compile mcp_server.py`.
- On-disk version (no stdio loop):
```bash
python3 mcp_server.py --print-version
# expect: {"version": "...", "tools_hash": "<12 hex>"}  and exit 0
```
- `server_info` tool over stdio, **with no service running** (it reports the wrapper, not HTTP) —
  this is the hard "local-dispatch, no BASE" AC (NIT-2): the tool must succeed with no `MDREVIEW_BASE`
  set and no service reachable, so a future refactor that routes `server_info` through
  `route()`/`http()` fails this smoke loudly:
```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"server_info","arguments":{}}}' \
 | python3 mcp_server.py | python3 -c "import sys,json; \
   ls=[json.loads(l) for l in sys.stdin if l.strip()]; \
   info=json.loads(ls[-1]['result']['content'][0]['text']); \
   print('tools_hash' in info and info['tool_count']==16 and 'server_info' in info['tool_names'])"
# expect: True   (and: ran with no service / no MDREVIEW_BASE → confirms local dispatch)
```
- **Three-way hash identity (NIT-1).** One assertion pins that `serverInfo.tools_hash` (from
  `initialize`) **==** the `server_info` tool's `tools_hash` **==** `--print-version`'s `tools_hash`
  on a fresh checkout. This belongs in `mcp_smoke.py` (extended in MR-042) so it stays enforced:
```bash
disk=$(python3 mcp_server.py --print-version | python3 -c "import sys,json;print(json.load(sys.stdin)['tools_hash'])")
# init_hash = ls[0]['result']['serverInfo']['tools_hash'];  tool_hash = info['tools_hash'] (from above)
# assert: init_hash == tool_hash == "$disk"
```

### MR-041 — Agent-loop harness (`agent_smoke.py` + Node-CDP render check)

**Scope note (SHOULD-2):** the render proof uses the repo's **Node built-in-`WebSocket` CDP** pattern,
**not** a bespoke stdlib RFC6455 client. The harness is `agent_smoke.py` (stdlib) **plus** a small
Node-CDP `naturalWidth` check it invokes; the always-on gate (asset-served + `--dump-dom` repoint) is
stdlib-only and runs even without Node/Chrome.

- `python3 -m py_compile agent_smoke.py`.
- Full run against the throwaway container — drives `mcp_server.py` over stdio, no human curl:
```bash
MDREVIEW_BASE=$BASE python3 agent_smoke.py
# expect (Chrome+Node present): "PASS: agent loop renders — asset 200 image/*, <img> repointed,
#                                AND #article img naturalWidth>0"; served asset url == img.src; exit 0
# expect (no Chrome OR no Node): gate PASS (asset 200 + repoint), render half "SKIPPED: no Chrome/Node",
#                                exit 3 (fail-loud — never a silent pass)
```
- The harness internally performs (measured-working sequence):
  1. `initialize` → `tools/call create_review` with markdown referencing `/assets/<fig>.png`.
  2. write a real PNG to a temp file; `tools/call attach_asset {id, name:"/assets/<fig>.png", path:<tmp>}`
     — exercises the **path** branch (`mcp_server.py:282-293`); assert `stored` returned, `isError` false.
  3. **Always-on gate (stdlib, no Chrome/Node):** `GET {base}/api/reviews/{id}/asset/{stored}` via
     stdlib `urllib` → assert `200` + `Content-Type` starts `image/` (header-dump via `urllib`, never
     `curl -sI`); **and** headless Chrome `--dump-dom` of `/review/{id}` parsed with stdlib HTML →
     assert the rendered `<img src>` is the served asset URL (the **repoint** proof).
  4. **Render proof (Node-CDP):** launch headless Chrome with `/review/{id}` as argv; via the **Node
     built-in-`WebSocket` CDP** check, `Runtime.evaluate`
     `Array.from(document.querySelectorAll('#article img')).map(i=>({src:i.src,nw:i.naturalWidth}))`;
     assert `nw>0` and `src == {asset url}`. (Measured: returns `nw=1` for a 1×1 PNG.) **Skip loudly**
     (exit 3, printed SKIPPED) if Chrome **or** Node is absent — step 3's gate still passed.
  5. `tools/call delete_review` cleanup.
- Independent cross-check the harness should match (a reviewer can run by hand):
```bash
# the manual equivalent of the step-3 repoint gate (proves repoint, not yet decode):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --no-sandbox --virtual-time-budget=3000 --dump-dom "$BASE/review/$id" \
  | grep -o '<img[^>]*src="[^"]*asset/[^"]*"[^>]*>'
# expect: the <img> src repointed to .../asset/<stored>.png (DOM proof of repoint; naturalWidth via the
#         Node-CDP check in step 4 proves the decode)
```

### MR-042 — Discoverability lock-in (`mcp_smoke.py`)
- `python3 -m py_compile mcp_smoke.py`.
- `MDREVIEW_BASE=$BASE python3 mcp_smoke.py` → `PASS: all MCP smoke assertions hold`. New/changed
  assertions:
  - tool count is **16** and the name set includes `server_info` (the existing exact-15 check updated).
  - `serverInfo.tools_hash` present on `initialize`.
  - **Three-way hash identity (NIT-1):** `serverInfo.tools_hash` == the `server_info` tool's
    `tools_hash` == `python3 mcp_server.py --print-version`'s `tools_hash` — byte-identical on a fresh
    checkout, proving all three derive from the one `_tools_hash()` over the one canonical input.
  - `attach_asset` description mentions `path`; `get_source` description tells when to read; the
    `INSTRUCTIONS` text names path-attach, get_source, and the comment loop.
  - **Honest-staleness text (SHOULD-1):** assert `INSTRUCTIONS`/the `server_info` description state
    that comparison-to-on-disk is a human/CI step and **do not** claim the agent self-detects
    staleness (a regression-lock so the scoping can't silently drift back).
- All **existing** 22 assertions still pass (run the unchanged suite end-to-end).

### MR-043 — Docs sweep
- Grep the docs reflect the new surface (no render needed; docs layer):
```bash
grep -l "server_info" README.md AGENTS.md CLAUDE.md docs/future-mcp.md   # all four mention it
grep -c "16 tools\|reconnect" CLAUDE.md README.md                          # tool count + reconnect remedy present
```
- The "15 tools" string is updated to 16 wherever it appears (verified: `CLAUDE.md:137` and
  `docs/future-mcp.md:45` both say "15 tools" — correct both to 16, plus add `server_info` to the
  tool enumeration in `CLAUDE.md:137`).
- **Honest-staleness wording (SHOULD-1):** confirm the staleness section says the **human/CI**
  compares `server_info`'s running hash to `--print-version`, and **no** doc claims the agent
  self-detects staleness:
```bash
grep -rin "human\|CI\|--print-version" docs/future-mcp.md CLAUDE.md | grep -i stale  # comparison attributed to human/CI
! grep -rin "agent detects stale\|agent.*self-detect" README.md AGENTS.md CLAUDE.md docs/future-mcp.md  # must find nothing
```

### Sprint-12 G7 (whole-epic)
- Rebuild the container; `curl /healthz` → `{"ok": true}`; `curl /api/reviews` → 200.
- A product page (`viewer.html`) was touched this sprint (the retro-tickets), so per G7: run
  `scripts/render-smoke.sh` against `/review/{id}` asserting `#article`, `table` (if present), `img`,
  `#lightbox`, plus a screenshot under `reviews/sprint-12-render-evidence-*`.
- Run `agent_smoke.py` (the epic's headline proof) and record its PASS + the proved `tools_hash`.
- Independent `staff-critic` sprint-close review recorded in `reviews/sprint-12-close-review-*.md`.

## Assumptions & open questions

Proceeding on these (invoked autonomously, no `--ask`). None is a BLOCKER-FOR-HUMAN — each has a safe
default that does not risk wasting the sprint.

- **[load-bearing] `agent_smoke.py` is a sibling, not an extension of `mcp_smoke.py`.** Assumption:
  sibling (Decision 2). Justification: the fast protocol smoke must stay browser-free and quick; the
  agent loop needs Chrome + CDP + a skip path. A reviewer could prefer one file; the cost of being
  wrong is a file move, not a redesign — safe to proceed.
- **[load-bearing] The staleness signal is `tools_hash` + a `server_info` tool, not a service
  `/healthz` build field — and detection is honestly scoped (SHOULD-1, resolved).** Assumption:
  wrapper-side hash (Decision 1), and the agent **surfaces** its running hash while the **human/CI
  compares** it to `--print-version` (an MCP-only agent has no on-disk comparand and cannot
  self-detect). Justification: the staleness is in the wrapper process, which versions independently
  of the HTTP service; a service field as the wrapper's own version wouldn't detect a stale wrapper.
  Option (b)'s other form — the service publishing the *expected* wrapper hash as an MCP-reachable
  comparand — is named a non-goal/future option, not built. Safe default; honestly scoped as
  surface-and-human/CI-compare, remedy invariant (reconnect).
- **[load-bearing] Discoverability needs no new code — only a verification ticket** (Decision 3).
  Assumption: `instructions` + tool descriptions already cover path-attach/get_source/comments
  (verified in `mcp_server.py`). If a reviewer finds a genuine gap, MR-042 widens to add the missing
  text — but the verified state is "covered," so the safe default is verify-only.
- **[minor] Ticket layer for `mcp_server.py`/smokes is `svc`.** The taxonomy has no `mcp` value; `svc`
  is the closest. Flagged in the breakdown; trivially re-taggable.
- **[minor] The render-check is the repo's Node-CDP pattern, invoked from `agent_smoke.py`** (SHOULD-2,
  resolved), **not** a bespoke stdlib RFC6455 WS client and not a new `scripts/*.sh`. Justification:
  the repo already drives CDP via Node's built-in `WebSocket` (sprint-09 render-evidence; sprint-11
  close) with zero pip; the "stdlib-only" rule binds the service runtime, not test tooling. The render
  half depends on Node + Chrome and **skips loudly** if either is absent; the always-on gate
  (asset-served + `--dump-dom` repoint) stays stdlib-only. Fallback if pure-no-Node is ever mandated:
  `--dump-dom` repoint gate + manual G7 spot-check — never a new WS client.
- **[minor] Throwaway-container port :8155** in examples — any free non-:8137/:8139 port works.

## Least-sure decision

**Resolved at G1 (was the render-check transport).** My original least-sure call — a hand-rolled
stdlib RFC6455 WS client for the render half — is **dropped**: the staff-critic agreed it
over-engineered a runtime-only rule, and Decision 2 now uses the repo's established **Node built-in-
`WebSocket` CDP** pattern (zero pip, already the render-evidence toolchain), with a documented
`--dump-dom`-repoint + manual-spot-check fallback if pure-no-Node is ever mandated. No new WS code
either way.

**Current least-sure call: the Node dependency of the render half.** The always-on gate (asset-served
+ `--dump-dom` repoint) is stdlib-only and Node-free, but the `naturalWidth>0` proof now requires Node
**and** Chrome. That is the repo's own render-evidence toolchain (so it is defensible), but it does
widen the agent-loop proof's environment surface, and a clone without Node sees the render half skip
(loudly). The mitigation is the fail-loud skip + the documented no-Node fallback. If a reviewer wants
the headline render proof to need *no* Node, the honest cost is dropping `naturalWidth` from the
automated gate to a manual G7 spot-check — that trade (automated decode-proof vs. zero-Node) is the
one call I'd most want a second opinion on.

## Review resolutions

Applied by the plan author after the independent G1 staff-critic review
(`reviews/mcp-agent-effectiveness-plan-review-2026-06-19.md`, verdict PASS-WITH-CONDITIONS).

- **2026-06-19 — SHOULD-1 (staleness overclaims "detectable by the agent"):** adopted the critic's
  option (a) honest scoping throughout. Rewrote the Product Goal, Decision 1 (item 3 "Surface, not
  self-detect" + the "Why"), the MCP-wrapper `INSTRUCTIONS` bullet, MR-040's ACs/Verification, MR-042's
  regression-lock assertions, the MR-043 docs sweep + its grep checks, and the load-bearing assumption:
  `server_info` lets the agent **report** the running hash; **comparison-to-on-disk is a human/CI step**
  (`--print-version`); an **MCP-only agent has no comparand over MCP and cannot self-detect** staleness;
  the remedy (reconnect) is invariant. No surface may say "the agent detects staleness." Option (b)
  (service publishes the expected wrapper hash as an MCP-reachable comparand) is named an explicit
  **non-goal/future option**, not built. MR-040's design (`tools_hash`, `server_info`, `--print-version`)
  is unchanged.
- **2026-06-19 — SHOULD-2 (drop the bespoke stdlib RFC6455 WS client):** re-specified MR-041 to use the
  repo's established **Node built-in-`WebSocket` CDP** render check (verified pattern: sprint-09
  render-evidence README; sprint-11 close), **not** a hand-rolled WS client. Two layers: (i) always-on,
  stdlib-only gate = asset serves 200+`image/*` (urllib) **and** the viewer **repoints** the `<img>`
  (`--dump-dom` + stdlib HTML parse); (ii) render proof = `naturalWidth>0` via Node-CDP, **fail-loud
  skip on no Chrome OR no Node**. Narrowed the "stdlib-only/zero-pip" constraint to bind the **service
  runtime, not test tooling**. Documented fallback (pure-no-Node) = `--dump-dom` repoint + manual G7
  spot-check, never a new WS client. Updated Decision 2 (heading/context/chosen-shape/why), the
  Harnesses subsection, Key constraints (two bullets), the Risks table (two rows), MR-041's title +
  Verification, the minor assumption, and the Least-sure decision (now resolved; the new least-sure
  call is the render half's Node dependency).
- **2026-06-19 — NIT-1 (`--print-version` vs running hash contract):** added a named MR-040 AC + an
  `mcp_smoke.py` assertion (MR-042) pinning **three-way byte-identity** — `serverInfo.tools_hash` ==
  the `server_info` tool's `tools_hash` == `--print-version`'s `tools_hash` — all derived from one
  `_tools_hash()` over the one canonical input (`json.dumps(TOOLS, sort_keys=True)` + `INSTRUCTIONS`),
  so the fresh case is identical by construction, not luck.
- **2026-06-19 — NIT-2 (`server_info` no-service smoke as a hard AC):** promoted the "runs with no
  service / no `MDREVIEW_BASE`" check to a **named MR-040 acceptance criterion** (in the AC list, the
  Verification command, and the Risks-table mitigation), so a refactor that routes `server_info`
  through `route()`/`http()` fails the smoke loudly.
- **2026-06-19 — NIT-3 (`layer: svc` for `mcp_server.py` + smokes; don't expand the taxonomy):**
  recorded in the ticket-breakdown footnote that the staff-critic **confirmed** `svc` is the right call
  and that adding an `mcp`/`tooling` layer is deferred process scope-creep — settled, not to be
  relitigated at G7. No taxonomy change.
