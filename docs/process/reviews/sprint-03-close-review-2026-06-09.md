---
review_of: sprints/sprint-03.md
gate: G7
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-06-09
verdict: PASS-WITH-FIXES
status: resolved
---

# G7 sprint-close review — sprint-03 "process-hardening-2"

Independent read-diff review of MR-012..014 (docs-only sprint that edited the planner agent, the
README incl. the G7 row, and the feature-cycle skill). Reviewer != implementer.

**Verdict: PASS-WITH-FIXES.** The three tickets' substantive edits are correct, mutually
consistent, and the dogfooding is clean (zero process-doc line anchors; the wire-into-the-row rule
genuinely beats "name the row"). One BLOCKER and one SHOULD-FIX, both resolved.

## BLOCKER (resolved)

**B1 — the unconditional rebuild + curl smoke was owed but unrecorded, and sprint-03's own close
checklist dropped it.** The G7 row this sprint shipped says a docs/infra-only sprint "still owes
the container rebuild + `curl /healthz` + `/api/reviews` smoke", and skill Phase 6 step 1 runs it
unconditionally — but the sprint-03 Close gate checklist reduced verification to "read-diff" and
omitted it. The sprint that reworded G7 was about to close ignoring the clause it shipped.
**Resolved:** ran the smoke against the rebuilt container — `{"ok":true}`, `/api/reviews` returns
6 reviews (sane JSON) — recorded at `reviews/sprint-03-render-evidence-2026-06-09/smoke.txt`; and
corrected the sprint-03 Close gate checklist to require that unconditional smoke (read-diff only
for the rest). The per-page render-smoke/screenshot is correctly NOT owed (no product page
touched).

## SHOULD-FIX (resolved)

**S1 — README ↔ skill drift on the per-page render bar.** MR-013 gated the per-page DOM assertion
+ screenshot in the README G7 row on a product page being touched, but skill Phase 6 step 1 still
said "open every touched page ... screenshot" unconditionally — vacuous for this sprint (empty
set) but a latent contradiction for the next page-touching sprint. **Resolved:** Phase 6 step 1
now scopes the per-page render-smoke + open/screenshot to "only if a product page was touched this
sprint (see the G7 pass-condition row)", matching the README. README stays the source of truth.

## NIT
- **N1 — "byte-for-byte unchanged" not git-diffable:** `main` has no `docs/process/` baseline, so
  MR-013's "every other G7 clause unchanged" rests on the plan's before-quote + the G1 review's
  attestation, not a diff. The clauses (done-or-carried-over, docs-sweep carry-over ineligibility,
  independent review, retro) all read intact and coherent in the shipped row. Limitation noted.

## Per-area checks (pass)
- **MR-013 G7 rewording:** rebuild + curl kept unconditional; only per-page render-smoke +
  screenshot gated on a product page; docs/infra carve-out explicit; consistent with Phase 6. The
  G1 B1 over-scoping is genuinely resolved in the shipped text. Citation convention landed in
  Reviews (gate evidence).
- **MR-012 planner rules:** Method step 6 requires enforcement "written into the named gate
  pass-condition row's text", "citing a row ... not sufficient", DoD/G5/prose = non-enforcing
  pointers — real strengthening, closes the G1 S1 loophole. Method step 2 narrows `path:line` to
  code + adds cite-by-name. Additive.
- **MR-014 rail:** Phase 6 step 0 precedes the staff-critic spawn and excludes
  `close_review`/`status: closed`/retro (kept in Phase 8, correct rationale). SKILL invariant
  points at Phase 6, no contradiction.
- **Self-consistency + dogfooding:** README Citation convention and planner Method step 2 agree;
  no dangling/duplicated wording; zero `*.md:NNN` process-doc anchors across all sprint-03
  artifacts.

## Resolution log
- 2026-06-09 — review recorded (PASS-WITH-FIXES). B1 resolved (owed smoke run + recorded; sprint
  Close-gate checklist corrected). S1 resolved (Phase 6 step 1 scoped to product-page changes,
  matching the README G7 row). N1 noted. Gate **cleared**; sprint-03 closes. Notably, the new
  pre-G7 board-reconciliation rail (MR-014) was dogfooded this close — the board was reconciled
  before this critic was spawned.
