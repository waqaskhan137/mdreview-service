---
review_of: epics/legacy-feedback-retire-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: CHANGES-REQUESTED
status: resolved   # both blockers fixed in the revision; confirmed PASS in the r2 review
---

# G1 Plan-Gate review — legacy feedback write-path retirement

**Artifact:** `epics/legacy-feedback-retire-plan.md` (authored by `mdreview-planner`)
**Brief:** `docs/process/requirements/legacy-feedback-retire.md`
**Audit:** `reviews/ponytail-audit-2026-06-19.md`
**Gate:** `docs/process/README.md` — G1 row + "Reviews (gate evidence)" section

## Verdict

**CHANGES-REQUESTED.** The plan's *core decision is right* (retire only the write surface; keep
every reader; keep the `summary()` guard) and the scope discipline is genuinely good. But its
single most load-bearing piece of evidence — the `summary()` design-fork case table — is
**factually wrong**, verified against both the code (`app.py:127-149`) and the live `:8139` volume.
The conclusion survives the correction, but a G1 plan whose central justification mis-describes the
code is not safe to spawn tickets from: the table directly seeds an acceptance criterion that tests
a state which does not exist, and would let a real regression through. Two BLOCKERs and three
worth-considering items below. None require a human product decision; all are author-fixable in one
revision.

---

## Findings (blockers first)

### BLOCKER 1 — The `summary()` design-fork case table is wrong; the AC derived from it tests a non-existent state. (confidence: HIGH — verified against code + live data)

The plan's "one real design fork" (plan §"The one real design fork", and the table at plan
lines 97-102) is the decision it flags as least-certain and asks the reviewer to stress-test. I did.
The **decision** (KEEP the guard, keep `summary()` reading via `.get()`) is correct. The **case
table justifying it is not**, in two independent ways:

The guard is `app.py:143`: `if not m.get("feedback_updated") and total == 0: status="awaiting"`,
followed by `elif total and addressed == total: "resolved"` else `"feedback"`.

**(a) The "human cleared feedback" row (`feedback_updated>0`, `total==0`) does not regress, and does
not exist in the data.** The table claims that deleting the guard flips this case from `feedback`
to `awaiting`, regressing "the 12 live reviews." Tracing the actual code: with `total==0`, the
`elif total and ...` is falsy under *both* KEEP and delete-the-branch, so the case resolves to
`feedback` either way — it never flips. The only way to make it flip to `awaiting` is to *rewrite*
the guard to `if total == 0:` (dropping the field reference), which is a third option nobody
proposed. Worse, I checked the live volume: of the 12 reviews with `feedback_updated>0`, **zero**
have `notes_total==0` — their counts are 1,2,3,4,6,8,12. So this row describes a state with **no
live instances**. (Verified: `curl :8139/api/reviews`, 45 reviews, `feedback_updated>0` set = 12,
all with `notes_total>=1`, all currently `status:"feedback"`.)

