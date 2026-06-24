---
slug: working-banner-animation
captured: 2026-06-24
source: this session — the cheap low-hanging slice of GH issue #27 (viewer agent-turn transparency). User: "work on cheap ux fix."
related_epic: epics/working-banner-animation-plan.md
related_issue: "#27"
---

# Working-banner waiting animation

A small, single-ticket `ui` enhancement. The cheap low-hanging slice of GH issue **#27** (viewer agent-turn transparency). Scope is **only** the waiting animation; the rest of #27 (behind-the-scenes progress steps, streamed / diff-animated document updates) stays in #27 and is explicitly **out of scope** here.

## The change

The viewer's turn banner currently shows a **static** "Agent is working on your feedback…" while the agent works (the `working` branch of `renderBanner` in `viewer.html` — message at `viewer.html:235`, banner markup `#turnbanner`/`#turntext` at `:167`, the 6-state first-match banner from MR-052). A static banner is indistinguishable from a hung/dead agent — exactly the confusion that came up when a spawned agent died and the review stranded (see #25 / #26).

Add a lightweight **waiting animation** to the `working`-state banner so the reviewer can see it is actively live: an animated ellipsis or a small CSS spinner, **CSS-only via `@keyframes`**. The banner already re-renders each ~2s poll, so no new JS timer is needed — the animation is pure CSS attached to the working-state markup. Keep it subtle and consistent with the existing viewer styling (dual light/dark theme — the animation must read on both panes). **Only the `working` state animates**; the other banner states (parked / done / blocked / your-turn / stale "may have stopped") are unchanged.

## Constraints

- `viewer.html` only (single self-contained HTML file with inline CSS/JS; JS-rendered — a 200 is not a render).
- No `app.py` / Dockerfile / MCP change. No new dependency (pure CSS).
- Respect `prefers-reduced-motion` (no motion when the user opts out) — accessibility basic, not optional.

## Validation (the gate)

This is a `ui` ticket, so G4/G7 owe a render-smoke from the rebuilt image: `scripts/render-smoke.sh` asserting the banner + the new animation element render in the `working` state, plus a browser open / screenshot showing the animation present, and a check that `prefers-reduced-motion` disables it. Build a throwaway container on a scratch port (never 8139 live / 8137 compose). All temp/evidence under the gitignored `.scratch/`.

## Out of scope (stays in #27)

- Behind-the-scenes progress steps (claimed → reading comments → editing → resolving → handing back).
- Streamed / diff-animated document updates (the "jerky update" half of #27).
