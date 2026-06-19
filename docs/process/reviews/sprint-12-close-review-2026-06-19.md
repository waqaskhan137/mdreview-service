---
review_of: sprints/sprint-12.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G7 sprint-close review — sprint-12 (mcp-agent-effectiveness)

**Verdict: PASS.** I ran every proof myself against the live :8155 container, not the tickets'
word. The epic's headline acceptance bar holds: `agent_smoke.py` completes the full
create→path-attach→serve→repoint→`naturalWidth>0` loop unaided with zero human curl (exit 0),
and the fail-loud skip is real (exit 3, render half SKIPPED, gate still green). `mcp_smoke.py`
passes all 34 assertions (16 tools + the new discoverability/three-way-hash locks + the existing
suite). Both G1 SHOULDs shipped, `app.py` is untouched, and the two retro-tickets are honest
documentation of already-merged commits. No BLOCKER, no SHOULD, one NIT.

## Per-ticket AC check

| Ticket | ACs | Verdict |
|--------|-----|---------|
| **MR-038** (retro: table CSS) | render-smoke asserts `table` + `#article` render from the merged `dae815e` | **met** — `render-smoke.sh … 'table' '#article'` → `ok: table (1)`, `ok: #article (1)`, exit 0; screenshot shows a styled table. Only viewer.html commits since sprint-11 close are `dae815e`/`2ed9593` (no re-implementation). |
| **MR-039** (retro: lightbox) | render-smoke asserts `#lightbox` + `img` + `#article` from merged `2ed9593` | **met** — `render-smoke.sh … '#lightbox' 'img' '#article'` → `ok: #lightbox (1)`, `ok: img (2)`, `ok: #article (1)`, exit 0. `2ed9593` is a merged ancestor of HEAD. |
| **MR-040** (staleness signal) | one `_tools_hash()`; three-way byte-identity; local `server_info`; `serverInfo.tools_hash`; `--print-version`; honest scoping; 15→16 | **met** — single `_tools_hash()` at `mcp_server.py:223-228`; `--print-version` → `{"version":"0.1.0","tools_hash":"e6843ee24b2c"}`; `server_info` returns locally with `MDREVIEW_BASE=http://localhost:1` (dead port), `isError:false`, `tool_count:16`; three-way identity `e6843ee24b2c == e6843ee24b2c == e6843ee24b2c` even with no service. Ticket's cited hash reproduced independently. |
| **MR-041** (`agent_smoke.py`) | full loop unaided; `naturalWidth>0`; Node-CDP not bespoke WS; fail-loud-skip | **met** — full run PASS exit 0 (`nw=1`, `src==asset`, zero curl); fail-loud skip exit 3 with Node hidden. Render half uses Node's built-in `WebSocket` (`agent_smoke.py:121`); no RFC6455 client. |
| **MR-042** (`mcp_smoke.py`) | 16-tool count + name set; `serverInfo.tools_hash`; three-way identity; discoverability; honest-staleness regression-lock; existing 22 green | **met** — 34/34 assertions pass, including all new locks; existing suite still green. |
| **MR-043** (docs sweep) | `server_info` in all four docs; 15→16; reconnect/human-CI guidance; no "agent self-detects" | **met** — `server_info` present in README/AGENTS/CLAUDE/future-mcp; tool count corrected to 16; human/CI comparison + reconnect remedy stated; negative grep for agent self-detection finds nothing (only the explicit "cannot self-detect" negation). |

## Acceptance bar + G1 SHOULDs

- **`agent_smoke.py` PASSED (the acceptance bar).** Full loop unaided, exit 0, `naturalWidth=1`,
  `src==asset`, no operator curl. This is the deliverable; it is green.
- **`mcp_smoke.py` PASSED.** 34/34 assertions, exit 0.
- **SHOULD-1 (honest staleness scoping) shipped.** Every staleness surface — `INSTRUCTIONS`,
  the `server_info` tool description, and all four docs — attributes the compare to a human/CI via
  `--print-version` and states the MCP-only agent *cannot* self-detect. The only "self-detect"
  string anywhere (`mcp_server.py:216`) is a negation. No surface claims agent self-detection.
