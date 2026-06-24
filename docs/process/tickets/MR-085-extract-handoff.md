---
id: MR-085
title: Extract handoff.py + HandoffService (turn baton + lease decision table)
status: ready
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-084]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the turn-baton + agent-lease decision logic (the hairy inline `/handoff` body) into named
`HandoffService` methods. The biggest readability win in the refactor; the lease decision table and
its pinned dispatch order must survive exactly.

## Acceptance criteria

- [ ] `src/mdreview/handoff.py` defines `HandoffService(store)` covering the `/handoff` body: the
      **pinned dispatch order** (reclaim → hand-back → flip → claim-lease → 400, `app.py:605`) is
      preserved so an ambiguous body stays deterministic; the read-decide-write happens under
      `store.lock`; `notify_all()` is called after a successful write, under the lock.
- [ ] **Lease matrix smoke (the gate, MR-055):** claim grants; same-owner renews; foreign-fresh →
      **409**; foreign-stale + `turn=="agent"` → **grant** (takeover); foreign-stale-but-already-
      reclaimed → **409**. Driven with `state:"working"` bodies varying `owner`/turn per
      `app.py:639-664`.
- [ ] Golden-transcript byte-identical for the handoff flip + `/status`; `python3 -m py_compile
      src/app.py src/mdreview/handoff.py`.

## Notes / context

- `app.py:600-675` (the `/handoff` arm): `app.py:605` (pinned order), `app.py:639-664` (the lease
  decision table), `app.py:667-672` (`notify_all` under the write lock).
- Epic: `handoff.py` row + "Reuse, do not rewrite" (keep the pinned dispatch order).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
