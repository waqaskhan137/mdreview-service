---
retro_of: feature-cycle run — comment-resolution epic (sprint-11 / MR-033–037)
agent: cycle-retrospective
timestamp: 2026-06-19
scope: the RUN (plan → G1 → tickets → sprint → implement → G7 → PR), not the feature
---

# Cycle retrospective — comment-resolution (sprint-11)

**Verdict: smooth despite the size — friction in the plan's structural read.** The largest epic
in the repo (service + state machine + MCP contract + a ~75% viewer rewrite) ran the full cycle in
one day, five tickets, zero parks, zero carry-overs, two NITs fixed in-sprint at G7. The one real
friction was upstream: the planner reached the *right* destination (Option (a), viewer authoring
on comments) via a *wrong map* of the existing code — it called the MR-006 gutter a separate
"system to wall off" when it is a second *view of the same `notes` array*. The critic had to correct
that framing, and both G1 BLOCKERs fell out of it. This is the inverse of a win the last two retros
praised (the planner *correctly* reading viewer internals), which makes the missing rail worth naming.

## What went well (load-bearing)

- **The G1 critic earned its keep on the highest-value axis: it read the code and re-mapped the
  seam.** It verified that `renderComments()` iterates `notes` and authoring pushes to `notes`
  (`comment-resolution-plan-review-2026-06-19.md`, "The fork ruling (#1)") — "one data model, two
  views, not two systems" — and from that single correction derived BLOCKER-1 (legacy author
  surfaces left live → a *real* double-author viewer) and BLOCKER-2 (`GET /feedback`/dashboard go
  stale once authoring moves). Both were preventable double-ship failures; the gate caught them
  before tickets spawned. This is G1 doing exactly its job.
- **Round 2 was convergent, not churn.** The r2 block re-verified all 2 BLOCKER + 4 SHOULD + 3 NIT
  against the code and found *no new* issues — a clean confirmation, not a second class of defect.
- **The verification rig scaled to the largest epic without new invention.** `mcp_smoke` (22
  assertions / 14 tools), render-smoke with flat selectors + two-selector nesting, and the
  Node-built-in-WebSocket CDP harness (15 interaction checks incl. "authoring posts `/comments` not
  `/feedback`" via a fetch-recorder, agent-resolve-on-poll, reply-to-resolved re-render, dual-pane
  role colors) covered a state machine, an MCP contract, and an interaction-heavy viewer. The
  carried footguns (flat matcher, scheme-emulation not `--force-dark-mode`, GET header-dump) all
  held — none recurred.

## Top suggestions (prioritized)

### 1. Add a planner Method step: map every existing surface that touches the load-bearing data model BEFORE proposing to fork/freeze it. `[agent]` (mdreview-planner)
*Highest value — a near-recurring class, and the root of both this cycle's BLOCKERs.* The planner's
"Explore before designing" step says "grep/read the real code paths" and "reuse before inventing,"
but nothing forces it to **state how each existing surface relates to the data model it is about to
fork**. Here the gutter *is* a projection of `notes` (`viewer.html:444` `mk.dataset.id=i`,
`renderComments` iterates `notes`), so "wall it off as a rival system" was structurally wrong and
spawned two BLOCKERs about leftover surfaces and stale read paths. The planner already does a
"Current model (verified against the code)" table for the *store* — the fix is to require the **same
table for every read/write/render surface of that store** (kept-as-is / projected / repointed /
retired), so "you described an existing system you didn't read closely" surfaces at authoring, not
by the critic. Add to Method step 2 (Explore before designing): *"When the design forks or freezes
an existing data model, enumerate every surface that reads, writes, or renders it as a fate table
(kept / projected / repointed / retired) before proposing the fork — a surface you call a 'separate
system' that is actually a view of the same store is the seam an implementer builds wrong."* This is
the inverse of the win the last two retros praised (correctly reading `dashboard.html`'s
pane-adaptive structure); the planner does it well by habit, not by rule.

