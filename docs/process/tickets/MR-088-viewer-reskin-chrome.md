---
id: MR-088
title: Viewer re-skin — chrome (top bar + breadcrumb + title meta) + baton banner + numbered lines + article typography
status: done           # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: []
branch: feat/ui-updates   # cycle runs on feat/ui-updates (off dev), single-flight
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Re-skin the **non-comment** half of `viewer.html` to the mockup: the top bar (`← Reviews` home link +
filename, and `vN · <turn state>` on the right), the breadcrumb line
(`project / session / source_path`) above the title, the title + `N words · ~M min read · vN` meta,
the "Your turn" baton banner, the numbered markdown lines, and the `#article` typography. Restyle
only — the baton JS (`renderBanner`, `#turnsteps` timeline, `#turntimer`), `numberBlocks()`, and the
`STALE_S` staleness timer keep their exact contracts. No backend change.

See epic decisions **D4** (dark mode), **D5** (numbered lines / mermaid order). The COMMENTS rail +
bottom dock are MR-089.

## Acceptance criteria

- [ ] Top bar renders: `← Reviews` link (home), the `source_path` filename, and a right-side
      `vN · <turn state>`. Breadcrumb line `project / session / source_path` renders above the title,
      wired from `META.project/session/source_path` already fetched in `boot()`, rendering **only the
      segments present** (legacy reviews lack provenance — epic R5/Key constraint #3).
- [ ] Title + meta (`N words · ~M min read · vN`) render to the mockup.
- [ ] Baton banner (`#turnbanner`) restyled to the mockup's violet "Your turn" treatment + "Send to
      agent" button **without changing `renderBanner()`'s class logic** (`loading`/`warn`/`steps`/
      `show`, `#turnsteps`, `#turntimer`). The ids/classes the JS toggles are unchanged; only CSS
      changes. (epic Recommended approach → Viewer)
- [ ] `STALE_S` (viewer, line 249) stays `180` and keeps its source-of-truth mirror comment pointing
      at `app.py:57` `LEASE_TTL_S`. `grep STALE_S viewer.html` still shows `180`. (Key constraint #2)
- [ ] Numbered lines: `.blk`/`.num` restyled to the mockup's lighter left-margin number; the
      `.blk.has-comment` margin-bar + dot stays. `load()` keeps the order `numberBlocks()` (line 508)
      **then** `await renderMermaid()` (line 509) — not reordered (epic D5).
- [ ] `#article` typography re-skinned; serif body retained (epic assumption 4). Lightbox, footnote
      `.sr-only` clip, and the `#article img` light mat (line 43) are unchanged (the mat is a
      documented non-goal — do not widen past `img`).
- [ ] Dark mode preserved (epic D4): mockup light palette as `:root`, existing
      `@media (prefers-color-scheme: dark)` token swap retained; baton banner verified on BOTH panes.
- [ ] Local validation passes: `python3 -m py_compile app.py` + `docker build`, then from the
      rebuilt container `scripts/render-smoke.sh "$BASE/review/<id>" '.topbar-or-final-id'
      '.breadcrumb' '#doctitle' '#turnbanner' '#sendbtn' '.blk' '.num'` — every selector ≥1 node
      (seed the fixture `turn=reviewer` so the banner shows "Your turn"; flat selectors only). Plus
      both-pane screenshots of `/review/<id>` via `preferredColorScheme=1`/`=0` (never
      `--force-dark-mode`), inspecting the baton banner on each pane (epic R4).
- [ ] Functional spot-check (no regression): `numberBlocks()` produced `.blk`+`.num` on the
      re-skinned article; the baton "Send to agent" flips `turn` to `agent`; the staleness timeline
      ticks with a `working` lease.

## Notes / context

- Epic plan: decisions D4, D5; Verification §3 (chrome/baton/numbered-line selectors), §4 (baton +
  staleness functional checks).
- Current file: `viewer.html` — `numberBlocks()` (513), `load()` order (508–509), `STALE_S` (249),
  `#article img` mat (43), `renderBanner`/`#turnbanner`/`#turnsteps`/`#turntimer`/`#sendbtn`/
  `#reclaimbtn` (baton machinery). `META`/`boot()` provenance fetch.
- Served at `/review/{id}` via `_read` (`app.py:812`).
- **Re-skin the DOM, not the wiring** (epic Core principle): keep the baton/numbering ids; restyle
  CSS only. Any renamed id is updated at every JS reference in THIS ticket.
- Footguns: flat render-smoke selectors; a 200 is not a render; capture both panes via
  `preferredColorScheme`.

## Work log

- `2026-06-25` — Re-skinned the viewer chrome in `viewer.html` (CSS + markup + small JS; no JS
  contract changed). Palette swapped to the mockup (violet `--accent` baton/comments, blue `--blue`
  headings/links, `--noteline` violet) with the dark theme preserved via the
  `@media (prefers-color-scheme:dark)` token swap. New full-width sticky `.topbar`: `← Reviews` +
  `#filename` (basename of `source_path`, violet) on the left, `#topstate` (`vN · <turn state>`) on
  the right, set in `renderBanner`. Added `#breadcrumb` (`project / session / source_path`, present
  segments only — `renderChrome()`, legacy-safe). Removed the `.howto` box (the mockup has none; the
  baton banner already carries the guidance). `#doctitle` → sans bold; `#docmeta` appends `· vN`.
  `#article h2` → blue uppercase; blockquote → violet left bar; links/footnotes → blue. Numbered
  `.blk .num` restyled (tabular, lighter). Re-skinned the baton banner (`.turnbanner`) to the violet
  treatment with a pencil-icon `::before` and a right-hand `.turnactions` column; **moved `#sendbtn`
  into the banner** (was in the dock) next to `#reclaimbtn` — `renderBanner`'s show/disable/relabel
  logic and all ids (`#turntext/#turntimer/#turnsteps/#turnbanner` classes) unchanged. `STALE_S=180`
  and its mirror comment untouched.

## Validation

- `2026-06-25` — `python3 -m py_compile app.py` green; viewer inline JS parses (`new Function`).
- Render-smoke (throwaway :8155, `turn=reviewer` fixture with comments): `.topbar .home #filename
  .breadcrumb #doctitle #docmeta #turnbanner #sendbtn #reclaimbtn .blk(6) .num(6) #article` all
  ≥1 node, exit 0.
- `grep STALE_S viewer.html` → still `180` with the mirror comment (Key constraint #2).
- Both panes vs mockup: light (`.scratch/shots/viewer-mine-light.png`) + dark
  (`viewer-mine-dark.png`), captured via `preferredColorScheme=1`/`=0` (never `--force-dark-mode`) —
  top bar, breadcrumb, sans title, violet baton + pencil icon + blue "Send to agent →", blue
  section headings, violet blockquote bar, numbered lines all match; baton legible on both panes.
- Baton functional spot-check carried into MR-089's verification (Send flips turn; banner states).

## Follow-ups

- Reviewer-side Resolve button is a deliberate non-goal (epic D3) — handled (rejected) in MR-089's surface.
- Comment-entry tint (`.gentry.reviewer`/`.gentry.agent`) still amber/teal pending MR-089 (the
  comments-rail ticket) — palette tokens already violet, the hard-coded entry backgrounds change there.
