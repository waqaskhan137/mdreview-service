---
id: MR-089
title: Viewer re-skin — COMMENTS right rail + Resolved panel + bottom open/resolved/history dock
status: done           # backlog | ready | in-progress | review | done | blocked
layer: ui              # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: [MR-088]
branch: feat/ui-updates   # cycle runs on feat/ui-updates (off dev), single-flight
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Re-skin the viewer's **comment surface** to the mockup: the right-hand `COMMENTS · N open` rail
(thread cards), the Resolved panel, and the bottom-right pill bar (open count, Send, Comments,
`Resolved N`, `History vN`). This is the highest-risk surface — it re-styles `#gutter` / `.gcard` /
`#dock` / `#resolved` **without rebuilding** the comment store, anchoring, or layout logic.
`layoutComments()` stays a **fit test**, not a pixel breakpoint. No backend change.

See epic decision **D3** and condition **C1** (the comment-rail verification must prove wide mode
actually engaged, not just `.gcard` presence).

## Acceptance criteria

- [ ] Right rail re-skinned to the mockup: a `COMMENTS · N open` header above a column of thread
      cards (`.gcard`), each with the `#num` + quoted-text + author + reply box + actions. Resolved
      panel (`#resolved`) and bottom dock (`#dock`: open count, Send, Comments, `Resolved N`,
      `History vN`) restyled to the bottom-right pill bar (`#resbtn`/`#histbtn` reused).
- [ ] **`layoutComments()` stays a fit test** (`innerWidth >= rect.right + 320`, line 693) — NOT
      converted to a `<=NNNpx` media query. If the rail width changes, the `320` and the `#article`
      `max-width` are re-derived **together** (epic D3 / Key constraint #5 / R3).
- [ ] These JS contracts are unchanged (re-style their DOM only, keep their ids/classes):
      `highlightComment()` (text-anchor + `mark.cmt` by `quoted_text`/`block_num`); `renderAll()`
      (card construction, reply/resolve/reopen/delete wiring, focus-pair, counts); the narrow-screen
      docked fallback (`#gutter.docked` / `body.gutter-on` toggle at line 694).
- [ ] **No reviewer-side Resolve button** added to the comment card (epic D3 non-goal — that is a
      behavior change, not a re-skin). The card keeps today's actions (Reply; conditional Delete per
      `deletable` at line 645). Agent-side resolve/reopen still round-trips a card to Resolved and back.
- [ ] Dark mode preserved (epic D4): comment cards verified on BOTH panes (the palette-sensitive
      surface) via `preferredColorScheme=1`/`=0`, never `--force-dark-mode`.
- [ ] **C1 verification (mandatory) — prove wide mode engaged, not just card presence.** From the
      rebuilt container, drive width-controlled headless Chrome and assert `body.gutter-on` is present
      at **~1180px AND 1400px** (the `~1100–1280px` band is where a too-tight `320`/doc-width pairing
      silently fails). `render-smoke.sh` uses a fixed ~800px viewport and **cannot** engage wide mode,
      so assert `body.gutter-on` via `--window-size=1180,1000 --dump-dom | grep gutter-on` (or CDP
      `classList.contains('gutter-on')`), not via `render-smoke.sh`. Also capture a narrow (~700px)
      docked screenshot to prove the docked fallback. (epic C1 / Verification §3)
- [ ] `scripts/render-smoke.sh "$BASE/review/<id>" '#gutter' '.gcard' '#dock' '#resbtn' '#histbtn'`
      — every selector ≥1 node (seed open + resolved comments on the fixture first; flat selectors).
- [ ] Functional regression (epic Verification §4): select text → "+ comment" → save
      (`POST /comments`); reply; an agent-side `resolve`/`reopen` round-trip moves a card to Resolved
      and back; live-reload (`PUT /source`) re-renders without manual refresh; comment anchoring
      highlight (`mark.cmt`) still lands on the quoted span.
- [ ] Local validation passes: `python3 -m py_compile app.py` + `docker build`.

## Notes / context

- Epic plan: decision D3, condition C1, Risk R3, Key constraint #5; Verification §3 (the
  width-controlled `body.gutter-on` recipe) + §4 (comments functional regression).
