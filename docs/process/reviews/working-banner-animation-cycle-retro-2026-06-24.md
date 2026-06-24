---
review_of: epics/working-banner-animation-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: Smooth — clean single-ticket ui cycle, 0 parks, 0 carry-overs; G1 caught both smoke-recipe defects before the ticket was written, G7 PASS on an independent re-run.
status: resolved
---

# Cycle retrospective — working-banner-animation (sprint-21, MR-061)

Subject: the **run**, not the feature. First `ui` cycle in this recent run (the agent-watcher /
watcher-launch-fix cycles were svc/docs), so the G7 render-smoke obligation (rebuild a throwaway
container, drive headless Chrome, assert DOM nodes + a reduced-motion CDP probe, both-pane
screenshots) actually applied here — and it worked end to end.

## Verdict

**Smooth.** A CSS-only animated waiting ellipsis on the viewer's working-state turn banner — the
cheap high-value slice of GH #27. G1 PASS-WITH-NITS, G7 PASS, one `viewer.html` commit (8+/1-),
0 parks, 0 carry-overs.

## What went well (load-bearing)

- **G1 earned its keep on the smoke recipe.** Both "blocking" findings were in the verification
  recipe, not the design: B1 a non-existent `POST /…/ping` (the lease claim is the
  `{state:"working"}` arm of `/handoff`, `app.py:635-662`), B2 a compound `#turnbanner.working`
  selector that `render-smoke.sh:72`'s flat matcher rejects as bad-usage (exit 2). Both caught
  *before* MR-061 was written — exactly what G1 is for. Without it the smoke would have 404'd on
  the lease claim and exit-2'd on the assertion, i.e. tested nothing.
- **G7 was a genuine independent re-run, not a diff read.** The critic rebuilt a throwaway image
  (scratch port 8767), confirmed `turnworking` is baked into the served `viewer.html`, ran the
  positive + the load-bearing **negative** smoke (`.working` absent after a reclaim — proves the
  top-of-function `remove` clears the class), and ran both CDP arms of the reduced-motion probe.
  A JS-rendered banner verified as a render, not a 200.
- **Clean split for a tiny change.** The orchestrator made the 3 `viewer.html` edits itself and
  delegated only the heavy render-smoke (docker build + CDP) to a subagent. Right-sized.
- **Standing rails held again.** `.scratch/`-in-subagent-prompts and "commit scaffold to dev
  before impl" both held (now ~4 cycles running).

## Top suggestions (suggest-only)

1. **Write the `reviews/` directory-split convention into the README.** `[process]` — Gate `.md`
   under `docs/process/reviews/`, bulky render evidence under repo-root `reviews/<sprint>-render-
   evidence-*`. This is now the **7th consecutive** adherence and still unwritten: README:36 only
   documents `reviews/` as the gate-evidence dir, and the G7 row (README:165) names
   `reviews/sprint-NN-render-evidence-*` without stating the two-location split. A convention this
   stable that a fresh session would have to reverse-engineer should be one sentence in the README,
   not folklore.

2. **Name the "slice a big issue" pattern in the process docs.** `[process]` — This cycle correctly
   scoped to ONLY the animation and explicitly left progress-steps + streamed-diff in #27 (plan
   Non-goals; commit body "Cheap slice of issue #27"). "Take a big GH issue, ship the cheap
   high-value slice as its own tiny epic, leave the rest in the issue" is a repeatable scoping move,
   not a one-off — worth a named entry in G0/G1 guidance so future cycles reach for it deliberately
   instead of rediscovering it. (Pairs naturally with a `[feature]` follow-up: the remaining #27
   work — progress steps + streamed/diff updates — stays a backlog ticket.)

3. **Pin the scratch port in the smoke recipe (or template the evidence header).** `[skill]` — The
   implementer's `SMOKE.md` and ticket validation note said port 8766; the G7 critic used 8767 (G7
   nit, cosmetic, recipe identical). The port is arbitrary per run, so the mismatch is harmless —
   but having the smoke recipe emit the actual port into the evidence header (rather than a
   hard-coded literal the next reader trusts) removes a recurring cosmetic divergence between the
   implementer's and the critic's evidence with zero downside.

## Metrics

- **G1 rounds:** 1 (PASS-WITH-NITS; 2 blocking + 1 worth-considering + 1 nit, all folded, no 2nd round — design unchanged, fixes were smoke-recipe-only).
- **G7 rounds:** 1 (PASS, independent re-run; 2 no-change notes).
- **Tickets:** 1 shipped (MR-061), 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0. The one load-bearing fork (animate `::after` ellipsis vs spinner span) held; the two `(minor)` assumptions the critic touched (the `/ping` endpoint, the marker selector) were verification-recipe details, corrected at G1 before the ticket existed — not overturned implementation assumptions.
