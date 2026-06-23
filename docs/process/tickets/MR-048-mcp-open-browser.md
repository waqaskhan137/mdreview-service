---
id: MR-048
title: MCP wrapper opens a new review_url in the default browser (opt-in MDREVIEW_OPEN_BROWSER)
status: done
layer: svc
priority: P3
sprint:                # out-of-cycle (own branch MR-048-mcp-open-browser); not part of a sprint
epic:                  # none — standalone UX fix
depends_on: []
branch: MR-048-mcp-open-browser
created: 2026-06-21
updated: 2026-06-21
---

## Goal

When an agent calls `create_review`, the human has to copy the returned `review_url` out of the
chat and paste it into a browser. An LLM can't open a browser itself (it only returns text), so the
auto-open must be a local side-effect. The MCP wrapper (`mcp_server.py`) runs as a local stdio
process on the user's machine — the right place to pop the page. Make it open the new `review_url`
in the default browser, **opt-in** so CI/headless runs are unaffected.

## Acceptance criteria

- [x] `mcp_server.py` opens the `review_url` in the local default browser after a successful
      `create_review`, gated by env `MDREVIEW_OPEN_BROWSER` (truthy: `1`/`true`/`yes`); **off by
      default**.
- [x] Only `create_review` opens (not `update_source` — the viewer live-reloads the existing tab,
      so reopening would spawn duplicate tabs).
- [x] Best-effort and **protocol-safe**: the open helper swallows all exceptions so it never raises
      into the JSON-RPC stream; a `ponytail:` comment names the stdout-safety assumption (macOS
      `open` writes nothing to stdout) and the fd-redirect upgrade path for console-browser/Linux.
- [x] No tool-surface change: `TOOLS`/`INSTRUCTIONS` untouched, so `tools_hash` is unchanged
      (`f265447b5a8c`). **Behaviour-only change → the staleness check won't flag it; a client
      reconnect/restart is required for it to take effect** (stdio loads code at startup). Noted in
      the module docstring `Run:` line.
- [x] Local validation passes: `python3 -m py_compile mcp_server.py`; `_open_review` extracts the
      url, ignores bad/missing input without raising, and is gated off by default.

## Notes / context

- Implementation: `mcp_server.py` — `import webbrowser`, module-level `OPEN_IN_BROWSER` flag,
  `_open_review(text)` helper, and the gated call in `handle_tools_call` after the `create_review`
  result is sent.
- Enable: add `"MDREVIEW_OPEN_BROWSER": "1"` to the mdreview server's `env` in `~/.claude.json`
  (done 2026-06-21), then reconnect the MCP client / restart Claude Code.
- Out-of-cycle: kept off the standing `legacy-feedback-retire` (sprint-13) dev→main PR #11 to avoid
  scope creep — own branch `MR-048-mcp-open-browser`.
- Known ceiling (not built): with the flag on, **every** `create_review` opens a tab — fine
  interactively; a batch agent creating N reviews pops N tabs. Upgrade path if it bites: a last-url
  / rate guard. Deliberately deferred (YAGNI).

## Work log

- `2026-06-21` — `mcp_server.py`: added `import webbrowser`; `OPEN_IN_BROWSER` env flag (default
  off); `_open_review(text)` (parses `review_url`, best-effort, swallows all errors); gated call in
  `handle_tools_call` after the `create_review` result. Updated the module docstring `Run:` line.
  Enabled in `~/.claude.json` (`MDREVIEW_OPEN_BROWSER=1`).

## Validation

- `2026-06-21` — `python3 -m py_compile mcp_server.py` → OK. `python3 mcp_server.py --print-version`
  → `tools_hash f265447b5a8c` (unchanged surface). Unit check (monkeypatched `webbrowser.open`, no
  real browser): `_open_review` extracts `review_url`; bad JSON / missing key → no open, no raise;
  `OPEN_IN_BROWSER` is `False` when the env is unset. `~/.claude.json` re-validated as parseable
  with the new env key.

## Follow-ups

- None required. Multi-tab guard deferred per Notes (YAGNI).
