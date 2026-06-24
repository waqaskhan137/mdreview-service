---
id: sprint-26
name: viewer-transparency — live agent-turn progress timeline + timer
status: active         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: While an agent works a turn, show a live progress timeline (Connected → Editing → Updating comments → Done/Stopped) derived from existing /status signals, plus a live elapsed timer and a final revision duration — so a long-but-working run reads as progress, not a freeze.
close_review:          # reviews/sprint-26-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Land the `viewer-transparency` batch (GH #27, step-level scope): MR-073 adds the derived live timeline
+ timer in `renderBanner` (UI-only, no service change, no agent instrumentation), MR-075 sweeps the
docs. The headline: the owner watching a ~2.5-min run sees live stages + a ticking timer instead of a
static "Agent is working…" that's indistinguishable from a hang. The literal tool-call stream (Tier-2)
is deferred. MR-074 (the `agent_status.message` contract) is cut (the plumbing already round-trips).
Sprint closes at G7.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-073 | Live progress timeline + elapsed/duration timer in the working banner (derived from /status) | ui | P1 | ready |
| MR-075 | Docs sweep: agent-turn progress timeline + timer behaviour | docs | P2 | ready |

## Preferred execution order

1. **MR-073** (ui) — the derived timeline + timer in `renderBanner`. The headline; standalone.
2. **MR-075** (docs) — sweep the turn-baton docs. `depends_on` MR-073 (prose must match what ships).

## Notes / retro

- G1 PASS 2026-06-24 (staff-critic GO-WITH-NITS, 2 nits folded; owner chose step-level over the literal
  tool-call stream — see `reviews/viewer-transparency-plan-review-2026-06-24.md`). MR-074 cut (the
  `ping_working` `message` already round-trips; only the viewer display was missing → MR-073).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at `reviews/sprint-26-close-review-YYYY-MM-DD.md`,
      verifying shipped work against each ticket's ACs — **including the node-CDP lifecycle drive** of
      the timeline (the live steps, the ticking timer, the final duration, the signal-honesty
      reply-then-`blocked` path, and the MR-062/066/067/068 no-regression re-asserts; `render-smoke.sh`
      can't drive a time-dependent banner) — with findings resolved or carried;
- [ ] retro + carry-overs recorded above, and `close_review:` set in frontmatter.

**G7 scope note.** MR-073 is a `viewer.html` change whose deliverable is a *time-dependent,
signal-sequenced* JS state, so it owes a **node-CDP eval driver** (`timeline_smoke.py`, the
`agent_smoke.py` pattern) against a **rebuilt throwaway container** (scratch port, never
8139/8137/compose-against-the-live-volume) walking the lifecycle + crash + pickup-timeout, both panes
(`preferredColorScheme`, never `--force-dark-mode`), reduced-motion via computed `animationName`. A
bare `render-smoke.sh` against the timeline is a first-paint complement only, not the proof. MR-075 is
docs-only (grep + py_compile). All temp under the gitignored `.scratch/`; evidence to
`reviews/sprint-26-render-evidence-2026-06-24/`.
