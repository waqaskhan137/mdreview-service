---
review_of: epics/mcp-agent-effectiveness-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G1 review — mcp-agent-effectiveness plan

**Verdict: PASS-WITH-CONDITIONS.** The plan is well-grounded — every code citation I
checked is accurate, the design forks are argued (not defaulted), and the right-sizing is
honest (no `app.py` change, retro-tickets done-on-arrival, discoverability scoped to
verification). Two conditions block a clean pass: the staleness signal as written does not
deliver the brief's "detectable by **the agent**" — only "detectable by a human/CI with a
shell" — and the bespoke stdlib RFC6455 WebSocket client reinvents a tool the repo already
has (Node's built-in `WebSocket` CDP pattern) to satisfy a "stdlib" rule that does not apply
to test tooling. Both are correctable within the tickets without a redesign; neither changes
the epic's shape.

## Verification of load-bearing claims (all confirmed against code)

- `SERVER_INFO = {"name":"mdreview-mcp","version":"0.1.0"}` at `mcp_server.py:31`; surfaced
  in `serverInfo` on `initialize` at `mcp_server.py:330-339`. ✓
- `TOOLS` is exactly 15 (`mcp_server.py:54-204`); `mcp_smoke.py:63-67` asserts an exact
  15-name set — the plan's "must update to 16" is real and correctly flagged. ✓
- `attach_asset` `path` branch reads+encodes locally at `mcp_server.py:282-293`
  (`open(os.path.expanduser(args["path"]))`); description prefers `path`
  (`mcp_server.py:124-131`). ✓
- `INSTRUCTIONS` (`mcp_server.py:36-47`) names attach_asset, get_source, and the comment
  loop. ✓ `get_source` description at `mcp_server.py:83-84`. ✓
- `main()` (the `--print-version` insertion point) is at `mcp_server.py:366-373`. ✓
- Service: `POST …/assets` decodes b64 + stores (`app.py:556-572`); serve path is
  `GET /api/reviews/{id}/asset/{stored}` via manifest, never path-joining the segment
  (`app.py:620-632`); `/healthz` at `app.py:420`; `GET …/source` at `app.py:464`. The
  planner's correction of the brief's `/asset/{stored}` shorthand to the real prefixed path
  is right. ✓
- Viewer: `rewriteAssetImages` repoints by full-src-then-basename, leaves http/data/
  protocol-relative untouched (`viewer.html:270-285`); `#lightbox` markup at
  `viewer.html:170`, CSS at `:42-44`, handler at `:547-552`; table `img` CSS at `:41`. ✓
- Retro commits exist and are viewer-only: `dae815e` (table CSS, +4) and `2ed9593`
  (lightbox, +12). ✓
- `render-smoke.sh` is a flat matcher (`tag/.class/tag.class/#id`; a space → exit 2),
  `--dump-dom` serializes markup (cannot read `naturalWidth`), exits 3 fail-loud on no
  Chrome (`scripts/render-smoke.sh:22-58,72`). The "a 200 is not a render / a repointed src
  is not a loaded image" gap is genuine. ✓
- `Dockerfile:8-9` copies `app.py viewer.html dashboard.html` + `static/`, not
  `mcp_server.py` or the smokes — the "no COPY change needed" claim is correct. ✓
- Docs say "15 tools" at `CLAUDE.md:137` and `docs/future-mcp.md:45` (MR-043's targets). ✓

## Ruling on #1 — Is agent-detection real?

**No, not as written — it is human/CI-with-shell detection wearing an "agent" label.** Trace
it end-to-end: `server_info` hands the agent X (`tools_hash` of the **running** process).
The only comparand Y (the on-disk hash) is produced by `python3 mcp_server.py
--print-version` — a **shell** command. An agent that speaks only MCP has X and nothing to
compare it to. Decision 1's own contract sentence — *"if `server_info.tools_hash` differs
from the value the repo prints for the current `mcp_server.py`"* — silently assumes the agent
can run the repo command. On the dev mac where the operator has a shell, this works; for the
"autonomous agent, no human, no curl" actor the brief and Product Goal name, it does not.

This is genuinely useful for the **human/CI** half of the brief's "agent **and** human" — keep
it. But the plan must do one of:
- **(a) Scope the claim honestly.** Say plainly in the plan, tool text, and docs: *the agent
  reads its running `tools_hash` and reports it; comparison-to-on-disk is a human/CI step
  (`--print-version`). The agent's structural remedy on any suspected staleness is the same
  single action regardless — reconnect.* This is defensible because the remedy is invariant.
- **(b) Give the agent a comparand it can reach over MCP.** The cleanest is to have the
  **HTTP service** expose the expected `tools_hash` (e.g. in `/healthz` or a small info route)
  computed from the wrapper code it ships alongside — then `server_info` (running wrapper) vs
  a `get`-able service field (current code) is an all-MCP comparison. The plan rejects a
  service `/healthz` build field on the grounds that "the wrapper and service version
  independently" — true, but that argues against using it as the wrapper's *own* version, not
  against the service publishing the *expected* wrapper hash as a reference. This is more
  work and may not be worth it; (a) is the honest minimum.

Either closes it. What must not ship is the current phrasing, which lets "a hash nobody on the
agent side can compare" read as "the agent detects staleness." Pick (a) or (b) explicitly in
MR-040.

## Ruling on #2 — Bespoke stdlib WS client vs Node-CDP

**The reviewer's instinct is right: the hand-rolled RFC6455 client is over-engineering driven
by a misapplied constraint.** The "stdlib-only / zero pip" rule (requirement Constraints;
plan Key constraints) is about the **service runtime** — "the MCP wrapper stays a thin,
stateless proxy," "no runtime dependency." A G7 acceptance harness is dev/CI tooling, not
runtime, and this repo **already drives headless Chrome over CDP via Node's built-in
`WebSocket`** (sprint-11 close + this session's render evidence) with zero installs. Node is
already a de-facto test dependency. So the plan's own "Least-sure decision" correctly names
the cost — *"a hand-rolled WebSocket client is a genuine maintenance/fragility surface
(framing edge cases, Chrome headless flag/endpoint drift)"* — and then pays it anyway to
honor a rule that does not bind here.

The right shape is the one the reviewer sketched, and it is strictly less code:
- **Always-on, Chrome-free:** the HTTP asset-served assertion (200 + `image/*`) in
  `agent_smoke.py` over stdlib `urllib` — keep as planned.
- **Repoint proof:** `--dump-dom` src-grep (stdlib parse, already in `render-smoke.sh`'s
  wheelhouse) — keep.
- **`naturalWidth>0` render proof:** the **existing ~30-line Node built-in-`WebSocket` CDP
  pattern**, fail-loud-skip when Chrome/Node absent — instead of a new stdlib RFC6455 client.

This keeps the "a 200 is not a render" bar (the planner's strongest argument for needing a JS
eval) **without** inventing a WS client. Two notes so the swap isn't a silent constraint
break:
- Using Node makes the render half depend on Node as well as Chrome. That is fine — it is the
  repo's established render-evidence toolchain — but state it in the harness header and the
  fail-loud-skip so "no Node" skips loudly, exactly like "no Chrome."
- If the owner insists the harness be *pure Python with no Node*, then the honest fallback is
  the planner's own stated one: assert **repoint** via `--dump-dom` for the gate and treat
  `naturalWidth>0` as a manual G7 spot-check — **not** a bespoke WS client. Writing new
  protocol code to dodge a Node dependency that the repo already relies on for exactly this is
  the over-engineering the process should catch.

Net: **do not build the stdlib RFC6455 client.** Use Node-CDP (preferred) or `--dump-dom`
repoint + manual spot-check (fallback). MR-041 should pick one and say why.

## Findings

### [SHOULD] Staleness signal does not meet "detectable by the agent" as phrased
Decision 1 / Product Goal. Covered in ruling #1. Fix: MR-040 explicitly adopts (a) honest
scope-down *or* (b) a service-published expected-hash comparand; the chosen wording lands in
the tool description, `INSTRUCTIONS`, and MR-043's docs. Do not ship the current "the agent
detects" framing unqualified.

### [SHOULD] Drop the bespoke RFC6455 WebSocket client for the established Node-CDP pattern
Decision 2 / Least-sure decision / Risks ("Stdlib CDP client is fragile"). Covered in ruling
#2. Fix: MR-041 uses Node built-in `WebSocket` CDP for the `naturalWidth` check (fail-loud-skip
on no Chrome **or** no Node), or falls back to `--dump-dom` repoint + manual spot-check. The
"stdlib-only" constraint is reasserted in the plan as binding the harness — narrow it to the
service runtime so the ticket isn't held to a rule that produces worse tooling.

### [NIT] `--print-version` output contract is unspecified for the on-disk-vs-running diff
Verification (MR-040) shows `--print-version` printing `{version, tools_hash}` and separately
asserts `serverInfo.tools_hash` "equals `--print-version`'s hash." Good — but pin that the two
hashes are computed by the **same** `_tools_hash()` over the **same** canonical input
(`json.dumps(TOOLS, sort_keys=True)` + `INSTRUCTIONS`), so the "fresh" case is byte-identical
by construction, not by luck. One assertion in `mcp_smoke.py` ( `serverInfo.tools_hash` ==
the `server_info` tool's `tools_hash` == `--print-version`'s) nails it.

### [NIT] `server_info` local-dispatch path needs its own no-service smoke, as the plan says — make it a hard AC
Risks table already calls this out (the tool must return without a BASE because it reports the
wrapper, not HTTP). Confirm MR-040's AC *requires* the "no service running" assertion
(Verification already drives it with no service — good); keep that as a named AC so a future
refactor that routes `server_info` through `route()`/`http()` fails the smoke loudly.

### [NIT] `layer: svc` for `mcp_server.py` + smokes is a fine call; don't expand the taxonomy in this epic
The plan flags it and offers `svc` as closest fit (`mcp_server.py` is not `app.py` and not a
served `ui` asset). Agreed — adding an `mcp`/`tooling` layer is process scope-creep, correctly
deferred. No action; just confirming the reviewer agrees so it isn't relitigated at G7.

## Right-sizing, decomposition, verification recipe (assessed, no blocker)

- **Retro-tickets (MR-038/039) done-on-arrival with a render-smoke AC: correct.** Both commits
  are viewer-only and merged; the ACs assert the *shipped* DOM (`table`/`#article`,
  `#lightbox`/`img`/`#article`) via the flat two-selector form the script requires — they do
  not re-implement. Two tickets (not one) for 1:1 commit→ticket mapping is the right call.
- **Splitting MR-040 (signal) / MR-041 (harness) / MR-042 (smoke+discoverability) is real, not
  artificial:** different files, a genuine dependency (041 and 042 assert 040's `server_info`),
  and different test profiles (fast protocol smoke vs heavy browser harness). The
  sibling-not-extension call for `agent_smoke.py` is justified — bolting Chrome onto the
  22-assertion fast smoke would slow the always-run gate.
- **Discoverability as verify-only (MR-042) is honest.** I read `tools/list` +
  `INSTRUCTIONS` as an agent would: `attach_asset` explicitly says *prefer `path`… never emit
  base64 through your context* (`mcp_server.py:124-131`), `get_source` says read the draft on a
  resumed session (`:83-84`), and `INSTRUCTIONS` names all three flows. There is no hidden gap;
  inventing a feature here would be make-work. The regression-lock assertions are the right
  deliverable.
- **MR-043 docs-sweep correctly not carry-over-eligible** (Definition of Done / G7); its grep
  targets (`CLAUDE.md:137`, `docs/future-mcp.md:45`) are the real "15 tools" sites.
- **Verification recipe** uses throwaway containers on `:8155` (non-:8137/:8139), never
  `docker compose`, GET-header-dump not `curl -sI` (HEAD 501s), and the agent-loop ticket's
  step 4 proves the `<img>` *loaded* (`naturalWidth>0`), not merely 200 — subject to the #2
  swap (the *mechanism* of that step changes from stdlib-WS to Node-CDP; the *assertion*
  stands). The fail-loud-skip on no-Chrome matches `render-smoke.sh` exit 3. Recipe is sound.

## Should G1 pass?

**Yes — PASS-WITH-CONDITIONS.** The plan can spawn tickets now provided MR-040 and MR-041
carry the two SHOULD resolutions as explicit ACs (honest staleness scope; Node-CDP-or-
`--dump-dom`, not a bespoke WS client). Neither is a redesign; both are wording/tool-choice
calls the implementer makes inside the existing ticket boundaries. The NITs are
implementer-discretion. No BLOCKER.

## Resolution log

- **2026-06-19 — SHOULD-1 (staleness overclaims "detectable by the agent"):** resolved via the critic's option (a) honest scoping across Product Goal, Decision 1, the `INSTRUCTIONS` bullet, MR-040 ACs/Verification, MR-042 assertions, and MR-043 docs — `server_info` reports the running hash; human/CI compares to `--print-version`; an MCP-only agent cannot self-detect; remedy invariant (reconnect). Option (b) named a non-goal/future, not built. MR-040 design unchanged.
- **2026-06-19 — SHOULD-2 (drop the bespoke stdlib RFC6455 WS client):** MR-041 re-specified to the repo's Node built-in-`WebSocket` CDP pattern (sprint-09/-11 evidence), two layers (always-on stdlib gate = asset 200+repoint via `--dump-dom`; `naturalWidth>0` render proof via Node-CDP, fail-loud-skip on no Chrome OR no Node); "stdlib-only" narrowed to bind the service runtime not test tooling; pure-no-Node fallback = repoint + manual G7 spot-check, never a new WS client. MR-041 title/scope/Verification updated.
- **2026-06-19 — NIT-1 (`--print-version` vs running-hash contract):** added a named MR-040 AC + `mcp_smoke.py` assertion pinning three-way byte-identity (`serverInfo.tools_hash` == `server_info` tool's == `--print-version`'s) from one `_tools_hash()` over `json.dumps(TOOLS, sort_keys=True)` + `INSTRUCTIONS`.
- **2026-06-19 — NIT-2 (`server_info` no-service smoke as a hard AC):** the "runs with no service / no `MDREVIEW_BASE`" check is now a named MR-040 acceptance criterion (AC list + Verification + Risks mitigation), so routing `server_info` through `route()`/`http()` fails the smoke loudly.
- **2026-06-19 — NIT-3 (`layer: svc` + don't expand taxonomy):** ticket-breakdown footnote records the critic's confirmation that `svc` is correct and an `mcp`/`tooling` layer is deferred scope-creep — settled, no taxonomy change.

### Round 2 (re-review) — 2026-06-19

Delta re-review against the revised plan + Resolution log. Each Round-1 finding re-checked; code
claims the conditions turn on re-verified (no new nits, settled architecture not re-opened).

- **SHOULD-1 (staleness honestly scoped): ACCEPTED.** Option (a) landed everywhere — Product Goal,
  Decision 1 item 3 + Why, `INSTRUCTIONS`/`server_info`-description contract, MR-040 ACs, MR-042
  regression-lock, MR-043 docs grep. Every "self-detect" occurrence is a negation or the explicit
  "do not say 'the agent detects staleness'" guardrail; no positive claim survives. Option (b)
  named a non-goal/future, not built. Brief's "agent **and** human" reconciled honestly (agent
  surfaces its running hash via `server_info`; human/CI compares to `--print-version`; remedy
  invariant = reconnect). MR-043 even adds a `! grep ... "agent detects stale"` AC that must find
  nothing. Verified `SERVER_INFO`/`INSTRUCTIONS`/`serverInfo` plumbing exists as cited.
- **SHOULD-2 (no bespoke WS client): ACCEPTED.** Render proof re-specified to the repo's Node
  built-in-`WebSocket` CDP pattern — precedent verified real (sprint-09 render-evidence README +
  sprint-09 retro both document the "Node built-in WebSocket driver" over CDP). Every WS-client
  mention is a negation ("not a bespoke RFC6455 client", "do not hand-roll", "never a new WS
  client"). "Stdlib-only" narrowed to bind the service runtime, not test tooling (Key constraints).
  Pure-no-Node fallback = `--dump-dom` repoint + manual G7 spot-check, not a WS client. Always-on
  Chrome/Node-free gate (stdlib `urllib` 200+`image/*` + `--dump-dom` repoint) preserved; CDP layer
  is genuinely load-bearing (confirmed `--dump-dom` serializes markup, cannot read `naturalWidth`;
  `render-smoke.sh` exits 3 fail-loud on no Chrome — the swap matches that contract).
- **NIT-1 (three-way hash byte-identity): ACCEPTED.** Named MR-040 AC + MR-042 `mcp_smoke.py`
  assertion: `serverInfo.tools_hash` == `server_info` tool's == `--print-version`'s, one
  `_tools_hash()` over `json.dumps(TOOLS, sort_keys=True)` + `INSTRUCTIONS`, identical by
  construction.
- **NIT-2 (no-service `server_info` smoke as a hard AC): ACCEPTED.** Promoted to a named MR-040 AC
  (AC list + Verification command driving it with no `MDREVIEW_BASE` + Risks mitigation), so routing
  `server_info` through `route()`/`http()` fails the smoke loudly. (Confirmed `mcp_smoke.py` still
  asserts exactly 15 today — the "update to 16" edit is real and flagged required.)
- **NIT-3 (`layer: svc` footnote): ACCEPTED.** Ticket-breakdown footnote records the call as settled
  and defers an `mcp`/`tooling` layer as scope-creep.

**Round-2 verdict: PASS.** All 2 SHOULD + 3 NIT conditions landed; every load-bearing code claim
re-verified; no STILL-OPEN items. G1 passes — the plan may spawn tickets and proceed to sprint-12.
