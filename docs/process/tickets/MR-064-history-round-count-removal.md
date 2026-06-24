---
id: MR-064
title: "snapshot_round: stop writing the retired notes count into round.json (+ README.md:55 shape)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-23
epic: history-version-fix
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The History modal stamps every round "0 notes" because `snapshot_round` writes `notes_total`/
`notes_addressed` into `round.json` from the legacy `notes.json` store (retired since MR-036) — the
viewer authors `comments.json`, which is never snapshotted per round, so the count is `0` for every
comments-era round and cannot be made truthful retroactively. Remove the count from the source
(`round.json`) so the lie has no backing data, and update the one documented contract that advertises
the old per-round shape. This is the service half of `history-version-fix` (Defect B); MR-065 removes
the corresponding viewer label and notes block.

## Acceptance criteria

- [ ] `snapshot_round` (`app.py` ~:197-200) **stops writing `notes_total`/`notes_addressed`** into
      `round.json`; the per-round `round.json` keeps only `round` + `ts`. The `notes.json` read used
      only to compute those counts (`app.py:196`) is removed. The only per-round consumer of those
      keys was `viewer.html:679`, changed in MR-065.
- [ ] The file copy of `source.md`/`feedback.md`/`notes.json` into the round dir (`app.py:192-195`)
      is **kept unchanged** so archived round bodies stay intact (back-compat). The `revision = n + 1`
      bump (`app.py:202`) is **kept** — the counter is sound.
- [ ] The `summary()` per-review `notes_total` (`app.py:160`) is **UNTOUCHED** — it is the
      comment-aware dashboard total (a different field), not the per-round count being removed.
- [ ] `GET /history` (`app.py:675-688`) and `/history/{n}` (`app.py:690-702`) need **no behavioral
      change**: `/history` returns the `round.json` array (now naturally without the count keys);
      `/history/{n}` still returns `source`/`feedback`/`notes` for back-compat. No new route, no
      shadowing of the id regex `[A-Za-z0-9]{4,40}`.
- [ ] `README.md:55` is updated: the documented `GET /history` per-round shape changes from
      `{round, ts, notes_total, notes_addressed}` to `{round, ts}` (noting the dropped keys are inert
      on rounds archived before this change). Doc ships in the same ticket as the code so it never
      lags.
- [ ] Back-compat holds with no migration: existing rounds on disk keep their old `notes_total` keys
      (the new client never reads them, so they are inert); new rounds simply omit them.
- [ ] Local validation passes: `python3 -m py_compile app.py`, **plus** a curl smoke on a rebuilt
      throwaway container (scratch port, never 8139/8137, never `docker compose up`; all temp under
      `.scratch/`) — POST a review, PUT `/source` twice (→ `revision=2`, `round-0` + `round-1`),
      then `GET /history` + `/history/{n}` show the new `round.json` shape with **no `notes_total`/
      `notes_addressed`** key per round (assert via `python3 -c`), `/history/0` still returns the
      archived body, and `revision==2`; **plus** a grep confirming `README.md:55` no longer
      documents per-round `notes_total`
      (`grep -n 'history' README.md | grep -q 'notes_total'` → no hit).

## Notes / context

- Epic plan: `docs/process/epics/history-version-fix-plan.md` — "Defect-B decision (resolved — remove,
  not count)", "Recommended approach / Service (`app.py`)", "Verification / MR-064 (svc)", and the
  ticket table. Defect B root cause: `snapshot_round` writes counts from the retired `notes.json`
  (`app.py:196-200`); `comments.json` is never per-round snapshotted, so a retroactive count is
  impossible and would still be `0` — removal is forced, not a preference.
- The exact lines: `snapshot_round` is `app.py:181-203`; the count read is `:196`; the count write is
  `:197-200`; the file copy to keep is `:192-195`; the revision bump to keep is `:202`. `/history` is
  `app.py:675-688`, `/history/{n}` is `app.py:690-702`, `GET /source` is `app.py:543`, and the
  `summary()` `revision`/`notes_total` are `app.py:162`/`:160`.
- The `summary()`-level `notes_total` (`app.py:160-161`), documented in CLAUDE.md/README's review-row
  copy, is the comment-aware per-review total — a **different** field, left untouched.
- Grep confirms the only readers of the per-round `notes_total` are `/history` (passthrough) and the
  `viewer.html:679` label (changed in MR-065); MCP `get_history` is a pure passthrough with no count
  consumer (`grep -n notes_total app.py *.html mcp_server.py`).
- svc-only — no `viewer.html`/`dashboard.html` change, so **no render-smoke is owed** at G7 for this
  ticket. MR-065 owes the modal-DOM verification.

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
