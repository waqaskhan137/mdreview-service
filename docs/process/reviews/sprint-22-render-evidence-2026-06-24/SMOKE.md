# MR-062 render-smoke evidence — banner loading spinner

**Ticket:** MR-062 (issue #27, supersedes MR-061) — replace the opacity-pulse ellipsis on the
agent-turn waiting banner with a rotating CSS spinner.
**Branch:** `MR-062-banner-loading-spinner`
**Gate:** G4 / G7 render-smoke.
**Date:** 2026-06-24.

## What was proven

`viewer.html` swaps MR-061's pulse for a rotating ring. `renderBanner` adds the `loading` class to
`#turnbanner` in **both** agent-turn *waiting* arms — the `if(!as)` "Sent — waiting for pickup" arm
(the MR-061 gap, now broadened) **and** the "Agent is working…" arm — but **not** the stale
"may have stopped" arm nor the reviewer turn. CSS animates
`#turnbanner.loading #turntext::before` (11px ring, `border-top-color:transparent`,
`animation:turnspin .8s linear infinite`); `@media (prefers-reduced-motion:reduce)` disables the
animation to a static ring.

## Environment

- Throwaway image `mdreview-mr062-smoke` built from repo root (`docker build`). **Build: PASS.**
- Disposable container `mr062smoke` on **scratch port 8768** (`-p 8768:8080`, `MDREVIEW_DATA=/data`).
  Never 8137/8139; no `docker compose up`. `GET /healthz` → `{"ok": true}`. **Healthz: PASS.**
- Review id: `1b9f0b4f47`.
- Selector assertions via `scripts/render-smoke.sh` (headless Chrome `--dump-dom` → stdlib element
  counter; only flat `tag`/`.class`/`#id`; exit 1 on 0 matches). The script **rejects** the compound
  `#turnbanner.loading` (exit 2), so each state asserts the flat `.loading` class is present/absent
  while the banner's `#turntext` renders.

## Per-state results

State is set purely via `POST /api/reviews/<id>/handoff` (no MCP needed for state).

| State | Handoff body | turn / agent_status | Selector(s) | Node count | Exit | Verdict |
|---|---|---|---|---|---|---|
| **A — Sent, waiting for pickup** (the broadened case; MR-061 gap) | `{"to":"agent"}` | `turn=agent`, `agent_status=null` | `#turntext`, `.loading` | 1, 1 | 0 | **PASS** — spinner present in waiting-for-pickup |
| **B — Agent is working** | `{"state":"working","owner":"smoke"}` (after `{to:agent}`) | `turn=agent`, `state=working` | `.loading` | 1 | 0 | **PASS** — spinner present |
| **D — reviewer turn** (reclaim arm) | `{"to":"reviewer","by":"reviewer"}` | `turn=reviewer`, lease retained | `.loading` | 0 | 1 | **PASS** — spinner ABSENT (exit 1 = expected) |
| **D — banner still renders** | (same state) | — | `#turntext` | 1 | 0 | **PASS** — banner itself present |

Raw `render-smoke.sh` output:

```
# State A — http://localhost:8768/review/1b9f0b4f47  '#turntext' '.loading'
  ok : #turntext (1 node)
  ok : .loading (1 node)
RENDER_SMOKE_A_EXIT=0

# State B — '.loading'
  ok : .loading (1 node)
RENDER_SMOKE_B_EXIT=0

# State D — '.loading'  (absent → exit 1 = PASS)
render-smoke: 1 selector(s) matched no rendered element: .loading
  MISSING: .loading (0 nodes)
RENDER_SMOKE_D_LOADING_EXIT=1

# State D — '#turntext'  (banner still renders)
  ok : #turntext (1 node)
RENDER_SMOKE_D_TURNTEXT_EXIT=0
```

## Reduced-motion probe (CDP)

Loaded `/review/1b9f0b4f47` in the working state in headless Chrome over the DevTools Protocol, read
`getComputedStyle(document.querySelector('#turntext'),'::before').animationName`:

```json
{"without_emulation": "turnspin", "with_reduced_motion": "none"}
```

- Without emulation → `animationName == "turnspin"`. **PASS** (spinner animates).
- With `Emulation.setEmulatedMedia({features:[{name:'prefers-reduced-motion',value:'reduce'}]})`
  → `animationName == "none"`. **PASS** (static ring; honours the media query).

## Both-pane screenshots (State B — Agent is working)

Headless Chrome, `--blink-settings=preferredColorScheme=1` (light) / `=0` (dark). The partial ring
(`border-top-color:transparent`) sits left of "Agent is working on your feedback…" and is legible on
both panes.

- `banner-working-light.png` — **PASS** (ring visible on light pane).
- `banner-working-dark.png` — **PASS** (ring visible on dark pane).

## Summary — one line per check

- build (`docker build mdreview-mr062-smoke`): **PASS**
- healthz (`GET /healthz` on :8768): **PASS**
- State A `.loading` present (`#turntext` + `.loading`, exit 0): **PASS**
- State B `.loading` present (exit 0): **PASS**
- State D `.loading` absent (exit 1) + `#turntext` present (exit 0): **PASS**
- reduced-motion `turnspin` / `none`: **PASS**
- both-pane screenshots (ring legible light + dark): **PASS**

**Overall: PASS.** Teardown: container `mr062smoke` + image `mdreview-mr062-smoke` removed; `.scratch/`
cleaned.
