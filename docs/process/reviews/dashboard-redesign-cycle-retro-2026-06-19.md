---
retro_of: sprint-09 / dashboard-redesign cycle (G0–G8)
reviewer: cycle-retrospective
timestamp: 2026-06-19
scope: the RUN (plan → G1 → tickets → sprint → implement → G7 → ship), not the feature
---

# Cycle retro — dashboard-redesign (sprint-09)

**Verdict: smooth.** A prescriptive single-file `ui` brief ran clean through the full cycle: G1
PASS-WITH-CONDITIONS (1 SHOULD + 6 NIT) → r2 PASS, G7 first-pass PASS (0 blocker / 0 should / 2
NIT), one ticket, zero carry-overs, zero wrong load-bearing assumptions. The accumulated
planner discipline did real work here; the one genuine recurrence is a verification-recipe lesson
that lives in the wrong file.

## What went well (load-bearing)

- **The planner pre-measured the two render-observable forks**, so G1 had nothing to litigate on
  them: column overshoot (the `minmax(280px,1fr)` 4/4/5/6/8 table → the `max-width:1600px` 5-col
  cap, with the ceiling tied to `5×280 + 4×10 + 2×24 ≈ 1488` math) and the ~60px collapsed-card
  height. The critic *reproduced* both and ruled them correct calls, not creep. This is the
  "measure forks; don't argue them" Method bullet paying off — the alternative is a prose argument
  that surfaces at G4.
- **The pane-adaptive theme finding was caught at plan time, not ship time.** The brief said "keep
  the dark theme"; the planner verified `dashboard.html` is actually pane-adaptive (`:root` +
  `@media`, not dark-only) and made A1 "keep both panes" load-bearing. A naive reading would have
  collapsed to dark-only and silently regressed light-theme users under the brief's own
  "preserve all functionality" clause.
- **CDP measurement caught a reviewer error, not just an implementer one.** At G7 the critic
  re-measured the live layout with `getBoundingClientRect` over CDP, caught its *own* downscaled-PNG
  miscount (read 4 cols, measured 5), and retracted it. The screenshot alone would have left a
  false NIT standing; measuring the live layout is what made the evidence trustworthy.

## Top suggestions (prioritized)

1. **Put the dark-pane capture flag where the planner reads it when WRITING verification — not only
   in the close reference.** `[agent]` (mdreview-planner) — *highest value, a confirmed
   recurrence.* The plan's Verification step 4d shipped `--force-dark-mode` again, and the G1 SHOULD
   was "this repo already rejected this flag on record" (`theme-awareness-plan-review-2026-06-18.md`).
   The correct flag (`--blink-settings=preferredColorScheme=0/1`) currently lives only in
   `.claude/skills/feature-cycle/references/04-close-and-ship.md` — read at G7, **after** the
   planner has already authored the wrong recipe. The planner's footgun list and Method bullets name
   the dark-pane `getComputedStyle` *check* (Method bullet 2, hand-derived-asset) but never the
   *capture flag*. Add a one-line rail to the planner's footguns/Method: "for a pane-adaptive page,
   emulate panes with `--blink-settings=preferredColorScheme=0/1`; never `--force-dark-mode`
   (auto-invert) and never a no-flag shot (bare headless resolves dark by default)." That moves the
   lesson upstream of where the mistake is made and would have made this a 0-condition G1.

2. **Promote the CDP interaction-evidence pattern to a checked-in `scripts/` helper.** `[feature]`
   (backlog ticket) — *recurring across UI cycles, not a one-off.* This cycle and sprint-08 both
   hand-rolled "drive Chrome over CDP (Node built-in WebSocket) to click expand/collapse/delete and
   measure column counts + computed styles" because `render-smoke.sh` proves static DOM nodes and a
   screenshot proves first-paint — neither proves an *interaction* state or a *measured* layout. The
   three interaction-driven screenshots (`expanded`/`search-filtered`/`group-collapsed`) are
   currently "captured by hand, file-existence checked at G7" precisely because there is no tool. A
   small `scripts/cdp-drive.js` (or `.sh` wrapper) that loads a URL, runs a click script, emulates a
   pane, and dumps `getBoundingClientRect`/`getComputedStyle` would turn "the implementer did it this
   once" into a reusable rail and make those three shots gate-verifiable instead of trust-based. Scope
   it as a backlog ticket, not a process mandate — let the next UI cycle pull it.

3. **Full G0–G8 on a fully-specified single-file UI rewrite is near the proportionality line — name
   the explicit "lightweight UI" lane.** `[process]` — *balanced read, not a complaint.* The user
   handed an exact grid value and exact behaviors and said "show me the result"; the orchestrator
   asked and the user chose the full cycle. The cycle earned its keep on three concrete things — the
   column-overshoot cap (the brief's literal value overshoots its own "3–5 columns" intent on 1080p),
   the pane-adaptive A1 finding, and the both-pane verification SHOULD — none of which a direct build
   would necessarily have caught. But the ticket *was* the plan restated (one file, one slice, no
   decomposition value), and the two G1 rounds + r2 re-grep were ceremony for a plan whose only live
   defect was a one-line flag. Worth a short `docs/process/` note: for a prescriptive single-file
   `ui` brief, G1 may be a **single focused pass on forks + verification recipe** (not a full
   re-decomposition), and a clean r1 with only NITs need not always spawn an r2 re-grep. Keep the
   gates; right-size the effort.

## Metrics

- **G1 rounds:** 2 (r1 PASS-WITH-CONDITIONS: 1 SHOULD + 6 NIT; r2 PASS).
- **G7 rounds:** 1 (first-pass PASS: 0 blocker / 0 should / 2 NIT, both accepted no-change).
- **Tickets:** 1 shipped (MR-031), 0 carried.
- **Parks / BLOCKED:** 0.
- **Wrong load-bearing assumptions:** 0 (A1 pane-adaptive, A3 notes-count, A4 1600px-cap all held;
  critic reproduced and confirmed each).
- **Cycle size:** 6 commits; 1 feature commit (`b0ebdbc`); `dashboard.html` +178/−50.
- **Recurring-class friction:** 1 — the `--force-dark-mode` verification-flag mistake recurred in
  the plan despite being fixed in the close reference a cycle earlier (suggestion 1).
