---
id: MR-005
title: History snapshots on PUT + /history routes
status: done
layer: svc
priority: P2
sprint: sprint-01
epic: review-dashboard
depends_on: [MR-001]
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Stop losing the past. The service is overwrite-based, so prior drafts and feedback rounds vanish.
Add lightweight append-only snapshots so an agent can revisit any earlier draft and the feedback
it received.

## Acceptance criteria

- [ ] On `PUT /source` (`app.py:197`), under the existing `_lock`, if the review has prior
      content, copy the outgoing `source.md` + current `notes.json` + `feedback.md` into the next
      `{id}/history/round-{N}/`, write `round.json` (`{round, ts, notes_total, notes_addressed}`),
      and bump a `revision` counter in `meta.json`. Then write the new source (existing behavior).
- [ ] Snapshot happens only on `PUT /source`, NOT on `POST /feedback` (feedback auto-saves per
      keystroke; per-POST snapshots would explode).
- [ ] `GET /api/reviews/{id}/history` returns `{"rounds": [round.json...]}` newest first;
      `GET /api/reviews/{id}/history/{n}` returns `{source, notes, feedback, ...round meta}`.
- [ ] Routes match before broader patterns (no shadowing of `/source`/`/feedback`).
- [ ] Local validation: `python3 -m py_compile app.py`; create a review, `PUT` a revised source,
      `GET /history` shows one round, `GET /history/0` returns the prior draft + notes.

## Notes / context

- PUT handler at `app.py:197-202`; reuse `_read`/`_read_json`/`_write`/`meta`/`bump`.
- `summary()` (MR-002) reads the `revision` counter for the dashboard badge.
- Epic: `epics/review-dashboard-plan.md`.

## Work log

- `2026-06-08` — `app.py`: added `snapshot_round(rid)` — under `_lock`, copies the current
  `source.md`/`feedback.md`/`notes.json` into `{id}/history/round-{N}/`, writes `round.json`
  (`round`, `ts`, `notes_total`, `notes_addressed`), and bumps `meta.revision`. Wired it into the
  `PUT /source` handler before the overwrite. Snapshot happens only on PUT, not on
  `POST /feedback`. Added `GET /api/reviews/{id}/history` (rounds newest-first) and
  `GET /api/reviews/{id}/history/{n}` (source + feedback + notes for one round). Routes use
  `re.fullmatch` so `/history` and `/history/{n}` do not cross-match.

## Validation

- `2026-06-08` — `python3 -m py_compile app.py` passed. On an isolated instance: created a
  review, added a note, PUT a revised draft -> `revision` became 1, `GET /history` listed
  `round 0` with `notes_total: 1`, `GET /history/0` returned the prior `# v0 draft` plus the
  note. A second PUT produced `round 1` (list `[1, 0]`). `GET /history/9` -> `404`. The live
  `GET /source` still returned the latest draft.

## Follow-ups

Full diff/timeline UI is a deliberate Non-goal (see epic).
