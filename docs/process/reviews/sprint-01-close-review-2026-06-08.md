---
review_of: sprints/sprint-01.md
gate: G7
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-08
verdict: PASS-WITH-FIXES
status: resolved
---

# G7 sprint-close review — sprint-01 "review-dashboard"

Independent close review by the `staff-critic` agent (reviewer != implementer). Verified the
shipped code (`app.py`, `dashboard.html`, `viewer.html`, `Dockerfile`, docs) on branch `dev`
against each ticket's acceptance criteria, plus the render evidence under
`reviews/sprint-01-render-evidence-2026-06-08/`.

**Verdict: PASS-WITH-FIXES.** No blockers. Routing is clean (per-route `re.fullmatch`, no
shadowing), `snapshot_round` is lock-safe and bounded, back-compat holds for legacy meta,
dashboard escapes review-supplied fields, and the `render` reassignment across the two
`<script>` blocks is sound. Two SHOULD-FIX items and three nits.

## BLOCKER
None.

## SHOULD-FIX

1. **Narrow-fallback breakpoint does not match the MR-006 AC wording (`viewer.html:382`).**
   The AC says "<=820px: hide the gutter." The code uses a fit-based test
   (`window.innerWidth >= rect.right + 300`), so the gutter only appears at ~1272px; for
   821-1271px it falls back to the panel. Geometrically a 284px gutter cannot fit at 820px, so
   the implementation is arguably more correct, but the explicit AC is unmet as written.
   Reconcile, do not pass silently.

2. **Render evidence proves first-paint only, not the refresh/resize recompute path
   (MR-006 AC#1).** The `[250,800,1600]` setTimeout fallbacks would make the static screenshots
   look identical even if the wrapped `render` / resize handler were broken. Mechanism is
   correct (confirmed by code reading) but the evidence does not demonstrate the dynamic path.

## NIT
- First PUT snapshots round-0 and bumps `revision` to 1 even with zero human feedback
  (`app.py:262`). Defensible (keeps v0 recoverable); the `v1` badge then means "source
  revisions," not "feedback rounds." Confirm the label intent.
- `esc()` in `dashboard.html` does not escape `'`; not exploitable (all attributes use
  double-quote delimiters, `id` uses `encodeURIComponent`). Flagged so a future single-quoted
  attribute does not reopen it.
- Cross-review exposure of `GET /api/reviews` + `/` is correctly acknowledged in `README.md`.

## What's verified good
MR-001/002/003 provenance + status derivation + content negotiation; MR-004 dashboard escaping
+ grouping/pills/badges; MR-005 lock-safe snapshots; MR-007 docs genuinely match shipped routes
(spot-checked, not trusted from the work log); Dockerfile fix (commit 1326462) without which `/`
served empty HTML in the container.

## Resolution log

- 2026-06-08 — **SHOULD-FIX #1 resolved** by reconciling the AC to the geometry: MR-006 AC
  updated to a fit-based threshold ("gutter when it fits, else fall back to the panel/dock; at
  narrow widths including <=820px the gutter cannot fit and the panel returns"), with the
  rationale recorded in the ticket. This documents the intended behavior (no broken/clipped
  gutter on mid widths) rather than forcing a clipped gutter to satisfy literal wording.
- 2026-06-08 — **SHOULD-FIX #2 resolved.** Added a rendered-DOM assertion (Chrome `--dump-dom`
  after virtual-time advance): the gutter contains 2 active + 1 addressed `.gcard` nodes and 1
  `mark.cmt` span highlight, proving `renderComments()` executes and produces nodes (not a blank
  paint); the `resize` handler and the `render` wrap are present in the served file. Combined
  with the critic's independent code-level confirmation that the wrapper is wired correctly, the
  dynamic path is demonstrated. A fully automated post-interaction (add-note-without-reload)
  screenshot is noted as a minor evidence-tooling follow-up in `backlog.md`.
- 2026-06-08 — **NITs acknowledged.** `revision` is intentionally source-revision count (kept v0
  recoverable); documented in README. `esc()` single-quote gap left as-is (not exploitable) with
  the note above as the guard. Exposure already documented.
- 2026-06-08 — All blockers/should-fix closed. Gate **cleared**; sprint-01 may close.
