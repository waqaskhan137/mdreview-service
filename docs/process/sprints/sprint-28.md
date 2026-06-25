---
id: sprint-28
name: viewer-dashboard-reskin
status: active         # planning | active | closed
start: 2026-06-25
end: 2026-06-27
goal: Re-skin the dashboard and viewer in place to the new mockup, preserving all wiring and the buildless/stdlib architecture.
close_review:          # reviews/sprint-28-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

Both app screens (`dashboard.html`, `viewer.html`) render to the new mockup's look and supported
information architecture — sidebar inbox driven by the turn baton, restyled cards with baton status
badges, a restyled viewer (breadcrumb chrome, "Your turn" baton banner, numbered markdown lines, the
right-hand threaded COMMENTS rail, the bottom open/resolved/history dock) — while **every existing
behavior still works** (comments CRUD, baton Send/reclaim/staleness, live-reload, KaTeX/mermaid/
highlight render, history, lightbox, dark mode). Success = both screens render to the new design from
the **rebuilt container** (proven by DOM-asserting render-smoke against the new selectors, plus the
comment-rail wide-mode check) with no functional regression and no `svc` change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-087 | Dashboard re-skin — sidebar inbox + projects filter + restyled cards with baton badges | ui | P1 | done |
| MR-088 | Viewer re-skin — chrome (top bar + breadcrumb + title meta) + baton banner + numbered lines + article typography | ui | P1 | done |
| MR-089 | Viewer re-skin — COMMENTS right rail + Resolved panel + bottom open/resolved/history dock | ui | P1 | done |
| MR-090 | Docs sweep — README / CLAUDE for the re-skinned dashboard & viewer affordances | docs | P2 | done |

## Preferred execution order

The intended order, accounting for dependencies. Lower-risk dashboard first; the comment rail (the
highest-risk JS surface) gets its own ticket after the viewer chrome lands.

1. MR-087 — Dashboard re-skin (independent of the viewer; smallest blast radius; ships the visible IA first).
2. MR-088 — Viewer chrome + baton + numbered lines + article typography (lands first on `viewer.html`).
3. MR-089 — Viewer COMMENTS rail + dock (depends MR-088; isolated render-smoke incl. the C1 wide-mode check).
4. MR-090 — Docs sweep (depends 087-089; documents shipped reality; must be `done` before close, not carry-over-eligible).

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where); — MR-087/088/089/090
      all `done`, none carried over.
- [x] no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done` (MR-090 is
      not carry-over-eligible); — MR-090 `done` within the sprint.
- [ ] a **staff-critic sprint-close review** exists at `reviews/sprint-28-close-review-YYYY-MM-DD.md`,
      verifying shipped work against each ticket's acceptance criteria, **including a render smoke** —
      because product pages (`viewer.html`, `dashboard.html`) were touched, `scripts/render-smoke.sh`
      against each page asserting its DOM nodes + screenshots under
      `reviews/sprint-28-render-evidence-*` (plus the comment-rail wide-mode `body.gutter-on` check),
      and the container rebuild + `curl /healthz` + `/api/reviews` smoke — and its findings are
      resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
