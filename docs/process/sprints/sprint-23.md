---
id: sprint-23
name: history-version-fix — labels + notes-count
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Reconcile the History modal's version labels with the dashboard badge (list the current draft on top, relabel archived rounds) and remove the untruthful per-round "0 notes" count at its source.
close_review: reviews/sprint-23-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent; re-drove the node-CDP modal verify)
---

## Goal

Land the two-ticket `history-version-fix` batch. The History modal currently tops out at `v(N-1)`
while the dashboard badge shows `vN`, never lists the current live draft, and stamps every round
"0 notes" (the retired `notes.json` count). Success by the end date: MR-064 `done` on `dev` (svc —
`snapshot_round` stops writing the legacy count into `round.json` + `README.md:55` updated to the
`{round, ts}` shape, validated by `py_compile` + a curl smoke) and MR-065 `done` (ui — the History
modal lists the current draft as `current (v{rev})` from existing endpoints, relabels archived rounds
newest-first display-only, and drops the count label + empty notes block, validated by a node-CDP
modal-DOM drive + screenshot). Sprint closes at G7.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-064 | snapshot_round: stop writing the retired notes count into round.json (+ README.md:55 shape) | svc | P2 | done |
| MR-065 | History modal: list current draft as `current (vN)`, relabel rounds, drop "0 notes" | ui | P2 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first. MR-065 `depends_on` MR-064
(the UI must not display a count the service may still emit).

1. MR-064 (svc) — remove the legacy count from `snapshot_round`/`round.json`; update `README.md:55`
   to `{round, ts}`; `py_compile` + curl smoke of `/history` + `/history/{n}` on a 2-PUT review.
2. MR-065 (ui) — History modal current-draft top entry (always rendered; relocate the
   `viewer.html:678` early-return) + relabel + count removal; static render-smoke for `#histbtn` +
   dashboard `.badge`, and a node-CDP drive for the modal DOM. Depends on MR-064.

## Notes / retro

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-23-close-review-2026-06-24.md`).
MR-064 + MR-065 `done`, no carry-overs. **This closes the `history-version-fix` epic — epic `done`.** GH #18 closed.

- **Shipped (GH #18, two defects):** MR-064 (svc) — `snapshot_round` stops writing the untruthful per-round
  notes count (it counted the retired `notes.json`, always 0 since the comments era); `round.json` is now
  `{round, ts}`, README `/history` shape updated. MR-065 (ui) — the History modal lists the current draft
  as a `current (vN)` top entry that reconciles with the dashboard `vN` badge (Defect A), relabels archived
  rounds `v{round} · earlier draft` newest-first, and drops the "0 notes" label (Defect B).
- **The modal-verification wall (named-recurrence solved):** `render-smoke.sh` can't open the click-populated
  History modal (sprint-07 hit this and waived it as cosmetic). Here the modal DOM WAS the deliverable, so
  the smoke is a **node-CDP eval driver** (the `agent_smoke.py` WebSocket/`Runtime.evaluate` pattern) — G1
  caught that bare render-smoke would false-pass, and both G7 (the implementer's + the critic's independent
  re-run, 11/11) drove it for real. Worth promoting node-CDP as the standard for any click-gated viewer DOM.
- **Carry-overs:** none. #18 is fully resolved. Relationship to #19 (a future version-picker/diff) left
  un-cornered — the labels are now trustworthy, the on-disk round-n/`/history/{n}` are unchanged.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-064 + MR-065 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-23-close-review-2026-06-24.md`, verifying shipped work against each ticket's
      acceptance criteria, **including a render smoke** of the touched page (the History modal, re-driven
      independently by the critic via node-CDP — render-smoke.sh can't open it), and its findings resolved;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (history-version-fix specifics).** **MR-065 IS a product-page change** — it edits
`viewer.html` (baked into the container at build time). The History modal is `display:none` until
`openHistory()` runs on a click, and `scripts/render-smoke.sh` does a single `--dump-dom` with no
click/eval, so a bare `render-smoke.sh` against the modal selectors (`.histitem`/`.histdoc`) returns 0
on a correct build (false fail; the sprint-07 wall). So MR-065 **owes a node-CDP modal-DOM
verification** (the proven `agent_smoke.py:112-148` pattern: Node built-in `WebSocket` over CDP,
`Runtime.evaluate{returnByValue, awaitPromise}` to call `openHistory()` and read the populated modal
back) asserting `.histitem` count >= 3, top entry `current (v2)` == the dashboard `.badge`, archived
`v1`/`v0` newest-first, **no "notes" text** on the rendered DOM, and the current entry click yielding
`#histview .histdoc` with the draft text — **plus a screenshot** of the open modal, **plus** a static
`render-smoke.sh` for the non-modal nodes only (`#histbtn`, dashboard `.badge`). Bare render-smoke
against the modal selectors is **forbidden**. Evidence under
`reviews/sprint-23-render-evidence-2026-06-24/`.

**MR-064 is svc + a single README line** (no served page touched), so it owes **no render-smoke** —
its gate is `python3 -m py_compile app.py` + the curl smoke (POST → 2 PUTs → `/history` +
`/history/{n}` show the new `round.json` shape with no `notes_total`) + the README grep in its
acceptance criteria.

Both tickets rebuild a **throwaway container** on a **scratch port** (never 8139/8137, never
`docker compose up`); all temp under the gitignored `.scratch/`, evidence moved to the gate folder.
