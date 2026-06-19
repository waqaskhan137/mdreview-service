---
review_of: sprints/sprint-09.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# sprint-09 (dashboard-redesign) — independent close review (G7)

**Verdict: PASS.** MR-031 ships a clean single-file rewrite of `dashboard.html` that meets every
load-bearing AC under independent reproduction: 3–5 columns capped at 5 (measured live, not just
screenshotted), collapse/expand with all three guards (action-control, keyboard parity, text
selection) working, search + empty-group hiding, collapsible groups with session-`Set` memory, a
pane-adaptive theme legible on both panes — and, the constraint the brief hinges on, **preserved
Open/Delete/version/notes all reproduced end-to-end** (delete removes the card from the DOM *and*
`/api/reviews`; `v2` and `2 notes · 1 done` render from real data). No `app.py`/`Dockerfile`/
`viewer.html` drift. Sprint should close.

## Reproduction (independent, not from the Work log)

- `git fetch origin main` then `git diff origin/main...dev --stat`: **`dashboard.html` + process files
  only**; `git diff origin/main...dev -- app.py Dockerfile viewer.html mcp_server.py` is **empty** — no
  service/infra drift.
- `python3 -m py_compile app.py` → exit 0 (file unchanged).
- `docker build -t mdreview-dash2 .` OK; ran throwaway on **:8141** (never compose/:8139). Seeded 2
  projects, a `blog 2 › run-1` session with ≥7 cards, and a throwaway "Delete me".
- `scripts/render-smoke.sh '/' '.grid' '.card' '#search' '.group-header'` → all ok (`.grid` 3 /
  `.card` 9 / `#search` 1 / `.group-header` 2), exit 0. Flat selectors only — no descendant
  selectors anywhere in the evidence/ticket (footgun 11 clean).
- Interaction + measurement driven via Chrome DevTools Protocol (Node built-in `WebSocket`,
  `Emulation.setDeviceMetricsOverride`). All eight required screenshots present under
  `reviews/sprint-09-render-evidence-2026-06-19/` and viewed.

## MR-031 AC — met / not-met (with reproduced evidence)

1. **Density + columns — MET.** Live CDP `getBoundingClientRect` column count on the ≥8-card
   `run-1` grid: 1280px→4, 1440px→4, 1680px→**5**, 1920px→**5**, 2560px→**5** (`.wrap` max-width
   computes to `1600px`). The cap holds: 6 columns never realized on 1080p/ultrawide. Card width
   ~302px, collapsed card = title (single-line ellipsis, `padding-right:86px` for the action
   cluster, `dashboard.html:51`) + one meta row. `wide-5col.png` / `ultrawide-capped.png` /
   `collapsed.png` corroborate. (I initially miscounted the downscaled PNG as 4 cols; re-measuring
   against the exact evidence seed gave 5 — retracted.)
2. **Click-to-expand without swallowing actions/selection — MET.** Delegated handler
   (`dashboard.html:228-254`): delete branch first (`confirm→DELETE→load`, returns), `closest('a')`
   lets Open navigate, group-header/chips/bulk handled, then card toggle guarded by
   `closest('a, button')` + non-empty `getSelection()`. Reproduced via CDP: Enter on the Open link
   and on the Delete button does **not** expand the card; click on the Open link does not toggle;
   click on a card with 7 chars selected does **not** toggle (`selLen=7, expandedAfterClick=false`).
   Keyboard parity handler (`:256-262`) carries the same `closest('a, button')` guard; Enter on a
   focused card toggles `aria-expanded` false→true. `expanded.png` shows path + Open/Delete revealed,
   siblings collapsed.
3. **Search/filter + empty-group hiding — MET.** `applyFilter()` (`:194-215`) substring-matches
   `data-title/project/path`, ANDs the status chip, hides empty `.session` then `.project`.
   `search-filtered.png`: "pricing" → only the marketing-site match; the empty "blog 2" project AND
   the empty `q3` session sub-group are both hidden. CDP: "Has notes" chip → only feedback/resolved
   visible; "Done" → 0 visible + `#noresults` shown.
4. **Collapsible groups + session memory — MET.** Per-project `.group-header` (chevron + count
   badge); `setGroup()` (`:217-221`) toggles `.collapsed` and mutates a module-level
   `const collapsed = new Set()` (`:140`, **not** localStorage); `load()` re-applies it (`:184-189`)
   so collapse survives the delete-triggered re-render. `group-collapsed.png`: "blog 2" collapsed
   (▸ + count 12 visible, body hidden), other group open. Expand-all/Collapse-all loop the sections
   (`:246-247`).
5. **Preserved functionality — MET (the load-bearing check, reproduced end-to-end).**
   - **Delete:** CDP-clicked the throwaway's `.btn.del[data-id]` with `confirm` stubbed true → card
     count 9→8, gone from the DOM **and** from `/api/reviews` (`grep -c` → 0).
   - **Open:** `<a class="btn open" href="/review/{id}">` (`:126`); href sampled `/review/3c6e5606b4`.
   - **Version:** after two `PUT /source`, the card renders `<span class="badge rev">v2</span>`
     (`:121`); CDP read the rendered `.rev` text = `v2`.
   - **Notes:** after `POST /feedback` with 2 notes / 1 addressed, the `.badge` renders
     `2 notes · 1 done` via the reused `noteLabel()` (`:108-112`), and the `.pill.feedback` shows.
6. **Theme both panes — MET.** `light-pane.png` is genuinely light (cream `--bg`, dark text),
   `dark-pane.png` genuinely dark — pane-adaptive `:root` + `@media (prefers-color-scheme: dark)`
   kept (`:8-9`), not dark-only. No new literal color on a token surface: the one literal added is
   `.pill.feedback{color:#7a5b00...}` with a dark override `#f0cb5a` (`:55-56`) — both legible; chip
   "active" reuses `--accent` (`:21`). Diff confirms no other literal added.
7. **Hygiene — MET.** Diff = `dashboard.html` + process only; `py_compile` OK; both feature commits
   (`b0ebdbc`, `1ec61e8`) carry the ticket ID and the `Co-Authored-By: Claude` trailer; no
   descendant render-smoke selectors.

## Findings

No **[BLOCKER]**.

- **[NIT]** `docs/.../sprint-09-render-evidence-2026-06-19/README.md:12` and the ticket Work log
  describe `wide-5col.png` as showing the grid at "5 columns" — accurate, but the downscaled PNG
  reads as 4 at a glance; the claim is only trustworthy because the seed run-1 had exactly 8 cards
  wrapping 5+3. Independently re-measured: 5 columns confirmed at 1680/2560px. No action required;
  noting because a future reader eyeballing the PNG could doubt it.
- **[NIT]** `dashboard.html:251` `String(window.getSelection()).length` treats any document-wide
  selection (e.g. left over from a prior drag elsewhere on the page) as "suppress toggle." Matches
  the plan's Fork-1 decision and is the conventional trade-off; flagging only that it is page-global,
  not card-scoped. No change needed for this sprint.

## Resolution log

- **2026-06-19 — Verdict PASS, 0 blockers / 0 shoulds / 2 NITs (both accepted, no change).**
  NIT-1 (`wide-5col.png` reads as 4 columns in the downscaled PNG): the critic re-measured the live
  layout via CDP `getBoundingClientRect` and confirmed **5 columns** at 1680px (and the cap holds — 5
  at 1920/2560); the screenshot/README claim is accurate, nothing to fix. NIT-2 (the text-selection
  guard is page-global, not card-scoped): matches the plan's Fork-1 decision; accepted. Sprint-09
  closed at G7.