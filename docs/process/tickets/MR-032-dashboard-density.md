---
id: MR-032
title: Dashboard density — auto-fit row-fill + lone-card :has() cap + raise width cap to 2000px + trim whitespace
status: done
layer: ui
priority: P1
sprint: sprint-10
epic: dashboard-density
depends_on: []
branch: dev
created: 2026-06-19
updated: 2026-06-19
---

## Goal

Remove the remaining wasted space on the dashboard (follow-up to MR-031): sparse project rows leave a
big empty right gutter, there's too much gap under the search bar, and the 1600px cap floats the
content on wide screens. `dashboard.html` only — no service/API/`viewer.html` change; all existing
behavior preserved.

## Acceptance criteria

- [ ] **Row-fill (`auto-fill` → `auto-fit`).** `.grid` becomes
      `grid-template-columns:repeat(auto-fit,minmax(280px,1fr))` (was `auto-fill`), `gap:8px` (was
      10px). A session grid with 2+ cards now **fills the row** (no phantom empty tracks / right
      gutter).
- [ ] **Lone-card cap (the "sensible max").** Add `.grid:has(.card:only-child){grid-template-columns:
      minmax(280px,560px);}` so a **single-card session grid** caps that card at ~560px (≈2 columns)
      instead of stretching it to the full row width. The fill/cap unit is the **per-session grid**
      (`section.project > .group-body > .session > .grid > .card[]`), and `.card` is a direct child of
      `.grid` so `:only-child` matches. `:has()` degrades benignly (no support → lone card full-span,
      which the brief allows). Note: a search-filter that hides all-but-one card leaves >1 child, so
      the cap doesn't apply (filtered-to-one goes full-width, not narrow) — acceptable transient.
- [ ] **Width cap raised 1600 → 2000px** on **both** `.wrap` and `.bar-inner` (kept in lockstep so the
      search bar stays aligned to the content edge). Edge-to-edge fill ≤2000px; ≤1920 monitors show no
      visible cap; 2560 keeps a modest centred reading margin (not a floating 1600 column). Removing the
      cap entirely (true full-bleed for 4K) is a noted out-of-epic follow-up.
- [ ] **Tighten the top gap + whitespace (density table):**
      `.sub` margin `2px 0 18px → 2px 0 8px`; `.wrap` padding `16px 24px 96px → 10px 24px 64px`
      (top 16→10 pulls the first group under the bar; keep 24px side gutters; 96→64 bottom);
      `.project` margin `0 0 14px → 0 0 10px`; `.session` margin `8px 0 0 → 6px 0 0`;
      `.session>h3` margin `6px 0 6px → 4px 0 5px`; `.group-header` padding `5px 4px → 4px 4px`.
      Card interior (`padding:8px 10px`, `radius:8px`) stays as MR-031 set it (already halved). Still
      legible, not cramped.
- [ ] **Update the stale `.grid` comment** (the MR-031 "columns top out at 5" note) to describe
      auto-fit + the per-session lone-card cap + the 2000px ceiling.
- [ ] **Preserved functionality (re-verified, not assumed):** search/filter, status chips, card +
      group collapse/expand, Expand all / Collapse all, Open / Delete (throwaway) / version badge /
      notes-count, pane-adaptive theme — all still work.
- [ ] **No service/infra change.** `app.py`/routes/`Dockerfile` untouched; `python3 -m py_compile
      app.py` still passes.
- [ ] **GATING render evidence (rebuilt throwaway :8138, CDP via Node built-in WebSocket):**
      `render-smoke.sh '/' '.grid' '.card' '#search' '.group-header'` → all ok (flat selectors).
      Seed includes a **1-card project**, a **2-card session**, a **6-card session**, and a
      **two-session single-card project** ("multisess": run-1 1 card + run-2 1 card). Measured widths
      at 2560px (cap-2000/gap-8, content `2000−48=1952`, each `(1952−(N−1)×8)/N`): **2-card ≈972px**,
      **6-card ≈319px**, **lone-card session row ≈560px**. Screenshots under
      `reviews/sprint-10-render-evidence-2026-06-19/`: the tightened **top gap** (first header just
      under the bar), a **sparse project filling the row**, `multisession.png` (each single-card row
      capped), a **wide-viewport** edge-to-edge shot, and **both panes** (dark via
      `--blink-settings=preferredColorScheme=0` / CDP `Emulation.setEmulatedMedia`, never
      `--force-dark-mode`; re-check the dark-pane computed `body` background is the dark token).
- [ ] Local validation: `python3 -m py_compile app.py`; `docker build`; the render-smoke + screenshot
      set + the preserve-functionality re-check.

## Notes / context

- Epic plan: `epics/dashboard-density-plan.md` — Fork 1 (lone-card `:has()` cap, measured table),
  Fork 2 (cap 1600→2000, measured), Fork 3 (density table), Verification (the cap-2000/gap-8 width
  formula + the multisess seed). The cap-2200 numbers in the Fork tables are labeled *exploration*;
  the binding numbers are in Verification.
- This overrides the MR-031 A4 1600px cap (the user chose edge-to-edge).
- Footguns: a 200 is not a render (screenshots are the proof); flat render-smoke selectors; live
  instance :8139 — throwaway :8138, never `docker compose`; delete test on a throwaway review only.

## Work log

- `2026-06-19` — **Shipped within a direct, out-of-cycle dashboard redesign** (commit
  `0f44c1b`). Mid-implementation, the user gave an **explicit "make the change without the cycle"**
  exception for a larger redesign: replace the project-grouped default with **one flat continuous
  grid** (auto-fill `minmax(240px,1fr)`, sorted by latest activity, project-as-inline-tag, zero
  gutters), with a **"Group by project" toggle** that switches to grouped sections. MR-032's density
  CSS is **incorporated into the grouped mode** (`#list.grouped .grid` → `auto-fit minmax(280px,1fr)`
  + `.grid:has(.card:only-child){…560px}`) and the trimmed page/group spacing + `2000px` cap apply
  globally. So MR-032's deliverable shipped; the flat-grid redesign on top did **not** go through
  G1/G7 (the user's exception).
- Files: `dashboard.html`.

## Validation

- `2026-06-19` — `python3 -m py_compile app.py` OK; `docker build` OK; CDP-validated from a rebuilt
  throwaway container on :8138: flat default = 1 grid / 13 cards / 13 project tags; expand reveals
  path + actions; group-by toggle → 5 sections + Expand/Collapse-all; search filters; both panes
  legible; Delete removes from DOM **and** `/api/reviews`; notes ("2 notes · 1 done") + version
  ("v1") badges render. **Not gated by an independent G7 staff-critic review** (out-of-cycle per
  user request).

## Follow-ups

- True full-bleed (remove the 2000px cap) for 4K monitors — one-line change if the user wants it.
