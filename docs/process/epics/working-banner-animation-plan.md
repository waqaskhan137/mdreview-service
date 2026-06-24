---
epic: working-banner-animation
status: active          # draft | active | done  (stays draft until G1 passes)
created: 2026-06-24
source: requirements/working-banner-animation.md
gate: passed 2026-06-24    # G1 (Plan Gate): not passed | passed YYYY-MM-DD — tickets blocked until passed
review: reviews/working-banner-animation-plan-review-2026-06-24.md
related_sprints: [sprint-21]
related_tickets: [MR-061]
---

# Working-banner Waiting Animation Plan

The viewer's turn banner shows a **static** "Agent is working on your feedback…" while the agent
holds the turn. A frozen line of text is indistinguishable from a hung or dead agent — the exact
confusion that stranded a review when a spawned agent died (GH #25/#26). This epic adds a
**lightweight, CSS-only waiting animation** to that one banner state so the reviewer can see the
turn is live, not stuck. It is the cheap low-hanging slice of GH issue **#27**; the rest of #27
(behind-the-scenes progress steps, streamed/diff-animated document updates) stays in #27.

**Source requirement:** [`requirements/working-banner-animation.md`](../requirements/working-banner-animation.md)
— the original brief, kept verbatim.

## Product goal

When the agent is actively working (turn handed to agent, lease fresh), the viewer's turn banner
shows subtle, continuous motion so the reviewer can tell at a glance that the agent is alive and
working — not hung. Every other banner state (parked / stale "may have stopped" / your-turn /
done / blocked) looks exactly as it does today. Motion respects `prefers-reduced-motion`.

## Core design principle

**Pure-CSS motion, gated to a single class that only the working branch sets.** The banner already
re-renders on every ~2s `/status` poll via `renderBanner(st)`, so no JS timer is needed — the
animation is a CSS `@keyframes` that runs whenever a `working` marker class is present on
`#turnbanner`, and `renderBanner` is the single place that adds (working branch) or removes (every
other branch) that class. One class, one keyframe, one `prefers-reduced-motion` off-switch:
nothing else in the file changes, and no state but `working` can ever animate.

## Recommended approach

### Service (`app.py`)

- **No change.** The `working` state is already fully derivable client-side from the `/status`
  body: `renderBanner` decides it from `turn==='agent'` + `agent_status.at` freshness against
  `STALE_S` (`viewer.html:232-235`). `app.py` already emits `turn` and `agent_status` on
  `/status`. No new endpoint, field, or `meta.json` key.

### UI (`viewer.html`)

Three small edits, all inside `viewer.html`:

1. **`renderBanner` (around `viewer.html:226-248`) — carry the working state on a class.**
   The working branch is the third arm at `:235` (`msg="Agent is working on your feedback…"`).
   Today the message is written with `tt.textContent=msg` at `:246` for *all* states.
   - In the working branch only, set the marker: `bar.classList.add('working')`, and set the
     message **without** the trailing literal `…` (`msg="Agent is working on your feedback"`) so
     the animated `::after` is the *only* ellipsis (avoids a double "……").
   - In every other arm (parked `:233`, stale `:234`, and the whole `else` reviewer block
     `:238-245`), ensure the class is cleared: `bar.classList.remove('working')`. Place a single
     `bar.classList.remove('working')` at the top of `renderBanner` (right after the `if(!bar)return;`
     guard at `:230`) and add it back only in the working arm — this is the clean way to guarantee
     no stale `working` class survives a re-render into another state. **This removal is
     load-bearing:** without it the class would persist across the 2s poll when the agent goes
     stale or hands back, and a non-working banner would keep animating.

2. **`.turnbanner` CSS (around `viewer.html:80-83`) — add the animation rules.** Add adjacent to
   the existing `.turnbanner` rules:
   - An animated-ellipsis `::after` on `#turntext`, scoped to the working class:
     `#turnbanner.working #turntext::after{content:"…";...}` with a `@keyframes` that cycles the
     visible dots (e.g. steps the `content` or, more robustly, animates `clip-path`/width so the
     three-dot glyph is revealed one dot at a time, or animates `opacity` of the ellipsis as a
     gentle pulse). The animation must read on **both panes**: drive any colour from the existing
     theme vars (`--muted` / `--text`), never a hard-coded hex, because the banner already styles
     on `var(--text)` (`:80`) and the theme swaps via `@media (prefers-color-scheme: dark)` at
     `viewer.html:11`.
   - Keep it **subtle**: low-key, slow (~1.2–1.5s loop), muted colour — consistent with the
     banner's existing `rgba(127,127,127,.07)` background and 13px sans styling. No bouncing, no
     spinner ring that draws the eye away from the text.

3. **`prefers-reduced-motion` (same CSS block) — REQUIRED off-switch.** Add
   `@media (prefers-reduced-motion: reduce){ #turnbanner.working #turntext::after{animation:none;} }`
   so the ellipsis falls back to the static "…" (the `content:"…"` stays; only the `animation`
   stops). This restores today's exact appearance for users who opt out of motion.

**Animation choice: animated ellipsis via `#turntext::after`, not a spinner span.** Rationale:
(a) it needs **no new DOM element** — `renderBanner` already controls `#turntext`, so a `::after`
keyed by the `working` class is the smallest possible surface; (b) it reuses the ellipsis the
copy already implies, so the result reads as "still typing/working", which is the intended
semantics; (c) a spinner ring is a heavier, more attention-grabbing visual than this muted banner
wants. A tiny inline spinner span would also be acceptable, but it adds a markup element and a
second thing `renderBanner` must insert/remove; the ellipsis is cleaner for an equivalent effect.

> **Render-observable fork to settle at implementation, not in prose.** Decide the *keyframe
> technique* (stepping `content` strings vs animating `clip-path`/`width` over a static `…` vs an
> `opacity` pulse) by eyeballing all three in the throwaway container on **both** panes, and keep
> the one that is smooth and legible on light and dark. `content`-stepping keyframes have uneven
> browser support and can jump; a `width`/`clip-path` reveal over a literal `…` is usually the
> most robust. This is a 5-minute screenshot comparison, not an argument — record the chosen
> technique in the ticket's Work log.

## Rollout phases

A single shippable slice — one phase, one ticket.

### Phase 1 — Animate the working banner state (CSS-only)

- The three `viewer.html` edits above: marker class in `renderBanner`'s working arm + class
  removal everywhere else, the `@keyframes` ellipsis scoped to `#turnbanner.working #turntext`,
  and the `prefers-reduced-motion` off-switch.
- Validate with `py_compile` (sanity, no `app.py` change) + a render-smoke from the **rebuilt**
  throwaway container asserting the banner renders in the working state with the animation marker
  present, a both-pane screenshot, and a reduced-motion check. Ship.

## Non-goals

Explicit scope boundaries — what this epic is deliberately **not** doing.

- **No behind-the-scenes progress steps** (claimed → reading comments → editing → resolving →
  handing back). Stays in #27.
- **No streamed / diff-animated document updates** (the "jerky update" half of #27). Stays in #27.
- **No animation on any state but `working`.** Parked, stale ("may have stopped"), your-turn,
  done, and blocked banners are byte-for-byte unchanged.
- **No `app.py`, Dockerfile, MCP, or `meta.json` change.** No new served file (so no new
  `Dockerfile COPY` row is needed — the change is entirely inside the already-copied
  `viewer.html`).
- **No new dependency.** Pure CSS `@keyframes`; nothing vendored into `static/`.
- **No new JS timer / `setInterval`.** The existing ~2s poll re-render is all the JS involved, and
  even that only toggles a class — the motion itself is CSS.

## Key constraints

Hard rules the implementation must not violate (the project footguns, made specific).

- **`viewer.html` only.** Single self-contained HTML file with inline CSS/JS. No other file is
  touched. Because no *new served file* is introduced, the sprint-01 "new asset needs a
  `Dockerfile COPY`" footgun does **not** apply here — but the validation still rebuilds the image,
  because the served `viewer.html` is baked into the container at build time
  (`Dockerfile:8 COPY app.py viewer.html dashboard.html ./`), so a smoke against a stale container
  would not exercise the edit.
- **JS-rendered surface — a 200 is not a render.** The banner is written by `renderBanner` at
  runtime, so verification must drive headless Chrome to serialize the rendered DOM and assert the
  nodes, via `scripts/render-smoke.sh`, never a curl 200.
- **Dual-theme: must read on both panes.** The viewer themes via
  `@media (prefers-color-scheme: dark)` (`viewer.html:11`). The animation colour must come from
  the theme vars (`--muted`/`--text`), and the both-pane screenshot must **emulate the pane with
  scheme emulation**, NOT `--force-dark-mode`: use `--blink-settings=preferredColorScheme=0` (dark)
  / `=1` (light), because bare headless Chrome resolves *dark* by default and `--force-dark-mode`
  is an auto-invert filter, not scheme emulation — both would mis-verify the panes.
- **Class hygiene is load-bearing.** `renderBanner` runs every poll for every state; the `working`
  class MUST be removed in the non-working branches (single `remove` at the top of the function),
  or a banner that transitions working → stale/done/your-turn would keep animating. Verification
  must assert a non-working state does **not** carry the marker class.
- **Only behaviour, not a pixel breakpoint.** No responsive/breakpoint logic is added; this
  footgun does not apply.
- **No `do_HEAD`.** Not relevant (no header assertions here), but any header check would use a GET
  header-dump, never `curl -sI`.
- **`render-smoke.sh` is a flat matcher.** It supports only `tag` / `.class` / `tag.class` / `#id`
  (`render-smoke.sh:72`). It rejects descendant combinators (`#turnbanner .working`) **and an id
  with a `.class` suffix** (`#turnbanner.working`) as bad usage (exit 2), and cannot assert a
  `::after` pseudo-element (not a DOM node). Assert the marker with the **bare class `.working`**
  (only `#turnbanner` carries it, so it is unambiguous) and assert the banner with `#turnbanner` /
  `#turntext` separately — see Verification.

## Preferred execution order

1. **MR-061** — the only ticket. No dependencies; ships standalone.

## Ticket breakdown

How this epic decomposes into tickets (create in `tickets/` after G1, then link here).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-061 | Animate the viewer's `working`-state turn banner (CSS-only ellipsis) | ui | 1 |

### MR-061 — acceptance criteria (for the groomed ticket)

- **A1 — Working state animates.** When `/status` returns `turn==='agent'` with a **fresh**
  `agent_status` (`at` within `STALE_S`), the banner shows the "Agent is working on your feedback"
  copy with a continuously animating ellipsis. `#turnbanner` carries a `working` marker class in
  this state.
- **A2 — No other state animates.** Parked (`turn==='agent'`, no `agent_status`), stale
  (`turn==='agent'`, `at` older than `STALE_S` → "may have stopped"), your-turn, done, and blocked
  banners are visually unchanged and `#turnbanner` does **not** carry the `working` class.
- **A3 — Class hygiene across re-render.** A banner that transitions from working to a non-working
  state on a subsequent poll drops the `working` class and stops animating (verified by forcing a
  non-working `/status` and asserting the marker is absent).
- **A4 — Reduced motion.** Under emulated `prefers-reduced-motion: reduce` (via CDP
  `Emulation.setEmulatedMedia`, not a Chrome flag),
  `getComputedStyle($("#turntext"), '::after').animationName` resolves to **`none`** while the
  static `content:"…"` remains; without the emulation it resolves to the real `@keyframes` ident.
  The banner otherwise looks identical to today.
- **A5 — Dual-theme legibility.** The animated ellipsis reads on both light and dark panes
  (colour driven by theme vars, not a hard-coded hex), shown by both-pane screenshots.
- **A6 — Scope.** Only `viewer.html` changed; `git diff --stat` touches no other file. No new
  dependency, no `app.py`/Dockerfile/MCP/`meta.json` change.

Link MR-061 to GH **#27** in its body and note the rest of #27 is out of scope. This is its own
tiny epic (not part of agent-watcher / watcher-launch-fix). The existing file's em-dash house
style is fine to match in the edited CSS/JS comments.

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| **Double ellipsis** ("Agent is working……") if the literal `…` is left in the working message while the `::after` adds another. | Drop the trailing `…` from the message string in the working branch only; the `::after` is the sole ellipsis. Verified visually in the both-pane screenshot. |
| **Stale `working` class keeps a non-working banner animating** after a state transition. | Single `bar.classList.remove('working')` at the top of `renderBanner`, re-added only in the working arm. A3 asserts the marker is absent in a non-working state. |
| **Pseudo-element can't be render-smoke-asserted.** `::after` is not a DOM node, so `render-smoke.sh` cannot count it. | Assert the **state** instead: render the working `/status`, dump the DOM, and assert `#turnbanner` plus the marker via the **bare class `.working`** (a compound `#turnbanner.working` is rejected by `render-smoke.sh:72`; only `#turnbanner` carries `.working`, so the bare class is unambiguous). The animation *presence* is proven by the screenshot; render-smoke proves the marker/state wiring. |
| **Verification false-passes by resolving the wrong pane** (bare headless = dark; `--force-dark-mode` = invert filter). | Emulate scheme with `--blink-settings=preferredColorScheme=0/1`; capture and eyeball both panes. |
| **Smoke runs against a stale container** and never exercises the edit. | Rebuild a throwaway image from the working tree before smoking; run on a scratch port, never 8139 (live) or 8137 (compose). |
| **Motion is too loud / distracting** for the muted banner. | Subtle, slow (~1.2–1.5s) muted ellipsis; choose the smoothest keyframe technique by eyeballing in the container before committing. |

## Verification

All commands run from a throwaway container built from the working tree, on a **scratch port**
(example uses `8765` — never `8139` live, never `8137` compose). All temp files live under the
gitignored `.scratch/`; **clean its contents when done** (do not `rmdir` it).

### 0. Compile sanity (no `app.py` change, but the gate names it)

```bash
python3 -m py_compile app.py    # expect: no output, exit 0
```

### 1. Build + run a throwaway container on a scratch port

```bash
mkdir -p .scratch
docker build -t mdreview-mr061 .
docker run -d --name mr061-smoke -p 8765:8080 -v "$PWD/.scratch/data:/data" mdreview-mr061
BASE=http://localhost:8765
curl -s "$BASE/healthz"                          # expect: ok / 200
```

### 2. Force the `working` state, then capture the review id

Create a review, hand the turn to the agent, and claim a **fresh** lease so `/status` returns the
working state (`turn==='agent'` + fresh `agent_status.at`):

```bash
id=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"MR-061 smoke","markdown":"# Working banner smoke\n\nbody\n"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')

# 1. flip the turn to the agent (the `{to:"agent"}` arm of /handoff)
curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' \
  -d '{"to":"agent"}'

# 2. claim the lease so /status returns a FRESH working agent_status.
#    There is NO /ping route — the lease claim is the {state:"working"} arm of the SAME
#    /handoff endpoint (verified app.py:635-662). The grant stamps at=now, so the banner
#    takes the genuine working arm, not the stale "may have stopped" arm.
curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' \
  -d '{"state":"working","owner":"smoke-owner"}'

# confirm /status is the working state (turn==agent, agent_status.state==working, fresh at)
curl -s "$BASE/api/reviews/$id/status"
# expect JSON with: "turn":"agent", "agent_status":{"state":"working","at":<recent epoch>, ...}
```

> Both steps hit `POST /api/reviews/{id}/handoff`: the `{to:"agent"}` arm flips the turn (parks the
> lease), the `{state:"working","owner":…}` arm claims/renews it and stamps `at=now` (verified
> `app.py:635-662`; the viewer posts handoff to `API+'/handoff'` at `viewer.html:222`). The
> equivalent MCP path is `create_review` → `hand_back`/handoff to agent → `ping_working(id,
> owner=…)`. Either way the goal is a `/status` body with `turn==='agent'` and a fresh
> `agent_status` so `renderBanner` takes the working arm, not the stale arm.

### 3. render-smoke: working banner renders with the marker (rebuilt container)

```bash
# the banner is rendered by renderBanner from /status; assert the real nodes (flat selectors only)
scripts/render-smoke.sh "$BASE/review/$id" '#turnbanner' '#turntext'
# expect exit 0 (both nodes present)
```

Assert the **working marker class** is present in the working state and **absent** in a non-working
state. `render-smoke.sh` is a flat matcher: a compound `#turnbanner.working` (an id with a `.class`
suffix) is REJECTED by its `_VALID` regex (`render-smoke.sh:72`) as bad usage (exit 2), not a render
miss. So assert the **bare class `.working`** — it validates, and only `#turnbanner` ever carries
that class, so it is unambiguous:

```bash
# working state -> .working renders (only #turnbanner carries it)
scripts/render-smoke.sh "$BASE/review/$id" '.working'   # expect exit 0 (1 node)

# now flip to a non-working state (reclaim the turn -> reviewer's turn) and re-assert ABSENCE
curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' \
  -d '{"to":"reviewer","by":"reviewer"}'
scripts/render-smoke.sh "$BASE/review/$id" '.working'   # expect exit 1 (0 nodes: marker gone)
# (re-claim working again before the screenshot steps if needed — repeat the step-2 working claim)
```

> Note: `render-smoke.sh` cannot assert a `::after` pseudo-element (not a DOM node). The marker
> class on `#turnbanner` is the render-smoke-able proxy for "working state wired up"; the
> animation's visible presence is proven by the screenshots below.

### 4. Both-pane screenshots (scheme emulation, NOT `--force-dark-mode`)

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"   # or your binary
# LIGHT pane
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --blink-settings=preferredColorScheme=1 --virtual-time-budget=2500 \
  --screenshot=.scratch/banner-light.png --window-size=1100,700 "$BASE/review/$id"
# DARK pane
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --blink-settings=preferredColorScheme=0 --virtual-time-budget=2500 \
  --screenshot=.scratch/banner-dark.png --window-size=1100,700 "$BASE/review/$id"
```

Eyeball both: the working banner shows the animating ellipsis and reads clearly on each pane. (A
screenshot is a single frame, so it proves first-paint + presence, not the motion itself — the
motion is established by the keyframe CSS + the render-smoke marker; the screenshot confirms the
ellipsis renders legibly on both panes.)

### 5. Reduced-motion check (concrete computed-style probe)

This is a `getComputedStyle` assertion on the `::after` pseudo, not a screenshot eyeball: a still
frame can't distinguish "paused" from "off". A pseudo-element's `animation-name` is not visible in
`--dump-dom`, so evaluate it in the page. **Use CDP `Emulation.setEmulatedMedia` to emulate
`prefers-reduced-motion: reduce`, not a `--force-prefers-reduced-motion` Chrome flag** — the CDP
route is portable across headless builds (some lack the flag) and is the same `setEmulatedMedia`
mechanism this plan already relies on for scheme.

Pass condition — run the probe twice on `/review/$id` (working state):

- **With** `Emulation.setEmulatedMedia({features:[{name:'prefers-reduced-motion',value:'reduce'}]})`:
  `getComputedStyle($("#turntext"), '::after').animationName` resolves to **`none`** (animation
  disabled) while the static `content:"…"` remains.
- **Without** the emulation (default): the same probe resolves to a **real keyframe name** (the
  `@keyframes` ident the ticket defines), i.e. the ellipsis animates.

```js
// CDP-driven evaluate (e.g. via puppeteer / chrome-remote-interface against the headless target):
//   page.emulateMediaFeatures([{name:'prefers-reduced-motion', value:'reduce'}])   // or no-emulate
//   await page.goto(`${BASE}/review/${id}`)
//   await page.evaluate(() =>
//     getComputedStyle(document.querySelector('#turntext'), '::after').animationName)
//   // => 'none' under reduce; the keyframe ident (non-'none') without it
```

Also capture a reduced-motion screenshot for the record (scheme emulation, no auto-invert):

```bash
# CDP setEmulatedMedia is authoritative for the assertion above; this screenshot is just a visual
# record that the static "…" still renders under reduce on a chosen pane.
"$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --blink-settings=preferredColorScheme=1 --virtual-time-budget=2500 \
  --screenshot=.scratch/banner-reduced.png --window-size=1100,700 "$BASE/review/$id"
```

The pass condition is: **reduced-motion → `animationName === 'none'`, static `…` shown;
default → `animationName` is the real keyframe ident, ellipsis animates.**

### 6. Scope + teardown

```bash
git diff --stat            # expect: only viewer.html changed
docker rm -f mr061-smoke && docker rmi mdreview-mr061
rm -rf .scratch/*          # clean CONTENTS, keep the gitignored dir
```

## Assumptions and open questions

Recorded; proceeding on the stated assumptions (no BLOCKER-FOR-HUMAN).

- **(minor) Exact lease/handoff endpoint shape for forcing `working`.** Confirmed against
  `app.py`: there is **no `/ping` route**. Both the turn flip and the lease claim go through the
  single `POST /api/reviews/{id}/handoff` endpoint — the `{to:"agent"}` arm flips the turn, and the
  `{state:"working","owner":…}` arm claims/renews the lease and stamps `at=now`
  (`app.py:635-662`; the viewer posts handoff to `API+'/handoff'` at `viewer.html:222`). The
  equivalent MCP path is `ping_working`. Justification: these are existing, exercised paths; the
  smoke recipe in Verification now uses the confirmed handoff shape, so nothing further needs
  pinning at grooming.

- **(minor) Animation keyframe technique** (stepping `content` vs `width`/`clip-path` reveal over a
  static `…` vs `opacity` pulse). Assumption: a `width`/`clip-path` reveal over a literal `…` (or a
  gentle `opacity` pulse) — chosen by eyeballing all three on both panes in the throwaway
  container, since `content`-stepping keyframes have uneven browser support and can jump.
  Justification: this is a render-observable detail settled by a 5-minute screenshot comparison at
  implementation, not a design fork; any of the three satisfies the ACs.

- **(minor) Marker class name.** Assumption: `working` on `#turnbanner` (so
  `#turnbanner.working #turntext::after` scopes the animation in CSS, and `render-smoke.sh` asserts
  it via the **bare class `.working`** — the compound `#turnbanner.working` is rejected by the flat
  matcher (`render-smoke.sh:72`), but only `#turnbanner` carries `.working` so the bare class is
  unambiguous). Justification: matches the state name and the existing `.turnbanner.show` toggle
  convention; any unique class works.

- **(load-bearing — answered by assumption, safe default) Animate the ellipsis vs add a spinner
  span.** Assumption: animate an ellipsis via `#turntext::after` (no new DOM element). This is the
  one design fork that shapes the edit. Justification: it is the smallest surface (no markup
  added, `renderBanner` only toggles a class), reuses the copy's implied "…", and is subtler than a
  spinner ring — which fits the muted banner. A spinner span is an acceptable fallback if a clean
  ellipsis animation proves visually poor on a pane, but the ellipsis is the default. This is safe
  to default because both options satisfy every AC and the choice is reversible within the same
  one-file ticket.

## Review resolutions

### 2026-06-24 — G1 staff-critic (PASS-WITH-NITS; design approved, fixes in the smoke recipe)

Source: `reviews/working-banner-animation-plan-review-2026-06-24.md`. Design unchanged; all edits
are in the Verification / smoke recipe so the ticket author writes a smoke that actually runs.

- **B1 (blocking — wrong lease-claim endpoint).** The recipe posted to a non-existent
  `POST /api/reviews/{id}/ping`. There is no `/ping` route: the lease claim is the
  `{state:"working","owner":…}` arm of `POST /api/reviews/{id}/handoff` (verified `app.py:635-662`).
  Rewrote the force-working-state step to: create → `handoff {to:"agent"}` (flip) →
  `handoff {state:"working","owner":"smoke-owner"}` (claim, stamps `at=now`) → render. Updated the
  matching open-question assumption to the confirmed handoff shape (no `/ping`).
- **B2 (blocking — render-smoke rejects `#turnbanner.working`).** `render-smoke.sh:72`'s `_VALID`
  rejects an id with a `.class` suffix (exit 2). Replaced every `#turnbanner.working` assertion with
  the **bare class `.working`** (validates; only `#turnbanner` carries it, so unambiguous): assert
  `.working` (exit 0) in the working state, absent (0 nodes / exit 1) after the reclaim. Updated the
  flat-matcher constraint, the risks-table row, the marker-class assumption, and the `::after` risk
  row to match. Kept the flat `#turnbanner` / `#turntext` assertions.
- **W1 (worth-considering — pin the reduced-motion probe).** Made the reduced-motion check a
  concrete assertion: under emulated `prefers-reduced-motion: reduce`,
  `getComputedStyle($("#turntext"), '::after').animationName` must resolve to `none`, vs the real
  `@keyframes` ident without the emulation. Pinned in both Verification §5 and AC A4.
- **N1 (nit — emulation portability).** Switched the reduced-motion emulation from a
  `--force-prefers-reduced-motion` flag to CDP `Emulation.setEmulatedMedia({features:[{name:
  'prefers-reduced-motion',value:'reduce'}]})` for portability across headless builds, consistent
  with the scheme-emulation approach the plan already uses.

Everything the critic confirmed sound is unchanged: the working-vs-stale arm distinction, the
remove-class-at-top + add-in-working-arm pattern, the `.show` non-collision, `--muted`/`--text`
theme vars, dropping the literal `…` for the `::after`, and the single-ticket scope.
