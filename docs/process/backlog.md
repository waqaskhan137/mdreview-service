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

## From the rich-rendering brief (sprint-06) — deferred P1/P2

The agent's real-review feedback (`requirements/rich-rendering.md`) had more than the two P0s we
shipped. These were scoped out by the user and are the natural next thread:

- **Theme awareness (P1)** — *highest-value remainder, same real-review report.* An image that
  assumes a light background looks wrong on a dark review pane (the agent: "exactly the bug we just
  hit on the site"). Want: render the doc/images on a consistent neutral card regardless of pane
  theme, **or** set the host `color-scheme` so `@media (prefers-color-scheme)` inside `<img>` SVGs
  fires and theme-aware diagrams adapt. Focused `ui` change to `viewer.html`. Its own small sprint.
- **Footnotes (P2)** — GFM footnotes show as text; marked core needs an extension. **Now cheap:**
  sprint-06 established the marked-extension pattern (`setupKatex` in `viewer.html`), so a footnote
  extension is the same shape. `ui`.
- **Syntax highlighting (P2)** — fenced code isn't highlighted; no highlighter is bundled. Vendor a
  small highlighter into `static/` (same stdlib-vendoring approach as KaTeX/marked/mermaid) and wire
  it into the render path. `ui`+`infra` (a new `static/` file, copied by the existing `COPY static/`).
- **Local-dir `{name,path}` asset read (cut at S5)** — the server-side-file-read attach form, cut
  from sprint-06 for the no-auth posture. If revived: **must** ship the `os.path.realpath(root) +
  os.sep` boundary check + negative-path ACs (see `rich-rendering-plan.md` Risks). Low priority.

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
