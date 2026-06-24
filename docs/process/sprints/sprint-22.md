---
id: sprint-22
name: watcher-ux-fixes — spinner + recipe arg-order
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Restore the stashed rotating-spinner affordance on both agent-turn waiting states (superseding MR-061's pulse) and fix the README scoped watcher launch recipe arg order so the documented command actually runs.
close_review: reviews/sprint-22-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent; re-ran render-smoke)
---

## Goal

Land the two-ticket `watcher-ux-fixes` batch — both already designed and validated, this sprint is
restore + verification fidelity, not redesign. MR-062 restores the stashed CSS rotating spinner onto
`viewer.html` (an 11px `--muted` ring on `#turntext::before`, added by `renderBanner` in **both** the
"waiting for pickup" and "Agent is working…" arms), superseding MR-061's too-subtle pulse and its
`turnworking` keyframes, with a reduced-motion static-ring fallback. MR-063 reorders the three README
scoped-recipe literals prompt-last (so `--allowedTools`'s variadic list no longer swallows `-p`'s
prompt) and adds the variadic note, closing GH #25. Success by the end date: MR-062 `done` on `dev`
(validated by render-smoke + reduced-motion probe + both-pane screenshots) and MR-063 `done`
(`py_compile` sanity + grep confirmation); sprint closes at G7.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-062 | Replace MR-061's pulse with a rotating CSS spinner on both agent-turn waiting states (restore stash) | ui | P2 | done |
| MR-063 | Fix the scoped watcher launch recipe arg order — `-p` prompt last (GH #25) | docs | P1 | done |

## Preferred execution order

The intended order, accounting for dependencies. Unblocking work first. The two are independent
(no `depends_on` between them) and may land in either order; the order below is a convenience.

1. MR-063 (docs) — trivial, no dependency, retires GH #25 immediately: reorder the three README
   recipe literals prompt-last + variadic note; verify the full-autonomy recipe; `py_compile` +
   grep.
2. MR-062 (ui) — restore `stash@{0}`, re-validate (render-smoke States A/B/D + State-C code
   inspection + reduced-motion CDP probe + both-pane screenshots), evidence under
   `reviews/sprint-22-render-evidence-2026-06-24/`.

## Notes / retro

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-22-close-review-2026-06-24.md`).
MR-062 + MR-063 `done`, no carry-overs. **This closes the `watcher-ux-fixes` epic — epic `done`.**

- **Shipped:** MR-062 (ui) — replaced MR-061's faint opacity-pulse ellipsis with a visible CSS rotating
  spinner (`#turntext::before`), broadened to BOTH agent-turn waiting states (the "Sent — waiting for
  pickup" arm that MR-061 missed + "Agent is working"), reduced-motion static-ring fallback; supersedes
  MR-061. MR-063 (docs) — fixed the watcher launch-recipe arg order (GH #25): the variadic `--allowedTools`
  was swallowing the trailing `<prompt>`; moved `-p "<prompt>"` last in all 3 README recipes + a note.
- **Origin = live product-owner testing:** the spinner replaces MR-061 because the owner tested it and
  the subtle pulse + narrow scope failed the goal; #25 was found the same way (a real dead-agent strand).
  Good case for "ship → owner eyeballs → iterate". MR-062's change was product-owner-approved via a
  quick-iterate `:8139` deploy, then formalized through this cycle (the stash carried the eyeballed code).
- **G7 critic re-ran** the render-smoke from a rebuilt image — State A (waiting-for-pickup) `.loading`
  present is the headline (the MR-061 gap), plus working/absent/reduced-motion/both-panes.
- **Carry-overs:** none. The rest of #27 (progress steps, streamed updates) stays in #27; watcher
  resilience (dies on server restart) stays in #26.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-062 + MR-063 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-22-close-review-2026-06-24.md`, verifying shipped work against each ticket's
      acceptance criteria, **including a render smoke** of the touched page (`viewer.html` for MR-062,
      re-run independently by the critic; MR-063 is docs-only), and its findings are resolved or carried;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.

**G7 scope note (watcher-ux-fixes specifics).** MR-062 **IS** a product-page change — it edits
`viewer.html` (baked into the container at build time, `Dockerfile:8`). So per the G7 pass-condition
row it **DOES owe** `scripts/render-smoke.sh` DOM assertions + screenshots: the close review must
rebuild a **throwaway container** from the working tree (a scratch-port `docker run`, e.g. 8765 —
**never** the live 8139 instance, **never** `docker compose up`/8137), drive the banner states via
`POST /handoff`, then assert the bare class `.loading` **present** in the waiting-for-pickup state
(`{to:agent}` only) and the working state (`{state:working,owner:smoke}`), **absent** after a reclaim
(`{to:reviewer,by:reviewer}`, exit 1 on 0 nodes), with the stale arm verified by code inspection
(`viewer.html:241` adds no class); capture **both-pane screenshots** (scheme emulation
`--blink-settings=preferredColorScheme=1/0`, NOT `--force-dark-mode`), **plus** the CDP
reduced-motion probe (`getComputedStyle($("#turntext"),'::before').animationName === 'none'` under
reduce, `turnspin` without). Route is `$BASE/review/{id}`. All evidence produced under the gitignored
`.scratch/` then **moved to** `reviews/sprint-22-render-evidence-2026-06-24/` for the gate.

**MR-063 is docs-only** (README markdown; no served page touched), so it owes **no render-smoke** —
its gate is `py_compile app.py` (unchanged sanity) + the grep confirmation in its acceptance
criteria.
