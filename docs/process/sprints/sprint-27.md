---
id: sprint-27
name: OOP refactor + src/ restructure
status: active        # planning | active | closed
start: 2026-06-25
end: 2026-06-27
goal: Restructure all code under src/ with a clean root and decompose app.py into 7 single-responsibility modules wired by constructor injection, with byte-identical external behaviour.
close_review:         # reviews/sprint-27-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Ship the Tier B OOP refactor of `mdreview-service` as a **pure internal refactor**: the HTTP API,
the `/data` on-disk format, and the viewer all behave byte-identically, while the 833-line `app.py`
monolith becomes seven cohesive modules under `src/mdreview/` (`config`, `store`, `comments`,
`assets`, `reviews`, `handoff`, `server`) wired by a single `main()` composition root via
constructor injection (one `Store` into the service classes; the handler reads `self.server.app`).
The root is left clean (code under `src/`, frontend under `web/`, smokes under `tests/`, infra at
root). Success by the end date: the service ships from `python -m mdreview`, every smoke +
render-smoke pass against a rebuilt throwaway container, the golden curl transcript diffs identical,
and an `mdreview-qc` end-to-end run is green on the new image.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-076 | Capture golden transcript + relocate `app.py`→`src/app.py`, frontend→`web/`, swap `HERE`→`WEB_DIR` | svc | P1 | ready |
| MR-077 | Service `Dockerfile`: `COPY src/`+`web/`, `ENV MDREVIEW_WEB_DIR`/`PYTHONPATH`, `CMD python src/app.py` | infra | P1 | ready |
| MR-078 | Move `mcp_server.py`/`watch.py`→`src/`, smokes+render-smoke→`tests/`, fix `SERVER` path, `Dockerfile.watcher` COPY | infra | P1 | ready |
| MR-079 | Repoint the 3 live `py_compile` gate refs (incl. the G4 row) + `CLAUDE.md` to `src/...` | docs | P2 | ready |
| MR-080 | Extract `config.py` (constants + `WEB_DIR`, drop `HERE`) + package skeleton | svc | P1 | ready |
| MR-081 | Extract `store.py` + `Store` (typed I/O + the one Condition) | svc | P1 | ready |
| MR-082 | Extract `comments.py` + `CommentService` (state machine, incl. the inline GET/DELETE arms) | svc | P1 | ready |
| MR-083 | Extract `assets.py` + `AssetService` (content-hash storage + manifest) | svc | P1 | ready |
| MR-084 | Extract `reviews.py` + `ReviewService` (lifecycle, summary/list, history, inline doc reads) | svc | P1 | ready |
| MR-085 | Extract `handoff.py` + `HandoffService` (turn baton + lease decision table) | svc | P1 | ready |
| MR-086 | Rename `src/app.py`→`src/mdreview/server.py`, add `__main__.py`, flip entrypoint to `python -m mdreview` | svc | P1 | ready |

## Preferred execution order

Move-first, then decompose bottom-up. Each ticket builds + smokes green before the next; each
Phase-1 commit diffs byte-identical against the golden transcript captured in MR-076.

1. **MR-076** — golden transcript + relocate `app.py`/frontend, `HERE`→`WEB_DIR` (foundation).
2. **MR-077** — service Dockerfile to the new layout (build + render-smoke).
3. **MR-078** — move scripts/smokes; `Dockerfile.watcher` COPY; stable container destinations.
4. **MR-079** — repoint the live `py_compile` gate (completes Phase 0).
5. **MR-080** — `config.py` + package skeleton.
6. **MR-081** — `store.py` + `Store` (the lock; long-poll wake smoke).
7. **MR-082** — `comments.py` + `CommentService` (incl. the G1-blocker inline arms).
8. **MR-083** — `assets.py` + `AssetService`.
9. **MR-084** — `reviews.py` + `ReviewService` (the `/feedback`-with-comment diff).
10. **MR-085** — `handoff.py` + `HandoffService` (lease matrix).
11. **MR-086** — rename to `server.py`, `__main__.py`, flip `CMD` to `python -m mdreview`; the
    no-store-helper grep contract + full smokes + render + `mdreview-qc`.

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at `reviews/sprint-27-close-review-YYYY-MM-DD.md`,
      verifying shipped work against each ticket's acceptance criteria, **including a render smoke**
      of the moved viewer/dashboard pages (served pages relocated to `web/`, so the per-page DOM
      assertion + screenshot under `reviews/sprint-27-render-evidence-*` are owed), plus the
      container rebuild + `curl /healthz` + `/api/reviews` smoke;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