### 2. Add a required "preserve-constraint impact table" to the epic-plan template. `[skill]` (templates/epic-plan.md)
*Directly prevents the BLOCKER-2 class; cheap and reusable.* The brief's explicit constraint was
"preserve all existing functionality and data," yet BLOCKER-2 was a *silent staleness* of an
existing read path (`GET /feedback`) and the dashboard once authoring moved — the plan froze them
"byte-for-byte" without noticing that freezing a read path is only back-compat if nothing migrates
onto the new path. A standing template section — *every existing endpoint/surface the change touches
× {kept-as-is | projected | retired} × how the preserve-constraint is met* — would have forced the
planner to write the `GET /feedback`/`summary()` row and see it go stale at authoring time. The
planner produced exactly this table *after* the critic asked (the per-surface fate table that
settled BLOCKER-1); making it a template field surfaces it on the first pass. Pairs with suggestion
1 (which says map the *internal* surfaces); this pins the *contract* surfaces named in the brief.

### 3. Note the staged-rewrite risk for near-total single-file UI rewrites — don't split, but call the seam. `[process]`
*Balanced, not a complaint.* MR-036 rewrote ~75% of `viewer.html` (+246/−209 of 544 lines) as one
ticket — the legacy-surface retirement grew it, and the plan flagged a possible split
("retire `#panel`/Collect" vs "Resolved panel + reopen") but shipped it whole. **That was the right
call:** the split's own failure mode is "a viewer authoring two stores mid-sprint," exactly what
BLOCKER-1 prevents, so the two halves had to land together. But a near-total inline-JS rewrite done
as ~10 staged Edits + deleting a second `<script>` block is a distinct failure surface from a fresh
file — a half-applied rewrite can leave dead handlers or a stale second view. The CDP harness caught
this here (it asserted no `POST /feedback`, `comment_id`-only `data-id`, no legacy `#panel`/`#items`).
Worth a one-line process note: *for a >50%-of-file UI rewrite kept as one ticket, the render
evidence must assert the OLD surfaces are gone (negative assertions: no legacy ids, no legacy POST),
not just that the new ones render* — the staged-edit risk is a leftover, and a leftover is invisible
to a "new nodes present" check. Keep the ticket whole; harden its evidence.

### 4. Promote the fetch-recorder CDP pattern to a checked-in helper. `[feature]` (backlog ticket)
*Recurring across UI cycles — the dashboard-redesign retro already proposed `scripts/cdp-drive.js`.*
This cycle's CDP harness added a genuinely reusable capability the last retro's proposal didn't name:
a **network/fetch recorder** to prove "authoring issues `POST /comments`, never `POST /feedback`" —
a negative-network assertion that render-smoke and screenshots structurally cannot make. Fold this
into the already-backlogged `cdp-drive` helper as a first-class mode (record requests, assert a URL
was/wasn't hit) so the next interaction-heavy viewer cycle pulls it instead of hand-rolling a
WebSocket client again. Scope as a backlog ticket, not a mandate.

## Metrics

- **G1 rounds:** 2 (r1 PASS-WITH-CONDITIONS: 2 BLOCKER + 4 SHOULD + 3 NIT; r2 PASS — no new issues).
- **G7 rounds:** 1 (first-pass PASS: 0 BLOCKER / 0 SHOULD / 2 NIT, both fixed in-sprint).
- **Tickets shipped vs carried:** 5 shipped (MR-033–037), 0 carried.
- **Parks / BLOCKED:** 0.
- **Wrong load-bearing assumptions:** 1 (the "gutter is a separate system" framing — right
  destination, wrong map; both G1 BLOCKERs derived from it). No BLOCKER-FOR-HUMAN was needed.
- **Cycle size:** 5 feature commits; `app.py` +193 across MR-033/034, `mcp_server.py` +82 /
  `mcp_smoke.py` +63 (MR-035), `viewer.html` +246/−209 (MR-036, ~75% rewrite), docs +129 (MR-037).
- **Carried-rail payoff:** flat matcher, scheme-emulation (not `--force-dark-mode`), GET header-dump
  — all observed, none recurred. The dark-pane capture flag added by the dashboard-redesign retro
  was used correctly here (real dual-pane screenshots, not a vacuous pair).
- **Recurring-class friction:** 1 — a structural mis-read of viewer internals at plan time. This is
  the *inverse* of a win the last two retros praised (planner reading `dashboard.html` correctly);
  it has **not** been raised before as a suggestion, and suggestion 1 names the missing rail.
