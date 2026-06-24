---
id: sprint-14
name: agent-handoff-baton — Chunk 1 (server baton contract)
status: closed         # planning | active | closed
start: 2026-06-23
end: 2026-06-24
goal: Ship the server-side handoff baton contract (MR-051) — POST /handoff + 4 meta.json fields + /status surfacing — additive and invisible, so the viewer (MR-052) and agent (MR-053) surfaces can be built against it.
close_review: reviews/sprint-14-close-review-2026-06-23.md
---

## Goal

Land **Chunk 1** of the agent-handoff-baton epic to its own PR. Success by the end date: the
`POST /api/reviews/{id}/handoff` route exists with all four guarded body forms under `_lock`, the
four additive `meta.json` fields (`turn`, `turn_updated`, `handoff`, `agent_status`) are written and
surfaced on `GET /status`, every existing flow is byte-for-byte unchanged for a review that never
touches `/handoff`, and the epic's MR-051 curl round-trip (flip → lease-claim → foreign-owner 409 →
hand-back → reclaim → idempotent re-flip → 400 on malformed → dashboard-status invariance) passes on
a throwaway container. This is the only chunk in this sprint; MR-052 and MR-053 are committed to a
later sprint after Chunk 1 ships.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-051 | Handoff baton contract — `POST /handoff` + 4 `meta.json` fields + `/status` surfacing | svc | P1 | done |

## Preferred execution order

1. MR-051 — the server baton contract (no dependencies; foundation for MR-052/MR-053).

## Notes / retro

_Filled in as the sprint runs and at close._

- Chunk 1 of 3 (chunked delivery per product-owner request). MR-052 (viewer UI) and MR-053 (MCP +
  CLAUDE.md) are `ready` but committed to the next sprint after this one ships.
- **Closed 2026-06-23. G7 PASS** (`reviews/sprint-14-close-review-2026-06-23.md`, staff-critic,
  independent rebuild + 15-step smoke on a throwaway container, 0 BLOCKER / 0 SHOULD / 2 NITs). MR-051
  `done`, **no carry-overs** (it was the only committed ticket). No product page was touched, so no
  per-page DOM assertion/screenshot was owed; the container rebuild + `/healthz` + `/api/reviews`
  smoke was done.
- **Two NITs carried to MR-052 (next sprint), no rework here:** (1) `agent_status.at` is float
  seconds — MR-052's staleness math (`now - at > N`) must use the same unit; (2) a non-JSON body
  reaches the `400` via `_body_json()` coercing to `{}` then the `else` arm (the observable contract
  is still a correct `400`; the swallow is the pre-existing repo convention).
- **Epic stays `active`:** Chunk 1 shipped; MR-052 + MR-053 remain for the next sprint(s).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] MR-051 is `done`;
- [x] a **staff-critic sprint-close review** exists at `reviews/sprint-14-close-review-2026-06-23.md`,
      verifying MR-051 against its acceptance criteria, including the container rebuild + `curl
      /healthz` + `/api/reviews` smoke (no product page touched this sprint — `svc`-only — so no
      per-page DOM assertion/screenshot is owed);
- [x] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
