---
id: MR-021
title: Replace static demo with animated GIF of the review loop (drop-in) and re-publish
status: backlog
layer: ui
priority: P2
sprint:                # NOT committed to sprint-05 — next cycle (would fail G6: not ready)
epic: landing-page
depends_on: [MR-019, MR-020]
branch:
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Upgrade the landing page's static `site/demo.png` to an animated capture of the live review loop —
a human typing a note, the agent's `PUT /source` live-reloading the viewer, the addressed note
striking through — dropped into the same `<img>` slot with no layout change, then re-publish.

## Acceptance criteria

_Not groomed (G2 not attempted) — captured from the epic plan, Phase 2. Open questions below must
close before this can be `ready`._

- [ ] Animated GIF (or `<video autoplay muted loop playsinline>` with the PNG as poster — decide)
      of the real loop, replacing `site/demo.png` in the same slot; no other layout/HTML change.
- [ ] Re-publish via the MR-020 pinned sequence; live render-smoke still green (`img.demo-img`, or
      `video.demo-vid` if switched to video).

## Notes / context

- Epic: `docs/process/epics/landing-page-plan.md` (Phase 2; Decision 2; Assumptions — GIF vs.
  video is the open question; capture tooling does not exist yet).
- Deliberately NOT in sprint-05: the asset does not exist and the format decision is open, so the
  ticket cannot be `ready`, and committing it would fail G6.
- **Carried advisory from the sprint-05 close review (F7):** capture the GIF against a
  **throwaway local instance** (e.g. `docker run --rm -p 8137:8080 mdreview-service`), not by
  staging/deleting a review on the user's live container — epic Decision 2 prescribes the
  deterministic local capture.

## Work log

_Not started._

## Validation

_Not started._

## Follow-ups

(none)
