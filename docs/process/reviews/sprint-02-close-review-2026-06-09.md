---
review_of: sprints/sprint-02.md
gate: G7
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-09
verdict: PASS-WITH-FIXES
status: resolved
---

# G7 sprint-close review — sprint-02 "process-hardening"

Independent close review by `staff-critic` (reviewer != implementer). Verified MR-008..MR-011
against their AC, the shipped diff (planner agent, `scripts/render-smoke.sh`, README, skill
reference), README self-consistency, and the render evidence. The reviewer **re-ran the
render-smoke live** against the container, including the async-render case and a render-wait
ablation (`RENDER_SMOKE_VTB=1`).

**Verdict: PASS-WITH-FIXES.** No blockers. The load-bearing artifact (`render-smoke.sh`) does what
it exists to do: real DOM-element matching (not substring grep), a load-bearing render-wait,
fail-loud exit 3, and it cannot false-pass. All four tickets' core AC met; the gate-row wording
landed in the correct G4/G7 rows; the gate set and lifecycle are unchanged.

## BLOCKER
None.

## SHOULD-FIX (all resolved)

1. **Unsupported selectors silently mis-parsed** (`render-smoke.sh`). A selector with a combinator
   / attribute / pseudo / whitespace was accepted and matched 0, looking identical to a render
   failure (never a false-pass, but a misleading signal). **Resolved:** the script now validates
   each selector against the supported grammar (`tag`/`.class`/`tag.class`/`#id`) and exits 2
   (bad usage) naming any unsupported selector. Verified live: `"div > .card"`, `"[data-id]"`, and
   a space-containing arg all now exit 2; valid selectors still exit 0.
2. **AC named `document.querySelectorAll`; shipped an `html.parser` element counter.** Intent met
   (the epic blesses an equivalent that distinguishes rendered nodes from source text), but the
   headline mechanism differed. **Resolved:** MR-009 AC now records the implementation note (flat
   matcher, rejects unsupported selectors).
3. **Render evidence omitted the async exit-0 case** (the reason the render-wait exists).
   **Resolved:** appended to `reviews/sprint-02-render-evidence-2026-06-09/render-smoke-runs.txt`:
   viewer `.gcard`/`mark.cmt` -> 2 nodes each exit 0; the same with `RENDER_SMOKE_VTB=1` -> 0
   nodes exit 1 (render-wait load-bearing); the combinator-reject -> exit 2; plus a note that
   `.gcard`/`mark.cmt` only render on a review that has comments.
4. **Stale line anchors (off by ~7 after the README grew).** Content landed in the correct rows,
   but numeric cites pointed at blank lines. **Resolved:** the active tickets (MR-010, MR-011)
   now cite the **gate rows by name** rather than brittle line numbers. (The epic's historical
   anchors are left as-authored; row-name references are the durable form going forward.)
5. **Close-step board drift** (sprint listed tickets `ready`, checkboxes unchecked, `close_review`
   empty). **Resolved:** reconciled as part of closing — sprint-02 committed tickets set `done`,
   close-gate checked, `close_review` set, TRACKER moved.

## NIT
- `render-smoke.sh` runs Chrome with `--no-sandbox` (deliberate for local/CI). Acknowledged.

## Confirmations (independently re-verified live)
- Anti-grep genuine: `.empty` is in `dashboard.html` CSS source but renders 0 elements when
  reviews exist -> exit 1.
- `.card` is JS-rendered (built in JS, injected via innerHTML), so the present-case exercises the
  render-wait — not a static-HTML freebie.
- Exit status not masked (`set -u`, no pipe; the Python heredoc's `sys.exit` propagates).
- G7 row coherent: "done or explicitly carried over" + "a docs-sweep ticket is NOT eligible for
  carry-over" is a rule + carve-out, not a contradiction.
- README internally consistent across DoD / G5 / G7; gate set G0-G8 + lifecycle unchanged.
- MR-008 planner edits present and sound (fit-based rule + Dockerfile-COPY footgun, additive).

## Resolution log
- 2026-06-09 — review recorded (PASS-WITH-FIXES, no blockers). All five SHOULD-FIX resolved in
  Phase 7 (script selector-validation + live re-test; MR-009 note; async/ablation evidence added;
  ticket anchors de-brittled to row names; close-step reconciliation). Gate **cleared**;
  sprint-02 closes.
