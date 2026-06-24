---
id: MR-065
title: "History modal: list current draft as `current (vN)`, relabel rounds, drop \"0 notes\""
status: done          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-23
epic: history-version-fix
depends_on: [MR-064]
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The History modal mislabels versions and lies about per-round feedback. It tops out at `v(N-1)` while
the dashboard badge shows `vN`, never lists the current live draft the human is reading, and stamps
every entry "0 notes" (the retired `notes.json` count). This ticket reconciles the labels by listing
the current draft as the top `current (v{rev})` entry from existing endpoints (no new route),
relabels archived rounds display-only, and removes the count label and empty per-round notes section.
This is the viewer half of `history-version-fix` (Defect A + the Defect-B label removal); it depends
on MR-064, which removes the count from the service so the viewer never displays a field the service
may still emit.

## Acceptance criteria

- [ ] `openHistory` (`viewer.html` ~:674-682) builds a synthetic **top entry for the current draft**,
      labeled `current (v{rev})` where `{rev}` is `revision` read once on open from `GET /api/reviews/
      {id}` (the `summary()` payload) — **no new endpoint**. Its body is `GET /api/reviews/{id}/source`
      rendered through the existing `marked.parse` → `.histdoc` path, exactly as `showRound` renders an
      archived round.
- [ ] The `viewer.html:678` empty-rounds **early-return is relocated** so the current-draft top entry
      **always renders**, including for a never-PUT review (`rounds.length===0`): inject the current
      entry first, then archived rounds below — when there are none, the "No earlier versions yet" copy
      renders **below** the current entry (the archived section's empty state), not instead of it.
- [ ] At **`revision==0`** the top entry reads plain `current` (**no `(v0)`** parenthetical), to agree
      with the dashboard hiding its badge below v1 (`dashboard.html:127`, `(r.revision||0)>0`); at
      `revision>=1` it reads `current (v{rev})` and equals the badge number.
- [ ] Archived rounds are relabeled `v{round} · earlier draft · {timestamp}`, **newest-first**,
      **display-only** — the on-disk `round-n` dirs and the `/history/{n}` path are **NOT** renumbered.
      With the current draft pinned on top, the list reads `vN (current), v(N-1) … v0`, top number ==
      dashboard badge.
- [ ] The **"· N notes" label is removed** from the archived-round entry (`viewer.html:679`, drops
      `+r.notes_total+' notes'` and the `(… done)` clause), and the **empty per-round notes section is
      removed** from `showRound` (`viewer.html:688-689`, the `notes that round` block that rendered the
      always-empty legacy `d.notes`). The archived round body (`d.source`) still renders.
- [ ] `dashboard.html` is **not changed** — the `v${r.revision}` badge (`:127`) is the source of truth
      the History top entry reconciles *to*. Confirm-by-smoke that badge and top entry show the same
      number; do not touch the badge.
- [ ] Local validation passes: `python3 -m py_compile app.py` (gate owed even though no `app.py`
      change here), **plus** a **node-CDP eval driver** under `.scratch/` (the proven
      `agent_smoke.py:112-148` pattern — Node built-in `WebSocket` over CDP,
      `Runtime.evaluate{returnByValue, awaitPromise}`) against a **rebuilt throwaway container**
      (scratch port, never 8139/8137, never `docker compose up`). Fixture = a **>=2-PUT review + a
      comment** (`revision=2`, `round-0` + `round-1`). The driver navigates `$BASE/review/{id}`, calls
      `openHistory()` (or clicks `#histbtn`), polls until `.histitem` populates, settles ~500ms, then
      asserts on the **rendered DOM**:
      - `.histitem` count **>= 3** (current + round-1 + round-0);
      - top entry text **== `current (v2)`** and **equals the dashboard `.badge`** number (the v>=1
        case);
      - archived rows read **`v1 …` then `v0 …`** newest-first, with `· earlier draft`, **no count**;
      - **NO "notes" text** and **no "notes that round"** anywhere in the modal DOM
        (`!/\bnotes\b/.test(document.querySelector('#histbody').innerText)` — Defect B asserted on the
        rendered DOM, not a source grep);
      - clicking the top entry yields **`#histview .histdoc`** whose `innerText` contains the current
        draft text (`v2 draft`), proving `/source` renders through the same `marked` path as
        `showRound`. The script prints a JSON verdict and `process.exit(non-zero)` on any failed
        assertion (fail-loud, never a silent pass).
- [ ] **Plus** a static `scripts/render-smoke.sh "$BASE/review/{id}" '#histbtn'` for the non-modal
      nodes and `render-smoke.sh "$BASE/?id={id}" '.badge'` for the dashboard badge (the
      reconciliation cross-check). **Bare `render-smoke.sh` against the modal selectors
      (`.histitem`/`.histdoc`) is FORBIDDEN** — the modal is `display:none` until `openHistory()` runs
      on a click, and `render-smoke.sh` does a single `--dump-dom` with no click/eval, so those
      selectors match 0 even on a correct build (false fail; the sprint-07 wall). Modal-internal
      assertions are done by the node-CDP reads only.
- [ ] **A screenshot of the open modal** is captured as G4/G7 evidence (CDP `Page.captureScreenshot`
      after opening, under `.scratch/`, scratch port). The screenshot is evidence, **not** the
      acceptance test — the node-CDP DOM assertions are the acceptance test. All evidence moved to
      `reviews/sprint-23-render-evidence-2026-06-24/` for the gate.

## Notes / context

- Epic plan: `docs/process/epics/history-version-fix-plan.md` — "Defect-A label design", "The
  revision-0 / empty-rounds edge", "Recommended approach / UI (`viewer.html` / `dashboard.html`)",
  "Verification / MR-065 (ui)" (the pinned node-CDP driver + the forbidden bare render-smoke), the
  "JS-rendered surfaces" / flat-selector key constraints, and the Risks table.
- Reconciliation arithmetic (the crux): `revision` == count of PUTs == version of the current draft,
  so the dashboard badge `vN` names the current draft. `round-k` archived the draft that was version
  `k`. So top entry = `current (v{rev})`; archived `round-(N-1)` … `round-0` = `v(N-1)` … `v0`. The
  off-by-one is fixed by **including the current draft**, not by renumbering rounds (renumbering would
  desync `/history/{n}`, keyed on on-disk `round-n` — see Non-goals / Key constraints).
- The current-draft body reuses the exact existing render path: `viewer.html:376` already fetches
  `GET /source` as text; archived source renders via `marked.parse(d.source)` at `:687`. Same `marked`
  global, same `.histdoc` container — no node-vs-browser gap, a reuse not a new render surface.
- Lines: `openHistory` `:674-682`, the empty-rounds early-return `:678`, the count label `:679`, the
  `notes that round` block `:688-689`, the archived body render `:687`, the `#histbtn` click handler
  `:692`, the static `#histbody` div `:199`, `#histbtn` in served HTML `:189`. Dashboard badge
  `dashboard.html:127`.
- **Why bare render-smoke against the modal is forbidden:** this repo already proved a headless target
  cannot open this exact modal in sprint-07 (`reviews/sprint-07-close-review-2026-06-18.md`). A 200 is
  not a render; a `--dump-dom` of a closed modal is not a render. The node-CDP eval runs page JS in
  scope to open the modal and read it back — that is the acceptance mechanism. Fallback only if
  node-CDP proves awkward in the build env: a `?history=1` auto-open hook — but that adds deep-link
  product behavior, so it is the fallback, never the default.
- **MR-065 IS a product-page change** (`viewer.html`), so G7 owes the node-CDP modal-DOM verification
  + screenshot under `reviews/sprint-23-render-evidence-2026-06-24/` — NOT a bare render-smoke against
  the modal. depends_on MR-064 (must not display a count the service may still emit).

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.

## Work log

- `2026-06-24` — `viewer.html` only. `openHistory()` now `Promise.all`-fetches `/history` + `/api/reviews/{id}`
  (for `revision`), renders a top `.histitem data-n="current"` labeled `current (v{rev})` (plain `current`
  at rev 0) + "live draft", then archived rounds `v{round} · earlier draft · {ts}` newest-first (NO notes
  count), and calls `showRound('current')` so the modal always opens with content. The empty-rounds
  early-return is relocated (the current entry always renders; "No earlier versions yet" shows below when
  there are no rounds). `showRound(n)` branches `n==='current'` (live draft from `GET /source`) vs a round
  (`/history/{n}`); the "notes that round" section is removed. dashboard.html unchanged (the `v${revision}`
  badge is the source of truth the top entry reconciles with).

## Validation

- `2026-06-24` — `py_compile app.py` OK (unchanged). Modal DOM verified by a **node-CDP driver** (the
  `agent_smoke.py` WebSocket/`Runtime.evaluate` pattern — render-smoke.sh can't open the click-populated
  modal, the sprint-07 wall) against a **rebuilt throwaway container** (scratch port 8770, never
  8139/8137/compose). Fixture: a review + 2 PUTs (revision=2, rounds 0+1) + a reviewer comment. 10/10
  assertions PASS: 3 histitems; top `current (v2) · live draft`; archived `v1`/`v0` "earlier draft"
  newest-first; **no "notes" text anywhere in the modal** (with a comment present — Defect B); current
  draft auto-shown = v2; **badge reconciles** (`revision==2`, top has v2 — Defect A); archived-click → v1
  draft; `#histbtn` static render-smoke exit 0. Evidence:
  `reviews/sprint-23-render-evidence-2026-06-24/` (SMOKE.md + history-modal.png).
