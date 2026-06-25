---
id: MR-081
title: Extract store.py + Store (typed I/O + the one Condition)
status: done
layer: svc
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-080]
branch: refactor/oop-src-layout
created: 2026-06-25
updated: 2026-06-25
---

## Goal

The single persistence seam. `Store` owns `DATA_DIR` and the **one** `threading.Condition`, exposing
typed read/write + lock/notify/wait pass-throughs. This is the most dangerous extraction (MR-054
long-poll correctness), so it is isolated and its smoke is the long-poll wake test.

## Acceptance criteria

- [x] `src/mdreview/store.py` defines `Store(data_dir)` with: `lock` (the `Condition`),
      `notify_all()`, `wait(timeout)`, `dir(rid)`, `exists(rid)`, `read_text(path, default="")`,
      `read_bytes(path, default=b"")`, `read_json(path, default)`, `write_text(path, text)`,
      `ctype_for(name)`, `to_float(s, default)`, and the `_CTYPES` table.
- [x] **MR-054 invariant verbatim:** exactly **one** `Condition` over one lock, owned by the single
      injected `Store` (grep the extracted tree: one `Condition(` / zero extra `Lock(`); no service
      constructs its own lock). Services never **re-acquire** `store.lock`; the lock is taken only at
      the call sites that take it today (the router arms + `_wait`). `list_reviews()`/`summary()`
      stay **lock-free** (confirmed: `_wait` calls `list_reviews()` while holding the lock).
      `notify_all()` only after a successful write and only under `store.lock`; `wait()` releases
      that same lock.
- [x] **Long-poll wake smoke (the gate for this ticket):** shell A `GET
      /api/reviews/wait?since=0&turn=agent&timeout=20` parks; shell B (within the timeout) `POST
      /api/reviews/<id>/handoff {"to":"agent"}` must wake A with `{"reviews":[{... "turn":"agent"
      ...}]}`, not `{"timeout": true}`.
- [x] Golden-transcript byte-identical; `python3 -m py_compile src/app.py src/mdreview/store.py`.

## Notes / context

- `app.py:46-58` (the Condition-over-one-lock rationale), `app.py:52` (`_lock`), `app.py:62-133` (the
  file-IO helpers + `_CTYPES`), `app.py:421-460` (`_wait`, stays in `server.py` but parks on
  `store.wait`), `app.py:667-672` (`notify_all` under the write lock).
- Epic: `store.py` row + "Key constraints → MR-054 lock invariant survives verbatim" + the lock risk
  row (grep the acquisition sites, not just the constructor).

## Work log

- `2026-06-25` — Created `src/mdreview/store.py` with `Store(data_dir)`: owns the one
  `threading.Condition` (`lock` property + `notify_all()` / `wait(timeout)` pass-throughs) and the
  typed IO (`dir`, `exists`, `read_text`, `read_bytes`, `read_json`, `write_text`, `ctype_for`,
  `to_float`) + the `_CTYPES` table. In `src/app.py`: `_store = Store(DATA_DIR)`, `_lock =
  _store.lock` (alias to the same Condition), and thin module-level shims (`_dir = _store.dir`, …)
  so the route arms and not-yet-extracted functions read unchanged; the standalone helper defs and
  the `threading` import are gone. Files: `src/mdreview/store.py`, `src/app.py`.

## Validation

- `2026-06-25` — `python3 -m py_compile src/app.py src/mdreview/store.py` → OK. Golden sweep →
  **byte-identical** (41/41). **One-Condition invariant:** exactly one `Condition(` in the extracted
  tree (`store.py`), zero stray `Lock(`. **Long-poll wake smoke (the gate):** a waiter parked with
  `since=now` (so the baseline scan finds nothing) woke in **1.08s** when `/handoff {to:agent}` fired
  `notify_all`, returning the flipped review (`turn: agent`), not the 20s `{timeout:true}` — MR-054
  correctness preserved across the Store boundary.

## Follow-ups

Anything deliberately deferred.
