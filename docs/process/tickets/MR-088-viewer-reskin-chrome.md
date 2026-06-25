---
id: MR-088
title: Viewer re-skin — chrome (top bar + breadcrumb + title meta) + baton banner + numbered lines + article typography
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: []
branch:                # MR-088-viewer-reskin-chrome, once work starts
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

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Reviewer-side Resolve button is a deliberate non-goal (epic D3) — handled (rejected) in MR-089's surface.
