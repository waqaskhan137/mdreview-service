---
id: sprint-21
name: working-banner-animation — waiting ellipsis
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Add a subtle CSS-only animated ellipsis to the viewer's working-state turn banner so a reviewer can see at a glance that the agent is alive and working, not hung — every other banner state unchanged, motion respecting prefers-reduced-motion.
close_review:          # reviews/sprint-21-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Land the single `working-banner-animation` slice — the cheap low-hanging slice of GH #27. The
viewer's turn banner is static ("Agent is working on your feedback…") while the agent holds the
turn, and a frozen line is indistinguishable from a hung agent. Add a CSS-only animated ellipsis
on `#turntext::after`, scoped to a `working` class that only `renderBanner`'s working arm sets, with
a `prefers-reduced-motion` off-switch. Success by the end date: MR-061 `done` on `dev`, validated by
the render-smoke + both-pane screenshots + reduced-motion probe (this is a `viewer.html` change, so
render evidence is owed — see the G7 scope note). No `app.py`/Dockerfile/MCP/`meta.json` change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-061 | Animate the viewer's `working`-state turn banner (CSS-only ellipsis) | ui | P2 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first.

1. MR-061 — the three `viewer.html` edits (marker class in `renderBanner`'s working arm + class
   removal at the top, the `@keyframes` ellipsis scoped to `#turnbanner.working #turntext::after`,
   and the `prefers-reduced-motion` off-switch), validated by `py_compile app.py` (sanity) + the
   render-smoke + both-pane screenshots + reduced-motion probe from a rebuilt throwaway container.
   Single ticket, no dependencies; ships standalone.

## Notes / retro

_Filled in as the sprint runs and at close._

- Scope changes, carry-overs to the next sprint, what went well / poorly.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-21-close-review-YYYY-MM-DD.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (working-banner-animation specifics).** This sprint **IS** a product-page change —
it edits `viewer.html` (baked into the container at build time, `Dockerfile:8`). So per the G7
pass-condition row it **DOES owe** `scripts/render-smoke.sh` DOM assertions + a screenshot: the
close review must rebuild a **throwaway container** from the working tree (a scratch-port
`docker run`, e.g. port 8765 — **never** the live 8139 instance, **never** `docker compose up`/8137),
force the working state (`POST /handoff {"to":"agent"}` then `POST /handoff
{"state":"working","owner":…}`), then assert `#turnbanner` + `#turntext` + the bare class `.working`
(exit 0 in the working state; `.working` **absent** after a reclaim to the reviewer's turn), capture
**both-pane screenshots** of the working banner (scheme emulation `--blink-settings=
preferredColorScheme=1/0`, NOT `--force-dark-mode`), **plus** the reduced-motion probe (CDP
`Emulation.setEmulatedMedia` → `getComputedStyle($("#turntext"),'::after').animationName === 'none'`
under reduce, the real `@keyframes` ident without it). All evidence is produced under the gitignored
`.scratch/` then **moved to the repo-root `reviews/sprint-21-render-evidence-2026-06-24/`** for the
gate (the bulky-render-evidence convention).
