# Backlog — deferred / not-yet-groomed ideas

Parking lot. Promote an item to a ticket (and into a sprint) when it is ready to groom. Keep each
entry to a line or two with enough context to pick up later.

## Deferred

- ~~**MCP wrapper for mdreview-service**~~ — **SHIPPED** in the `mcp-wrapper` epic / sprint-04
  (2026-06-09) as `mcp_server.py` + `mcp_smoke.py`. Retired from the backlog.
- **COPY `mcp_server.py` (+ `mcp_smoke.py`) into the container image** (`infra`; acknowledged
  follow-up from the `mcp-wrapper` plan). The wrapper runs on the agent host today; if it should be
  runnable from inside the published image, the `Dockerfile` needs a matching `COPY` (mirrors the
  sprint-01 `dashboard.html` lesson). Small.
- **Optional `mcp`-SDK variant of the wrapper** (acknowledged follow-up from the `mcp-wrapper`
  plan). The shipped server is stdlib-only by design; a separate, clearly-optional SDK-based variant
  could track the spec automatically at the cost of a dependency. Its own epic if pursued.

## Ideas (ungroomed)

- **process-hardening-3 (tiny)** — from the `mcp-wrapper` retro: (a) `[agent]` give the planner a
  pre-G1 self-audit that every "gate X asserts Y" claim maps to a real gate-row condition or a
  per-ticket AC (an MR-012 defect recurred one cycle after MR-012 shipped); (b) `[skill]` make the
  pre-G7 rail's "run + record the unconditional smoke" standing in Phase 6's docs/infra branch
  (it rode the last two cycles on a per-cycle note). Two small edits; groom only if the meta-thread
  is worth re-opening.

- **Automated post-interaction render evidence** (from sprint-01 G7, SHOULD-FIX #2). Current
  render-smoke is headless-Chrome single-shot (first paint) + a `--dump-dom` node assertion. A
  small scripted interaction (add a note, assert the gutter card appears without reload; resize,
  assert relayout) would make the dynamic-path evidence fully automated. Needs a CDP/puppeteer
  driver, so it is its own small `infra` ticket.
