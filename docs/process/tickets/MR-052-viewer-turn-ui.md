---
id: MR-052
title: Viewer turn UI — Send button + 6-state banner + reclaim + lastTurn poll
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P2
sprint:                # scheduled into the sprint AFTER sprint-14 (Chunk 1 ships first)
epic: agent-handoff-baton
depends_on: [MR-051]
branch:                # MR-052-viewer-turn-ui, once work starts
created: 2026-06-23
updated: 2026-06-23
---

## Goal

The human-facing turn surface in `viewer.html`: a **Send to agent** button, a **status banner** that
tells the reviewer what the agent is doing (parked / working / stale / done / blocked / your-turn),
and an always-available **Take back the turn** escape — all driven by the `/handoff` + `/status`
contract MR-051 ships. `viewer.html` only; no `app.py`, no new served file, no dashboard change.

## Acceptance criteria

- [ ] **Send button** in the dock row next to History (`#histbtn`, `viewer.html:171-176`), stable
      class `sendagent`. Enabled only while `turn === "reviewer"`; on click `POST /handoff
      {to:"agent"}`, then disabled + relabelled ("Sent — agent's turn"); re-enabled when a later poll
      sees `turn` back to `reviewer`.
- [ ] **Status banner**, stable class `turnbanner`, a thin bar under the top bar (after `#docmeta`,
      `viewer.html:160`). A **first-match decision** (agent rows keyed on `turn === "agent"`, reviewer
      rows on `agent_status.state`) with all six rows:
      1. `turn=agent`, `agent_status` absent → "Sent — waiting for an agent to pick this up."
      2. `turn=agent`, `agent_status.at` recent → "Agent is working on your feedback…"
      3. `turn=agent`, `agent_status.at` stale (`now - at > N`, N ≈ 3 min) → "Agent may have stopped — Take back the turn?"
      4. `turn=reviewer`, `agent_status.state="done"` → "Agent updated the draft: «message». Your turn."
      5. `turn=reviewer`, `agent_status.state="blocked"` → "Agent needs you: «message»."
      6. `turn=reviewer`, otherwise → "Your turn. Comment, then Send to agent."
      Derived purely from the `/status` body the poll already fetches (no new fetch).
- [ ] **Take back the turn** control, stable class `reclaim`, shown whenever `turn === "agent"`
      (rows 1–3), always clickable; on click `POST /handoff {to:"reviewer", by:"reviewer"}`.
- [ ] **Poll extension.** The 2s poll (`viewer.html:595-607`) gains a `lastTurn` (alongside `lastSrc`
      `:203` / `lastCmt` `:204`). **Ordering rule:** on a tick that sees both a source push and a turn
      flip, run `await load()` first (it re-fetches `/status` and resets `lastSrc`, `:318-321`), then
      update the banner from a `/status` body, so the "Draft updated by AI" toast (`:603`) and the
      banner do not race. The banner also updates on a **turn-only** tick (add an `s.turn !==
      lastTurn` branch), and is set once on first load from `load()`.
- [ ] **Validation (G4 ui).** Rebuild a **throwaway** container (scratch port, never 8139/8137);
      `scripts/render-smoke.sh "$B/review/$ID" '.sendagent' '.turnbanner' '.reclaim'` exits 0 (flat
      class selectors only — render-smoke rejects attribute selectors / descendant combinators).
- [ ] **Interaction proof (G1 SHOULD-1).** A node-CDP check (repo `agent_smoke.py` / MR-049 pattern)
      that is a **timed, multi-step drive across the 2s poll** (not a single navigate-and-read):
      (a) initial `turn=reviewer` — Send enabled, banner row 6;
      (b) click Send → `{to:agent}` fires, banner → row 1, then after a scripted `{state:working}` POST
      → row 2, Send disabled;
      (c) click reclaim → `{to:reviewer,by:reviewer}`, banner → a reviewer row, Send re-enabled;
      (d) push `{to:reviewer,state:done,message}` → row 4 renders and the source-push toast does not
      clobber it (the ordering rule).
      Plus a screenshot under `reviews/sprint-NN-render-evidence-*` (a product page was touched). If
      any banner styling is pane-adaptive, capture both panes via `Emulation.setEmulatedMedia` /
      `preferredColorScheme` — **never** `--force-dark-mode`.

## Notes / context

- Epic plan §UI (`viewer.html`) and §Verification → MR-052.
- Anchors: `#dockbar`/`#histbtn` `viewer.html:171-176`; `#docmeta` `:160`; poll `:595-607`; `load()`
  `:318-321`; `lastSrc`/`lastCmt` `:203-204`; the existing in-gesture poll early-return `:600` (the
  banner simply updates on the next tick — acceptable, it is persistent state).
- No `app.py` change. `viewer.html` is already in `Dockerfile:8`, so no Dockerfile COPY is needed
  (stated so a reviewer does not flag a phantom missing COPY).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Independent of MR-053 (no dependency between the viewer and the MCP/docs work).
