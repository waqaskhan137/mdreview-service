---
epic: legacy-feedback-retire
status: active        # draft | active | done  (G1 passed 2026-06-19)
created: 2026-06-19
source: requirements/legacy-feedback-retire.md
gate: passed 2026-06-19   # G1 (Plan Gate): PASS on round 2 (r2 review); tickets unblocked
review: reviews/legacy-feedback-retire-plan-review-2026-06-19-r2.md   # G1: r1 CHANGES-REQUESTED → revised → r2 PASS
related_sprints: [sprint-13]
related_tickets: [MR-046, MR-047]
---

# Legacy feedback write-path retirement Plan

The viewer stopped writing notes/feedback in MR-036 (`26411e4`, ~24h before the audit) — it
authors **comments** now. The old `POST /api/reviews/{id}/feedback` write path and the
`feedback_updated` *write* are frozen: nothing in this workspace or the running container calls
them. This epic retires the **frozen write surface** (the POST write body → `410 Gone`, the `bump`,
the field initialiser) **as a deliberate documented-contract change** — landing `app.py` and the
agent docs (`CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/future-mcp.md`) together in one sprint — while
leaving the **read path completely intact**, because 12 live reviews on the `:8139` volume still carry
real reviewer notes and a real `feedback_updated` timestamp that the dashboard and `summary()` status
both depend on. (The MCP `get_status` description already leads with `comments_updated`, so no
`mcp_server.py` change is owed — see "MCP edit — right-sized".) This is cleanup that respects an
installed base, not a free delete: the audit it acts on was over-corrected twice (live-volume check,
then staff-critic) precisely because "the current viewer stopped writing X" was repeatedly mistaken
for "X is empty."

**Source requirement:** [`requirements/legacy-feedback-retire.md`](../requirements/legacy-feedback-retire.md)
— the original brief, kept verbatim. Full evidence + revision history in
[`reviews/ponytail-audit-2026-06-19.md`](../../../reviews/ponytail-audit-2026-06-19.md).

## Product goal

The documented agent contract no longer advertises a write surface that nothing writes to, on a
no-auth public-ish service. Concretely, when this epic is done:

- `POST /api/reviews/{id}/feedback` no longer writes — it returns `410 Gone` ("use comments") and is
  no longer a documented write endpoint inviting external callers to overwrite a review's
  `notes.json`/`feedback.md`.
- The "Detecting the human is done" guidance in `CLAUDE.md` and `AGENTS.md` tells agents to watch
  **`comments_updated`** (the live signal), not the dead `feedback_updated` write.
- No doc asserts the old heuristic is in force — including `docs/future-mcp.md:61` ("…is unchanged"),
  which is corrected. The MCP `get_status` tool description already matches reality (no edit needed).
- **Nothing a real review depends on changes:** all 45 live reviews keep their derived status, the
  dashboard keeps sorting by recency, `GET /feedback` still returns every persisted note, and
  `GET /history/{n}` still returns archived `feedback.md`/`notes.json`. Zero data is lost; zero
  read behaviour changes.

## Core design principle

**Retire only what is *written*, never what is *read*.** The single fact that keeps this design
coherent: `feedback_updated` and the `notes/feedback` files are **write-dead but read-live**. So the
cut is surgical — remove the three write sites (the route's POST write body → `410 Gone`, the `bump`
call, the `create_review` initialiser) and the *documentation that advertises them as a write
contract* — and leave **every reader untouched and default-safe**: `summary()` still reads
`feedback_updated` via `.get()` (so the 12 live `fu>0` reviews keep their status), `dashboard.html`
still sorts by it, the `status` payload still emits it, `GET /feedback` and `GET /history` still read
the files. A missing key on a *new* review must degrade to today's "no feedback yet" behaviour, not flip
a populated review to the wrong status.

## Recommended approach

### Service (`app.py`)

