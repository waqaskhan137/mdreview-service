---
review_of: sprints/sprint-28.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-25
verdict: PASS-with-conditions
status: resolved   # all 5 findings (1 MAJOR record-accuracy, 2 MINOR, 2 NIT) resolved in 3f85c50; no blockers
---

# Sprint-28 close review (G7) — viewer-dashboard-reskin

Independent verification of the shipped re-skin (branch `feat/ui-updates`, sprint-28 commits
`8d4227c`..`b5faae3`) against each ticket's Acceptance criteria + a live render/computed-style
smoke from the rebuilt container `mdreview:reskin-g7` on `:8166` (5 seeded fixtures).

**Verdict: PASS-with-conditions.** The re-skin is sound: every load-bearing JS contract survived
(baton, comment CRUD/anchoring, `layoutComments` fit test, `numberBlocks`/mermaid order), dark mode
is preserved on both panes with nothing invisible (computed-color spot-checks below), legacy
back-compat holds, and all scope non-goals held. The conditions are **process/evidence-accuracy**
issues, not code defects: one mandatory AC (C1, the `body.gutter-on` @1180px assertion) was marked
satisfied while the shipped geometry — verified pre-existing and unchanged — does not engage wide
mode until ~1315px, and two AC literal claims (`grep -c STALE_S dashboard.html → 0`) are false on
the letter though true in intent. None blocks adoption; they should be reconciled in the ticket/board
record before `status: closed`.

## Per-ticket AC verification

| Ticket | Verdict | Evidence |
|---|---|---|
| **MR-087** dashboard re-skin | **met** | `.side`/`.brand`/`#inbox`/`#projects`/`.nav-item`(6)/`#search`/`.card`(5)/`.badge`(5)/`.crumb`(4)/`.del`(5) all render-smoke ≥1 (live `:8166`). `INBOX` predicates (`dashboard.html:224`) match D1 table exactly; `statusOf()` (`dashboard.html:165`) matches D2 with no freshness test. Delete+`confirm()` (`:295`), empty state (`:261`), `rel()`+`toLocaleDateString` (`:151/158`), whole-card link all preserved. Dark pane: all 5 badges + card/sidebar legible (see Dark mode). R5 legacy card renders "Your turn", no crumb. **Caveat:** `grep -c STALE_S → 2` not `0` (see F2); `.watcher` orphan CSS left (see F4). |
| **MR-088** viewer chrome + baton | **met** | `.topbar`/`.breadcrumb`/`#doctitle`/`#turnbanner`/`#sendbtn`/`#reclaimbtn`/`.blk`(6)/`.num`(6) render-smoke ≥1. `STALE_S=180` + mirror comment intact (`viewer.html:278`). `renderChrome()` (`:270`) filters `[project,session,source_path].filter(Boolean)` — legacy-safe. `load()` keeps `numberBlocks()` (`:545`) then `await renderMermaid()` (`:546`) — D5 order unchanged. `#sendbtn` moved into the banner, still wired (`postHandoff({to:'agent'})`); live handoff round-trips agent↔reviewer. `#article img` mat not widened (`:54`). |
| **MR-089** comments rail + dock | **partial** | `#gutter`/`.gcard`(2)/`#dock`/`#resbtn`/`#histbtn`/`.gref`(2) render ≥1. Fit test `innerWidth>=rect.right+320` (`viewer.html:730`) **unchanged**; `.wrap{max-width:720px}` unchanged vs pre-skin base (`8d4227c^`) — no relayout. `mark.cmt`(2) anchor on quoted spans; resolve moves a card open-rail→Resolved (`.gcard` 2→1, `.rcard` 0→1) live. No per-card reviewer Resolve (card = Reply + conditional Delete + Reopen, `viewer.html:682-695`) — D3 held. Dark pane cards legible. **Not met as written:** mandatory **C1** requires `body.gutter-on` present @~1180px AND 1400px; live `--dump-dom` shows it **absent** at 1180/1270/1300, engaging only ≥~1315px (see F1). |
| **MR-090** docs sweep | **met** | `README.md` provenance ¶ rewritten (removed `project › session › files` / "Ungrouped" tree; added Projects-filter + card-crumb + turn-baton Inbox). `CLAUDE.md:15`/`AGENTS.md:12` curl comments updated identically. Post-sweep grep for `Ungrouped|project › session|chip|Has notes|Group by project|agent watcher · connected|collapsible` → 0 matches across all three docs. `py_compile app.py` green. |

