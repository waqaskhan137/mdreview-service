---
review_of: epics/dashboard-density-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G1 independent re-review (round 2) — dashboard-density plan

Round-1 was PASS-WITH-CONDITIONS (0 BLOCKER, 2 SHOULD, 2 NIT). All four are genuinely fixed,
verified against the live `dashboard.html` and recomputed arithmetic — not taken on the resolution
log's word. No new blocker introduced. **G1 passes.**

- **SHOULD-1 (verification widths)** — FIXED. Recomputed: content `2000−48=1952`, 2-card
  `(1952−8)/2 = 972`, 6-card `(1952−5×8)/6 = 318.67 ≈ 319`. The Verification recipe (`:319-341`)
  asserts exactly 972/319, with the formula stated. The stale 1071/350 now appear only in the
  Fork-1 exploration table (`:117-121`), explicitly labeled cap-2200/gap-10 and pointing to the
  shipped numbers. 560 and `.wrap`=2000 correct and unchanged. The 1440px line was also corrected
  (`692` against the 1392 content width — checks out).
- **SHOULD-2 (per-session unit + seed)** — FIXED. Fill/cap unit reframed to the **per-session grid**
  in the summary (`:18`), product goal (`:31`), Core principle (`:59-66`), and Fork 1 (`:105-108`),
  matching the real render (`dashboard.html:177-178`, `.grid` per session, `.card` a direct child —
  verified). Two-session single-card project ("multisess", `run-1`+`run-2`) is in the seed
  (`:297-298`), with a CDP assertion that each session row caps ≈560px (`:334-336`) and a
  `multisession.png` screenshot (`:350-353`). render-smoke counts bumped (`.grid >=5`, `.card >=11`).
- **NIT (`:only-child` ignores `.is-hidden`)** — ACTIONED. Filter-interaction note in Fork 1
  (`:148-154`) correctly states `applyFilter()` uses `display:none` (`dashboard.html:201`, confirmed),
  so a filtered-to-one grid keeps >1 child → no cap → lone visible card goes **full-width**, named as
  an acceptable transient state.
- **NIT (dark-pane enum re-check)** — ACTIONED. Key constraint (`:236-238`) now mandates a live
  computed-`body`-bg assertion in the close review instead of inheriting the `rgb(17,17,17)` comment.
- **NIT (stale `.grid` comment)** — Confirmed still the planned MR-032 edit (`:199-201`, risk-table
  row), extended to describe the per-session cap. The stale comment correctly still lives in the code
  (`dashboard.html:44`), to be fixed by the ticket, not the plan.

## Residual (non-gating)
- The Fork-1 candidate table (`:117-119`) keeps `350` in the 6-card column for candidates (a)/(b)/(c)
  as the cap-2200 exploration constant. It is labeled exploration and is purely a relative comparison,
  so it does not mislead a verifier — but if the table is ever lifted out of context, that `350`
  reads as a target. Cosmetic; not a condition.

## Resolution log
- SHOULD-1 — FIXED (arithmetic recomputed independently: 972 / 318.67 confirmed; exploration numbers
  quarantined to labeled Fork tables).
- SHOULD-2 — FIXED (per-session framing in all four cited locations; render structure verified at
  `dashboard.html:177-178`; multisess seed + CDP assertion + screenshot present).
- NIT `:only-child`/`.is-hidden` — ACTIONED (mechanism verified at `dashboard.html:201,50`).
- NIT dark-pane enum — ACTIONED (live re-check mandated).
- NIT stale comment — ACTIONED (planned ticket edit, per-session wording).

Verdict: **PASS**. G1 passes; the plan is clear to proceed to ticketing (MR-032, sprint-10).
