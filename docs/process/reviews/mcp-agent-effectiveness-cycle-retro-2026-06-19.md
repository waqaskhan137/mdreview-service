---
retro_of: feature-cycle run — mcp-agent-effectiveness epic (sprint-12 / MR-038–043)
agent: cycle-retrospective
timestamp: 2026-06-19
scope: the RUN (plan → G1 → tickets → sprint → implement → G7 → PR), not the feature
---

# Cycle retrospective — mcp-agent-effectiveness (sprint-12)

**Verdict: smooth — the unusual thing is *why the cycle existed*, not how it ran.** Six tickets,
one day, zero parks, zero carry-overs, clean 1:1 commit→ticket mapping, G1 PASS-WITH-CONDITIONS
(0 BLOCKER / 2 SHOULD / 3 NIT) → r2 PASS, G7 PASS first pass (1 NIT accepted-no-change). The G7
critic independently re-ran `agent_smoke.py` (exit 0, `nw=1`, zero curl) and `mcp_smoke.py` (34/34)
rather than trusting the tickets. The run is not where the friction was. The friction was **upstream
of the cycle**: the orchestrator had been hot-patching agent-facing failures by hand (curl-attaching
an image, killing a stale MCP process, shipping table-CSS `dae815e` and a lightbox `2ed9593` as
ad-hoc direct commits) instead of routing fixes through the gates — which is the exact thing the user
called out. The cycle converted that backlog of hand-fixes into provable, gated property. So the
highest-value retro question is not "was this run clean" (it was) but "does the process now guard
against the antipattern that *triggered* it" — and the honest answer is: **the release valve exists
but is undocumented and operator-discretion, not a rail.**

## What went well (load-bearing)

