---
id: sprint-15
name: agent-handoff-baton — Chunk 2 (viewer turn UI)
status: closed         # planning | active | closed
start: 2026-06-23
end: 2026-06-24
goal: Ship the viewer turn UI (MR-052) — Send to agent button + 6-state banner + Take-back-the-turn reclaim + lastTurn poll — driven by the MR-051 baton contract, so a reviewer can run the whole loop from the review page.
close_review: reviews/sprint-15-close-review-2026-06-23.md
---

## Goal

Land **Chunk 2** of the agent-handoff-baton epic. Success by the end date: in `viewer.html`, a
turn-gated **Send to agent** button, a **6-state first-match status banner** (parked / working /
stale / done / blocked / your-turn), and an always-available **Take back the turn** control, all
driven purely from the `/status` body the 2s poll already fetches (the new `turn` / `agent_status`
fields MR-051 surfaces). The source-push-then-banner ordering rule holds so the "Draft updated by AI"
toast and the banner do not race. `viewer.html` only; no `app.py`, no MCP, no new served file.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-052 | Viewer turn UI — Send button + 6-state banner + reclaim + `lastTurn` poll | ui | P2 | done |

## Preferred execution order

1. MR-052 — the viewer turn UI (depends on MR-051, which shipped in sprint-14).

## Notes / retro

_Filled in as the sprint runs and at close._

- Chunk 2 of 3. Depends on MR-051 (`done`, sprint-14). MR-053 (Chunk 3, MCP + CLAUDE.md) remains
  `ready` for a later sprint.
- **Carries the 2 sprint-14 G7 NITs into MR-052:** (1) `agent_status.at` is **float epoch seconds**,
  so the staleness check must be `(Date.now()/1000) - at > N`; (2) the non-JSON→400 path is a
  recorded observation only (no action). Both handled — staleness uses epoch seconds.
- **Closed 2026-06-23. G7 PASS** (`reviews/sprint-15-close-review-2026-06-23.md`, staff-critic,
  independent rebuild-from-disk + render-smoke + all 6 banner rows driven via curl + `--dump-dom`
  (row 3 forced by backdating `at`) + XSS textContent probe, 0 BLOCKER / 0 SHOULD / 3 NITs). MR-052
  `done`, **no carry-overs**. The 3 G7 NITs were addressed post-review: NIT-1 (dead `lastTurn`)
  removed, NIT-3 (stale-row caps) fixed, NIT-2 (cosmetic flicker) accepted.
- **Epic stays `active`:** Chunks 1+2 shipped; **MR-053 (Chunk 3, MCP + CLAUDE.md) remains** for the
  next sprint.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] MR-052 is `done`;
- [x] a **staff-critic sprint-close review** exists at `reviews/sprint-15-close-review-2026-06-23.md`,
      verifying MR-052 against its acceptance criteria — and because a **product page (`viewer.html`)
      is touched**, `scripts/render-smoke.sh` against the viewer asserting the `.sendagent` /
      `.turnbanner` / `.reclaim` nodes **plus a screenshot** under `reviews/sprint-15-render-evidence-2026-06-23/`,
      and the container rebuild + `curl /healthz` + `/api/reviews` smoke;
- [x] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
