---
id: MR-062
title: "Replace MR-061's pulse with a rotating CSS spinner on both agent-turn waiting states (restore stash)"
status: done          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-22
epic: watcher-ux-fixes
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

A reviewer who pressed **Send to agent** needs an unambiguous, visible "loading" affordance in
**both** agent-turn waiting moments — the "Sent — waiting for an agent to pick this up" window
**and** the "Agent is working…" window — instead of MR-061's too-subtle opacity pulse that only
animated the narrow working state. The fix is **already implemented**, product-owner-eyeballed, was
deployed to :8139, and is parked in git `stash@{0}` ("spinner-wip (MR-062): rotating spinner on both
agent-turn waiting states, replaces MR-061 pulse"). This ticket is **restore-and-re-validate**, not
re-author: the spinner is a hand-written inline `viewer.html` CSS ring + keyframe that **supersedes
MR-061**. `viewer.html` only — no `app.py`/Dockerfile/MCP change.

## Acceptance criteria

- [ ] The stash `stash@{0}` ("spinner-wip (MR-062)…") is **restored** onto the MR-062 branch (do
      **not** re-write the diff by hand); `viewer.html` is the only file changed.
- [ ] MR-061's `#turnbanner.working #turntext::after` opacity-pulse, its `@keyframes turnworking`,
      and its `.working`-scoped `prefers-reduced-motion` override are **removed** (the pulse is
      superseded, deleted not kept alongside).
- [ ] The rotating spinner `#turnbanner.loading #turntext::before` exists with the pinned
      properties: 11px ring, `border:2px solid var(--muted)`, `border-top-color:transparent`,
      `animation:turnspin .8s linear infinite`; and `@keyframes turnspin{to{transform:rotate(360deg)}}`
      exists. Colour via `--muted` so it reads on both panes.
- [ ] A `@media (prefers-reduced-motion:reduce)` block renders a **static ring** (animation removed,
      ring still visible) — the reduced-motion fallback.
- [ ] `renderBanner` **removes** `loading` once at the top of the function, and **adds** `loading`
      in **both** agent-turn waiting arms: the `if(!as)` "Sent — waiting for an agent to pick this
      up" arm **and** the genuine "Agent is working…" arm. It adds **no** `loading` class in the
      stale "Agent may have stopped" arm, nor on a reviewer turn.
- [ ] MR-062 **supersedes MR-061** (the pulse + `turnworking` keyframes are gone, not co-existing).
- [ ] Local validation passes: `python3 -m py_compile app.py` (sanity; no `app.py` change), plus the
      render-smoke + reduced-motion CDP probe + both-pane screenshots below, all from a **rebuilt
      throwaway container on a scratch port** (never 8139 live, never 8137 compose, never
      `docker compose up`); temp artifacts under `.scratch/`, then moved to
      `reviews/sprint-22-render-evidence-2026-06-24/` for the gate. Route is `$BASE/review/{id}`.
  - [ ] **State A — waiting-for-pickup** (`turn=agent`, no lease): force with
        `POST /api/reviews/{id}/handoff {"to":"agent"}` **only** (do not claim a lease), then
        `scripts/render-smoke.sh "$BASE/review/{id}" '.loading' '#turntext'` → exit 0
        (spinner **PRESENT**). Assert with the **bare class `.loading`** (or `div.loading`) — the
        flat matcher rejects the compound `#turnbanner.loading` (exit 2).
  - [ ] **State B — agent working** (`turn=agent`, fresh lease): then
        `POST /api/reviews/{id}/handoff {"state":"working","owner":"smoke"}`, then
        `scripts/render-smoke.sh "$BASE/review/{id}" '.loading' '#turntext'` → exit 0
        (spinner **PRESENT**).
  - [ ] **State C — stale** ("Agent may have stopped"): **verified by code inspection, not a render**
        (the stale heartbeat cannot be force-stamped: `{state:"working"}` always stamps `at=now`,
        `app.py:660`). Inspect that the stale arm of `renderBanner` (`viewer.html:241`, the
        `else if(…>STALE_S)` branch) adds **no** `loading` class; cite the line post-stash in the
        evidence notes.
  - [ ] **State D — reviewer turn** (spinner **ABSENT**, live render): reclaim with
        `POST /api/reviews/{id}/handoff {"to":"reviewer","by":"reviewer"}` (a bare
        `{"to":"reviewer"}` hits the 400 `else` arm and does **not** flip the turn), then
        `scripts/render-smoke.sh "$BASE/review/{id}" '.loading' >/dev/null; test $? -eq 1`
        (absence → render-smoke exits **1** on 0 nodes, so the absence check **inverts** the
        expected exit) and `scripts/render-smoke.sh "$BASE/review/{id}" '#turntext'` → exit 0
        (banner present).
  - [ ] **Reduced-motion CDP probe** (computed style, not a screenshot): with Chrome emulating
        `prefers-reduced-motion: reduce`, `getComputedStyle($("#turntext"),'::before').animationName`
        resolves to **`none`** under reduce, **`turnspin`** without it. (The probe targets `::before`
        — the spinner moved from MR-061's `::after` to `::before`.)
  - [ ] **Both-pane screenshots** of State B (spinner on): dark pane
        `--blink-settings=preferredColorScheme=0`, light pane `=1` (or CDP
        `Emulation.setEmulatedMedia`). **Never** `--force-dark-mode` (auto-invert, not scheme
        emulation) and never a bare-headless "light" shot (bare headless resolves dark). Saved under
        `reviews/sprint-22-render-evidence-2026-06-24/`.

## Notes / context

- Epic plan: `docs/process/epics/watcher-ux-fixes-plan.md` — §"Recommended approach / UI
  (`viewer.html`)" (the pinned stash spots: CSS at `viewer.html:84-89`, `renderBanner` at
  `viewer.html:232-255`), §"Key constraints" (flat-matcher / scheme-emulation / `.loading` not
  `#turnbanner.loading` footguns), §"Verification / MR-062" (the State A-D recipe, reduced-motion
  probe, both-pane shots), §"MR-062 acceptance criteria", and §"Review resolutions" (the folded G1
  smoke-recipe nits N1-N4: viewer route `/review/{id}`, stale state non-force-stampable → code
  inspection, reviewer-flip body `{"to":"reviewer","by":"reviewer"}`, reduced-motion probe targets
  `::before`).
- `viewer.html` stash anchors (confirm they still read as found at restore time): CSS MR-061 block at
  `viewer.html:84-89` (`::after` pulse `:87`, `@keyframes turnworking` `:88`, `.working`
  reduced-motion override `:89`); `renderBanner` at `viewer.html:232-255` (top-of-function
  `remove` `:237`, the `if(!as)` waiting-for-pickup arm `:240`, the stale arm `:241`, the working
  arm `:242`, the reviewer-turn `else` `:245-252`).
- `app.py` line refs (verify before relying): `{state:"working"}` always stamps `at=now`
  (`app.py:660`); reclaim arm `{"to":"reviewer","by":"reviewer"}` (`app.py:616`) vs the 400 `else`
  (`app.py:664`). No `app.py` change is made.
- render-smoke is a **flat matcher** (`tag` / `.class` / `tag.class` / `#id`): assert the loading
  state with the bare class `.loading`, **not** `#turnbanner.loading` (rejected as bad usage,
  exit 2). Absence is `.loading` matching 0 nodes, which render-smoke reports as **exit 1** — so an
  absence check passes when the smoke exits 1 (inverted).
- **Supersedes MR-061** (`MR-061-animate-working-banner.md`). Links GH **#27** (the rest of #27 —
  behind-the-scenes progress steps, streamed/diff-animated updates — stays in #27).
- This **IS** a product-page change (`viewer.html` baked into the container at build time,
  `Dockerfile:8`), so G7 owes a render-smoke from a **rebuilt** throwaway container (a 200 is not a
  render: the banner is written by `renderBanner` at runtime).

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.

## Work log

- `2026-06-24` — Restored the product-owner-eyeballed spinner from `stash@{0}` onto this branch
  (`viewer.html` only, 9/9), relabelled the MR-061 comments to MR-062. CSS near `.turnbanner` (~:84):
  removed MR-061's `#turnbanner.working #turntext::after` opacity-pulse + `@keyframes turnworking` +
  its reduced-motion override; added `#turnbanner.loading #turntext::before` (11px ring,
  `border:2px solid var(--muted)`, `border-top-color:transparent`, `animation:turnspin .8s linear
  infinite`), `@keyframes turnspin{to{transform:rotate(360deg)}}`, and a `@media (prefers-reduced-motion:
  reduce)` static-ring fallback. `renderBanner` (~:237-242): `remove('loading')` at the top, `add('loading')`
  in BOTH the `if(!as)` waiting-for-pickup arm AND the working arm — NOT the stale arm nor the reviewer
  branch. Supersedes MR-061's pulse (deleted). No `app.py`/Dockerfile/MCP change.

## Validation

- `2026-06-24` — `py_compile app.py` OK (unchanged). G4/G7 render-smoke from a **rebuilt throwaway image**
  (`mdreview-mr062-smoke`, disposable container on scratch port 8768 — never 8139/8137/compose):
  **State A (waiting-for-pickup**, `{to:agent}` only, agent_status null): `#turntext` + `.loading` present
  (exit 0) — proves the spinner now shows in the post-Send waiting state, the MR-061 gap. **State B (working**,
  `{state:working,owner:smoke}`): `.loading` present (exit 0). **State D (reviewer**, `{to:reviewer,by:reviewer}`):
  `.loading` absent (0 nodes / exit 1), `#turntext` present. **Stale arm**: code inspection (adds no class).
  **Reduced motion (CDP):** `getComputedStyle(#turntext,'::before').animationName` = `none` under reduce,
  `turnspin` without. **Both panes:** light + dark screenshots show the spinner ring legible. Evidence:
  `reviews/sprint-22-render-evidence-2026-06-24/` (SMOKE.md + banner-working-light.png + banner-working-dark.png).
