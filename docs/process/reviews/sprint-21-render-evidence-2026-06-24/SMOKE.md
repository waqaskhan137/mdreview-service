# MR-061 G4/G7 render-smoke evidence — animated working banner

**Ticket:** MR-061 (issue #27) — animated waiting ellipsis on the turn banner, *working state only*.
**Branch:** `MR-061-animate-working-banner`.
**Method:** rebuilt image (`mdreview-mr061-smoke`) → disposable container on scratch port `8766` →
forced the genuine *working* banner arm via the handoff API → render-smoke DOM-node counts + headless-Chrome
screenshots (both schemes) + CDP reduced-motion probe. No live/compose ports touched; throwaway image +
container removed at teardown.

## The change asserted
`viewer.html`: `renderBanner` adds a `.working` class to `#turnbanner` only in the genuine "Agent is working"
arm (and removes it otherwise), and drops the literal trailing `…` from that message. CSS animates
`#turnbanner.working #turntext::after` (pulsing-opacity ellipsis, keyframe `turnworking`), disabled under
`@media (prefers-reduced-motion: reduce)`.

## Results (one line per check)

| Check | Result |
|---|---|
| Docker image build (rebuilt, not just file change) | **PASS** |
| Container `/healthz` → `{"ok": true}` | **PASS** |
| Working-state render: `#turnbanner` present (1 node) | **PASS** |
| Working-state render: `#turntext` present (1 node) | **PASS** |
| Working-state render: `.working` present (1 node) — class applied | **PASS** |
| Negative: `.working` ABSENT after turn reclaimed to reviewer (0 nodes, exit 1) | **PASS** |
| Light-pane screenshot — banner + ellipsis visible/legible | **PASS** |
| Dark-pane screenshot — banner + ellipsis visible/legible | **PASS** |
| Reduced-motion `reduce` → `animationName == 'none'` | **PASS** |
| No-preference → `animationName == 'turnworking'` | **PASS** |

**Overall: PASS.**

## Raw outputs

### 1. Build
`docker build -t mdreview-mr061-smoke .` → `naming to docker.io/library/mdreview-mr061-smoke:latest done`
(success; tail showed all 10 steps DONE).

### 2. Health
`curl -s localhost:8766/healthz` → `{"ok": true}`

### 3. Forced working state (review id `9f0eca59dc`)
`POST /handoff {"to":"agent"}` then `POST /handoff {"state":"working","owner":"smoke-owner"}`.
`GET /status`:
```
"turn": "agent",
"agent_status": { "state": "working", "message": "", "owner": "smoke-owner", "at": <fresh> }
```

### 4. Working-state render-smoke (flat selectors)
```
$ scripts/render-smoke.sh http://localhost:8766/review/9f0eca59dc '#turnbanner' '#turntext' '.working'
  ok : #turnbanner (1 node)
  ok : #turntext (1 node)
  ok : .working (1 node)
exit=0
```

### 5. Negative check (turn reclaimed to reviewer)
`POST /handoff {"to":"reviewer","by":"reviewer"}` → `turn=reviewer`.
```
$ scripts/render-smoke.sh http://localhost:8766/review/9f0eca59dc '.working'
render-smoke: 1 selector(s) matched no rendered element: .working
  MISSING: .working (0 nodes)
exit=1
```
`.working` is carried by the working arm only.

### 6. Screenshots
`banner-light.png` (`--blink-settings=preferredColorScheme=1`) and `banner-dark.png`
(`preferredColorScheme=0`). Both render the banner "Agent is working on your feedback…" with the
trailing ellipsis (the `::after`) present and legible on its pane.

### 7. Reduced-motion probe (CDP `Emulation.setEmulatedMedia` + `getComputedStyle(...,'::after').animationName`)
```
prefers-reduced-motion=reduce          animationName='none'
prefers-reduced-motion=no-preference   animationName='turnworking'
```

## Notes
- Animation is opacity-pulsing, so a single static frame correctly shows the ellipsis present.
- Throwaway container `mr061smoke` + image `mdreview-mr061-smoke` removed at teardown; `.scratch/` cleaned.
