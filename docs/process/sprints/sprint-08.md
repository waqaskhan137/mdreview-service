---
id: sprint-08
name: render-fidelity
status: active
start: 2026-06-18
end: 2026-06-25
goal: Render GFM footnotes and syntax-highlighted fenced code in the viewer, so a draft reviews as it will publish.
close_review:          # reviews/sprint-08-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

By the end of the sprint, a reviewer opening `/review/{id}` sees the last two publish-fidelity
features the viewer was missing: **GFM footnotes** (`[^id]` refs → an ordered back-ref section) and
**syntax-highlighted** fenced code (vendored highlight.js, a dual-scheme theme legible on both light
and dark panes), with mermaid blocks still rendered as diagrams (not highlighted). Both register on
the existing `marked` extension path (`setupKatex`→`setupMarked`) at parse time. Nothing already
shipped regresses (math, mermaid, image mat, GFM tables, block numbering); a doc with no footnotes
and no code renders byte-identical to today. `viewer.html` + vendored `static/` files only — no
service/API/MCP change.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-028 | Vendor `marked-footnote`; render GFM footnotes (refs + ordered back-ref section) | ui | P2 | ready |
| MR-029 | Vendor highlight.js (common) + `marked-highlight` + dual-scheme theme; highlight fenced code (skip mermaid) | ui | P2 | ready |
| MR-030 | Docs — footnotes + syntax highlighting render in the viewer | docs | P2 | ready |

All vendored assets (~136 KB total) are committed into `static/` and served by the existing route —
no `app.py` / `Dockerfile` change. MR-021, the cut local-dir asset read, and the infra backlog items
stay backlog (not committed).

## Preferred execution order

Ordered by risk, not hard dependency (MR-028/029 both extend `setupMarked()` + the head, so run
sequentially to avoid a trivial merge conflict).

1. **MR-028** — footnotes (smallest, one tiny vendored file, no theme decision).
2. **MR-029** — highlighting (larger payload + dual-scheme theme; the browser-global + sync-parse
   path was reproduced at G1).
3. **MR-030** — docs (depends on both; **not** carry-over eligible per G7).

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or carried over (MR-030 is a docs ticket — **not**
      carry-over eligible; deferred docs are force-closed at close);
- [ ] **no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done`**;
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-08-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      ACs; since product pages (`viewer.html`, `static/**`) are touched, it rebuilds the container,
      runs `curl /healthz` + `/api/reviews`, **and** runs `scripts/render-smoke.sh` against
      `/review/{id}` asserting the footnote nodes (`sup`/`.footnotes`) + highlighted tokens
      (`.hljs`/`.hljs-keyword`) + no-regression (`.katex`/`.mermaid`/`table`), with **light AND dark**
      screenshots under `reviews/sprint-08-render-evidence-*` (the hljs theme is theme-sensitive);
- [ ] retro + carry-overs recorded above, and `close_review:` set in frontmatter.
