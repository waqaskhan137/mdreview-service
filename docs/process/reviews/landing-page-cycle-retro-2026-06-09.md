---
review_of: the landing-page feature-cycle run (sprint-05)
gate: none (Phase 10 — cycle retrospective, suggestions only)
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-09 (Europe/London)
verdict: smooth-run-with-recurring-friction
status: recorded
---

# Cycle Retrospective — landing-page (sprint-05)

**Verdict:** Smooth run with one foreseen-and-honored human dependency. 1/2 tickets shipped
`done`, MR-020 cleanly parked on a user-only DNS record (carried, not failed), G1 one revision
round, G7 PASS first pass. The friction is concentrated in two **recurring** classes the prior
cycle already named.

## What went well (load-bearing)

- **Plan pre-resolution paid off.** The pinned worktree+rsync publish sequence, the `http.server`
  G4 target, and screenshot-first demo all executed without surprises (sprint Notes; G7 F5
  reproduced byte-identical `gh-pages` parity). One G1 revision round vs two in prior cycles.
- **Honest park accounting.** MR-020 shipped everything automatable (gh-pages published
  `a528282`, Pages enabled, edge-verified via `--resolve`), recorded an exact resume sequence,
  and withheld the README URL so it never asserts a 404ing URL (G7 F8). G7 PASS first pass, zero
  fix commits.
- **The brief-via-mdreview loop** (review `fccf5afec9`, two rounds: custom domain, then concrete
  subdomain) dogfooded the product to harden the brief before G0 — a genuinely good pattern worth
  keeping.

## Top suggestions (prioritized; suggest-only)

1. **`[agent]` Give `mdreview-planner` a standing "verify every capability claim against the file
   before writing it" rail.** Second consecutive cycle where G1 r1 found a claims-vs-reality
   defect: mcp-wrapper had the phantom enforcement claim (MR-012 class); this cycle F1 (BLOCKER)
   was the planner asserting `scripts/render-smoke.sh` has a "Chrome screenshot path" — fictional;
   the script only `--dump-dom`s (G1 review F1, confirmed in r2 against
   `scripts/render-smoke.sh:54-114`). Broaden the mcp-wrapper retro's phantom-enforcement
   self-audit to **any capability claim about a script/tool/command** — the planner must open the
   cited file and confirm the capability exists before writing it.

2. **`[skill]` Add a "tickets with known user-only steps" pattern to the cycle.** MR-020's DNS
   record was foreseeable as user-only **at plan time** (the plan's BLOCKER-FOR-HUMAN, Decisions
   3/4, and Risks all named it), yet the human ask happened mid-sprint (AskUserQuestion -> "can't
   right now" -> blocked -> carry). Pausing was the right call, but the skill has no pattern for
   it. Suggest: when the plan flags a user-only step, **front-load the ask at sprint open (G6)**,
   or split the human-gated tail into its own non-committed ticket so the sprint's committed set
   is fully autonomous.

3. **`[skill]` Generalize the G7 close-review smoke instruction to not assume compose state
   matches the live instance.** `references/04-close-and-ship.md` (Phase 6 step 1) says
   `docker compose up -d --build` unconditionally; the orchestrator had to deviate because the
   compose file maps 8137 but the user's live `mdreview` container serves 8139 — compose-up would
   have recreated the live instance the MCP server points at (G7 F6; sprint Notes).
   `references/03-implement.md` already has the `lsof` guard — mirror it into Phase 6/8: prefer a
   throwaway `docker build` + `docker run` on a free port when a live instance is detected.

4. **`[skill]`/`[process]` Generalize the G7 per-page render trigger instead of routing around it
   case-by-case.** Second cycle the G7 row's product-page list
   (`viewer.html`/`dashboard.html`/`static/**`) did not name the touched surface — here `site/`
   (G1 F2; G7 Summary). The plan correctly routed the render obligation into MR-019's own G4 AC
   (robust), but that is a per-epic workaround the planner must re-derive every time a new surface
   appears. Consider a generalized trigger ("any human-facing rendered surface this sprint
   touched, served from wherever it lives").

5. **`[feature]` Add a cheap "could this verification command ever succeed?" check to plan
   verification blocks.** The plan's publish-verification block included
   `curl -s https://…/CNAME` expecting the CNAME contents — but GitHub Pages *consumes* the CNAME
   file and never serves it, so that command 404s by design (MR-020 Work log "Runbook
   correction"). Caught at implement, replaced with a `gh api … --jq .cname` check. Same class as
   F1's fictional capability, in a verification command; folds into suggestion 1 if that rail
   covers commands the plan *prescribes*, not just capabilities it *claims*.

## Metrics

- **G1 rounds:** 2 (r1 PASS-WITH-FIXES — 1 BLOCKER F1 + 2 MAJOR + 4 MINOR/NIT; r2 PASS). One
  planner revision round.
- **G7 rounds:** 1 (PASS first pass; F7 MINOR carried to MR-021, F8 informational; zero fix
  commits).
- **Tickets:** 1 shipped `done` (MR-019) / 1 carried (MR-020, `blocked` on user DNS) — MR-021
  correctly never committed (backlog, not-ready).
- **Parks:** 1 (MR-020 DNS — foreseeable at plan time, explicitly carried per the Blocking rule).
- **Wrong load-bearing assumptions:** 1 — the fictional `render-smoke.sh` screenshot capability
  (F1, BLOCKER, overturned at G1). The repo-owner-vs-domain-owner BLOCKER-FOR-HUMAN was answered
  from conversation context (the user offered the domain), not a wrong assumption.

## Artifacts

- Plan: `epics/landing-page-plan.md`; G1: `reviews/landing-page-plan-review-2026-06-09.md` +
  `-r2.md`; G7: `reviews/sprint-05-close-review-2026-06-09.md`; sprint:
  `sprints/sprint-05.md`; parked ticket: `tickets/MR-020-gh-pages-publish.md`; prior retro:
  `reviews/mcp-wrapper-cycle-retro-2026-06-09.md`.
- Skill files targeted by suggestions 2-3:
  `.claude/skills/feature-cycle/references/04-close-and-ship.md` (unconditional compose-up) and
  `references/03-implement.md` (the existing `lsof` guard to mirror).