**(b) The row that *actually* regresses is mis-labelled "same".** Table row 1 ("brand-new review,
no comments", `feedback_updated` absent, `total==0`) is marked `awaiting ✓ (same)` under guard
deletion. That is backwards: deleting the guard branch flips **this** case from `awaiting` to
`feedback`. And this is the populated case — **31 of 45 live reviews** are exactly
`feedback_updated==0, notes_total==0, status:"awaiting"`. So the guard's real job is to keep *new /
empty* reviews out of `feedback`, and deleting it would regress 31 reviews, not the 12 the plan
names.

**Why this blocks G1, given the conclusion is right:** the AC in plan §Risks and §Ticket-breakdown
("verify a live review with `feedback_updated > 0` and `total == 0` does **not** show `awaiting`")
and the Verification snippet at plan lines 332-338 both test population (a) — which is empty. That
AC passes vacuously on a no-op and would equally pass on a *broken* implementation, because no live
review can ever enter the state it checks. The correct AC asserts that a **brand-new review**
(`feedback_updated` absent, no comments) still derives `awaiting` after the change — i.e. it guards
population (b)/the 31 reviews. As written, the plan's headline safety check is security theatre.

**Direction:** rewrite the case table against the three populations that actually exist — Pop A (12:
`fu>0, total>=1` → `feedback`/`resolved`, guard irrelevant), Pop B (31: `fu==0, total==0` →
`awaiting`, guard load-bearing), Pop C (`fu>0, total==0` → does not occur). State plainly that the
guard protects **new/empty** reviews (Pop B), not the 12. Keep the decision (KEEP guard); fix the
reasoning and repoint the AC at a fresh review. The "12 live reviews" framing inherited from the
audit should be dropped here — for the guard specifically it is the wrong population.

### BLOCKER 2 — Missed reader: `docs/future-mcp.md:61` asserts the heuristic "is unchanged"; Phase 2 makes that false. (confidence: HIGH — verified)

The plan's call-site sweep (a G1 must-be-complete item) concludes in Assumption #5 that
`docs/future-mcp.md` "needs no edit," claiming it only *references* AGENTS.md. It does more than
reference it. `docs/future-mcp.md:61` reads verbatim: *"The 'human is done' heuristic in `AGENTS.md`
is unchanged."* Phase 2 rewrites exactly that heuristic (`feedback_updated` → `comments_updated`).
The moment that lands, this sentence is a stale falsehood in the MCP design-record doc. The plan
even claims it "verified the two references don't restate the old wording" — but this line pins the
heuristic by asserting its immutability, which is the same failure mode the rest of the epic exists
to fix.

Blast radius is small (a design-record doc, not the live agent contract), so this is a BLOCKER on
**completeness of the sweep**, not on safety — but the whole premise of this gate is that the audit
was over-corrected twice by missing readers, and the plan's own discipline is "never miss a reader."
A missed reader in the very sweep that claims completeness has to be closed before tickets.

**Direction:** add `docs/future-mcp.md:61` to the Phase-2 docs ticket scope — either drop the
"is unchanged" clause or update it to point at the new `comments_updated` heuristic. Flip
Assumption #5 from "needs no edit" to "needs a one-line edit."

---

## Worth considering

- **Plan is misfiled and its links only resolve from the intended location.** (confidence: HIGH)
  The README Layout section places epics at `docs/process/epics/<slug>-plan.md`; all 12 existing
  epics live there. This plan sits at **repo-root `/epics/`** (untracked). Its frontmatter
  `source: requirements/legacy-feedback-retire.md` and body links (`../requirements/...`,
  `../../../reviews/...`) are written for `docs/process/epics/` and are broken from its actual
  location. Fix with `git mv epics/legacy-feedback-retire-plan.md docs/process/epics/`. Mechanical,
  but resolve before tickets so they aren't created against a misfiled, broken-link plan. (Note: I
  placed *this review* in repo-root `reviews/` to sit beside the audit it cites, matching where the
  existing `reviews/` tree actually is — the README's `docs/process/reviews/` path is itself not
  where the live evidence lives, a pre-existing inconsistency, not this plan's fault.)

- **The `mcp_server.py:108` description is already mostly correct; the plan overstates the edit.**
  (confidence: HIGH) The plan (lines 148-150) says `get_status` "advertises `feedback_updated`" and
  asks to "lead with `comments_updated` ... present `feedback_updated` as legacy." The actual text
  (`mcp_server.py:109-110`) already says *"Watch comments_updated for new/changed comment threads."*
  It only *lists* `feedback_updated` as one of three timestamps it returns — which stays factually
  true. The edit is cosmetic at most; the "must reconnect the MCP client" ceremony the plan attaches
  to it is real but is being spent on a near-no-op. Worth right-sizing so the orchestrator doesn't
  treat this as a load-bearing contract change requiring a reconnect dance for what is one
  de-emphasis word.

- **Two-ticket Phase-1/Phase-2 split vs. "land together."** (confidence: MEDIUM) The brief's hard
  constraint (a) is "land app.py + both docs + MCP description **together**." The plan splits this
  into a svc ticket (Phase 1) and docs/MCP tickets (Phase 2), svc-first, and leans on the
  Definition-of-Done same-sprint-docs-sweep rule to call it atomic. Svc-before-docs is the *right*
  order (the alternative — docs say "use comments" while the route still 200s — is worse). And on a
  single-deploy, no-CD repo where nothing ships mid-sprint, the inter-ticket window is not a live
  exposure. So I do **not** flag this as a blocker. But the plan should say explicitly that "land
  together" is satisfied at the **sprint** granularity (both phases in sprint-13, docs-sweep
  non-carry-over per G7), not the commit granularity, and that the window is internal-only. As
  written it asserts atomicity a two-commit split doesn't literally provide; name the granularity so
  the G7 reviewer doesn't read it as a contradiction.

- **404 vs 410 on the removed route — the plan's default is defensible; make the reviewer's lever a
  decision, not a footnote.** (confidence: MEDIUM, judgment call) I confirmed the fall-through:
  after the POST arm is removed, `POST /feedback` matches the path block (`app.py:481`, method-
  agnostic `re.fullmatch`), passes `_exists`, matches neither arm, and exits to the final
  `app.py:662` → `404 {"error":"no route"}`. No early-return trap; the GET arm stays reachable. On a
  no-auth, public-ish service where the audit's whole worry is "an undiscovered caller using the
  documented curl recipe," a bare 404 is indistinguishable from "wrong URL," whereas a **410 Gone +
  'use comments'** body is a self-documenting signal to exactly that caller at ~3 lines' cost. The
  plan recommends straight removal and demotes 410 to "the reviewer's lever." I'd lean the other way
  — default to 410 — but it's a preference with a real trade-off (410 keeps a vestigial handler the
  cleanup is trying to delete). Not a blocker; the author should pick deliberately and record why,
  rather than leave it as a fallback the reviewer has to pull.

