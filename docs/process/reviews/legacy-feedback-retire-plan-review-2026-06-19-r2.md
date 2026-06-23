---
review_of: epics/legacy-feedback-retire-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G1 Plan-Gate re-review (round 2) — legacy feedback write-path retirement

**Artifact:** `epics/legacy-feedback-retire-plan.md` (revised by `mdreview-planner` after round 1)
**Round 1:** `reviews/legacy-feedback-retire-plan-review-2026-06-19.md` (CHANGES-REQUESTED, 2 blockers)
**Gate:** `docs/process/README.md` — G1 row + "Reviews (gate evidence)" section

## Verdict

**PASS — ready for tickets.** Both round-1 blockers are genuinely closed (verified against
`app.py:127–149`, `mcp_server.py:108–109`, `docs/future-mcp.md:61`, and a re-derivation of the
status logic). The new decisions the revision introduced — `410 Gone`, the collapse to two tickets,
and the sprint-granularity atomicity statement — are sound and introduce no new defect. This is a
focused re-review; settled round-1 scope was not re-litigated.

## Round-1 blockers — confirmed resolved

**BLOCKER 1 — design-fork case table + safety AC. Closed: ✓ (re-verified against code + a fresh
derivation).** The corrected table (plan, "The one real design fork") now has the right rows. I
re-derived `summary()`'s three-way branch (`app.py:143–148`) for every population, KEEP vs
delete-the-branch:

| population | KEEP guard | guard branch DELETED |
|---|---|---|
| Pop A `fu>0, total>=1` (12 live) | feedback / resolved | feedback / resolved (same) |
| Pop B `fu==0, total==0` (31 live + every new review) | **awaiting** | **feedback (FLIPS)** |
| Pop C `fu>0, total==0` (0 live) | feedback | feedback (same) |

This matches the revised table exactly: only Pop B flips, Pop A and Pop C do not. The false
round-1 claims are gone — the plan no longer says deleting the guard flips Pop C to `awaiting`, no
longer attributes the guard's protection to "the 12 live reviews," and re-justifies KEEP on the
real basis (it holds new/empty reviews out of `feedback`). The safety AC was replaced everywhere it
appeared (design fork, Risks, Verification, Assumption #2): the vacuous `fu>0,total==0` test is
removed and replaced with (a) a freshly created review with no comments still derives `awaiting`
(plan Verification, the `fresh-review-status` assert) and (b) the 31 live Pop-B reviews stay
`awaiting` (the `flipped-off-awaiting: []` check). The new AC fails on a broken impl and passes on a
correct one — it is no longer security theatre. `app.py:143` traced; corrected table is right.

**BLOCKER 2 — missed reader `docs/future-mcp.md:61`. Closed: ✓ (verified).** `docs/future-mcp.md:61`
still reads verbatim *"The 'human is done' heuristic in `AGENTS.md` is unchanged."* — and it is now
in Phase-2 docs-ticket scope (Docs section, rollout Phase 2, execution order, ticket-table row,
Risks "docs/route drift" + "missed reader", and the Verification `grep -n "unchanged"`). Assumption
#5 is flipped from "needs no edit" to "load-bearing — needs a one-line edit," with the correction
called out as caught at G1. Sweep completeness is restored.

## New decisions introduced by the revision — pressure-tested

**1. `410 Gone` for the removed POST route — sound, accept.** Mechanically clean in the single-file
regex router: the plan keeps a 3-line `if m == "POST": return self._json(410, {...})` arm in place
of the deleted write body — no `_body_json`, no `_lock`, no `_write`, no `bump`. I confirmed the
field's sole writer is the `bump(rid,"feedback_updated")` at `app.py:500`, which is removed with the
write body, so the 410 stub re-adds **no** write surface — it is a pure signal. The audit's goal is
to retire the *write*, not necessarily every byte of the handler; a 410 that writes nothing fully
satisfies that while being strictly more informative than the bare 404 fall-through (I confirmed the
fall-through lands at `app.py:662` `{"error":"no route"}`, which is indistinguishable from a typo'd
URL). On a no-auth, public-ish service this is the better call, not worse — the vestigial 3 lines
are a justified cost for a self-documenting deprecation signal. The Verification curl now expects
`<- 410` (plan Verification step 1). Judgment call, decided deliberately and recorded; no concern.

**2. Collapse to 2 tickets (MCP ticket dropped) — accurate, no scope owed.** I read the live
`get_status` description (`mcp_server.py:108–109`): *"Cheap poll: a review's source_updated,
feedback_updated, and comments_updated timestamps. Watch comments_updated for new/changed comment
threads."* Its "watch" guidance already leads with `comments_updated` and only *lists*
`feedback_updated` as one of three still-emitted timestamps (factually true after this epic — the
field is still in the `status` payload at `app.py:511`). I also confirmed the full tool list
(`mcp_server.py`) contains no `post_feedback`/`update_feedback`; `get_feedback` is GET-only. Nothing
is owed in `mcp_server.py`, so dropping the MCP edit, its ticket, and the reconnect ceremony is
correct — and because no `mcp_server.py` change lands, the reconnect note rightly does not apply to
this epic. No regression in scope.

**3. Atomicity granularity — stated correctly, no contradiction with the brief.** The plan now says
explicitly (Ticket breakdown, "Atomicity / 'land together' granularity") that the brief's "land
together" is satisfied at **sprint** granularity (both tickets in sprint-13, svc-before-docs,
docs-sweep a non-carry-over same-sprint obligation per the G7 pass-condition row and the Definition
of Done), **not** commit granularity, and that on this single-deploy/no-CD repo the inter-ticket
window is internal-only, not a live exposure. This is consistent with the README's G7 row (a
docs-sweep ticket is not eligible for carry-over) and removes the round-1 reading of a contradiction
with "land atomically."

## Still open

None. No new defect was introduced by the revision. The round-1 worth-considering items are also
addressed: the plan is filed at the canonical `docs/process/epics/legacy-feedback-retire-plan.md`
(git-tracked; no stray repo-root `epics/`), so its `../requirements/...` / `../../../reviews/...`
links resolve; the MCP edit is right-sized to no-change; and 404-vs-410 is decided deliberately.

## What I re-verified this round

- `summary()` derivation re-run in Python across all five population/edge cases — only Pop B (new /
  empty) flips on guard deletion; Pop A and Pop C do not. Matches the revised table.
- `app.py`: POST write body + `bump` at `495–501`/`500`, `create_review` initialiser `feedback_updated: 0`
  at `:193`, `status` payload default at `:511`, GET arm `486–494`, final 404 default at `:662`,
  guard at `:143`. All line numbers the revision cites are accurate.
- `mcp_server.py:108–109` `get_status` description leads with `comments_updated`; no
  `post_feedback`/`update_feedback` tool exists — the dropped-MCP-ticket decision holds.
- `docs/future-mcp.md:61` is the live "…is unchanged" assertion now in docs-ticket scope.
- `dashboard.html:117` reads `r.feedback_updated||0` (default-safe); `app.py:15` is the stale
  "(viewer saves here)" POST docstring line the plan flags for rewrite, `:14` (GET) reads clean.

---

**VERDICT: PASS** — both round-1 blockers (wrong design-fork table + vacuous safety AC; missed
reader `docs/future-mcp.md:61`) are confirmed resolved, and the three new decisions (410 Gone,
two-ticket collapse, sprint-granularity atomicity) are sound and defect-free. The epic may move to
`gate: passed` and spawn its two tickets (svc, then docs) in sprint-13.