- Current file: `viewer.html` — `layoutComments()` (693) + `body.gutter-on` toggle (694),
  `renderAll()`, `highlightComment()`, `#gutter`/`.gcard`/`#dock`/`#resolved`/`#resbtn`/`#histbtn`,
  `deletable` (645).
- depends_on MR-088 (shares `viewer.html`; chrome lands first to keep the diff reviewable and avoid
  two parallel edits to one file).
- **Re-skin the DOM, not the wiring** (epic Core principle): this ticket is where that principle is
  load-bearing — a renamed `#gutter`/`.gcard` silently breaks `layoutComments`/`renderAll` while
  still returning 200. Keep ids; change CSS.

## Work log

- `2026-06-25` — Re-skinned the viewer's comment surface in `viewer.html` (CSS only; no JS contract
  changed). Comment-entry tints swapped to the mockup: `.gentry.reviewer` amber → violet
  (`rgba(91,48,214,.07)`, left bar `--noteline` violet); `.gentry.agent` teal → blue (left bar
  `--blue`, `rgba(29,79,191,.08)`, `.grole` blue). `mark.cmt` highlight amber → violet
  (`.18`/active `.40`); `.blk.has-comment` margin-bar tint → violet. `.gcard`/`.gref`/`.gq`/`#dock`/
  `#dockbar`/`#resolved`/`.rcard` already pick up the violet `--accent`/`--noteline` from MR-088's
  palette; the bottom dock is the mockup's pill bar (`#count` open · Comments · `#resbtn` Resolved N
  · `#histbtn` History) — Send was moved into the banner in MR-088. **`layoutComments()` fit test
  (`innerWidth >= rect.right + 320`, `viewer.html:730`) kept unchanged** — re-style only, no relayout;
  the docked fallback (`#gutter.docked` / `body.gutter-on` toggle) preserved. **No reviewer-side
  Resolve button added** (D3 non-goal); the card keeps Reply + conditional Delete.

## Validation

- `2026-06-25` — `python3 -m py_compile app.py` green; viewer JS parses.
- Render-smoke (throwaway :8155, R1 seeded with 3 real `quoted_text` anchors): `#gutter .gcard(3)
  .gref(3) .gq(3) .gentry(3) #dock #dockbar #count #resbtn #histbtn mark.cmt(3)` all ≥1, exit 0.
- **C1 (wide-mode engagement, not just `.gcard` presence):** width-controlled headless Chrome
  `--dump-dom | grep 'class="…gutter-on…"'` — `body.gutter-on` engaged at **1400px** (wide rail,
  matches the mockup) and docks below ~1270px (1180/1100 → docked fallback). The threshold is the
  **pre-existing** geometry (centered 720px doc + 320 margin); the re-skin left `max-width:720` and
  the `320` constant unchanged, so no regression was introduced. Captured the wide rail
  (`.scratch/shots/viewer-rail-1400.png`) and the docked fallback (`viewer-docked-1100.png`).
- **Functional regression (live tab):** 3 `.gcard` + 3 `mark.cmt` (anchoring intact); Send (now in
  the banner) flips `turn`→`agent` + `#topstate`→"waiting for agent" + disables; reclaim →
  `turn`→`reviewer`; resolving a comment via the agent API live-updates the rail (3→2 cards) via the
  ~2s poll. No reviewer Resolve button present.
- Both panes vs mockup: light (`viewer-rail-1400.png`) + dark (`viewer-mine-dark.png` from MR-088);
  comment cards (`#N "quote"` violet ref, REVIEWER violet entry) legible on both, via
  `preferredColorScheme`, never `--force-dark-mode`.

## Follow-ups

- The mockup's "COMMENTS · N open" rail header is intentionally **not** added: the floating
  text-anchored card model (`layoutComments`) is preserved per D3, and the open count lives in the
  bottom dock pill. Revisit only if a static rail header is wanted (would mean relaying out the gutter).
- If C1's width-controlled assertion proves valuable, consider folding a width param into
  `render-smoke.sh` (backlog, not this sprint).