- **SHOULD-2 (no bespoke WS client) shipped.** The render check uses Node's built-in `WebSocket`
  over CDP (`agent_smoke.py:121`); the stdlib gate (asset-served via `urllib` + `--dump-dom`
  repoint parse) is Node-free. No hand-rolled RFC6455 code exists.

## Findings

### [NIT] The "no Node" skip path doesn't also exercise "no Chrome" via the PATH trick
`PATH=/usr/bin:/bin python3 agent_smoke.py` correctly skips the Node-CDP render proof loudly
(exit 3), but the stdlib `--dump-dom` repoint gate still ran because `find_chrome()` resolves
Chrome by absolute path (`agent_smoke.py:76`), which `PATH` can't hide. This is *correct*
behaviour — the gate is meant to be Chrome-independent of `PATH` — and the fail-loud contract for
the render half is proven. No change required; noted only so a future reader doesn't mistake the
still-running repoint gate for a leak. The genuine "no Chrome" branch (`find_chrome()` → None) is
covered by code inspection: it prints `SKIP repoint gate — no Chrome` and the render half skips on
`not chrome`. Evidence (a clean exit-3 with Chrome also absent) would close it fully, but it is not
a gate-blocker.

## Commands run + results

- `python3 -m py_compile app.py mcp_server.py mcp_smoke.py agent_smoke.py` → OK.
- `curl /healthz` (:8155) → `{"ok": true}`; `GET /api/reviews` → 200.
- `MDREVIEW_BASE=http://localhost:8155 python3 agent_smoke.py` → **PASS, exit 0**
  (`nw=1`, `src==asset`, proving `tools_hash=e6843ee24b2c`).
- `MDREVIEW_BASE=http://localhost:8155 PATH=/usr/bin:/bin python3 agent_smoke.py` →
  **GATE PASS, render SKIPPED, exit 3** (fail-loud, no silent pass).
- `MDREVIEW_BASE=http://localhost:8155 python3 mcp_smoke.py` → **PASS, 34/34, exit 0**.
- `python3 mcp_server.py --print-version` → `{"version":"0.1.0","tools_hash":"e6843ee24b2c"}`, exit 0.
- `server_info` over stdio with `MDREVIEW_BASE=http://localhost:1` (dead port) → returned locally,
  `isError:false`, `tool_count:16`, `server_info` in names; three-way identity
  `e6843ee24b2c == e6843ee24b2c == e6843ee24b2c`.
- `render-smoke.sh … 'table' '#article'` → `ok: table (1)`, `ok: #article (1)`, exit 0.
- `render-smoke.sh … '#lightbox' 'img' '#article'` → `ok: #lightbox (1)`, `ok: img (2)`,
  `ok: #article (1)`, exit 0.
- Screenshot evidence: `reviews/sprint-12-render-evidence-2026-06-19/retro-table-lightbox-figure.png`
  (styled table visible).
- `git diff --stat 07be026 HEAD -- app.py …` → **app.py NOT in the diff**; only `agent_smoke.py`,
  `mcp_server.py`, `mcp_smoke.py`, `viewer.html` changed. `viewer.html` delta = exactly `dae815e`
  + `2ed9593` (both merged ancestors).
- Running :8155 container's `server_info` tools_hash == on-disk (`e6843ee24b2c`) — the image under
  test is the current code, not stale.

All six committed tickets are `status: done` with `sprint: sprint-12`. Sprint-12 **can close** at G7:
record retro + carry-overs (none) in `sprint-12.md`, set `close_review:` in frontmatter.

## Resolution log

- `2026-06-19` — **NIT (PATH-hide skip-test covers Node but not absolute-path Chrome) — ACCEPTED, no
  change.** The critic confirmed this is *correct* behaviour: the stdlib `--dump-dom` repoint gate is
  meant to be `PATH`-independent and must still run when Node is hidden; the render-half fail-loud
  contract is proven (exit 3, SKIPPED), and the genuine no-Chrome branch is covered by code inspection
  (`find_chrome()` → None → skip). Not worth a synthetic no-Chrome fixture. Verdict stands **PASS**;
  sprint-12 cleared to close.

