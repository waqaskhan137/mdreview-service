---
id: MR-046
title: Retire the dead POST /feedback write (→ 410 Gone) + feedback_updated bump/initialiser; keep every reader
status: done
layer: svc
priority: P2
sprint: sprint-13
epic: legacy-feedback-retire
depends_on: []
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

The viewer stopped writing notes/feedback in MR-036 (`26411e4`) — it authors comments now. The
`POST /api/reviews/{id}/feedback` write body and the `feedback_updated` *write* are frozen dead
code on a no-auth service: nothing calls them, but the route still overwrites a review's
`notes.json`/`feedback.md` if a straggler hits it. Retire the **write surface** while leaving the
**read surface and every `feedback_updated` reader untouched**, because 12 live reviews on the
`:8139` volume carry a real `feedback_updated` timestamp and 61 files of real reviewer notes that
`summary()`, the dashboard, `GET /feedback`, and `GET /history` all still read. This is the
"retire only what is written, never what is read" cut from the epic.

## Acceptance criteria

- [ ] The `POST` arm of the `/feedback` route (`app.py:495–501`) no longer writes: its body is
      replaced by `return self._json(410, {"error": "gone, use comments"})` — **no `_body_json`,
      no `_lock`, no `_write`, no `bump`**. `POST /api/reviews/{id}/feedback` returns **410**, not
      200 and not a 404 fall-through. The `GET` arm (`app.py:486–494`) is byte-unchanged.
- [ ] The `bump(rid, "feedback_updated")` call (`app.py:500`) is gone (it lived in the removed
      write body — the only writer of the field). `bump()` itself stays (used by `source_updated`,
      `comments_updated`).
- [ ] The `"feedback_updated": 0` initialiser in `create_review` (`app.py:193`) is removed; new
      reviews simply lack the key.
- [ ] **Readers untouched (out of scope to change):** `summary()` guard `if not
      m.get("feedback_updated") and total == 0` (`app.py:143`) and the whole status derivation
      (`app.py:127–149`); the `status` payload `"feedback_updated": mt.get("feedback_updated", 0)`
      (`app.py:511`); `GET /feedback` markdown+notes union (`app.py:486–494`); `snapshot_round`
      copy (`app.py:169`); `GET /history/{n}` read-back (`app.py:539–541`); `feedback_url` in the
      create response (`app.py:449`). Diff touches none of these.
- [ ] The in-file API docstring POST line (`app.py:15`) is updated to reflect the deprecation
      (e.g. `POST … /feedback → 410 (gone; use comments)`); the GET docstring line (`app.py:14`)
      is unchanged.
- [ ] **Guard non-regression (the real safety check):** a freshly created review (no notes, no
      comments) still derives `status: awaiting` (Pop B — the guard's load-bearing case); and the
      31 currently-`awaiting` reviews on the `:8139` volume (`feedback_updated==0, notes_total==0`)
      stay `awaiting` after a rebuild on a copy of that volume. **None flip to `feedback`.**
- [ ] Back-compat: a new review's `GET /status` returns `"feedback_updated": 0` (defaulted, key
      absent on disk) and `GET /feedback` still returns `markdown` + `notes`.
- [ ] Local validation passes: `python3 -m py_compile app.py`, plus the behavioural curls from the
      epic's Verification (410 on POST; read path intact; fresh review `awaiting`).
- [ ] Docs reflecting this behaviour change are deferred to the same-sprint docs-sweep **MR-047**
      (named here per the Definition of Done); MR-047 must be `done` before sprint-13 closes.

## Notes / context

- Epic: [`epics/legacy-feedback-retire-plan.md`](../epics/legacy-feedback-retire-plan.md) — see
  "Service (`app.py`)", "the one real design fork — the `summary()` guard" (Pop A/B/C table), and
  the "404-vs-410 decision" (default 410, verified the deleted-arm otherwise falls to
  `404 {"error":"no route"}` at `app.py:662`).
- The guard decision (KEEP it) and the 410 default both cleared G1 round-2
  (`reviews/legacy-feedback-retire-plan-review-2026-06-19-r2.md`).
- Live-data constraint: memory `legacy-notes-feedback-load-bearing`. Do **not** `docker compose`
  over `:8139` — use a throwaway container on another port for the rebuild smoke.
- No product page touched → no render-smoke owed for this ticket (G4 is `py_compile` + curls).

## Work log

- `2026-06-19` — `app.py`, three surgical edits, readers untouched:
  - POST arm of the `/feedback` route: replaced the write body (two `_write`s +
    `bump(rid,"feedback_updated")`) with `return self._json(410, {"error": "gone, use comments"})`
    — no `_body_json`, no `_lock`, no write, no bump. The GET arm above is byte-unchanged.
  - `create_review`: removed the `"feedback_updated": 0` initialiser — new reviews lack the key.
  - In-file API docstring: rewrote the `POST /feedback` line to `-> 410 (retired …)`; GET line kept.
  - Confirmed untouched: `summary()` guard (`app.py:143`) + status derivation, `status` payload
    `feedback_updated` default, `GET /feedback` notes union, `snapshot_round`, `GET /history`,
    `feedback_url` in the create response.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` → OK.
- Ran the **new** `app.py` against a `docker cp` copy of the live `:8139` volume (45 reviews) on a
  throwaway port — never composed over `:8139`:
  - **Guard non-regression:** 31 empty reviews (`feedback_updated==0, notes_total==0`) → **0 flipped
    off `awaiting`** (baseline on old `:8139` code was 31/31 awaiting). The guard's Pop-B job holds.
  - **POST /feedback → 410** `{"error":"gone, use comments"}`; verified it wrote nothing (GET
    `/feedback` `notes` still `[]` after a POST carrying a junk note).
  - **Read path intact:** GET `/feedback` returns `markdown` + `notes`.
  - **Back-compat:** fresh review's `/status` returns `feedback_updated: 0` (defaulted), its derived
    status is `awaiting`, and its on-disk `meta.json` has **no** `feedback_updated` key.
- Docs reflecting this behaviour change are carried by same-sprint **MR-047** (per DoD).

## Follow-ups

- AGENTS.md/CLAUDE.md dedup (audit finding 2) is a separate backlog item, not this epic.
