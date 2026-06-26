---
id: MR-085
title: Extract handoff.py + HandoffService (turn baton + lease decision table)
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-084]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Move the turn-baton + agent-lease decision logic (the hairy inline `/handoff` body) into named
`HandoffService` methods. The biggest readability win in the refactor; the lease decision table and
its pinned dispatch order must survive exactly.

## Acceptance criteria

- [x] `src/mdreview/handoff.py` defines `HandoffService(store)` covering the `/handoff` body: the
      **pinned dispatch order** (reclaim → hand-back → flip → claim-lease → 400, `app.py:605`) is
      preserved so an ambiguous body stays deterministic; the read-decide-write happens under
      `store.lock`; `notify_all()` is called after a successful write, under the lock.
- [x] **Lease matrix smoke (the gate, MR-055):** claim grants; same-owner renews; foreign-fresh →
      **409**; foreign-stale + `turn=="agent"` → **grant** (takeover); foreign-stale-but-already-
      reclaimed → **409**. Driven with `state:"working"` bodies varying `owner`/turn per
      `app.py:639-664`.
- [x] Golden-transcript byte-identical for the handoff flip + `/status`; `python3 -m py_compile
      src/app.py src/mdreview/handoff.py`.

## Notes / context

- `app.py:600-675` (the `/handoff` arm): `app.py:605` (pinned order), `app.py:639-664` (the lease
  decision table), `app.py:667-672` (`notify_all` under the write lock).
- Epic: `handoff.py` row + "Reuse, do not rewrite" (keep the pinned dispatch order).

## Work log

- `2026-06-25` — Created `src/mdreview/handoff.py` with `HandoffService(store, lease_ttl_s)`. Its
  `apply(rid, body)` is the guarded read-decide-write of the turn/lease state, moved verbatim: the
  PINNED dispatch order (reclaim -> hand-back -> flip -> lease -> 400), the MR-055 lease decision
  table (using `self.lease_ttl_s`), and `store.notify_all()` after a successful write. In
  `src/app.py`: `_handoff = HandoffService(_store, LEASE_TTL_S)`; the ~60-line handoff arm collapses
  to `with _lock: err = _handoff.apply(rid, self._body_json())`. Dropped the now-unused `_dir` /
  `_read_json` / `_write` store shims (handoff was their last user). Files: `src/mdreview/handoff.py`,
  `src/app.py`.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/handoff.py` → OK. Golden sweep →
  **byte-identical** (41/41: the flip + status). **Lease decision matrix (the gate), 5/5** via
  `.scratch/oop/lease.sh`: claim (cur unset) -> grant; renew (cur==owner) -> grant; foreign+fresh ->
  **409**; foreign+stale+turn=agent -> **takeover grant** (MR-055); foreign+stale+already-reclaimed
  -> **409**. The stale paths use `MDREVIEW_LEASE_TTL_S=0` so a fresh lease is instantly stale (no
  180s wait). `notify_all()` under the caller's lock is preserved (the MR-081 wake smoke still
  holds, same Condition).

## Follow-ups

Anything deliberately deferred.