Three write sites are removed; every reader is preserved verbatim. Verified call sites in the
current code (line numbers re-checked against the working tree — the brief's numbers had drifted):

**Remove (write surface):**
- The **write body** of the `POST` arm of the `/feedback` route — `app.py:495–501` inside the
  `re.fullmatch(r"/api/reviews/" + RID + r"/feedback", path)` block that opens at `app.py:481`.
  Replace the body (the two `_write`s + `bump(rid, "feedback_updated")`) with a deliberate
  deprecation response: `if m == "POST": return self._json(410, {"error": "gone, use comments"})`
  (no `_body_json`, no `_lock`, no write — a pure signal; see the 410 decision below). The
  `if m == "GET":` arm (`app.py:486–494`) stays exactly as-is. (We keep a 3-line POST arm rather than
  deleting it so the response is an explicit `410 Gone`, not a generic 404 fall-through.)
- The `bump(rid, "feedback_updated")` call — `app.py:500` (gone with the removed write body). This is
  the only writer of the field. `bump()` itself (`app.py:120`) stays — it is still called for
  `source_updated` and `comments_updated`.
- The `"feedback_updated": 0` initialiser in `create_review` — `app.py:193`. New reviews simply
  won't carry the key; `summary()`/`status` already default it (see "Preserve" below), so this is
  default-safe.

**Preserve exactly (read surface — touching any of these is out of scope):**
- `GET /feedback` notes union + markdown — `app.py:486–494` (`out["markdown"]` from `feedback.md`
  at `:488`; `out["notes"]` = on-disk notes + comment projection at `:492–493`).
- `summary()` note counting and the status derivation — `app.py:127–149`, including the
  `if not m.get("feedback_updated") and total == 0:` guard at `app.py:143`. **Keep this branch
  as-is** — it holds new/empty reviews (Pop B) in `awaiting`; deleting it regresses 31 live reviews
  plus every future new one (see the design fork below — we do **not** delete it, contra one reading
  of the audit).
- The `status` payload's `"feedback_updated": mt.get("feedback_updated", 0)` — `app.py:511`. Stays:
  the dashboard reads it, and emitting a stable default for new reviews is back-compat-correct.
- The `feedback_url` field in the `POST /api/reviews` create response (`app.py:449`) — **untouched**;
  it is the `GET /feedback` URL (read semantics), not the removed write. Noted explicitly so a future
  reader does not think the sweep missed it (G1 nitpick).
- `snapshot_round` copying `feedback.md`/`notes.json` — `app.py:169` — and the `GET /history/{n}`
  read-back at `app.py:539–541`. Untouched.
- The header docstring API block (`app.py:8–27`) — line 15 (`POST … /feedback … (viewer saves here)`)
  is now stale: rewrite it to reflect the deprecation (e.g. `POST … /feedback → 410 (gone; use
  comments)`) or drop it, matching the route change. The GET line (`:14`) reads cleanly standalone and
  stays as-is (confirm once its POST sibling is gone — G1 nitpick). This is doc-in-code, lands with
  the svc ticket.
- The `/` descriptor's `"collect_feedback": "GET /api/reviews/{id}/feedback"` — `app.py:430` — is
  already GET-only; no change needed, confirm it doesn't advertise the POST.

### The one real design fork — the `summary()` `feedback_updated` guard

The brief flags `app.py:143` (`if not m.get("feedback_updated") and total == 0`) and the audit says
"delete that branch deliberately if you go ahead." I traced the status derivation in
`summary()` (`app.py:127–149`) for every population that actually exists on the live `:8139` volume
(45 reviews; verified this session), so the decision rests on measured behaviour, not prose.

The guard is the **first** arm of a three-way derivation:

```python
if not m.get("feedback_updated") and total == 0:   # app.py:143 — the guard
    status = "awaiting"
elif total and addressed == total:                  # app.py:145
    status = "resolved"
else:                                                # app.py:147
    status = "feedback"
```

| population (live count) | `feedback_updated` on disk | `total` | status (KEEP guard) | status (guard branch DELETED) | guard role |
|---|---|---|---|---|---|
| **Pop A** — review with notes/comments (12: `fu>0`; plus any `fu==0, total>0`) | `>0` (all 12) | `>=1` | `feedback`/`resolved` ✓ | `feedback`/`resolved` ✓ (same) | irrelevant — `total>=1` skips the guard |
| **Pop B** — brand-new / empty review, no notes, no comments (**31 live**, plus every future new review) | absent/0 → falsy | 0 | `awaiting` ✓ | **`feedback` ✗ (regression)** | **load-bearing** — only the guard keeps these out of `feedback` |
| **Pop C** — `fu>0, total==0` (the contested row) | `>0` | 0 | `feedback` | `feedback` (same) | **does not occur** — 0 live instances; guard False here either way, falls to `else: feedback` regardless |

**Decision: KEEP the guard, do not delete it, and keep `summary()` reading the field via `.get()`.**
The guard's real job — verified against code and the live volume — is to hold **new/empty** reviews
(Pop B) in `awaiting`. Deleting its branch flips every Pop-B review from `awaiting` to `feedback`,
which is semantically wrong (an untouched review with no feedback and no comments is *awaiting* a
reviewer, not *in feedback*). That is **31 of 45 live reviews today, plus every review created from
here on** — the largest and growing cohort, not a corner case.

Two corrections to the inherited framing, both measured, both material to the AC below:

- The "12 live reviews" the audit protected are **Pop A** (`fu>0, total>=1`) — all of them have
  `notes_total` in `{1,2,3,4,6,8,12}`. For Pop A the guard is **irrelevant**: `total>=1` makes its
  `and total == 0` False, so they derive `feedback`/`resolved` *whether the guard is kept or its
  branch is deleted*. The guard does not protect the 12.
- The contested "human cleared feedback" case (**Pop C**, `fu>0, total==0`) **does not regress and
  does not exist**: `not m.get("feedback_updated")` is False (the field is truthy), so the guard is
  False and the case falls to `else: feedback` — identically with the branch kept or deleted. Zero
  live reviews are in this state. (The only way to *flip* Pop C would be to **rewrite** the guard to
  `if total == 0:`, dropping the field reference — a third option nobody proposed.)

The guard is a *reader*, and the core principle is "never remove a reader." We remove the field's
*writer*; the reader keeps working because `.get("feedback_updated")` returns the persisted value for
old reviews and a falsy default for new ones — both correct above. This is recorded as the plan's
least-certain decision and is the first thing the G1 reviewer should stress-test — but note the
contested fork is now resolved by measurement: the guard protects Pop B (new/empty), full stop.

### Safety precondition for removing the route (the deprecation-vs-delete fork)

The audit is explicit: hard-removing `POST /feedback` is only safe given "no *deployed* pre-MR-036
viewer + stop documenting it," and the grep "cannot see other deployments, saved old viewers, or
scripts using the documented `curl` recipe" on a no-auth service. I resolve this fork as follows:

**Remove the write behaviour and return `410 Gone` from the now-dead POST arm** (not a silent
fall-through to 404), justified by: (a) the documentation that *invites* external callers is removed
in the same sprint, and (b) the only known deployment is the `:8139` container, whose viewer is
post-MR-036 and does not POST feedback (`viewer.html:293` — "the shared server-side comments are the
single feedback surface"; no `POST /feedback` anywhere in `viewer.html`). Stated assumption: `:8139`
is the only live deployment (verified independently this session — see Verification).

**404-vs-410 decision — default to `410 Gone` (changed from the prior draft's "straight removal,
410 is the reviewer's lever").** Two independent signals point the same way: the audit's "no-auth,
public-ish, an undiscovered caller may still run the documented `curl` recipe" worry, and the G1
reviewer's lean. Mechanics (verified): once the `if m == "POST":` arm is deleted, a `POST /feedback`
still matches the path block (`app.py:481`, method-agnostic `re.fullmatch`), passes `_exists`,
matches neither remaining arm, and exits to the final default → `404 {"error": "no route"}`
(`app.py:662`). A bare 404 is **indistinguishable from a typo'd URL**; a deliberate **`410 Gone`**
with a one-line `{"error":"gone","use":"comments"}` body is a self-documenting deprecation signal to
exactly the caller the audit worries about, at ~3 lines' cost. Implementation: keep a minimal
`if m == "POST": return self._json(410, {"error":"gone, use comments"})` arm in place of the deleted
write body — it performs **no write, no `bump`** (the field's writer is still gone; this is a pure
signal). The only cost is a vestigial 3-line handler, which is acceptable for an explicit signal on a
no-auth surface. (The deprecation-comment-then-remove-later middle option is still rejected: a stub
that *200s* and is undocumented carries the same exposure with none of the cleanup benefit — 410 is
not that; it writes nothing.) The Verification curl below expects **410**, not 404.

### Docs (`CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/future-mcp.md`)

The contract surface that advertises the write must change in lockstep with `app.py` — this is the
"land it together" requirement, not optional polish. (`mcp_server.py` is listed below only to record
the **no-change** decision — its `get_status` description already leads with `comments_updated`.):

- **`CLAUDE.md:80–87`** and **`AGENTS.md:36–43`** — the "Detecting the human is done" section. Both
  carry the byte-identical, now-wrong line "Poll `status_url` and watch `feedback_updated` … treat
  the round as complete." Rewrite both to watch **`comments_updated`** (the live signal the viewer
  actually bumps), keeping the "or tell the human to reply 'done'" option. The `status` comment in
  the contract snippet (`CLAUDE.md:24`, `AGENTS.md:24`, `# {"source_updated":…, "feedback_updated":…}`)
  is a *read*-shape comment and stays accurate (the field is still emitted) — leave it, optionally
  add `comments_updated` to the comment for clarity.
- **`README.md:52`** — the API table row `POST /api/reviews/{id}/feedback … (legacy notes write; the
  viewer now authors comments instead)`. Remove this row (the write no longer exists). Keep the
  `GET /feedback` row (`README.md:51`) and the `status` row (`README.md:53`) exactly.
- **`mcp_server.py:108–109` — MCP edit right-sized to *no change* (decision).** I re-read the live
  description: it already reads *"Cheap poll: a review's source_updated, feedback_updated, and
  comments_updated timestamps. **Watch comments_updated for new/changed comment threads.**"* It
  **already leads the "watch" guidance with `comments_updated`** and merely *lists* `feedback_updated`
  as one of three timestamps the call returns — which stays factually true (the field is still
  emitted). There is **no MCP tool that POSTs feedback** (confirmed — no `post_feedback`/
  `update_feedback` in the tool list; `get_feedback` is GET-only at `mcp_server.py:101–104`), so
  nothing is removed and there are **no schema changes**. **Decision: drop the MCP description edit
  and the separate MCP ticket entirely** — the only conceivable change is de-emphasising one word in
  a sentence that already says the right thing, which is not worth a ticket. **Because no
  `mcp_server.py` change lands, no MCP-client reconnect is required** — the heavyweight reconnect
  ceremony (`server_info` `tools_hash` vs `--print-version`) is removed from this epic. This collapses
  the epic to **2 tickets: svc + docs.** (If a future cycle wants the de-emphasis, it is a trivial
  one-word docs change that *would* then carry the reconnect note — out of scope here.)
- **`docs/future-mcp.md:36, 61`** — line 36's `get_status` table row lists `{…, feedback_updated, …}`
  (still accurate — the field is still emitted; leave). **Line 61 reads verbatim: *"The 'human is
  done' heuristic in `AGENTS.md` is unchanged."* This is a reader that Phase 2 falsifies** — Phase 2
  rewrites exactly that heuristic (`feedback_updated` → `comments_updated`), so the sentence becomes a
  stale falsehood in the MCP design-record doc. **The docs ticket MUST edit line 61** — either drop
  the "is unchanged" clause or repoint it ("…now watches `comments_updated`, per the legacy-feedback
  retirement"). This is a one-line edit; it is in Phase-2 docs scope, not optional. (Caught at G1:
  the original sweep wrongly marked this file "needs no edit" — Assumption #5, now flipped.)

### AGENTS.md / CLAUDE.md dedup (finding 2) — scoped OUT of this epic

The audit explicitly downgraded this from "clean win" to "a preference with trade-offs." `AGENTS.md`
is named by `README.md:186` as *the* agent-integration doc, referenced by `docs/future-mcp.md:61`,
and the delivery process treats README/CLAUDE/AGENTS as three co-updated docs (Definition of Done
section). Collapsing `AGENTS.md` to a pointer is a real change with real costs and **is not what this
epic is about**. Critically, **finding 1 already forces the only edit the dedup would touch first** —
the duplicated "watch `feedback_updated`" lines in both docs get rewritten by the docs ticket here,
so the highest-drift line is fixed as a side effect without taking on the dedup project. The residual
duplication is logged as an **out-of-epic backlog follow-up** (drift-reduction: single-source +
generated/condensed view), not smuggled into scope. See Non-goals.

## Rollout phases

Two phases, each independently shippable. Phase 1 is the surgical, lowest-risk cut; Phase 2 lands the
contract change. They could ship in one sprint; the split keeps the "genuinely free" cut separable
from the "contract change" if the G1 reviewer wants to stage them.

### Phase 1 — Remove the dead write surface in `app.py` (genuinely free)

- Replace the `POST /feedback` write body (`app.py:495–501`) with a `410 Gone` deprecation response
  (no write, no `bump` — see the 410 decision), removing the `bump(rid, "feedback_updated")` it
  contained (`:500`) and the `"feedback_updated": 0` initialiser in `create_review` (`:193`). Update
  the in-file API docstring (`app.py:8–27`) to drop the POST-write line.
- Keep `summary()` guard, `status` payload, `GET /feedback`, `snapshot_round`, history read-back —
  all untouched.
- Validates with `py_compile`; behaviour-verifiable that the read path and new/empty-review status
  are unchanged, and that `POST /feedback` now returns 410 (curl examples in Verification).

### Phase 2 — Land the documented-contract change (docs)

- Rewrite the "human is done" guidance in `CLAUDE.md` + `AGENTS.md` to `comments_updated`.
- Remove the `POST /feedback` row from the `README.md` API table.
- Fix `docs/future-mcp.md:61` ("the heuristic … is unchanged" → drop/repoint to `comments_updated`),
  now that Phase 2 changes that heuristic.
- This phase carries the "contract change" weight; it must not merge without Phase 1 (otherwise the
  docs would describe a route that still exists). Order: Phase 1 svc, then Phase 2 docs.
- **MCP `get_status` description: no change planned.** The on-disk text (`mcp_server.py:108–109`)
  already leads with *"Watch comments_updated for new/changed comment threads"* and only *lists*
  `feedback_updated` as one of three still-emitted timestamps (factually true). There is no
  separate MCP ticket and no reconnect ceremony (see "MCP edit — right-sized" below).

## Non-goals

- **The read path is untouchable.** `GET /feedback` (`notes[]` union + `markdown`), `summary()`
  note-counting, `GET /history`/`/history/{n}` read-back, and `snapshot_round`'s copy of
  `feedback.md`/`notes.json` are explicitly **out of scope**. 61 non-empty `notes.json`/`feedback.md`
  files across 45 reviews depend on them. (Memory `legacy-notes-feedback-load-bearing`.)
- **Do not delete the `summary()` `feedback_updated` guard** (`app.py:143`) or remove the field from
  the `status` payload (`app.py:511`) or `dashboard.html` (`:117`). Those are *readers*; deleting the
  guard branch regresses the 31 new/empty (Pop B) reviews `awaiting`→`feedback` and every future new
  review. (See the design-fork table.)
- **AGENTS.md / CLAUDE.md dedup (finding 2)** — not in this epic. Logged as a backlog follow-up
  (drift-reduction via single-source/condensed view), per the audit's "preference with trade-offs."
- **`_CTYPES` `.bmp`/`.avif`/`.ico` (finding 3)** — explicit non-cut (`yagni`, `app.py:81–96`). Not
  touched.
- **The two smoke harnesses `mcp_smoke.py` / `agent_smoke.py` (finding 4)** — explicit non-cut. If
  anything, an out-of-epic *investigation note* (are they redundant?), never a refactor in this epic.
- **No `mcp_server.py` change** — its `get_status` description already leads with `comments_updated`
  (`mcp_server.py:108–109`); the previously-planned third (MCP) ticket is dropped and no MCP-client
  reconnect is owed by this epic. (See "MCP edit — right-sized".)
- **Frozen historical records are NOT retro-edited** — `docs/process/epics/mcp-wrapper-plan.md:110`,
  `docs/process/epics/dashboard-redesign-plan.md:39`, and `tickets/MR-002-list-and-summary.md:23`
  mention `feedback_updated` but are shipped epics/tickets; per the README's "never edit the brief /
  history" ethos they stay as-is. Named here so the sweep is provably complete, not silently
  incomplete (G1 nitpick). (`docs/future-mcp.md` is a *live design-record* doc, not a frozen ticket —
  hence it **is** edited; the distinction is the "is unchanged" assertion at `:61` that Phase 2
  falsifies.)
- **No new dependency, no new file, no product-page change.** This is svc + docs only. `dashboard.html`
  is **read** by the design (it sorts by `feedback_updated`) but **not edited**.

## Key constraints

- **Stdlib-only / zero pip** — this epic *removes* code and a doc surface; it adds nothing. Net deps:
  -0. No vendoring, no new asset.
- **No product page is touched** (`viewer.html` / `dashboard.html` / `static/**` unchanged) — so the
  G7 sprint-close evidence owed is the **container rebuild + `curl /healthz` + `curl /api/reviews`**
  smoke, **not** a `scripts/render-smoke.sh` per-page DOM assertion or screenshot (G7 pass-condition
  row: the per-page render evidence is owed "only if a product page was touched"). State this in the
  sprint file so the G7 reviewer doesn't flag a missing render-smoke as non-compliance.
- **Validation gate is `python3 -m py_compile app.py`** for the svc ticket; docs tickets validate by
  inspection (no test framework). No `docker build` change required (no `Dockerfile`/served-file
  change — nothing added to the `COPY` line).
- **Single-file regex router**: we are *replacing the body* of an existing arm in the
  `re.fullmatch(.../feedback)` block (`app.py:481`), not adding a route — no shadowing risk, no
  id-regex change. The `GET` arm (the first arm, `app.py:486–494`) must remain reachable; it is
  unaffected. The `POST` arm stays present but now returns `410 Gone` instead of writing.
- **Overwrite-based persistence**: the removed POST was the *only* overwriter of `notes.json`/
  `feedback.md` outside `snapshot_round`/`create_review`. Removing it means those files become
  strictly append-on-create + history-archive; no migration, existing files are read as-is.
- **Back-compat of `meta.json`**: after Phase 1, new reviews lack the `feedback_updated` key. Every
  reader already uses `m.get("feedback_updated")` / `mt.get("feedback_updated", 0)` — confirmed at
  `app.py:143, 511` and `dashboard.html:117` (`r.feedback_updated||0`). **No reader assumes
  presence.** This must hold; an AC verifies a brand-new review's `/status` returns
  `"feedback_updated": 0` and its dashboard status is `awaiting`.
- **No-auth service**: the write removal *reduces* exposure (one fewer unauthenticated write surface).
  The safety precondition is discharged by removing the inviting docs in the same sprint and returning
  an explicit `410 Gone` (not a silent 404) to any straggler caller (see the 404-vs-410 decision).
- **No MCP change, no MCP reconnect.** `mcp_server.py` is not edited (its `get_status` description
  already leads with `comments_updated`), so the stdio-server staleness/reconnect concern does not
  apply to this epic. HTTP/doc changes need no reconnect.
- **Commits** keep the `Co-Authored-By: Claude` trailer and reference the ticket ID; dates
  `Europe/London`.

## Preferred execution order

1. **Phase 1 — svc cut** (`app.py`): remove the POST handler + `bump` + initialiser + docstring line
   (return `410 Gone` from the now-removed POST arm — see "404-vs-410" decision below).
   `py_compile`; curl-verify read path and new/empty-review status unchanged. Smallest, lowest-risk,
   and a prerequisite for the docs.
2. **Phase 2 — docs sweep** (`CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/future-mcp.md`): rewrite
   "human is done" → `comments_updated`; drop the `POST /feedback` README row; fix
   `docs/future-mcp.md:61`'s "…is unchanged" line. Depends on (1) being merged so docs never describe
   a route that still exists. **No `mcp_server.py` change** (its description already leads with
   `comments_updated`; see "MCP edit — right-sized") — so no MCP-client reconnect in this epic.

## Ticket breakdown

How this epic decomposes into tickets (create them in `tickets/` **after G1**, then link here). IDs
are placeholders — the orchestrator allocates real IDs (highest existing is MR-045).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-### | Remove dead `POST /feedback` write handler (return `410 Gone`), `feedback_updated` bump + initialiser; keep all readers | svc | 1 |
| MR-### | Docs: rewrite "human is done" → `comments_updated` (CLAUDE.md + AGENTS.md); drop `POST /feedback` row from README API table; fix `docs/future-mcp.md:61` "…is unchanged" | docs | 2 |

**Two tickets, both in sprint-13** (svc before docs). The previously-planned third ticket (reword the
MCP `get_status` description) is **dropped**: the on-disk description already leads with
`comments_updated`, so there is nothing to change and no MCP-client reconnect is owed (see "MCP edit —
right-sized"). `docs/future-mcp.md:61` is folded into the docs ticket (it is the one MCP-doc reader
the heuristic change actually falsifies).

**Atomicity / "land together" granularity (explicit):** the brief's hard constraint (a) — "land
`app.py` + both docs together" — is satisfied at **sprint granularity**: both tickets ship in
**sprint-13**, svc-before-docs, with the docs sweep a non-carry-over same-sprint obligation (per the
process's Definition-of-Done same-sprint-docs rule and the G7 close). It is **not** commit
granularity (the svc cut and the docs sweep are two commits). On this single-deploy, no-CD repo
nothing ships mid-sprint, so the inter-ticket window is **internal-only** — not a live exposure. This
is stated here so the G7 reviewer reads "atomic at the sprint boundary," not a contradiction with the
brief's "land atomically."

## Risks & mitigations

- **An undiscovered deployment still runs a pre-MR-036 viewer that POSTs feedback.** The grep covers
  only `/Users/apple/Dev/personal` + the `:8139` container. *Mitigation:* the safety precondition is
  discharged by removing the inviting docs surface in the same sprint **and** returning a deliberate
  **`410 Gone` + "use comments"** body from the now-dead POST arm (the default decision, not a
  fallback) — so any straggler caller gets an explicit, self-documenting deprecation signal rather
  than a 404 that reads as a typo'd URL. Assumption ":8139 is the only deployment" is stated and was
  verified live this session.
- **Deleting the `summary()` guard would silently regress every new/empty review (Pop B) to `feedback`.**
  *Mitigation:* the plan KEEPS the guard (design-fork table, Pop B is load-bearing); the AC explicitly
  verifies that **a freshly created review (no notes, no comments) still derives `awaiting`** after the
  change, and that the 31 currently-`awaiting` reviews on the live `:8139` volume **stay `awaiting`**.
  (The earlier framing — "a review with `fu>0, total==0` must not show `awaiting`" — tested Pop C, a
  state no review is in and that passes vacuously on both a no-op and a broken impl; it is removed.)
- **A new review missing the `feedback_updated` key breaks a reader that assumed presence.**
  *Mitigation:* verified every reader uses `.get(...)`/`||0` (`app.py:143, 511`, `dashboard.html:117`);
  AC checks a fresh review's `/status` and dashboard status.
- **Docs and route drift apart (route changed but a doc still describes the POST write).**
  *Mitigation:* execution order forces svc-before-docs within one sprint; the Definition of Done
  requires durable behaviour changes reflected in README/CLAUDE/AGENTS in the same change (or a
  same-sprint docs-sweep). The docs ticket sweep explicitly includes `docs/future-mcp.md:61` (the
  reader the G1 review caught) so no doc is left asserting the old heuristic.
- **A reader of the `feedback_updated` write was missed in the sweep.** *Mitigation:* the verified
  reader list is `summary()` (`app.py:143`), the `status` payload (`:511`), `dashboard.html:117`,
  `GET /feedback`, `snapshot_round`/history — all preserved; the doc readers are
  `CLAUDE.md`/`AGENTS.md`/`README.md`/`docs/future-mcp.md:61`, all in the Phase-2 docs ticket. No
  `mcp_server.py` change is needed (its description already leads with `comments_updated`), so no MCP
  reconnect risk exists for this epic.

## Verification

All commands assume a freshly rebuilt container. The live evidence below was checked **this session**
against the running `mdreview` container on `:8139` (45 reviews; 12 with `feedback_updated > 0`; 14
with `notes_total > 0`) — the load-bearing-data claim is real, not inherited from the audit.

**Service (`py_compile` + behavioural curl):**

```bash
python3 -m py_compile app.py          # gate; must pass

BASE=http://localhost:8137            # or a throwaway rebuild; do NOT compose over :8139

# 1. POST /feedback no longer writes (was 200); it now returns 410 Gone (the deliberate signal).
rid=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"markdown":"# t","title":"t"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -w ' <- %{http_code}\n' -X POST "$BASE/api/reviews/$rid/feedback" \
  -H 'Content-Type: application/json' -d '{"markdown":"x","notes":[]}'
# expect: {"error": "gone, use comments"} <- 410   (NOT 200, NOT 404; no write performed)

# 2. Read path intact: GET /feedback still returns markdown + notes union.
curl -s "$BASE/api/reviews/$rid/feedback" | python3 -c \
 'import sys,json;d=json.load(sys.stdin);print("keys",sorted(set(d)&{"markdown","notes"}))'
# expect: keys ['markdown', 'notes']

# 3. New review back-compat: status defaults feedback_updated to 0, derived status is awaiting.
curl -s "$BASE/api/reviews/$rid/status" | python3 -c \
 'import sys,json;d=json.load(sys.stdin);print("feedback_updated",d.get("feedback_updated"));assert d.get("feedback_updated")==0'
curl -s "$BASE/api/reviews" | python3 -c \
 'import sys,json;rs=json.load(sys.stdin)["reviews"];m={r["id"]:r["status"] for r in rs};print("status",m.get("'"$rid"'"))'
# expect: feedback_updated 0 ; status awaiting
```

**Guard non-regression — the actual safety AC (Pop B / new+empty reviews stay `awaiting`):**

```bash
# (a) A FRESH review (no notes, no comments) must still derive "awaiting" after the change.
#     This is the load-bearing case: the guard's job is to hold new/empty reviews out of "feedback".
#     ($rid is the just-created review from step 3 above — no comments authored on it.)
curl -s "$BASE/api/reviews" | python3 -c \
 'import sys,json;rs=json.load(sys.stdin)["reviews"];m={r["id"]:r["status"] for r in rs};s=m.get("'"$rid"'");print("fresh-review-status",s);assert s=="awaiting", s'
# expect: fresh-review-status awaiting

# (b) The 31 currently-"awaiting" reviews on the live volume (fu==0, total==0) must STAY "awaiting"
#     after a rebuild on a copy of the :8139 volume — none flip to "feedback".
curl -s http://localhost:8139/api/reviews | python3 -c '
import sys,json
rs=json.load(sys.stdin)["reviews"]
empty=[r for r in rs if r.get("feedback_updated",0)==0 and r.get("notes_total",0)==0]
flipped=[r["id"] for r in empty if r.get("status")!="awaiting"]
print("empty/new reviews:", len(empty), "| flipped-off-awaiting:", flipped)
# expect: empty/new reviews: 31 | flipped-off-awaiting: []  (guard preserved every Pop-B review)
'
```

(Note the earlier check — "no review with `fu>0, total==0` shows `awaiting`" — is intentionally
*removed*: it tested Pop C, which has **0 live instances** and passes vacuously on a no-op and on a
broken impl alike. The two checks above test Pop B, the population the guard actually protects.)

**Docs (inspection):**

- `grep -n "feedback_updated" CLAUDE.md AGENTS.md` — the "Detecting the human is done" bullet must now
  say `comments_updated` in both; the only surviving `feedback_updated` mentions are the read-shape
  status comment (`:24`), which is correct.
- `grep -n "POST .*reviews/{id}/feedback" README.md` — the API-table write row is gone; the
  `GET /feedback` and `status` rows remain.
- `grep -n "unchanged" docs/future-mcp.md` — line 61's "the heuristic … is unchanged" is gone or
  repointed to `comments_updated`; no doc asserts the old heuristic is in force. (`:36`'s `get_status`
  table row stays — the field is still emitted.)
- **No MCP check / no reconnect.** `mcp_server.py` is not edited this epic (its `get_status`
  description already leads with `comments_updated`), so there is no description change to propagate and
  no client reconnect to verify.

**Render smoke:** **not owed.** No product page (`viewer.html`/`dashboard.html`/`static/**`) is
touched — `dashboard.html` is read by the design but unedited. The G7 sprint-close evidence is the
container rebuild + `curl /healthz` + `curl /api/reviews` (per the G7 pass-condition row's
"docs/infra-only sprint that touches no product page" clause). The svc ticket's G4 is `py_compile` +
the curl checks above; there is no `scripts/render-smoke.sh` step in this epic.

## Assumptions & open questions

Surfaced first per method; no `--ask` — proceeding on these documented assumptions.

1. **(load-bearing) `:8139` is the only live deployment, and no saved pre-MR-036 viewer or external
   script POSTs to `/feedback`.** *Assumption:* yes — the workspace grep + the running container's
   post-MR-036 viewer (`viewer.html:293`, no `POST /feedback` in the file) show no caller, and the
   inviting docs are removed in the same change. *Justification:* this is the audit's stated
   safe-removal basis. *If wrong,* the 410-Gone fallback (Risks) converts a silent break into a clear
   signal — a 3-line reviewer lever, not a re-scope. **Not a BLOCKER-FOR-HUMAN:** removal + doc-pull is
   safe under the audit's own criterion, and the fallback bounds the downside.

2. **(load-bearing) Keep the `summary()` `feedback_updated` guard; do not delete it.** *Assumption:*
   keeping it is correct — it is a reader, and deleting its branch regresses **31 new/empty (Pop B)
   reviews** plus every future new review (`awaiting`→`feedback`); see the corrected design-fork table.
   *Justification:* the core principle is "never remove a reader"; the audit's "delete that branch" was
   conditional. The contested fork is now resolved by measurement (Pop C does not occur; the guard
   protects Pop B, not the 12 `fu>0` reviews). **This is the decision the plan flags as least sure** —
   a reviewer could argue the audit *intended* the guard gone as part of "retire `feedback_updated`
   end-to-end." I hold that doing so is the destructive reading and contradicts the read-path-stays
   hard constraint. If the reviewer disagrees, this becomes a genuine product decision (accept the
   31-review status regression vs. keep the guard) — escalate then.

3. **(minor) The MCP `get_status` description needs *no* edit, and no MCP tool POSTs feedback.**
   *Assumption (revised at G1):* confirmed — no `post_feedback`/`update_feedback` tool exists, and the
   `get_status` description (`mcp_server.py:108–109`) already reads *"Watch comments_updated for
   new/changed comment threads"*, so there is nothing to reword. **The separate MCP ticket is dropped
   and no MCP-client reconnect is owed** (a reconnect is only needed when `mcp_server.py` itself
   changes, which it does not here). *Justification:* read the full tool list and the live description.

4. **(minor) Both tickets ship in one sprint** (sprint-13), svc-before-docs. *Assumption:* yes —
   total change is ~-22 lines across `app.py` + 4 docs (`CLAUDE.md`, `AGENTS.md`, `README.md`,
   `docs/future-mcp.md`); no `mcp_server.py` change; no reason to span sprints. "Land together" is
   satisfied at **sprint** granularity (see Ticket breakdown), not commit granularity.

5. **(load-bearing — corrected at G1) `docs/future-mcp.md` NEEDS a one-line edit.** *Was:* "needs no
   edit." *Corrected:* line 61 reads verbatim *"The 'human is done' heuristic in `AGENTS.md` is
   unchanged."* — and Phase 2 changes exactly that heuristic, making the sentence a stale falsehood.
   The docs ticket must drop or repoint it. (Caught by the G1 reviewer; the original sweep marked this
   file done in error — the precise miss-a-reader failure this gate exists to catch. Line 36's
   `get_status` table row stays accurate — the field is still emitted.)

**No BLOCKER-FOR-HUMAN items.** Both load-bearing forks have a safe, justified default with a named
fallback; neither risks wasting a sprint.

## Review resolutions

**2026-06-19 — resolving the G1 staff-critic review**
([`reviews/legacy-feedback-retire-plan-review-2026-06-19.md`](../reviews/legacy-feedback-retire-plan-review-2026-06-19.md),
verdict CHANGES-REQUESTED). Independently re-verified each cited fact against `app.py:127–149`,
`mcp_server.py:108–109`, `docs/future-mcp.md:61`, and the live `:8139` volume (45 reviews; 12 `fu>0`
all with `notes_total>=1`; 31 `fu==0,total==0,awaiting`; 0 in `fu>0,total==0`) before changing the
plan.

- **BLOCKER 1 (design-fork table wrong; AC vacuous) — RESOLVED.** Rewrote the `summary()` case table
  around the three real populations: **Pop A** (12, `fu>0,total>=1`) — guard *irrelevant*, derives
  `feedback`/`resolved` either way (the 12 are **not** what the guard protects); **Pop B** (31 live +
  every future new review, `fu==0,total==0`) — guard *load-bearing*, deleting its branch flips them
  `awaiting`→`feedback`; **Pop C** (`fu>0,total==0`) — *does not occur* (0 live) and does not flip
  (guard False, falls to `else: feedback` either way). Dropped the false "deleting the guard flips the
  12 to `awaiting`" claim and the "12 live reviews" attribution. Re-justified KEEP on the real basis:
  deleting the guard mislabels every empty/new review. **Replaced the safety AC** everywhere it
  appeared (design-fork, Risks, Verification): the old "a review with `fu>0,total==0` must not show
  `awaiting`" (tested empty Pop C, vacuous) is **removed**, replaced by (a) "a freshly created review,
  no comments, still derives `awaiting`" and (b) "the 31 currently-`awaiting` Pop-B reviews on the
  live volume stay `awaiting`."

- **BLOCKER 2 (missed reader `docs/future-mcp.md:61`) — RESOLVED.** Added `docs/future-mcp.md` to the
  Phase-2 docs ticket scope (the "the 'human is done' heuristic in `AGENTS.md` is unchanged" line must
  be dropped/repointed). Flipped **Assumption #5** from "needs no edit" to "load-bearing — needs a
  one-line edit." Updated the docs-section file list, the rollout/execution-order, the ticket-table
  row, the Risks "missed reader" entry, and the Verification grep to cover it.

- **Worth-considering — MCP edit right-sized; third ticket dropped.** Re-read `mcp_server.py:108–109`;
  it already leads with *"Watch comments_updated for new/changed comment threads."* **Decision: no
  `mcp_server.py` change, drop the separate MCP ticket, and drop the reconnect ceremony entirely** —
  collapsing the epic to **2 tickets (svc + docs)**. Updated the design section, rollout, execution
  order, ticket table, Risks, constraints, Verification, and Assumption #3 to match.

- **Worth-considering — 404-vs-410 decided.** Changed the default from "straight removal (410 is the
  reviewer's lever)" to **return `410 Gone` + `{"error":"gone, use comments"}`** from the now-dead
  POST arm (verified mechanics: a deleted POST arm falls through to `404 {"error":"no route"}` at
  `app.py:662`; the 410 stub does no write, no `bump`). Reason: on a no-auth, public-ish service a bare
  404 is indistinguishable from a typo'd URL, while 410 is a self-documenting deprecation signal to the
  exact straggler caller the audit worries about. Updated the design fork, Service "Remove" bullet,
  Phase-1 rollout, the router constraint, Risks, and the Verification curl (expects **410**, not 404).

- **Worth-considering — atomicity granularity stated.** Added an explicit note (Ticket breakdown) that
  the brief's "land together" is satisfied at **sprint** granularity (both tickets in **sprint-13**,
  svc-before-docs, docs-sweep non-carry-over per G7), **not** commit granularity, and that on this
  single-deploy/no-CD repo the inter-ticket window is internal-only — so the G7 reviewer doesn't read a
  contradiction with "land atomically."

- **Nitpicks addressed.** Noted `feedback_url` (`app.py:449`, GET-semantics) is deliberately untouched;
  added a non-goal that the three frozen historical records
  (`mcp-wrapper-plan.md:110`, `dashboard-redesign-plan.md:39`, `tickets/MR-002-list-and-summary.md:23`)
  are **not** retro-edited (verified the citations); and clarified the docstring update keeps the clean
  GET line (`app.py:14`) and rewrites the stale POST line (`:15`).
