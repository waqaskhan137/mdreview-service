---
id: MR-076
title: Capture golden transcript + relocate app.py→src/app.py, frontend→web/, swap HERE→WEB_DIR
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: []
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

The foundational Phase-0 move. First capture the **golden API transcript** against the current,
unchanged `app.py` — it is the byte-identical oracle every later commit diffs against. Then relocate
the monolith to `src/app.py` and the frontend to `web/`, with the single `HERE`→`WEB_DIR` path edit
as the only logic-touching change. No decomposition yet: `src/app.py` is still the monolith, just
relocated and path-fixed.

## Acceptance criteria

- [ ] **Golden transcript captured** against current `app.py` on a scratch port with a throwaway
      `MDREVIEW_DATA` (gitignored `.scratch/`), covering the full sweep incl. error arms: POST → GET
      source → PUT → GET feedback → POST comment → reply → resolve → 409 double-resolve → **reopen →
      200 reopened → reopen-non-resolved 409** → GET status → handoff flip → `/wait` wake → 410 POST
      feedback → POST asset → GET asset bytes (sha) → GET history → history/{n} → GET meta → GET
      single comment → **DELETE comment → GET 404** → **DELETE review (on a throwaway `id2`)**. Saved
      under `.scratch/` as the diff oracle (timestamps/ids/hashes normalised out).
- [ ] `git mv app.py src/app.py`; `git mv viewer.html dashboard.html static web/` (history preserved).
- [ ] `WEB_DIR` added to `src/app.py`: `os.environ.get("MDREVIEW_WEB_DIR")` override with a repo-root
      anchor (**from `src/app.py` the anchor is two `dirname`s → repo root**, not three; the three-level
      walk lands only once the constant moves to `src/mdreview/config.py` in MR-080). The three inline
      web reads use `WEB_DIR`, not `HERE`; `HERE` is dropped. `# ponytail:` comment on the constant.
- [ ] Boot `MDREVIEW_DATA=.scratch/m0 PORT=8155 python3 src/app.py`: `GET /review/<id>`, `GET /`, and
      `GET /static/marked.min.js` each return **200 and non-empty**; a header dump (`curl -sD - -o
      /dev/null`, never `curl -sI` — HEAD 501s) shows `text/html; charset=utf-8` and `text/javascript`.
- [ ] Local validation: `python3 -m py_compile src/app.py`.

## Notes / context

- `app.py:40` (`HERE`), `app.py:500` (dashboard), `app.py:812` (viewer), `app.py:818` (`/static`).
- Epic: [`epics/oop-refactor-src-layout-plan.md`](../epics/oop-refactor-src-layout-plan.md) — "UI →
  `web/`", "Path resolution after the move", "Preferred execution order" step 1 (the transcript).
- The transcript is not a deliverable file in the tree; it lives in `.scratch/` and is the oracle for
  every subsequent ticket's byte-identical diff.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
