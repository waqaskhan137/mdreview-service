---
review_of: epics/agent-handoff-baton-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: PASS-WITH-NITS
status: resolved
---

# G1 Plan-Gate Review — agent-handoff-baton

Independent review of `epics/agent-handoff-baton-plan.md` against the locked, human-approved brief
(`requirements/agent-handoff-baton.md`, mdreview `ff60fa640e`). I do **not** re-litigate the locked
product decisions (Fork A, one-agent-per-review, interactive/no-sweep, no-free-text-box, co-editing
to issue #16). I judge the plan: decomposition, sequencing, validation recipe, footguns, internal
consistency. Every code claim below was read against the working tree.

## Verdict

**PASS-WITH-NITS.** G1 passes. No BLOCKER. The decomposition is clean, the sequencing is correct,
the load-bearing footguns are accurate against the code, and the MR-051 validation genuinely proves
the contract. The items below are SHOULD/NIT refinements the planner should fold into the tickets at
G2 grooming; none is a product fork and none needs another review round to clear G1.

## What I verified (claims that hold)

These are load-bearing and I confirmed each against the code, so the implementer can trust them:

- **`bump()` is unlocked** (`app.py:120-124`): bare `_read_json` + mutate + `_write`, no `with _lock`.
  The plan's central footgun — `/handoff` must take `_lock` itself and never call bare `bump()` — is
  **correct**. `PUT /source` holds `_lock` across `snapshot_round` + `_write` + `bump` (`app.py:475-478`),
  exactly the discipline the plan tells `/handoff` to mirror.
- **Route non-shadowing** (`app.py:454`): `re.fullmatch(r"/api/reviews/" + RID, path)` with
  `RID = ([A-Za-z0-9]{4,40})` (`app.py:47`). A `/handoff` suffix breaks that `fullmatch`, so the
  bare-id arm cannot swallow `/api/reviews/{id}/handoff`, and `handoff` is not a legal id continuation,
  so the new arm cannot shadow another. Placement after `/status` (`app.py:503-513`) and before
  `/history` (`app.py:515`) is sound. POST-only with GET falling to 404 is consistent with the existing
  arms.
- **`/status` additivity** (`app.py:503-513`): the handler returns a hand-built dict of three keys.
  Adding four more keys is purely additive; nothing is removed. MCP `get_status` proxies `/status`
  verbatim (`mcp_server.py:363-364`), so the new fields flow through with no code change and no
  reconnect. **Correct.**
- **`summary()` copies the whole meta dict** (`app.py:134`: `m = dict(meta(rid))`), so new `meta.json`
  keys flow through `list_reviews()` (`app.py:152-155`) for free. The plan's "do not redundantly touch
  `summary()`" is right — but see SHOULD-2 for a status-derivation interaction it misses.
- **409 convention** (`app.py:337-338`): illegal comment transitions already return `409` with
  `{"error", "status"}`. The lease-held `409` matches house style, and `mcp_server.py`'s `http()`
  raises `ToolError` on any non-2xx (`mcp_server.py:342-344`), so a foreign-owner `409` surfaces to
  the agent as a tool error. **Q4's default is safe and consistent.**
- **render-smoke selector grammar** (`scripts/render-smoke.sh:72`): the `_VALID` regex
  `^(#id | tag(.class)* | (.class)+)$` accepts exactly `#id`, `tag`, `tag.class.class`, `.class.class`
  and **rejects** attribute selectors, descendant combinators (any space), and pseudo-classes as bad
  usage (exit 2). The plan's `.sendagent` / `.turnbanner` / `.reclaim` are bare `.class` forms — all
  valid; its warning against `[data-act=…]` and `#dockbar .sendagent` is **accurate**.
- **Viewer anchors**: `#dockbar`/`#histbtn` (`viewer.html:171-176`), `#docmeta` (`viewer.html:160`),
  `lastSrc`/`lastCmt` (`viewer.html:203-204`), the 2s poll (`viewer.html:595-607`) with its
  in-gesture early-return (`viewer.html:600`), and the load-bearing ordering claim — line 603's source
  branch calls `load()`, and `load()` re-fetches `/status` and overwrites `lastSrc` at
  `viewer.html:319-321`, it does **not** set `lastSrc` inline — **all confirmed**. The "reload first,
  then banner from the same `/status` body" rule is the right fix for the toast/banner race.
- **MCP surface**: `route()` is a flat `if name == …` chain ending `return None` (`mcp_server.py:407`);
  `tools_hash` is sha256 over `TOOLS` + `INSTRUCTIONS` (`mcp_server.py:275-283`), so adding a tool
  changes it — the plan's "reconnect required, hash changes" is correct. The CDP interaction pattern
  the plan leans on is real: MR-049 drove a synthetic event headlessly and asserted a DOM flip
  (`none → block`) via `Runtime.evaluate`, and `agent_smoke.py` is the repo's Node-built-in-WebSocket
  CDP harness. So an interaction check is an **extension of an existing pattern**, not net-new tooling
  (but see SHOULD-1).
- **Decomposition + sequencing**: MR-051 (svc) ships invisibly with **no** UI/agent dependency — the
  server change is genuinely additive and self-contained; MR-052/053 both depend only on MR-051 and
  are mutually independent; sprint-14 = {MR-051}. **The chunk boundaries are clean and the dependency
  graph is right.** Highest existing ticket is MR-050, so MR-051/052/053 are the next free IDs. No
  active sprint exists, so sprint-14 is consistent.

## Findings

### SHOULD-1 — The MR-052 "CDP interaction check" understates the work; it is a timed multi-step drive, not a single read

The plan says the interaction check "follow[s] the repo's existing pattern (`agent_smoke.py` /
MR-049)." That pattern is real but the existing instances each do **one** navigate → wait → read a
single flipped property. The MR-052 check must drive a **time-dependent state machine across the 2s
`setInterval`**: click Send → wait for a poll tick to fire `POST /handoff` and flip `turn` → script a
`{state:working}` POST → wait for the next tick to repaint the banner → click reclaim → wait again.
The 2s poll cadence (`viewer.html:596`) means the harness must either wait real seconds per transition
or stub the interval, and the in-gesture early-return (`viewer.html:600`) means a tick is skipped while
a gesture is open — both affect timing. This is buildable on the MR-049 `Runtime.evaluate` pattern but
it is a new harness, not a parameterization of `agent_smoke.py` (which checks `naturalWidth>0`, never
clicks). **Action:** in MR-052's AC, name the timing model explicitly — drive synthetic clicks via
`Runtime.evaluate`, and either reduce the poll interval under test or assert against the post-tick
state with an explicit wait — so the implementer budgets for it instead of discovering it at G4.

