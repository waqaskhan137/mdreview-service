---
id: MR-009
title: Add scripts/render-smoke.sh (DOM-node assertion against a served URL)
status: done
layer: infra
priority: P1
sprint: sprint-02
epic: process-hardening
depends_on: []
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Provide the single canonical render-smoke command so `ui` validation asserts the expected DOM
nodes actually rendered (not just a 200, not a substring of source). The script both docs will
reference, so the check cannot drift. (Retro suggestions 1 + 2.)

## Acceptance criteria

- [ ] New executable `scripts/render-smoke.sh <url> <css-selector>...`. Drives headless Chrome
      against the **served URL** (never a `file://` path) and, **after waiting for render**
      (virtual-time budget or equivalent), asserts each selector matches at least one node via
      **DOM-element evaluation**, NOT a substring grep of the dump (the inline CSS/JS source
      contains strings like `gcard`/`cmt`, so grep false-passes). Implementation note: shipped as
      a stdlib `html.parser` element counter rather than literal `document.querySelectorAll` — the
      epic blesses "an equivalent that distinguishes rendered nodes from source text"; it is a
      flat `tag`/`.class`/`tag.class`/`#id` matcher and rejects unsupported selectors (combinators,
      attributes, pseudo) with exit 2 so they fail loud rather than silently match 0.
- [ ] Contract: every selector matches >=1 node -> exit 0; any selector matches 0 -> nonzero
      exit + a message naming the missing selector.
- [ ] **Fails loud if no Chrome binary is found** (probes `google-chrome`/`chromium`/macOS
      `Google Chrome`, errors with the paths it tried); never silently exits 0.
- [ ] No new pip/runtime dependency (uses the Chrome binary the process already relies on).
- [ ] Validation (real, runnable): `docker compose up -d --build`; `curl localhost:8137/healthz`
      ok; a selector known to render on a page -> `exit=0`; a bogus selector -> nonzero +
      message; a source-only string (e.g. `gcard` as bare text, not a rendered `.gcard`) ->
      nonzero (proves it is not substring-grep); Chrome-absent path -> loud nonzero.

## Notes / context

Plan: `epics/process-hardening-plan.md` (Tooling section, Risks, Verification). Rationale for the
render-wait: `reviews/sprint-01-close-review-2026-06-08.md:62` (the working assertion used
`--dump-dom` after a virtual-time advance; the viewer renders via `setTimeout` + async mermaid).

## Work log

- `2026-06-08` — new executable `scripts/render-smoke.sh <url> <selector>...`. Drives headless
  Chrome (`--headless=new --virtual-time-budget` render-wait) to dump the RENDERED DOM, then a
  stdlib Python `html.parser` **counts elements** matching each selector (`tag`/`.class`/
  `tag.class`/`#id`) — text inside `<style>`/`<script>` is data, not elements, so source strings
  are correctly ignored. Fails loud (exit 3) when no Chrome is found; exit 1 + named selector
  when a selector matches 0 nodes; exit 0 when all match. `RENDER_SMOKE_CHROME` pins the binary
  (CI / fail-loud test). No pip/runtime dependency (uses the existing Chrome + stdlib python3).

## Validation

- `2026-06-08` — `bash -n` clean. Against the rebuilt container on `:8137` (`healthz` ok):
  - present `.card` on `/` -> `ok (6 nodes)`, exit 0.
  - bogus `.totally-not-here` -> exit 1, names it.
  - **anti-grep:** `.empty` appears twice in `dashboard.html` CSS source but renders 0 elements
    (reviews exist) -> exit 1 (proves DOM-element matching, not substring grep).
  - **fail-loud:** `RENDER_SMOKE_CHROME=/nonexistent/chrome` -> exit 3 with the tried path.
  - viewer `/review/<id>` with `.gcard mark.cmt` -> `ok (2 nodes)` each, exit 0.

## Follow-ups

None.