- **G1 caught two real over-claims/over-builds the planner half-flagged itself.** The critic
  measured that staleness was "human/CI-with-a-shell detection wearing an 'agent' label"
  (`mcp-agent-effectiveness-plan-review-2026-06-19.md`, ruling #1) and that the bespoke stdlib
  RFC6455 WebSocket client "reinvents a tool the repo already has" (ruling #2). Both were
  correctable inside ticket boundaries without redesign; the planner had already named the WS client
  as its own *least-sure decision*. The gate did exactly its job, and the "flag your least-sure call"
  planner habit fed the critic the right target. r2 re-verified every code claim and found no new
  issues — convergent, not churn.
- **The retro-tickets kept the board honest without re-implementing.** MR-038/039 documented the
  already-merged `dae815e`/`2ed9593` `done`-on-arrival, each carrying a render-smoke AC against the
  *shipped* DOM; G7 confirmed the `viewer.html` delta is exactly those two commits and nothing new
  (`sprint-12-close-review`, "Commands run"). This is the direct-fix-then-retro-ticket release valve
  working — the issue is that it worked by the orchestrator's judgment, not by a documented rail.
- **`agent_smoke.py` is a genuinely new gate artifact, not ceremony.** It is the first harness that
  drives the MCP *as an agent* (create → `attach_asset(path=…)` → serve → repoint → `naturalWidth>0`,
  zero curl) — distinct from `mcp_smoke.py`'s protocol surface and `render-smoke.sh`'s DOM nodes. The
  sibling-not-extension call (keep the fast protocol smoke browser-free) was correct and the critic
  agreed.

## Top suggestions (prioritized)

### 1. Document the "operator hot-patch → retro-ticket" release valve as a named rail, with a trigger. `[skill]` (`.claude/skills/feature-cycle/references/04-close-and-ship.md`, and a one-line `[process]` note in `docs/process/README.md`)
*Highest value — it closes the exact gap that triggered this whole epic, and it is currently
undocumented.* The repo demonstrably *has* a release valve: ship a small fix directly, then
retro-ticket it `done`-on-arrival so the board reflects reality (MR-038/039, and `mcp-wrapper` retro
suggestion 3 did the same with backlog cleanup). But the skill's only "reconcile the board" step
(`04-close-and-ship.md` step 0) reconciles *ticket statuses* before the G7 critic — it says nothing
about out-of-band direct commits. There is **no documented Phase 0 retro-ticket pattern and no
trigger** anywhere in the skill or `README.md`. The honest line between "lazy direct fix" and "this
needs the process" is the one the user drew: a one-line CSS fix (`dae815e`, +4) shipped direct and
retro-ticketed is *fine*; what is *not* fine is a **recurring agent-facing failure** (the stale-MCP /
image-embed loop) being papered over by repeated operator curl with **no gated proof** that the
agent can self-serve. Propose a rail: *(a) a direct fix is allowed but owes a retro-ticket
(`done`-on-arrival, naming the commit + a render/smoke AML AC) at the next cycle's board
reconciliation; (b) when the operator finds themselves hand-driving the same agent-facing failure
more than once, that is the trigger to open a cycle, not patch again.* This is the inverse of
ceremony — it names the cheap path *and* the line past which the cheap path is the antipattern.

### 2. Promote "an autonomous-agent-loop proof" to a named G7 expectation for agent-facing features. `[process]` (`docs/process/README.md`, G7 pass-condition row) — scoped, not universal.
*Prevents a recurring class: a feature that an agent must self-serve shipping with only a
protocol/DOM smoke and no proof the agent completes the real task unaided.* This epic exists
precisely because there was **no agent-driven proof** — `mcp_smoke.py` proved the protocol surface
and `render-smoke.sh` proved DOM nodes, but neither proved an agent could complete create →
path-attach → render with zero human curl, so an operator kept stepping in. `agent_smoke.py` is that
proof. The G7 row already conditionally requires a render-smoke *only if a product page was touched*;
mirror that shape: *if a sprint changes an **agent-facing MCP/tool surface**, G7 owes an
agent-loop harness run (drive the MCP as an agent, assert the real task completes unaided) where one
exists for that surface.* Keep it conditional and honest about its cost — note the Node+Chrome
dependency of the render half and its fail-loud skip (the planner's own current least-sure call). Do
**not** make it universal: a docs/infra/`app.py`-internal sprint that touches no agent-facing tool
owes nothing here.

### 3. Add a planner method rule: prefer an existing repo pattern over new infrastructure; name the precedent or justify the new build. `[agent]` (mdreview-planner)
*Recurring over-build class — this is the second cycle running where the critic scoped down an
over-build/over-claim the planner half-flagged.* The bespoke RFC6455 WS client was new
infrastructure to honor a runtime-only rule that does not bind test tooling, when the repo **already**
drives CDP via Node's built-in `WebSocket` (sprint-09/-11 evidence). The planner named it as its
least-sure call *and proposed it anyway*; the critic dropped it. Theme-awareness retro flagged the
adjacent class (an unmeasured "and vice-versa" overclaim the critic disproved by measurement). The
fix that prevents both: a planner rule — **"before proposing new infrastructure (a new client,
script, or harness), search the repo for an existing pattern that already does this; if one exists,
use it and cite it; if you build new, justify why the existing one cannot serve."** The planner's
"flag your least-sure call" habit is doing real work (good — keep it; it fed the critic the target),
but it surfaced the doubt *without resolving it against precedent the planner could have found
itself*. This rule turns "I'm unsure, someone check me" into "I checked the repo first."

### 4. File the two named non-goals to `backlog.md` so they are not silently lost. `[feature]` (backlog)
*Accuracy hygiene; cheap.* Two coherent deferrals were named in-plan but are filed nowhere: **option
(b)** — the HTTP service publishing the *expected* wrapper `tools_hash` as an MCP-reachable comparand
(which would make staleness an all-MCP check the agent could make *autonomously*, the only path to
the brief's literal "detectable by the agent") — and the **pure-no-Node fallback** for the render
half (`--dump-dom` repoint + manual G7 spot-check). Both are in the plan's Non-goals and the sprint
Notes, but `backlog.md` has no entry. The `mcp-wrapper` retro established that named follow-ups get
filed at close; do the same here so option (b) is rediscoverable when someone next wants true
agent-autonomous staleness detection.

## What should NOT change

- **The retro-tickets were right to be `done`-on-arrival, one-per-commit.** Two tickets (not one) for
  the two independent viewer commits kept the commit→ticket mapping 1:1; both critics agreed. Don't
  bureaucratize a +4 CSS fix into a full pre-implementation cycle — suggestion 1 protects exactly
  this.
- **The sibling `agent_smoke.py` / `mcp_smoke.py` split.** Keeping the fast protocol smoke
  browser-free and the heavy agent loop separate is correct; do not merge them.
- **`layer: svc` for `mcp_server.py` + smokes.** Settled at G1 (NIT-3); adding an `mcp`/`tooling`
  layer is process scope-creep. Leave it.

## Metrics

- **G1 rounds:** 2 (r1 PASS-WITH-CONDITIONS: 0 BLOCKER / 2 SHOULD / 3 NIT; r2 PASS — no new issues).
- **G7 rounds:** 1 (first-pass PASS: 0 BLOCKER / 0 SHOULD / 1 NIT accepted-no-change).
- **Tickets shipped vs carried:** 6 shipped (MR-038–043), 0 carried.
- **Parks / BLOCKED:** 0.
- **Wrong load-bearing assumptions:** 0 overturned. Both SHOULDs hit *plan claims/tool-choices*, not
  load-bearing assumptions — and the planner had pre-flagged the WS-client (its least-sure call) and
  scoped staleness honestly was a wording fix, not a wrong premise. (Every code citation the critic
  checked at G1 was accurate.)
- **Cycle size:** 4 feature/docs commits + 2 retro-tickets. `app.py` **untouched** (G7-verified);
  `mcp_server.py` +53 (MR-040), `agent_smoke.py` +239 new (MR-041), `mcp_smoke.py` +36 (MR-042, 22→34
  assertions, 15→16 tools), docs +53 across 4 files (MR-043). Retro commits `dae815e` (+4) /
  `2ed9593` (+12) predate the cycle.
- **Recurring-class friction:** 1 — an over-build (the bespoke WS client) scoped down by the critic
  at G1, the same *class* the theme-awareness retro flagged (planner half-flags an over-claim/
  over-build it then ships anyway). Suggestion 3 names the missing rail (prefer existing repo pattern;
  cite or justify). The **operator-hot-patch antipattern** is the meta-trigger and has **not** been
  raised as a process suggestion before — suggestion 1 closes it.