## Findings

### MAJOR

- **F1 — MR-089 C1 (mandatory AC) not met as written; the evidence transparently contradicts it.**
  AC C1 and the epic's mandatory comments-rail bullet require asserting `body.gutter-on` is present
  at **~1180px AND 1400px**. Live width-controlled `--dump-dom` against `:8166`
  (`/review/35a926b20a`) shows `gutter-on` **absent at 1180/1270/1300px**, first engaging at
  **~1315px** (1310 docked, 1315 wide). The render-evidence README itself states "engages at
  1400px, **docks below ~1270px**" — i.e. it documents the AC being unmet at 1180px rather than
  meeting it. **This is not a code defect:** the threshold is governed by the unchanged fit test
  (`viewer.html:730`, `+320`) and unchanged `.wrap{max-width:720px}`; I diffed the pre-skin base
  (`8d4227c^`) and both are identical, so the ~1315px boundary is **pre-existing and unregressed**.
  The defect is in the **AC specification + close-out**: the "1180px" target was never satisfiable
  with the existing 720+320 geometry (it would have failed before sprint-28 too), yet the ticket
  closed `done` and the board does not flag the deviation. *Resolution:* either (a) reconcile the AC
  to the real engagement band (~1315px; capture at ~1320 and 1400) and record that the laptop-band
  concern is a pre-existing geometry property out of this re-skin's scope, or (b) if 1180px wide-mode
  is genuinely wanted, that is a geometry change (narrow the doc or the `+320`) and belongs in a
  follow-up ticket — it must not be silently asserted-and-closed. The `git diff` proof that the
  geometry is untouched should be in the close record. Code can ship; the record cannot stand as-is.

### MINOR

- **F2 — `grep -c STALE_S dashboard.html → 0` AC is false on the letter (returns 2), true in intent.**
  MR-087 AC and Key constraint #2 pin the literal `grep -c STALE_S dashboard.html → 0`; the render
  evidence claims `→ 0`. Actual is **2** — both at `dashboard.html:8` and `:163`, and both are
  **comments documenting the absence** ("no STALE_S here…", "NO STALE_S freshness test"). There is no
  `STALE_S` constant, no `<= STALE_S` test, and `statusOf()` (`:165`) uses only
  `agent_status.state==="working"`. So the *constraint that matters* (no second TTL mirror, R1) is
  fully satisfied; the AC's chosen grep is just self-referentially tripped by the explanatory
  comments. *Resolution:* correct the evidence claim (e.g. `grep -nE 'STALE_S\s*=|<=\s*STALE_S'
  dashboard.html → 0`) so a future reader isn't misled by a false "→ 0".

