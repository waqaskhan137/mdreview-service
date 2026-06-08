# Backlog — deferred / not-yet-groomed ideas

Parking lot. Promote an item to a ticket (and into a sprint) when it is ready to groom. Keep each
entry to a line or two with enough context to pick up later.

## Deferred

- **MCP wrapper for mdreview-service** (deferred from the `review-dashboard` epic, 2026-06-08).
  A thin stdio MCP server wrapping the existing HTTP API as tools: `create_review`,
  `list_reviews`, `get_feedback`, `update_source`, `delete_review`. The HTTP contract is already
  MCP-ready; this is a clean separate deliverable. Sketch lives in `docs/future-mcp.md` (written
  in MR-007). Would become its own epic + sprint when picked up.

## Ideas (ungroomed)

- **Automated post-interaction render evidence** (from sprint-01 G7, SHOULD-FIX #2). Current
  render-smoke is headless-Chrome single-shot (first paint) + a `--dump-dom` node assertion. A
  small scripted interaction (add a note, assert the gutter card appears without reload; resize,
  assert relayout) would make the dynamic-path evidence fully automated. Needs a CDP/puppeteer
  driver, so it is its own small `infra` ticket.
