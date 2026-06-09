---
review_of: the mcp-wrapper cycle (sprint-04)
gate: retro (Phase 10)
reviewer: cycle-retrospective (agent)
independent: true
timestamp: 2026-06-09
verdict: smooth-run; hardening validated on product work
status: open
---

# Cycle Retrospective — mcp-wrapper (sprint-04)

**Verdict:** Smooth. The first product-code cycle through the hardened gates shipped clean — 4/4
`done`, 0 carried, 0 parks, G7 PASS on the first pass. The one notable event (a G1 blocker) is the
gates working as designed.

## What went well
- **G1 caught a real, load-bearing blocker.** The critic found the planner enforcing the epic's
  *defining* constraint ("HTTP service unchanged") in prose citing a non-existent G4 condition —
  the exact MR-012 defect class — fixed by wiring it into per-ticket ACs. G7 then independently
  re-ran that diff and found it empty. Enforced by mechanism, not memory, end to end.
- **Protocol assumptions grounded, not guessed.** The implementer confirmed `protocolVersion
  2025-06-18`, newline framing, and the `-32602` envelope against the official MCP spec via WebFetch
  before writing the read loop; all three verified correct. The plan's build-time-verify labels paid
  off exactly as intended.
- **The smoke was non-vacuous.** `mcp_smoke.py` parses `content[0].text`, extracts the id, asserts
  `revision>=1`, and cleans up — 11/11 against the rebuilt container. `py_compile` alone would not
  have caught a stubbed proxy; the round-trip did.

## Top suggestions (prioritized; suggest-only)
1. **`[agent]` Give `mdreview-planner` a pre-G1 self-audit for phantom enforcement claims.** The G1
   blocker was the planner violating MR-012 — a rule that shipped the prior cycle and lives in its
   own agent doc — and the MR-012 audit happened only reactively after the critic flagged it. Add a
   standing instruction: every "gate X asserts Y" claim must map to a real gate-row condition or a
   per-ticket AC before submitting for G1. Targets a recurring class (an MR-012 defect recurred one
   cycle after MR-012 shipped).
2. **`[skill]` Groom the carry-over rail into Phase 6 permanently.** Phase 6 step 1 prescribes
   recording evidence only in the product-page branch; the docs/infra-only branch owes the rebuild +
   curl smoke but is not told to record it anywhere. process-hardening-2 retro suggestion 1 ("rail
   runs AND records the smoke") rode this cycle on memory (it worked — `smoke.txt` exists). Make it
   standing: the docs/infra branch must capture rebuild + `/healthz` + `/api/reviews` output to
   `reviews/sprint-NN-render-evidence-*/smoke.txt`. **Answer to the grooming question: yes.**
3. **`[feature]` File the acknowledged follow-ups in `backlog.md`** (and retire the now-stale "MCP
   wrapper" entry — it shipped): COPY `mcp_server.py` into the image (`infra`); an optional `mcp`-SDK
   variant. *(Done by the orchestrator at close — see backlog.)*

## Meta verdict — did the hardening help this product cycle?
**Yes, demonstrably — and the same blocker marks where it is still incomplete.** process-hardening-2
redirected here precisely to test the gates on real code, and the test passed: G1 independently
caught a load-bearing blocker on the defining constraint, and G7 reproduced the diff + spec
cross-check rather than trusting the author. But shipping MR-012 into the planner's doc did not make
the planner self-apply it — the gate caught what the agent should have self-enforced (suggestion 1
closes that gap). Net: hardening validated on product work, and it surfaced its own next increment.

## Metrics
- **G1 rounds:** 2 (round 1 PASS-WITH-FIXES: 1 blocker + 4 should-fixes; round 2 PASS).
- **G7 rounds:** 1 (PASS first pass; 2 cosmetic NITs fixed at close).
- **Tickets:** 4 shipped / 0 carried.
- **Parks:** 0.
- **Wrong load-bearing assumptions:** 1 — the phantom "G4 asserts git diff" claim, overturned at G1.
  The 3 MCP protocol assumptions all verified correct at build time.

## Disposition
Suggestions 1-2 are proposals for a future process increment (a `process-hardening-3` could be a
*tiny* one — two edits — or fold them into the next product cycle's open). Suggestion 3's factual
cleanup (stale backlog entry + 2 unfiled follow-ups) was applied at close as accuracy hygiene.
