---
review_of: sprints/sprint-23.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-23 close review (G7) — history-version-fix (GH #18)

Independent staff-critic verification of sprint-23 (`dev`), implementing GH #18 via two tickets:
MR-064 (svc) and MR-065 (ui). The reviewer did not implement these. Both defects from #18 are
verified fixed against their acceptance criteria; MR-065 was independently re-driven with a fresh
node-CDP script (not the implementer's), the throwaway container rebuilt from the `dev` tree on a
scratch port, and the v0 edge driven live. **Verdict: PASS.**

## Verification method

- Rebuilt the image from the `dev` working tree (`docker build`), ran a disposable container on
  **scratch port 8771** (live 8139 / compose 8137 untouched, never `docker compose up`).
- MR-064: curl smoke (POST + 2 PUTs + a reviewer comment) asserting `/history` and `/history/{n}`
  shapes via `python3`; full grep of every per-round count reader across `app.py`, `viewer.html`,
  `dashboard.html`, `mcp_server.py`.
- MR-065: an **independent** node-CDP driver (Node v22 built-in `WebSocket` over CDP,
  `Runtime.evaluate{returnByValue,awaitPromise}` — the `agent_smoke.py:112-148` pattern) opened the
  click-populated modal via `openHistory()` and read the rendered DOM back; headless Chrome 149 on
  scratch debug port 9333. The v0 edge was driven live on a fresh never-PUT review (port 9334).
- All temp under gitignored `.scratch/`; throwaway container + image removed, Chrome killed, scratch
  emptied at the end.

---

## MR-064 (svc) — drop the per-round notes count from `round.json`

**Result: PASS — removal is safe, complete, and back-compat.**

- **Source change correct.** `snapshot_round` (`app.py:181-205`) no longer reads `notes.json` for a
  count nor writes `notes_total`/`notes_addressed`; `round.json` is now `{round, ts}` only. The
  `source.md`/`feedback.md`/`notes.json` file copy (`:192-195`) and the `revision = n+1` bump
  (`:204`) are kept. The comment-aware per-review `summary()` `notes_total`/`notes_addressed`
  (`app.py:160-161`) is **untouched**.
- **No surviving reader of the removed per-round keys.** Grep `notes_total|notes_addressed` across
  `app.py`, `viewer.html`, `dashboard.html`, `mcp_server.py`:
  - `app.py:160-161` — the `summary()` write (per-review, untouched). Not the round key.
  - `dashboard.html:112` — reads `r.notes_total||0` from the **`summary()` list payload**
    (`GET /api/reviews`), not from a round. Guarded with `||0`; no KeyError, no stale round data.
  - `viewer.html` — the old `:679` round-count label is **gone** (removed in MR-065).
  - `mcp_server.py get_history` (`:410-413`) is a **pure URL passthrough** — no field indexed.
  - `/history` (`app.py:677-690`) and `/history/{n}` (`:692-704`) are passthroughs; neither indexes
    the removed keys. `/history/{n}` still returns `source/feedback/notes` for back-compat.
- **README:55 updated.** `GET /history` per-round shape now documented `{round, ts}` (was
  `{round, ts, notes_total, notes_addressed}`). `/history/{n}` shape line unchanged (correct — it
  still returns the round body).
- **Curl smoke (re-run, port 8771).** POST `# v0 draft` → PUT `# v1` → PUT `# v2` + a reviewer
  comment. `/history` → `[{round:1,ts},{round:0,ts}]` — only `round`+`ts`, newest-first. `/history/0`
  keys = `[feedback, notes, round, source, ts]`, no `notes_total`/`notes_addressed`, body intact
  (`# v0 draft`). `revision==2`. README grep: 0 per-round `notes_total`. `summary()` still works: the
  list row shows `notes_total=1` (the comment), confirming the dashboard field is live and unaffected.

---

## MR-065 (ui) — History modal: current-draft top entry, relabel, drop "0 notes"

**Result: PASS — re-driven independently; the modal reconciles with the badge and the count is gone.**

Independent node-CDP drive against the rebuilt container (revision=2, rounds [1,0], + a reviewer
comment). Opened the modal via `openHistory()`, polled until `.histitem` populated, settled, then
asserted on the rendered DOM. **11/11 PASS:**

| Assertion | Result |
|---|---|
| `.histitem` count == 3 (current + v1 + v0) | PASS |
| top entry == `current (v2) · live draft` | PASS |
| top starts `current (v2)` (rev>=1 case) | PASS |
| archived `v1 · earlier draft` then `v0 · earlier draft`, newest-first | PASS |
| **NO "notes" text anywhere in `#histbody`** (with a comment present — Defect B) | PASS |
| `#histview .histdoc` auto-shows the current draft (`v2 draft`) | PASS |
| badge reconciles: `meta.revision==2` AND list `revision==2` AND top has `v2` (Defect A) | PASS |
| clicking the `v1` archived item → body `v1 draft` | PASS |
| `v1` heading reads `v1 draft` | PASS |

Screenshot of the open modal captured (CDP `Page.captureScreenshot`) and matches: `current (v2) ·
live draft`, `v1`/`v0` "earlier draft" newest-first, no count, CURRENT DRAFT → `v2 draft`.

**v0 edge (driven live on a fresh never-PUT review):** exactly **1** `.histitem`, top reads plain
**`current · live draft`** (no `(v0)`), the "No earlier versions yet" copy renders **below** the
current entry (relocated early-return AC), and CURRENT DRAFT auto-shows the body. This matches
`dashboard.html:127` (`(r.revision||0)>0`) which hides the badge below v1 — the viewer's
`(meta.revision)||0` defaults identically, so modal and badge agree at rev 0.

**Code shape (diff `c3aa252`).** `openHistory` `Promise.all`-fetches `/history` + `/api/reviews/{id}`
(revision from `meta()`), renders the `data-n="current"` top entry, archived rounds display-only
(on-disk `round-n` not renumbered), relocates the empty-rounds early-return, and calls
`showRound('current')`. `showRound` branches `n==='current'` (`GET /source`) vs a round
(`/history/{n}`) through the same `marked.parse` → `.histdoc` path; the "notes that round" block is
removed. No new endpoint.

---

## Scope

**PASS.** MR-064 = `app.py` + `README.md` (+ its own ticket file); MR-065 = `viewer.html` only.
`Dockerfile`, `dashboard.html` untouched. `mcp_server.py` shows a delta vs `main` but it is from
MR-053/MR-048 (prior sprints already on `dev`), **not** sprint-23 (`git log a0eabfa^..dev --
mcp_server.py` is empty). Both #18 defects fixed: version labels reconcile (Defect A), the "0 notes"
lie is gone at its source (Defect B). `python3 -m py_compile app.py` OK.

---

## Findings

No blocking findings. No must-fix. No nits material to the gate.

Minor observations (non-blocking, no action required):

- `GET /api/reviews/{id}` returns raw `meta()`, not `summary()`, so its payload has no `notes_total`
  and `revision` is absent (not `0`) on a never-PUT review. The viewer's `(meta.revision)||0` and the
  dashboard's `(r.revision||0)` both default correctly, so this is harmless and pre-existing — noted
  only so a future reader of that endpoint isn't surprised.
- Old rounds archived before MR-064 keep their inert `notes_total` keys on disk; the new viewer never
  reads them. Correct no-migration back-compat, as the ticket states.

---

## Resolution log

- 2026-06-24 — Independent G7 review. Rebuilt the image from `dev`, smoked MR-064 (curl) and re-drove
  MR-065 (fresh node-CDP, 11/11 PASS + v0 edge live) on scratch port 8771 / debug 9333-9334. Grep
  confirmed no surviving reader of the removed per-round count (dashboard reads the `summary()` field;
  mcp/history are passthroughs). Scope clean (mcp_server delta is pre-sprint-23). `py_compile` OK.
  Throwaway container + image removed, Chrome killed, `.scratch/` emptied; live 8139 untouched.
  **Verdict: PASS.** No open findings to carry.

## Resolution log

- 2026-06-24 — Independent G7 review (#18, two tickets). Verdict PASS, no blockers. MR-064: round.json is
  `{round, ts}` only, no surviving reader of the removed per-round count (dashboard reads the separate
  summary() total; MCP get_history + /history routes are passthroughs); README:55 updated; curl smoke
  confirms. MR-065: the critic re-drove the modal with a FRESH node-CDP script (11/11 incl. the v0 edge —
  plain `current`, empty-state below, matching the dashboard hiding its badge below v1): top `current (v2)`
  reconciles with the badge (Defect A), no "notes" text with a comment present (Defect B). Both #18 defects
  fixed. Review status: resolved; sprint-23 closed at G7; history-version-fix epic done; GH #18 closed.
