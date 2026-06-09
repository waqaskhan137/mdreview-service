---
review_of: epics/mcp-wrapper-plan.md
gate: G1
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-09
verdict: PASS (round 2)
status: resolved
---

# G1 plan review — mcp-wrapper epic (round 1)

Independent review by `staff-critic` (not the author). First product feature through the gates.
**Contract verification: all 8 tool->endpoint mappings correct** (verbs, response shapes, and
`app.py` line anchors spot-verified: POST `/api/reviews` 201 + urls, `RID` regex, `create_review`
provenance signature, `update_source` snapshots `round-0` on first PUT since `revision` starts at
0, `get_history` list/single via optional `round` arg matching the `(\d+)` capture). Cite-by-name
convention followed; the stdlib-vs-SDK call and newline-delimited stdio framing are the right
decisions, adequately de-risked behind `read_message`/`write_message` + build-time-verify.

## BLOCKER

**B1 — "HTTP service unchanged" (the epic's defining constraint) is enforced only in prose,
citing a G4 condition that does not exist — the exact MR-012 defect class.** The plan says "G4
asserts `git diff` shows no change to `app.py`/...", but the **G4 pass-condition row** has no
out-of-layer diff assertion (it is `py_compile` + ui render-smoke + "author self-checked the AC").
The planner is bound by its own rule (MR-012, shipped 2026-06-09: enforcement must be wired into
the gate row; citing a row alone is insufficient), and the single most important constraint
violates it.
**Required:** make "`git diff` against the branch base shows no change to
`app.py`/`viewer.html`/`dashboard.html`/`static/**`/`Dockerfile`/`docker-compose.yml`" a
**per-ticket acceptance criterion** on MR-015..MR-017, so it rides G4's existing "author
self-checked the AC" clause. Delete the free-floating "G4 asserts git diff" prose.

## SHOULD-FIX

- **S1 — the diff command false-passes after commit.** `git diff --stat <paths>` (no ref)
  compares working tree to index and reports nothing once the edit is committed. Use
  `git diff --stat <merge-base>...HEAD -- <paths>`. Add `docker-compose.yml` to the watched paths
  (it's `infra`; "service unchanged" must cover deploy config).
- **S2 — "confirm against the MCP spec" is not a testable AC.** Posture is right, but pin it: MR-015/
  MR-016 ACs must name a concrete target `protocolVersion` (dated string) and assert the exact
  `initialize` result fields and the `content[0].text` / `isError` envelope shape the harness
  checks.
- **S3 — missing non-goal: tools-only (no MCP resources/prompts).** `initialize` correctly
  advertises only `{tools:{}}`; add the explicit non-goal to foreclose scope drift.
- **S4 — the pipe-smoke hangs unless the server flushes per message and exits on stdin EOF.** Add a
  one-line MR-015 AC: flush stdout after each response, exit cleanly on EOF — the whole
  verification strategy rests on the pipe harness not hanging.

## NIT
- **N1 — `svc` layer tag on tickets forbidden from touching `app.py`.** Pragmatic (drives
  `py_compile`, no `docker build`) and explained, but name the tension in one line.

## Open questions for the author
- MR-016 error mapping: unknown tool name -> JSON-RPC `-32601/-32602` or an `isError` result?
  Pick one so MR-016's smoke can assert it.
- The wrapper returns the service's `review_url` (Host-derived). Does the docs ticket (MR-018)
  need `MDREVIEW_PUBLIC_BASE` guidance so the agent hands the human a reachable URL?

## Verdict: PASS-WITH-FIXES
Required before sign-off: B1 (hard-blocking — wire the service-unchanged check into per-ticket ACs)
+ S1-S4 (fast, same revision). Routed to the author `mdreview-planner`.

## Resolution log
- 2026-06-09 — round 1 recorded; routed to the author for revision. status: open.
- 2026-06-09 — author revised; **round-2 re-review: PASS**. B1 resolved (service-unchanged is now
  a per-ticket AC on MR-015/016/017 riding G4's "author self-checked the AC" clause; phantom "G4
  asserts git diff" prose deleted). S1 (base-relative diff + `docker-compose.yml`), S2 (pinned
  `protocolVersion: 2025-06-18` + exact `initialize`/`content`/`isError` assertions), S3
  (tools-only non-goal), S4 (flush-per-message + exit-on-EOF AC) all resolved. Open questions
  decided: unknown tool -> `-32602` asserted in MR-016; `MDREVIEW_PUBLIC_BASE` guidance -> MR-018.
  Author also audited for a second MR-012-class phantom-gate-condition; none found. G1 **cleared**;
  tickets may be created. status: resolved.
