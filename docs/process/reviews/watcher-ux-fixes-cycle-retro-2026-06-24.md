---
review_of: epics/watcher-ux-fixes-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: Smooth — clean 2-ticket fixes batch, G1 1 round / G7 1 round, 0 parks, 0 carry-overs; the owner-eyeballed stash restored faithfully and re-verified. Friction is one recurring class (G1 smoke-recipe nits) and one new render-verification gotcha.
status: resolved
---

# Cycle retrospective — watcher-ux-fixes (sprint-22, MR-062 + MR-063)

Subject: the **run**, not the features. A small two-ticket "fixes" batch the product owner asked
for in one pass: MR-062 (ui) restored a stashed, owner-eyeballed CSS spinner superseding MR-061's
pulse; MR-063 (docs) reordered the README watcher recipe so `--allowedTools` stops swallowing the
`-p` prompt (GH #25). Both designs were decided and owner-validated before the cycle; G1 gated
implementability + validation fidelity, not the designs.

## Verdict

**Smooth.** G1 PASS-WITH-NITS (1 round), G7 PASS (1 round, independent re-run from a rebuilt
throwaway image), two non-process commits (`viewer.html` 9/9, `README.md`), 0 parks, 0
carry-overs. Scope stayed clean: `app.py` / `Dockerfile` / `mcp_server.py` byte-unchanged.

## What went well (load-bearing)

- **The "ship → owner eyeballs live → quick-iterate → stash → formalize" loop ran cleanly.** G1
  verified `git stash apply` lands with no conflict and is `viewer.html`-only (G1 "What I
  verified"); G7 independently rebuilt the image and re-ran the render-smoke. The eyeballed code
  carried into the gated cycle without redesign churn, and the gates still did real work on it.
- **G1 earned its keep on the smoke recipe again.** All four nits (N1 wrong viewer route `/r/$id`
  vs `/review/$id`; N2 stale state not force-stampable via `/handoff`; N3 reviewer-flip needs
  `{to:reviewer,by:reviewer}` not bare `{to:reviewer}`; N4 reduced-motion probe targets `::before`)
  were caught before MR-062 was written — exactly G1's job.
- **Batching two unrelated small fixes into one "fixes" epic worked.** Independent tickets (no
  `depends_on`), one G1, one G7, no cross-contamination.

## Top suggestions (suggest-only, prioritized)

1. **[skill] Add a render-verification note: CSS/`requestAnimationFrame` animations PAUSE in a
   hidden/automation tab.** This run hit it live — the spinner looked frozen in the browser-MCP
   (claude-in-chrome) tab until the clock was advanced manually, because background/occluded tabs
   throttle animation timers. Any future visual verification of an *animation* (this repo now has
   two: MR-061 ellipsis, MR-062 spinner) risks a false "it's broken" read. The skill's render-smoke
   guidance should say: assert animation by **computed `animationName` via CDP** (already the
   reduced-motion method), not by eye in a possibly-hidden tab; if you must eyeball, foreground the
   tab or advance the virtual clock first. This is undocumented anywhere today (`scripts/`, README,
   skill all silent) and is the highest-value *new* fix this cycle surfaces.

2. **[process] Sanction the "owner-driven UI iterate-then-formalize" path explicitly.** This is now
   a **pattern**, not a one-off: MR-061 shipped, owner tested live and it failed the goal, the
   orchestrator quick-iterated on a throwaway :8139 image, owner approved, then it was formalized
   through a full cycle with the eyeballed code carried in by a git stash. It worked cleanly both
   times *because* G1 checked the stash applies faithfully and G7 re-verified. Naming it in G0/G1
   guidance (when it is allowed, and the two guardrails that make it safe — G1 must verify the stash
   is faithful + applies clean, G7 must re-run the smoke, not just diff-read) turns folklore into a
   repeatable, bounded move and stops a future session inventing a looser version of it.

3. **[agent] Give the planner/critic a standing "smoke-recipe against the live `/handoff` + route
   contract" check.** G1's nits this cycle (N1-N3) and MR-061's G1 blockers (B1 `/ping`, B2 compound
   selector) are the **same class twice running**: a verification recipe that names a route, a
   handoff body, or a flat-matcher selector the service does not actually support. A standing planner
   instruction — "every render-smoke step must cite the exact `app.py` route/handoff arm and use a
   flat (`tag`/`.class`/`#id`) selector" — would let the planner self-catch this class before G1,
   shrinking the recurring G1 nit round to zero. Highest-leverage because it kills a *recurring*
   class, not a one-off.

4. **[feature] Backlog the remaining GH #27 work.** This cycle (like MR-061) deliberately sliced one
   piece of #27 and left progress-steps + streamed/diff-animated updates in the issue; #26 (watcher
   dies on server restart) also stays parked. A standing backlog ticket keeps the deferred scope
   visible so the next "fixes" batch reaches for it deliberately.

## Notes (not new, no action)

- The `reviews/` directory-split convention (gate `.md` under `docs/process/reviews/`, bulky render
  evidence under repo-root `reviews/sprint-22-render-evidence-2026-06-24/`) held an **8th**
  consecutive time, still unwritten in the README. Already filed in the MR-061 / agent-watcher-C3 /
  watcher-launch-fix retros — tracked, not re-raised here.
- Scratch-port-in-evidence-header (implementer vs critic port divergence) already filed in the
  MR-061 retro; this cycle the critic used 8769 with no recipe mismatch. No action.
- Standing rails (scaffold-to-dev-before-impl, `.scratch/` for all smokes) held again.

## Was MR-061→MR-062 supersession a smell?

No. MR-061 shipped a real (if too-subtle) affordance, the owner tested it against the actual goal,
and the fix landed one sprint later — a responsive ship→feedback→supersede loop, not waste. The
only mild lesson: a UI affordance whose success criterion is "the owner can see it" is a candidate
for an owner eyeball *before* the ship, which is exactly what suggestion #2 formalizes.

## Metrics

- **G1 rounds:** 1 (PASS-WITH-NITS; 4 nits, all in the MR-062 smoke recipe, all folded — no 2nd round, designs unchanged).
- **G7 rounds:** 1 (PASS, independent re-run from a rebuilt image; 1 cosmetic non-blocking note on MR-063 prose line-number drift).
- **Tickets:** 2 shipped (MR-062, MR-063), 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0. A1 (MR-063 README-only, brief said "both files" but CLAUDE.md has no recipe literal) held and was confirmed at both G1 and G7; A2/A3 (stale state, viewer route) were verification-recipe corrections folded at G1, not overturned implementation assumptions.
