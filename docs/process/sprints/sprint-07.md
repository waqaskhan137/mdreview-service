---
id: sprint-07
name: theme-awareness
status: active
start: 2026-06-18
end: 2026-06-25
goal: Give embedded images a neutral mat so light-authored figures stay legible on a dark review pane.
close_review:          # reviews/sprint-07-close-review-YYYY-MM-DD.md — required by G7 before status: closed
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
| MR-027 | Viewer — neutral light mat behind `#article img` + `.histdoc img` (excludes mermaid/katex) | ui | P1 | ready |

Single-ticket sprint (the plan resolved to one focused CSS change). No P2/MR-021 work committed.

## Preferred execution order

1. **MR-027** — the `#article img, .histdoc img` mat in `viewer.html`, proven on both light and dark
   panes from a throwaway container (the bug is theme-specific; dark screenshot is the core artifact).

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over;
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-07-close-review-YYYY-MM-DD.md`, verifying shipped work against MR-027's
      acceptance criteria; since a product page (`viewer.html`) is touched, it rebuilds the
      container, runs `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh`
      against `/review/{id}` asserting `img` + `#article` (+ `.mermaid`), with **light AND dark**
      screenshots under `reviews/sprint-07-render-evidence-*` (the theme-specific proof);
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