## Nitpicks

- `app.py:15` header docstring POST line removal is in scope (plan covers "the two `/feedback`
  lines"); note line 14's GET line carries a now-stale "(viewer saves here)"-style framing in the
  POST entry only — confirm the GET docstring line reads cleanly once its POST sibling is gone.
  (confidence: HIGH)
- `feedback_url` in the create-review response (`app.py:449`) is GET-semantics and correctly
  untouched; the plan never mentions it. Harmless, but a complete sweep should note it so a future
  reader doesn't think it was missed. (confidence: HIGH)
- Two historical process docs reference the field — `docs/process/epics/mcp-wrapper-plan.md:110`,
  `docs/process/epics/dashboard-redesign-plan.md:39`, and ticket `MR-002-list-and-summary.md:23`.
  These are frozen historical records (shipped epics/tickets); per the README's "never edit the
  brief / history" ethos they should **not** be retro-edited. Flag as deliberately-out-of-scope so
  the sweep is provably complete, not silently incomplete. (confidence: HIGH)

---

## What I verified (so the author can trust or challenge each)

- `summary()` logic and all cited line numbers — `app.py:127-149` (guard at 143), POST handler
  `495-501` (bump at 500), `create_review` initialiser at 193, status payload at 511, GET arm
  486-494, route default 404 at 662. **All line numbers in the plan are accurate.**
- The guard-deletion behavior, reproduced in Python across all three populations (KEEP vs
  delete-branch): Pop B (new/empty) is the one that flips; Pop C (the plan's contested row) does
  not occur and does not flip.
- Live `:8139` volume: 45 reviews; 12 with `feedback_updated>0` (all `notes_total>=1`, all
  `status:feedback`); 31 `awaiting` (all `fu==0, total==0`). Matches the plan's headline counts but
  **contradicts its case-table attribution**.
- Sole writer of `feedback_updated` is `bump` at `app.py:500`; sole writers of
  `feedback.md`/`notes.json` are `create_review`, `snapshot_round`, and the removed POST handler —
  the plan's "becomes append-on-create + history-archive" claim holds.
- Smoke scripts (`mcp_smoke.py`, `agent_smoke.py`) and `viewer.html` do **not** POST `/feedback`
  (viewer uses comments only, `viewer.html:293`); no test directory exists. The "no caller in this
  workspace" basis holds for the local tree (it cannot, and the plan agrees it cannot, cover other
  deployments).
- `mcp_server.py:108-110` already leads with `comments_updated`; `docs/future-mcp.md:61` asserts the
  heuristic "is unchanged" (BLOCKER 2).

## What's good (load-bearing)

The read-path-stays discipline is correct and the Non-goals section is unusually disciplined — it
correctly keeps `summary()` counting, `GET /feedback`, `GET /history`, `snapshot_round`, the status
payload, and `dashboard.html` out of scope, and correctly scopes out the AGENTS/CLAUDE dedup as a
preference. The decision to KEEP the guard is the right call. The problem is entirely in the
*evidence* offered for it, not the call itself — which is exactly the trap (audit over-corrected by
mis-reading state) this gate exists to catch, so it has to be fixed before tickets.

---

## Resolution log

(empty — to be filled as each blocker is closed by the planner; set `status: resolved` only when
BLOCKER 1 and BLOCKER 2 are both closed.)

- [ ] BLOCKER 1 — design-fork case table corrected to the three real populations; safety AC
  repointed from the non-existent `fu>0,total==0` case to a brand-new-review `awaiting` assertion.
- [ ] BLOCKER 2 — `docs/future-mcp.md:61` added to Phase-2 docs scope; Assumption #5 flipped.
- [ ] (worth-considering) plan relocated to `docs/process/epics/`; links re-resolve.
- [ ] (worth-considering) `mcp_server.py` description edit right-sized; 404-vs-410 decided
  deliberately.

---

**VERDICT: CHANGES-REQUESTED** — BLOCKER 1 (wrong design-fork case table + vacuous safety AC) and
BLOCKER 2 (missed reader `docs/future-mcp.md:61`) must be resolved before tickets are spawned. The
plan's decisions are sound; its central evidence is not. Author-fixable in one revision; no human
product decision required.
