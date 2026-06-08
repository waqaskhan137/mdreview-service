---
id: MR-009
title: Add scripts/render-smoke.sh (DOM-node assertion against a served URL)
status: ready
layer: infra
priority: P1
sprint: sprint-02
epic: process-hardening
depends_on: []
branch:
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
      **DOM evaluation** (`document.querySelectorAll(sel).length`), NOT a substring grep of the
      dump (the inline CSS/JS source contains strings like `gcard`/`cmt`, so grep false-passes).
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None.