### SHOULD-2 — `agent_status` flowing into `summary()` can perturb the derived dashboard `status` — confirm it does not

The plan correctly notes new meta keys flow through `summary()` for free (`app.py:134`), but stops
there. `summary()` also **derives** `status` from `feedback_updated` + comment counts
(`app.py:143-148`). The new keys do not feed that derivation today, so the dashboard is unaffected —
**but the plan never states that the handoff fields must stay out of the `status` derivation**, and a
later "show turn on the dashboard" temptation (explicitly a Non-goal: "No dashboard change") could
quietly couple them. **Action:** add one line to MR-051's AC: the curl round-trip asserts that a review
mid-handoff (`turn=agent`) still derives the **same** dashboard `status` it would without the baton
(i.e. `GET /api/reviews` `status` is unchanged by a handoff). This nails the "ships invisibly" claim
where it is actually checkable, and locks the Non-goal in a test.

### SHOULD-3 — The four-body-form dispatch has undefined precedence and no malformed-body fallback

The dispatch table keys on the presence of `to` / `state` / `by`, but the plan never states the
**precedence order** or the behavior for a body that matches none or several rows. Concretely:
`{to:"reviewer", by:"reviewer", state:"done"}` matches both the reclaim row (#4, has `by:reviewer`)
and the hand-back row (#3, has `state`); `{to:"reviewer"}` with neither `state` nor `by` matches
neither cleanly; `{}` matches nothing. On a no-auth control surface where any URL-holder can POST, an
unspecified branch is a real footgun (silently flips the baton, or 500s on a `.get` of a missing key).
**Action:** MR-051's AC should fix an explicit dispatch order (e.g. reclaim `by:reviewer` checked
before hand-back `state`, or make the four forms mutually exclusive by a single discriminator) and
define the fallback — a malformed/unrecognized body returns `400`, never a partial mutation. Add one
negative case to the curl smoke (`POST {}` → 400, `turn` unchanged).

### NIT-1 — `turn_updated` "bump only on actual flip" needs the idempotent-working case spelled into the smoke assertion

The smoke (step 6) checks idempotent `{to:agent}` does not re-bump `turn_updated`. Good. But it does
**not** assert the symmetric case the brief calls out: a `{state:working}` renew bumps `agent_status.at`
and leaves `turn_updated` **unchanged** (step 2 records this in a comment but does not capture-and-compare
`turn_updated` across the working call the way step 6 does for the flip). **Action:** in step 2, capture
`turn_updated` before and after the `{state:working}` claim and assert equality, so "working never bumps
the turn clock" is proven, not just asserted in prose.

### NIT-2 — Q2 (second tool vs mode) leaks a tool-name into MR-053 that the brief does not bless

The plan's Q2 default invents `take_turn(document_id, message?, owner)` for the lease ping. That is a
fine default, but the brief names only `hand_back` and "the `working` lease ping" generically. The
name `take_turn` reads like a reclaim (the viewer's reclaim is literally "take back the turn"),
which is the opposite of what it does (an agent claiming/renewing its lease while it already holds the
turn). **Action:** at G2, pick a name that reads as a lease heartbeat (`ping_working` / `claim_lease`
/ `renew_lease`) to avoid colliding semantically with the viewer's reclaim. Pure naming, zero design
impact.

## Open questions Q1–Q4 — assessment

All four are correctly classified as minor implementation clarifications with safe defaults; none
hides a product fork. Specifically:

- **Q1 (owner client-supplied):** safe and **forced** by the code — the service has no session/auth
  concept to mint identity from. Correct.
- **Q2 (second tool vs mode):** safe; either is buildable. See NIT-2 on the chosen name only.
- **Q3 (staleness N):** safe; viewer-side constant, no server involvement, preserves the no-scheduler
  property. Correct.
- **Q4 (409 vs 200 on foreign owner):** safe and **consistent with the codebase** — `409` matches the
  comment-transition convention (`app.py:337-338`) and surfaces cleanly through `http()`'s `ToolError`
  raise (`mcp_server.py:342-344`). Correct.

No BLOCKER-FOR-HUMAN; the plan's own conclusion on this is right.

## Scope / Non-goals check

No scope leak. Every Non-goal in the plan traces to a locked decision in the brief (no daemon, no
sweep, no server-enforced single-writer, no free-text box, no co-editing, no new storage file, no
auth, no dashboard change). The plan adds no adjacent work. The one place the Non-goals are *testable*
— "ships invisibly / no dashboard change" — is where SHOULD-2 asks for an explicit assertion.

## Resolution log

### Round 1 — 2026-06-23 (staff-critic, independent)

- Verdict **PASS-WITH-NITS**; **G1 passes**, no BLOCKER. Tickets MR-051/052/053 may be created.
- Verified against the working tree: `bump()` unlocked (`app.py:120-124`), `PUT /source` lock
  discipline (`app.py:475-478`), route non-shadowing (`app.py:454` + `RID` at `:47`), `/status`
  additivity (`app.py:503-513`), `summary()` whole-dict copy (`app.py:134`), 409 convention
  (`app.py:337-338`), render-smoke grammar (`scripts/render-smoke.sh:72` rejects attribute selectors
  and combinators as claimed), viewer anchors + poll ordering (`viewer.html:160,171-176,203-204,
  319-321,595-607`), MCP `get_status` passthrough + `tools_hash` + `http()` raise
  (`mcp_server.py:363-364,275-283,342-344`), and the CDP-interaction precedent (MR-049 + `agent_smoke.py`).
  All load-bearing claims hold.
- Raised: SHOULD-1 (MR-052 interaction check is a timed multi-step drive, budget for it), SHOULD-2
  (assert handoff fields do not perturb the derived dashboard `status`), SHOULD-3 (define dispatch
  precedence + malformed-body 400), NIT-1 (assert `turn_updated` unchanged across a `working` renew),
  NIT-2 (rename the lease-ping tool away from "take_turn").
- These are G2-grooming refinements for the planner to fold into the ticket ACs; they do **not** gate
  G1 and need no further review round. Set this review `status: resolved` once the planner has
  reflected SHOULD-1..3 into the MR-051/MR-052 acceptance criteria (NIT-1/2 optional).

### Round 2 — 2026-06-23 (orchestrator, fold-in confirmed) — RESOLVED

All five findings reflected in the ticket ACs (tickets created at G2):

- **SHOULD-1** → MR-052 AC "Interaction proof": the node-CDP check is specified as a **timed,
  multi-step drive across the 2s poll** (steps a–d), not a single navigate-and-read.
- **SHOULD-2** → MR-051 AC "Dashboard status invariance": asserts a `turn=agent` review derives the
  **same** `summary()` status/counts (`app.py:143-148`), `summary()` untouched, checked via
  `GET /api/reviews` in the smoke.
- **SHOULD-3** → MR-051 AC "Explicit dispatch precedence + malformed-body guard": pinned order
  (reclaim → hand-back → flip → lease) so `{to:reviewer,by:reviewer,state:done}` is unambiguous, plus
  a **`400`** on an unrecognized body with a negative smoke case.
- **NIT-1** → MR-051 AC + Validation: `turn_updated` captured-and-compared **unchanged** across a
  `{state:working}` renew.
- **NIT-2** → MR-053 AC: lease-ping tool named **`ping_working`** (not `take_turn`).

Verdict stands **PASS-WITH-NITS**; G1 cleared. Review **resolved**.