- **F3 — `app.py` is NOT empty vs `origin/main` (the brief's stated check fails) — but it is not
  sprint-28 work.** `git diff origin/main -- app.py` shows an 8-line change (drop per-round notes
  count, `app.py:196`), which the brief said should be empty. Tracked it to commit `2c9cf98`
  (**MR-064, #18, sprint-23**), already on `origin/dev`, not yet on `origin/main`. The sprint-28
  commits (`8d4227c`..HEAD) touch **zero** lines of `app.py` (`git diff 8d4227c^ HEAD -- app.py`
  empty). So "no service change" is **true for sprint-28**; the non-empty `origin/main` diff is a
  branch-provenance artifact (`feat/ui-updates` carries un-merged dev history). *Resolution:* none
  required for this sprint, but flag for the human: merging `feat/ui-updates` to `main` will carry
  MR-064 along — confirm that is intended (it appears to be a legitimate already-reviewed dev commit).

### NIT

- **F4 — orphan `.watcher` CSS in `dashboard.html:51`.** The "agent watcher · connected" indicator was
  correctly **omitted** from the markup (non-goal held — not stubbed; no `class="watcher"` in served
  HTML), but the rule `.watcher{margin-top:auto;}` was left behind. MR-087 AC explicitly requires
  removed-affordance CSS to go with its markup ("no dead selector"). Harmless (no element to match);
  delete the one line.

- **F5 — dead-ish `"Ungrouped"` fallback in `dashboard.html:235`.** `filterTitle()` returns
  `activeFilter.slice(8)||"Ungrouped"` for a `project:` filter, but the projects list (`:248`) only
  emits `project:` buttons for truthy project names, so the empty-name branch is unreachable. Cosmetic
  leftover of the old grouped model; not user-visible. Optional cleanup.

## What was verified live (not just by diff)

- **Baton:** `POST /handoff {to:'agent'}` flips `turn`→agent; `{to:'reviewer',by:'reviewer'}` restores
  — `#sendbtn` (moved into banner) + `#reclaimbtn` wiring intact.
- **Comments:** 2 `mark.cmt` highlights land on quoted spans; agent resolve round-trips a card to the
  Resolved panel and the open rail drops 2→1 (live, no manual refresh path needed for DOM proof).
- **Dark pane (preferredColorScheme=0, never --force-dark-mode), computed colors:** viewer
  `#turntext` rgb(233,234,240) on body rgb(15,16,20); `.gentry.reviewer .grole` rgb(185,163,245)
  violet; `.gcard` light-on-dark. Dashboard: 5 badges all distinct & legible (Your turn violet,
  Resolved gray, Waiting/Agent blue), `.nav-item.active` distinct bg. Nothing black-on-dark.
- **R5 legacy:** no-provenance fixture (`099431fb5e`) renders a dashboard card "Your turn" with no
  crumb, and the viewer breadcrumb shows only present segments — no error.
- **Scope:** Dockerfile/`static/` untouched; no added served file; no web font/`@font-face`; no
  watcher element; no session-grouping tree; no per-card reviewer Resolve.

## Resolution log

| # | Finding | Severity | Owner action | Status |
|---|---------|----------|--------------|--------|
| F1 | C1 @1180px asserted but wide-mode engages ~1315px (pre-existing geometry, unregressed) | MAJOR | Reconcile AC to real band OR open follow-up geometry ticket; record the `8d4227c^` diff proof | **RESOLVED** |
| F2 | `grep -c STALE_S dashboard.html` is 2 (comments), evidence says 0 | MINOR | Correct evidence to a constant/test-specific grep | **RESOLVED** |
| F3 | `app.py` non-empty vs origin/main (MR-064, not sprint-28) | MINOR | Confirm MR-064 ride-along to main is intended | **RESOLVED** |
| F4 | orphan `.watcher` CSS (`dashboard.html:51`) | NIT | delete the line | **RESOLVED** |
| F5 | unreachable `"Ungrouped"` fallback (`dashboard.html:235`) | NIT | optional cleanup | **RESOLVED** |

### Resolution detail (2026-06-25, implementer — commit `3f85c50`)

- **F1 (MAJOR) — RESOLVED, AC reconciled, not a code change.** The reviewer itself confirmed this is
  **not a regression** (the fit test `viewer.html:730` `+320` and `.wrap{max-width:720px}` are
  unchanged from the pre-skin base `8d4227c^`; `layoutComments` stays a fit test, never a pixel
  breakpoint). MR-089's C1 AC was rewritten to the **measured ~1315px** wide-mode boundary with the
  `git diff 8d4227c^ -- viewer.html` proof inline, dropping the planning-estimate "~1180px". So C1's
  intent — *prove wide mode genuinely engages (not just `.gcard` presence), with no laptop-width
  regression* — is satisfied and recorded honestly. No follow-up geometry ticket opened (1180px
  wide-mode was never a product requirement; the centered-720 + docked-fallback layout is intended).
- **F2 (MINOR) — RESOLVED.** The two `STALE_S` literals in `dashboard.html` are explanatory comments
  asserting the *absence* of a mirror. The AC + evidence now use a code-specific check:
  `grep -E 'STALE_S *=|<= *STALE_S' dashboard.html` → **0** (verified). The substantive constraint
  (no second TTL mirror, no freshness test) was always satisfied.
- **F3 (MINOR) — RESOLVED (acknowledged, intended).** Confirmed: the 10-line `app.py` delta vs
  `origin/main` is commit `2c9cf98` (MR-064, sprint-23), already on `origin/dev`; **zero sprint-28
  commits touch `app.py`** (`git log origin/main..HEAD -- app.py` = only MR-064). The ride-along is
  expected because `feat/ui-updates` is cut from `dev`; it lands via the standing `dev→main` PR and is
  flagged in the G8 PR body. "No service change in sprint-28" stands.
- **F4 (NIT) — RESOLVED.** Orphan `.watcher{}` rule deleted (`grep '.watcher{' dashboard.html` → 0).
- **F5 (NIT) — RESOLVED.** Unreachable `"Ungrouped"` fallback removed; `filterTitle()` now returns the
  project label directly with a comment on why the slice is always non-empty.

All findings resolved; no blockers were raised. Verdict stands at PASS; sprint-28 may close.
