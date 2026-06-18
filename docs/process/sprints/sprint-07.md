---
id: sprint-07
name: theme-awareness
status: closed
start: 2026-06-18
end: 2026-06-18
goal: Give embedded images a neutral mat so light-authored figures stay legible on a dark review pane.
close_review: reviews/sprint-07-close-review-2026-06-18.md   # G7 staff-critic PASS, resolved
---

## Goal

By the end of the sprint, a reviewer opening `/review/{id}` on a **dark** OS pane sees light-authored
figures (PNG/SVG, including attached rich-rendering assets) rendered on a near-white mat — legible,
not a dark smear — and on a **light** pane the mat blends in. Mermaid (JS-themed) and KaTeX (span
text) are untouched; a document with no images looks byte-identical to today on both panes. The
inverse case (dark-authored / white-on-transparent figures) is an accepted non-goal this sprint
(needs per-image luminance detection — backlog). A `viewer.html`-only, CSS-only change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-027 | Viewer — neutral light mat behind `#article img` + `.histdoc img` (excludes mermaid/katex) | ui | P1 | done |

Single-ticket sprint (the plan resolved to one focused CSS change). No P2/MR-021 work committed.

## Preferred execution order

1. **MR-027** — the `#article img, .histdoc img` mat in `viewer.html`, proven on both light and dark
   panes from a throwaway container (the bug is theme-specific; dark screenshot is the core artifact).

## Notes / retro

- `2026-06-18` — MR-027 shipped same-day: a CSS-only `viewer.html` change (`#article img, .histdoc
  img` near-white mat), validated from a rebuilt throwaway container on :8138 (never compose/:8139).
- `2026-06-18` — **The G1 critic earned its keep.** The plan initially claimed a symmetric fix; the
  critic *measured* that a white mat **regresses** dark-authored/white-on-transparent figures
  (legible→invisible, luminance 238→5) and made the planner re-scope honestly to the light-authored-
  on-dark majority case, naming the inverse a non-goal. The shipped dark screenshot shows both the
  fix (B legible) and the non-goal (C washed out) side by side, so the tradeoff was signed off on
  sight, not hidden. The planner had also *measured* (not assumed) that host `color-scheme` can't
  reach an `<img>`-loaded SVG, correctly rejecting the brief's option (b).
- `2026-06-18` — **Closed at G7: staff-critic PASS** (`reviews/sprint-07-close-review-2026-06-18.md`,
  resolved). 0 blockers, 1 SHOULD, 2 NITs. The critic rebuilt on :8141 and reproduced the fix/
  non-goal/no-regression independently.
- **Carry-overs:** none (work-wise). One carry-**note** (SHOULD-1): the `.histdoc` history-modal mat
  arm is proven by shared-CSS-declaration + `showRound()` inspection, not a screenshot (the modal is
  closed at first paint); add a manually-opened-modal shot if a future cycle touches `.histdoc`.
- **Retro:** a tight single-ticket cycle. The two empirical measurements (the `color-scheme`
  boundary, the mat regression) — one by the planner pre-G1, one forced by the critic at G1 — kept
  the plan honest and meant G7 was a first-pass PASS with nothing to re-open. Scope held to the one
  P1 start to finish.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-07-close-review-YYYY-MM-DD.md`, verifying shipped work against MR-027's
      acceptance criteria; since a product page (`viewer.html`) is touched, it rebuilds the
      container, runs `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh`
      against `/review/{id}` asserting `img` + `#article` (+ `.mermaid`), with **light AND dark**
      screenshots under `reviews/sprint-07-render-evidence-*` (the theme-specific proof);
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
