---
id: MR-061
title: "Animate the viewer's `working`-state turn banner (CSS-only ellipsis)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-21
epic: working-banner-animation
depends_on: []
branch:                # MR-061-slug, once work starts
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The viewer's turn banner shows a **static** "Agent is working on your feedback…" while the agent
holds the turn. A frozen line of text is indistinguishable from a hung or dead agent — the exact
confusion that stranded a review when a spawned agent died (GH #25/#26). Add a **lightweight,
CSS-only waiting animation** to that one banner state so the reviewer can see at a glance that the
turn is live, not stuck. Every other banner state (parked / stale "may have stopped" / your-turn /
done / blocked) looks exactly as it does today, and motion respects `prefers-reduced-motion`. The
animation is a CSS `@keyframes` gated to a single `working` marker class that only the working
branch of `renderBanner` sets — no new JS timer, no DOM element, no `app.py`/Dockerfile/MCP change.

## Acceptance criteria

- [ ] **Marker class wiring in `renderBanner` (~`viewer.html:226-248`).** A single
      `bar.classList.remove('working')` is added near the top of `renderBanner`, right after the
      `if(!bar)return;` guard (~`viewer.html:230`), and `bar.classList.add('working')` is added
      **ONLY** in the working arm (the third arm, ~`viewer.html:235`,
      `msg="Agent is working on your feedback…"`). No other arm sets the class.
- [ ] **Drop the literal trailing `…` from the working arm's message** (`msg="Agent is working on
      your feedback"`) so the animated `::after` is the sole ellipsis (avoids a double "……").
- [ ] **CSS animation rules near `.turnbanner` (~`viewer.html:80`).** A `@keyframes` block plus a
      `#turnbanner.working #turntext::after{content:"…";…}` rule that animates the ellipsis (e.g.
      a `width`/`clip-path` reveal over a static `…`, or an `opacity` pulse — chosen by eyeballing
      on both panes; record the chosen technique in the Work log). Subtle and slow (~1.2-1.5s
      loop), colour driven from the theme vars (`--muted` / `--text`), **never** a hard-coded hex,
      so it reads on both light and dark panes.
- [ ] **Only the working state animates.** The animation is scoped to `#turnbanner.working
      #turntext::after`; the stale "may have stopped" arm, parked, your-turn, done, and blocked
      banners are byte-for-byte unchanged and `#turnbanner` does **not** carry the `working` class
      in those states.
- [ ] **`prefers-reduced-motion` off-switch (REQUIRED).** A
      `@media (prefers-reduced-motion: reduce){ #turnbanner.working #turntext::after{animation:none;} }`
      block disables the animation; the static `content:"…"` remains, so reduced-motion users see
      today's exact appearance.
- [ ] **Class hygiene across re-render.** A banner that transitions from working to a non-working
      state on a subsequent ~2s poll drops the `working` class and stops animating (the single
      top-of-function `remove` guarantees no stale `working` class survives a re-render).
- [ ] **Scope.** Only `viewer.html` changed; `git diff --stat` touches no other file. No new
      dependency, no `app.py`/Dockerfile/MCP/`meta.json` change.
- [ ] **Local validation passes:** `python3 -m py_compile app.py` (sanity; no `app.py` change),
      plus the render-smoke + screenshots + reduced-motion probe below, all from a **rebuilt
      throwaway container on a scratch port** (never 8139 live, never 8137 compose, never
      `docker compose up`); all temp artifacts under `.scratch/`, then moved to
      `reviews/sprint-21-render-evidence-2026-06-24/` for the gate.
  - [ ] **Force the working state.** Create a review, then
        `POST /api/reviews/{id}/handoff {"to":"agent"}` (flip the turn) then
        `POST /api/reviews/{id}/handoff {"state":"working","owner":"smoke-owner"}` (claim a fresh
        lease, stamps `at=now`) so `/status` returns `turn==='agent'` + fresh `agent_status` and
        `renderBanner` takes the working arm.
  - [ ] **render-smoke (flat selectors only).**
        `scripts/render-smoke.sh /review/{id} '#turnbanner' '#turntext'` → exit 0 (both nodes
        present), and `scripts/render-smoke.sh /review/{id} '.working'` → exit 0 in the working
        state (bare class `.working` — a compound `#turnbanner.working` is rejected by the flat
        matcher, `render-smoke.sh:72`; only `#turnbanner` carries `.working`, so the bare class is
        unambiguous). After a reclaim to the reviewer's turn
        (`POST /…/handoff {"to":"reviewer","by":"reviewer"}`),
        `scripts/render-smoke.sh /review/{id} '.working'` → `.working` **absent** (exit 1).
  - [ ] **Both-pane screenshots** of the working banner: headless Chrome with scheme emulation
        (`--blink-settings=preferredColorScheme=1` light / `=0` dark, NOT `--force-dark-mode`),
        confirming the animating ellipsis reads legibly on each pane.
  - [ ] **Reduced-motion probe.** Via CDP `Emulation.setEmulatedMedia({features:[{name:
        'prefers-reduced-motion',value:'reduce'}]})`,
        `getComputedStyle($("#turntext"), '::after').animationName` resolves to **`none`** while
        the static `content:"…"` remains; **without** the emulation it resolves to the real
        `@keyframes` ident (the ellipsis animates).

## Notes / context

- Epic plan: `docs/process/epics/working-banner-animation-plan.md` — §"Recommended approach / UI
  (`viewer.html`)" (the three edits), §"Key constraints" (flat-matcher / scheme-emulation /
  class-hygiene footguns), §"Verification" (the force-working recipe, render-smoke, both-pane
  screenshots, reduced-motion probe), §"MR-061 — acceptance criteria" (A1-A6), and §"Review
  resolutions" (the folded G1 smoke-recipe fixes: corrected `/handoff` lease-claim shape (no
  `/ping`), bare-class `.working` assertion, pinned reduced-motion probe, CDP-emulation
  portability).
- `viewer.html` line refs (verify they still read as found at implementation time): `renderBanner`
  at `viewer.html:226-248` (the `if(!bar)return;` guard at `:230`, the working arm at `:235`, the
  `tt.textContent=msg` write at `:246`, the parked arm at `:233`, the stale arm at `:234`, the
  reviewer `else` block at `:238-245`); `.turnbanner` CSS at `viewer.html:80-83`; the dark-scheme
  swap at `viewer.html:11`; the viewer posts handoff to `API+'/handoff'` at `viewer.html:222`;
  `STALE_S` freshness check at `viewer.html:232-235`.
- `app.py` line refs (verify before relying): `/handoff` lease-claim arm
  (`{state:"working",owner:…}`) at `app.py:635-662`. No `app.py` change is made — the working
  state is fully client-derivable from the existing `/status` body.
- `render-smoke.sh:72` — the flat `_VALID` matcher: supports `tag` / `.class` / `tag.class` /
  `#id`; rejects descendant combinators and an id with a `.class` suffix (`#turnbanner.working`,
  exit 2) and cannot assert a `::after` pseudo-element. Hence the bare-class `.working` assertion.
- Links GH **#27** — this is the cheap low-hanging slice of #27. The rest of #27 (behind-the-scenes
  progress steps, streamed/diff-animated document updates) is **out of scope** and stays in #27.
- No render-smoke footgun exception: this **is** a product-page change (`viewer.html` is baked into
  the container at build time, `Dockerfile:8`), so the smoke must run against a **rebuilt**
  throwaway container — a smoke against a stale container would not exercise the edit. A 200 is not
  a render: the banner is written by `renderBanner` at runtime, so verification drives headless
  Chrome via `scripts/render-smoke.sh`, never a curl 200.

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
