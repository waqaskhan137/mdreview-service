---
review_of: sprints/sprint-04.md
gate: G7
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-09
verdict: PASS
status: resolved
---

# G7 sprint-close review — sprint-04 "mcp-wrapper"

Independent close review by `staff-critic` (reviewer != implementer). First product-code sprint:
`mcp_server.py` (stdlib stdio MCP server) + `mcp_smoke.py` wrapping the HTTP API, plus docs.

**Verdict: PASS** — no blockers, no should-fixes. The reviewer independently ran the
service-unchanged diff (empty), cross-checked every MCP shape against the official spec rev
`2025-06-18`, and reproduced the full G7 evidence (rebuild + `/healthz` + `/api/reviews` + live
`mcp_smoke.py` 11/11, store cleaned back to 11 reviews).

## Confirmations (independently verified, not just read)
- **Service-unchanged guarantee HOLDS.** `git diff --stat "$(git merge-base origin/main HEAD)"...HEAD
  -- app.py viewer.html dashboard.html static Dockerfile docker-compose.yml` is **empty**. The
  defining constraint (MR-015/016/017 AC) is met; the thin-proxy adds no service route or state.
- **MCP shapes match the 2025-06-18 spec:** `initialize` (protocolVersion negotiation,
  `capabilities:{tools:{}}`, serverInfo); `notifications/initialized` and id-less notifications get
  no response; `tools/call` envelope `content[0].{type,text}` + `isError`; unknown tool ->
  `-32602` (the spec's own example), tool failure -> `isError:true`; newline-delimited stdio
  framing (not Content-Length). Verified against the spec's tools + transports pages.
- **Robustness:** EOF exits cleanly; stdout flushed per message (pipe smoke completes); a malformed
  line is skipped without killing the stream; handler exceptions -> `-32603`; `route()` KeyError ->
  `-32602`. All 8 routes match `app.py` verbs/paths; `get_history` switches on `round is not None`
  (so `round=0` selects the single round); `create_review` passes provenance through and still
  requires `markdown`.
- **`mcp_smoke.py`** is genuinely stdlib-only (json/subprocess), non-vacuous (parses
  `content[0].text`, extracts the id, asserts `revision>=1`), and cleans up the review it creates.
- **Docs (MR-018)** accurately describe all 8 tools, the run command, the `mcpServers` stdio
  config, `MDREVIEW_PUBLIC_BASE` guidance, the no-auth/`list_reviews` exposure note; `future-mcp.md`
  flipped to SHIPPED.

## NITs (both fixed at close)
- **N1 — plan said malformed JSON -> `-32700`; code skips the line.** The skip is the better
  behavior (no `id` to answer; stream survives) and no AC pinned `-32700`. **Fixed:** reconciled the
  epic plan's error-mapping prose to "a malformed line is skipped."
- **N2 — stale "Current epic: review-dashboard (sprint-01)" line in `CLAUDE.md`** (pre-existing,
  from the process-adoption commit, not MR-018). **Fixed:** replaced with a pointer to
  `docs/process/TRACKER.md` so it cannot go stale again.

The reviewer flagged (correctly) NOT to "clean up" `mcp_server.py`'s
`body.setdefault("markdown", args["markdown"])` — it is load-bearing (triggers the `-32602`
missing-arg path); left as-is.

## Resolution log
- 2026-06-09 — review recorded (PASS, no blockers/should-fixes). Both NITs fixed at close. The
  pre-G7 board rail was dogfooded AND extended to run+record the unconditional smoke (carrying
  process-hardening-2 retro suggestion 1). Gate **cleared**; sprint-04 closes.
