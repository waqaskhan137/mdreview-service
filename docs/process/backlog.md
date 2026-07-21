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

## From the rich-rendering brief (sprint-06) — status

The agent's real-review feedback (`requirements/rich-rendering.md`) had more than the two P0s. Most
of it is now shipped:

- ~~**Theme awareness (P1)**~~ — **SHIPPED** in `theme-awareness` / sprint-07 (PR #6): a near-white
  image mat so light-authored figures stay legible on a dark pane.
- ~~**Footnotes (P2)**~~ — **SHIPPED** in `render-fidelity` / sprint-08 (PR #7): vendored
  `marked-footnote`.
- ~~**Syntax highlighting (P2)**~~ — **SHIPPED** in `render-fidelity` / sprint-08 (PR #7): vendored
  highlight.js (common) + `marked-highlight`, dual-scheme theme.

Still open from that thread:

- **Per-image luminance heuristic (P2/P3)** — the theme-awareness **non-goal**: a dark-authored /
  white-on-transparent figure goes invisible on the light mat (measured 238→5). A per-image
  luminance/contrast check ("this figure is dark-authored → no mat / dark mat") would close the
  inverse direction. `ui`, non-trivial. Only if it bites in practice. (MR-027 follow-up.)
- **Local-dir `{name,path}` asset read (cut at S5)** — the server-side-file-read attach form, cut
  from sprint-06 for the no-auth posture. If revived: **must** ship the `os.path.realpath(root) +
  os.sep` boundary check + negative-path ACs (see `rich-rendering-plan.md` Risks). Low priority,
  security-sensitive. (MR-023/MR-024 follow-up.)

## Small hygiene / tech-debt (ungroomed)

- **`do_HEAD` is unimplemented — HEAD → 501** (`app.py`). Harmless today (browsers GET fonts/css/
  assets), but it means MIME checks must use a GET header-dump, and a `curl -sI` health probe would
  see a 501. A 3-line `do_HEAD = do_GET`-style addition (header-only) would fix it. (MR-022 follow-up.)
- **render-smoke has no descendant combinator** — `scripts/render-smoke.sh` only matches `tag`/
  `.class`/`tag.class`/`#id`; `#article img` is rejected. Documented as footgun 11; a real CSS-engine
  matcher is overkill, but worth a line in the script's usage. (MR-025 follow-up.)

## Ideas (ungroomed)

- **process-hardening-3 (tiny)** — from the `mcp-wrapper` retro: (a) `[agent]` give the planner a
  pre-G1 self-audit that every "gate X asserts Y" claim maps to a real gate-row condition or a
  per-ticket AC (an MR-012 defect recurred one cycle after MR-012 shipped); (b) `[skill]` make the
  pre-G7 rail's "run + record the unconditional smoke" standing in Phase 6's docs/infra branch
  (it rode the last two cycles on a per-cycle note). Two small edits; groom only if the meta-thread
  is worth re-opening.

- **`scripts/` CDP interaction-evidence helper** (from the dashboard-redesign retro, `[feature]`).
  sprint-09 drove Chrome over CDP (Node built-in `WebSocket`, no install) to capture *interaction*
  states (click expand/collapse, Delete-with-confirm) + *measure* column counts / computed styles —
  beyond the single-shot `render-smoke.sh` + screenshot. Promote that one-off driver to a checked-in,
  parameterized helper (`scripts/cdp-shot.mjs <url> <out-dir> <captures.json>`) so interaction-only
  evidence becomes gate-verifiable instead of trust-and-file-check. Pairs with / may subsume the
  "Automated post-interaction render evidence" item below. Its own small `infra` ticket.

- **Automated post-interaction render evidence** (from sprint-01 G7, SHOULD-FIX #2). Current
  render-smoke is headless-Chrome single-shot (first paint) + a `--dump-dom` node assertion. A
  small scripted interaction (add a note, assert the gutter card appears without reload; resize,
  assert relayout) would make the dynamic-path evidence fully automated. Needs a CDP/puppeteer
  driver, so it is its own small `infra` ticket.

- **Remove/hide the turn baton in the markdown viewer** (from the latex-paper-review planning
  session, 2026-07-21, `[feature]`). The owner's working flow is pull-based (comment in the
  browser, then ask the agent in the CLI to collect feedback); the latex mode ships with no baton
  at all, and the owner had the "Your turn / Send to agent" banner dropped from the comparison
  mockup. Removing it from the real markdown viewer touches the MR-051/052 handoff feature (and
  the shelved watcher depends on handoff state), so it is its own ticket with its own scoping, not
  a rider on `feat/latex-review`. Needs an explicit owner go-ahead before grooming.
