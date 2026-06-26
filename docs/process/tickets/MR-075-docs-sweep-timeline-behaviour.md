---
id: MR-075
title: "Docs sweep: agent-turn progress timeline + timer behaviour"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: docs            # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-26
epic: viewer-transparency
depends_on: [MR-073]
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Document the new agent-turn transparency so the "Detecting the human is done" / turn-baton docs reflect
that the viewer now shows a live progress timeline + timer while an agent works. MR-074 (the
`agent_status.message` status-hint contract) is cut, so this is the timeline/timer behaviour only.

## Acceptance criteria

- [ ] `CLAUDE.md` (and `README.md`/`AGENTS.md` where the turn-baton / "Agent is working" UX is
      described) note that the viewer renders a **derived live progress timeline** (Connected → Editing
      → Updating comments → Done/Stopped) + a **live elapsed timer** and a **final revision duration**,
      so a long-but-working run reads as progress, not a freeze. Make clear it is **derived from
      existing `/status` signals** (no new endpoint/field; the agent needs to do nothing extra).
- [ ] Note the documented limitation: the **final duration** is client-captured, so a page loaded after
      the agent finished shows no duration (only a live-watching page has it).
- [ ] Note the literal tool-call stream is a **deferred** follow-on (not shipped), so docs don't imply
      a per-tool-call feed exists.
- [ ] No stale claim that the working banner is static/opaque.
- [ ] `python3 -m py_compile app.py watch.py` (sanity; untouched).

## Notes / context

- Epic plan: `epics/viewer-transparency-plan.md` (MR-075). Depends on MR-073 being real so the prose
  matches what ships. Docs-only — no container needed; gate is the grep + py_compile sanity.

## Work log

- `2026-06-24` — `CLAUDE.md` turn-baton section: documented the MR-073 live progress timeline + ticking timer + final revision duration (derived from `/status`, agent does nothing extra; step-level, the literal tool-call stream deferred; final duration client-captured). No stale "static banner" claim.

## Validation

_Verified 2026-06-24 — grep coverage + py_compile sanity. PASS._

- Grep the touched docs cover the timeline + timer + the client-capture limitation + the deferred
  stream-json note; confirm no "static/opaque banner" claim remains. `py_compile` sanity.

## Follow-ups

- None. Closes the docs surface for the shipped (step-level) part of #27.
