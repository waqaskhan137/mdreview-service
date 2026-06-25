---
id: sprint-28
name: viewer-dashboard-reskin
status: closed         # planning | active | closed
start: 2026-06-25
end: 2026-06-27
goal: Re-skin the dashboard and viewer in place to the new mockup, preserving all wiring and the buildless/stdlib architecture.
close_review: reviews/sprint-28-close-review-2026-06-25.md   # G7 PASS-with-conditions, all 5 findings resolved (3f85c50)
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

**Closed 2026-06-25, G7 PASS-with-conditions** (`reviews/sprint-28-close-review-2026-06-25.md`,
independent staff-critic; all 5 findings resolved in `3f85c50`, 0 blockers). Both app screens
(`dashboard.html`, `viewer.html`) re-skinned in place to the mockup — sidebar turn-baton Inbox +
Projects filter + baton-badge cards on the dashboard; top-bar/breadcrumb chrome, violet baton banner
(Send moved in from the dock), numbered lines, blue headings, and the violet threaded comments rail
on the viewer. **No `svc` change** (every datum the new IA needs was already on `GET /api/reviews`);
buildless/stdlib preserved; dark theme kept on both files (verified by dark-pane computed-style
contrast, not just screenshots); `STALE_S` mirror untouched and no second mirror introduced.

**What went well:** the planner's footgun map (STALE_S mirror, fit-test, legacy back-compat, "200 is
not a render") held up — zero wiring regressions; the side-by-side mockup capture loop caught the
real fidelity gaps (project-only crumb, hairline divider, status dot) fast.

**G7 findings (all resolved, record-accuracy not defects):** the one MAJOR (F1) was a planning-estimate
in MR-089's C1 AC (~1180px) that didn't match the measured ~1315px wide-mode boundary — the geometry is
pre-existing and unregressed (proven by `git diff 8d4227c^`), so the AC was reconciled to reality rather
than the code changed. Two MINOR were grep-claim/branch-provenance accuracy (F2 STALE_S grep, F3 the
MR-064 `app.py` ride-along from `dev`). Two NIT were dead dashboard code (orphan `.watcher` CSS,
unreachable `"Ungrouped"`), removed.

**Carry-overs:** none. MR-090 (docs sweep) closed within the sprint (not carry-over-eligible).

**Follow-up (backlog, not blocking):** the mockup's static "COMMENTS · N open" rail header was
deliberately not added (the floating text-anchored `layoutComments` model is preserved per D3; the
open count lives in the dock pill). Revisit only if a static rail header is wanted.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where); — MR-087/088/089/090
      all `done`, none carried over.
- [x] no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done` (MR-090 is
      not carry-over-eligible); — MR-090 `done` within the sprint.
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-28-close-review-2026-06-25.md` (independent, PASS-with-conditions), verifying
      shipped work against each ticket's AC, **including a render smoke** — both pages'
      `scripts/render-smoke.sh` DOM assertions + screenshots + dark-pane computed-style + the wide-mode
      `body.gutter-on` check under `reviews/sprint-28-render-evidence-2026-06-25/`, plus the
      throwaway-container rebuild + `curl /healthz` + `/api/reviews` smoke — all 5 findings resolved
      (`3f85c50`), 0 blockers.
- [x] retro + carry-overs (none) recorded above, and `close_review:` set in frontmatter.
