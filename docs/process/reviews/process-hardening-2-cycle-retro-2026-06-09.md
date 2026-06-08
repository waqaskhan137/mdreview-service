---
review_of: the process-hardening-2 cycle (sprint-03)
gate: retro (Phase 10)
reviewer: cycle-retrospective (agent)
independent: true
timestamp: 2026-06-09
verdict: smooth-run; recommend redirect to product work
status: open
---

# Cycle Retrospective — process-hardening-2 (sprint-03)

**Verdict:** Smooth run — 3/3 shipped, 0 carried, 0 parks — but all friction was self-induced by
the meta-subject, concentrated in one artifact (the G7 smoke-conditional rewording), which bit at
**both** gates. The recurring class this thread existed to kill is now closed; a third consecutive
meta cycle is **not** warranted — redirect the flywheel to the MCP wrapper.

## What went well
- **The target class is genuinely closed.** G7 confirmed MR-012's wire-into-the-row rule
  "genuinely beats 'name the row'" and "closes the G1 S1 loophole". The two-cycle recurring defect
  (rules in prose/DoD/G5 instead of the enforcing row) now has an enforcing planner rule.
- **Clean uncertainty hygiene.** The planner flagged its least-sure load-bearing call
  (suggestion-3 rail scoping) and G1 confirmed it CORRECT, not overturned. Zero wrong load-bearing
  assumptions.
- **Dogfooded its own outputs in its own close:** the MR-014 pre-G7 rail reconciled the board
  before the G7 critic spawned, and the MR-012/013 cite-by-name rule held (zero stale anchors).

## Top suggestions (prioritized; suggest-only)

1. **Extend the pre-G7 rail to RUN + RECORD the unconditional smoke, not just reconcile the
   board.** `[skill]` (`references/04-close-and-ship.md` Phase 6). The G7 BLOCKER was that the
   sprint's own close checklist dropped the owed `rebuild + curl /healthz + /api/reviews` smoke;
   MR-014's rail reconciles checkboxes/TRACKER but stops short of running the smoke, so the critic
   still had to catch it. Folding the unconditional smoke into the rail's step-0 takes this off the
   critic's plate. Highest value (same-area-repeated signal).
2. **Make the sprint close-checklist INHERIT the G7 row's verification line rather than re-derive
   it.** `[process]`. The G7 B1 root cause was the very class this epic targeted: the checklist
   restated verification as "read-diff" instead of pointing at the G7 row's unconditional-smoke
   clause. "The close checklist cites the G7 pass-condition row, it does not paraphrase it."
3. **(lower) Capture raw smoke output, not a paraphrase.** `[skill]`. The evidence file records
   `/api/reviews` as "6 reviews (sane JSON)" rather than the raw response; the rail should `tee`
   actual output.
4. **(observation) G8 is a clean promote point now.** `[process]`. PR #2 carries two unmerged
   sprints (sprint-02 + sprint-03); a natural promote-to-`main` checkpoint.

## Meta-cycle vs. product redirect (honest read)

**Recommendation: stop meta-cycling; redirect to the MCP wrapper.**
- **Decisive:** two meta cycles cannot tell you whether the hardened process actually helps real
  feature work — only running it on product can. Both sprint-02 and sprint-03 were docs-only and
  self-referential; the process has improved itself twice without once being exercised against
  code/UI/infra. The MCP wrapper is the validation the meta-thread structurally cannot provide.
- The recurring class is closed (What-went-well #1) — the thread's reason to exist is discharged.
- This cycle's friction doesn't generalize: both blockers came from *editing gate wording*, a
  hazard unique to meta work. A product cycle won't reproduce it.
- The one real remaining gap is a one-line `[skill]` fix (suggestion 1) — fold it into the next
  cycle's open rather than spending a third meta sprint on it.

The MCP wrapper is well-positioned: the HTTP contract is already MCP-ready, the sketch lives in
`docs/future-mcp.md`, and it would become its own epic + sprint — a real product cycle that finally
exercises the hardened gates end-to-end.

## Metrics
- **G1 rounds:** 2 (round 1 PASS-WITH-FIXES: B1 over-scoped smoke conditional + S1 "name the row"
  loophole; round 2 PASS).
- **G7 rounds:** 1 (PASS-WITH-FIXES: B1 owed smoke dropped from own checklist; S1 README↔skill
  Phase 6 drift; both resolved in-line).
- **Tickets:** 3 shipped / 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 0 (the flagged-least-sure call was confirmed correct at G1).

## Disposition
Suggestions are proposals only; none applied. The headline is the redirect recommendation: the
next cycle should be the **MCP wrapper** (product), carrying suggestion 1 as a one-line skill fix
in its open.
