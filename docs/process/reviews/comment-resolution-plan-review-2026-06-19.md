---
review_of: epics/comment-resolution-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G1 review — comment-resolution plan

**Verdict: PASS-WITH-CONDITIONS.** The architecture is sound: a separate `comments.json` store,
one server-side state machine as the single writer, viewer and MCP as thin clients. I verified the
load-bearing claims against the code and they hold. The fork call (Option (a) + migrate viewer
authoring) is the *right* reading of the brief — but the plan misframes what it is migrating, and
two conditions below must be answered before tickets spawn or a sprint will ship the wrong viewer.

---

## The fork ruling (#1) — Option (a) is correct; the plan's own framing of it is wrong

**Ruling: Option (a) is the right call, AND "migrate the viewer authoring to comments" is correct —
but NOT for the reason the plan gives, and the plan's prose mis-describes the existing system in a
way that will mislead the implementer.**

I read the code. The decisive fact the plan gets *backwards*:

The brief says "Highlight-to-comment already works; this **adds** threaded replies." The plan treats
that "highlight-to-comment" as the `notes.json` authoring flow and frames the work as *replacing* it
("the existing note-authoring functionality is replaced", "legacy notes become read-only"). **That is
not what the code is.** The MR-006 gutter (`viewer.html:423-527`) — `renderComments()`,
`highlightNote()`, the `.gcard` cards beside `mark.cmt` highlights — *is* the existing
"highlight-to-comment" surface, and it is **a projection of the same `notes` array** that the
side-panel renders (`renderComments` at viewer.html:462 iterates `notes`; authoring at
viewer.html:387 pushes to `notes`; `render` is monkeypatched at viewer.html:498 to re-run
`renderComments`). There is **one** data model (`notes.json`) with **two** views (panel + gutter),
not two systems.

So the honest framing is the brief's own: this **extends** the existing gutter comment into a
*thread* (entries[], status, roles) — the old single `note` becomes the **first entry of a thread**.
That is a superset, not a replacement. The plan reaches the right *destination* (new store, viewer
authoring writes comments) but via a wrong *map* ("two parallel comment systems would be incoherent"
— there was never a second system), which matters because an implementer who believes legacy notes
are a rival UI to suppress will build the wrong seam. **The "preserve existing commenting
functionality" constraint is satisfied** because the gutter-thread *is* the evolved highlight-to-
comment — not because notes were frozen and walled off.

Two corollaries the plan must absorb (see BLOCKER-1, BLOCKER-2): the legacy panel (`#panel`,
`#items`, the side list at viewer.html:350-359, the `+ note` → `notes.push` → `POST /feedback`
authoring) and the agent's `GET /feedback` read path **still exist after this epic**. If viewer
authoring now writes `comments.json` but the old `#panel`/`addbtn` path still writes `notes.json`,
the viewer has two live author surfaces writing two stores — which is the *actual* "two systems"
incoherence, created by the migration, not inherited from today. The plan never says what happens to
`#panel`/`#items`/`#count`/`buildMd`/the `+ note` popover.

Should the plan stop and ask the user? **No.** Option (a) with viewer-authoring-on-comments is
defensible and within the brief; this is a PASS-WITH-CONDITIONS, not a BLOCK. But the two conditions
below are the difference between shipping the brief and shipping a confusing double-author viewer.

---

## BLOCKERS

**[BLOCKER-1] The plan never resolves the fate of the legacy authoring surfaces it leaves live.**
(plan: "The load-bearing fork", "UI" section; code: viewer.html:350-389 panel/authoring,
viewer.html:340-344 `save`/`sync`→`POST /feedback`, viewer.html:393-409 `buildMd`/`collect`)
The plan moves the *gutter* "+ note" to `POST /comments`, but the viewer also has (a) the side
`#panel` list rendering `notes`, (b) its own `addbtn`/`openPop`/`popsave` authoring that pushes to
`notes` and POSTs `/feedback`, (c) the `#count` header, (d) `buildMd`/the Collect modal. After
Phase 4 the same page would author comments from a highlight but still author notes from the same
selection popover, render a notes panel and a comments gutter side by side, and POST to two stores.
*That* is the incoherent double-system. The plan must state, per surface, one of: removed / kept
read-only / repointed to comments. (My recommendation: the selection→popover and gutter both author
*comments*; `#panel`/`#items`/`buildMd` either render comment threads or are retired; `#count`
counts open comments. But that is the decision the plan owes.) Without it, MR-036 has no defined
scope and "preserve existing functionality" is untestable.

**[BLOCKER-2] `GET /feedback` semantics after the cutover are unspecified — the agent's read path
silently goes stale.** (plan back-compat guarantee #3; code: app.py:355-359 `GET /feedback`,
app.py:120-135 `summary()`/dashboard counts)
The plan freezes `GET /feedback`/`notes.json`/`summary()` "byte-for-byte" AND moves new human input
to `comments.json`. Consequence the plan does not state: once authoring is on comments, a reviewer's
new feedback lands **only** in `comments.json`. `GET /feedback` returns `notes:[]`, and the dashboard
`status`/`notes_total` (still derived from `notes.json` at app.py:125-134) shows **"awaiting / 0
notes"** for a review that has active comments. An existing agent polling `GET /feedback` (the
documented contract in `CLAUDE.md`) sees *nothing the human said*. Freezing the legacy path is only
back-compat if nothing migrates onto the new path; the moment authoring moves, the frozen path is a
silent-data-loss channel for any non-comment-aware agent. Resolve one of: (a) dashboard
`status`/counts must also reflect comments (the plan lists this as a non-goal — reconsider, it is
load-bearing for "no behaviour regresses"), or (b) explicitly accept and document that `GET
/feedback` is legacy-only and the comment-aware path (`GET /comments` / `list_comments`) is now the
feedback channel, with `CLAUDE.md`'s contract updated in MR-037. Either is fine; leaving it implicit
is not — it directly contradicts the Product-goal claim that "the dashboard's note counts keep
working."

---

## SHOULD

**[SHOULD-1] The UI-resolve omission is an over-reading of the brief and likely the wrong product.**
(plan "Assumptions": "the planned UI has **no** human resolve button"; brief PART-1 title "AGENT
RESOLUTION", PART-1 "RESOLVED STATE")
The plan infers that because resolve is "the agent's action," the viewer needs no resolve control.
The brief assigns *resolve* to the agent and *reopen* to the reviewer, yes — but PART 1 is the **UI**
spec and a Google-Docs comment that a human can only ever watch get resolved by a bot is an unusual
product. More importantly this makes the entire Phase-4 resolve path **untestable without MCP**: the
CDP "resolve appears on poll" test fires `POST /comments/{cid}/resolve` out-of-band to fake the
agent. That is fine for the live-reload test but means the viewer ships with zero first-party resolve
affordance. This is a real fork worth a one-line owner answer, not a silent assumption — flagging it
to the owner is correct, but it should be an **open question answered before G1 closes**, not an
assumption baked into MR-036's scope. (Note: a UI resolve is "additive" only if the role attribution
is decided now — reviewer-attributed self-resolve vs agent-attributed — so it touches the model.)

**[SHOULD-2] The legacy-note seed is the riskiest sub-feature and should drop to backlog now, not at
grooming.** (plan: "One-time, opt-in seed"; risk: two-tab race, partial seed, meta-flag write race)
The plan itself flags the races (two tabs both seeing empty `comments.json` + the meta-flag write
race) and says it is "droppable." The store has no atomic compare-and-set; the guard is a client-read
of `comments.json` empty + a `meta` flag, and two tabs (or one tab + an MCP create) racing first-load
will double-seed or partially-seed, and a mid-seed failure leaves an inconsistent half-migration with
the flag possibly set. For a feature whose entire value is "a returning reviewer sees old notes in the
new UI," shipping a racy half-seed is worse than not seeding. Decide it **now**: backlog it, or if
kept, specify server-side idempotency (a single `POST /comments/seed` route that the server runs once
under `_lock`, not N client POSTs). Do not carry an unresolved race into MR-036.

**[SHOULD-3] `mark.cmt[data-id]` namespace collision between legacy notes and comments.** (code:
viewer.html:444 `mk.dataset.id=i` (array index); viewer.html:452-453, 466, 475 focus-pairing by
`data-id`; plan: "legacy note still renders if a review already has notes")
Today `data-id` on `mark.cmt` and `.gcard` is the **array index** `i`. Comments are keyed by
`comment_id` (`c…`). If the viewer renders legacy notes (index-keyed) and comments (id-keyed)
simultaneously — which the plan's back-compat read implies — the `focusPair`/`data-id` lookups
collide (index `2` vs `comment_id` "c…", and two cards can share `data-id="2"`). Resolve-1 (retire
legacy-note rendering once comments exist) makes this moot; otherwise the comment cards must key on
`comment_id` and the legacy ones be namespaced. Call it out in MR-036's AC.

**[SHOULD-4] Reply-to-resolved has no defined live surface in the Resolved panel.** (plan: "Reply is
legal in **every** state"; "Resolved panel … showing the full thread"; agent expectation "reply or
resolve again")
Reply-in-resolved is correct per the brief (agent can discuss without un-resolving — confirmed
against AGENT EXPECTATIONS). But the viewer section only describes the Resolved panel showing the
thread at resolve-time; it doesn't say a reply arriving (via `comments_updated`) re-renders the
*resolved* thread in the panel. If an agent replies to a resolved comment, the human must see it.
One line in MR-036 AC: `comments_updated` re-renders the Resolved panel threads too, not just the
active gutter.

## State machine + routes (#3) — verified, correct

- Legal/illegal table is complete and right: resolve-resolved→409, reopen-non-resolved→409
  (covers both `open` and `reopened` as illegal-to-reopen), missing→404, reply-any-state. The
  `open→resolved→reopened→resolved` walk and the append-only `status`/`thread`/`status_history`
  semantics are consistent.
- Single `apply_comment_transition` under `_lock` as the only writer is sufficient to prevent
  UI/MCP divergence — it mirrors the existing `attach_asset`/`POST /feedback` lock discipline
  (app.py:214-226, 344-348). Sound.
- **Router insertion point verified.** Every route uses `re.fullmatch` (app.py:323-468), so
  ordering only matters when two patterns can both fully match one path. The literal `comments`
  segment shares no full-match with `assets`/`asset`/`feedback`/`source`/`status`/`history`, and
  `/api/reviews/{id}` (app.py:323) cannot match `…/comments` under `fullmatch`. The claimed
  insertion point (between :437 and :439) is therefore safe — and in fact ordering is irrelevant
  here, the plan over-worries it. The `{cid}` regex `(c[A-Za-z0-9]{10})` cannot collide with the
  asset `stored` route because the preceding `comments/` literal disambiguates. Safe.

## Back-compat (#4) — verified independent, with the BLOCKER-2 caveat

`comments.json` is a separate file under `_dir(rid)`; nothing in the proposed comment paths reads or
writes `notes.json`/`feedback.md`/`meta.json` counts. `_read_json(path, [])` already returns `[]` for
a missing file (app.py:96-101), so existing reviews yield `{"comments":[]}` with no 500. `summary()`
(app.py:120-135) and `snapshot_round` (app.py:144-166) reference only `notes.json` and are genuinely
untouched. The data-isolation claim holds. The *behavioural* back-compat claim does not — see
BLOCKER-2: byte-identical endpoints can still mean a regressed agent experience once authoring moves.

## MCP contract (#5) — sound

Four tools, no `reopen`, `document_id`=review id, count 10→14, `mcp_smoke` round-trip. The
no-reopen-tool framing as **convention not authz** is honest and consistent with the existing
no-auth posture (the service trusts its network; `CLAUDE.md` already says so). Tool shapes match the
brief's PART-2 verbatim. The wrapper pattern (TOOLS entry + `route()` branch + KeyError-on-missing-arg
at mcp_server.py:165-203) is the established one. **One NIT:** the smoke must seed the comment via
HTTP `POST /comments` (create is reviewer-side) — the plan says this, good; just ensure the smoke's
`expected` set and the `== 10` count assertion at mcp_smoke.py:60-63 both move to 14 (the plan says
count, don't forget the `expected` set literal).

## Viewer evidence (#6) — adequate

render-smoke flat selectors (`.gcard`/`.gentry`/`#resolved`/`.resolved-count`/`mark.cmt`, two-selector
form for nesting) + CDP create/resolve/reopen + dual-pane via `preferredColorScheme`/
`setEmulatedMedia` (not `--force-dark-mode`) is the right rig and matches the hard-won conventions in
Key constraints. The "agent-resolve-appears-on-poll" CDP step is the correct way to prove
`comments_updated` live-reload. Adequate — subject to SHOULD-1 (if there's no UI resolve, label the
out-of-band `POST /resolve` as simulating MCP, which the plan already does).

## Ticket decomposition (#7) — order right; MR-033/034 split justified

`MR-033 → MR-034 → {MR-035, MR-036} → MR-037` is correctly ordered (store before machine before
clients before docs). The MR-033/MR-034 split (store+CRUD vs state machine) is **not** artificial:
MR-033 ships a usable create/list/get with its own curl smoke and proves back-compat in isolation,
and MR-034's 409/transition surface is a distinct, independently-testable concern — splitting keeps
each a reviewable vertical slice. MR-037 docs correctly not carry-over-eligible (G7). IDs MR-033–037,
sprint-11, confirmed against the tracker (last was sprint-10/MR-032). Good. **Caveat:** BLOCKER-1's
resolution may grow MR-036 (retiring/ repointing `#panel`/`buildMd`) — size it after that answer.

## NITs

- **[NIT]** Assumptions section: `"c"+token_hex(5)` is **11 chars, not 12** (verified:
  `token_hex(5)`=10 hex). The regex `(c[A-Za-z0-9]{10})` is correctly 11, so code is internally
  consistent — fix the prose so the implementer doesn't "correct" the regex to match a wrong count.
- **[NIT]** Comment model stores `anchor.start/end` "offsets within the block's `innerText`" but the
  existing `highlightNote` (viewer.html:437-447) searches `node.nodeValue` of a single **text node**,
  not block `innerText`. The plan says offsets are "hints, not bindings," so this is harmless, but
  the field description should say "text-node-local" to match the matcher it claims to reuse.
- **[NIT]** Phase 1 adds `comments_updated` to `GET /status` (good), but `GET /status` (app.py:368-377)
  currently returns only two fields; confirm MR-033's AC asserts the new field is present **and**
  defaults to `0` on a review that has never had a comment (the plan's verification does check `>0`
  after a create; add the `==0`-before case).

## Resolution log

- 2026-06-19 (author) **BLOCKER-1** — Added a per-surface fate table to the UI section: selection popover + gutter author **comments** (`POST /comments`); `#panel`/`#items` side list retired; `#count` counts open comments; `buildMd`/Collect retired (thread export → backlog); no viewer path writes `notes.json`. Exactly one author surface, one store after Phase 4. MR-036 scope, risks, phases, and verification (`POST /feedback` network-log assertion) updated.
- 2026-06-19 (author) **BLOCKER-2** — Chose **project (not legacy-only)**: `GET /feedback` returns the union of legacy `notes.json` + a read-time comment projection, and `summary()` folds comments into counts/status — both read-layer, no disk migration. Flipped the "comments don't feed the dashboard" non-goal to a back-compat guarantee; rewrote the Product-goal sentence, the Decision rationale, the back-compat guarantees, Key constraints, risks, and the MR-033/MR-034 verification to assert the live behaviour. Projection lives in MR-033 (union+fold), MR-034 re-asserts resolve flips it.
- 2026-06-19 (author) **SHOULD-1** — Moved "no client-side resolve button" from open question to a **recorded decision** with the brief PART-1 citation (resolve→agent, reopen→reviewer); CDP step 2's out-of-band `POST /resolve` now explicitly labelled as simulating the agent over MCP. Added a matching non-goal.
- 2026-06-19 (author) **SHOULD-2** — Dropped the client-side legacy-note seed from MR-036 scope and the rollout phase to **backlog** (race-prone, no compare-and-set); noted the only acceptable future form is a single server-side idempotent `POST /comments/seed` under `_lock`.
- 2026-06-19 (author) **SHOULD-3** — Retired legacy-note *rendering* in the viewer; comment cards/highlights key on `comment_id` (one `data-id` namespace), eliminating the index-vs-`comment_id` collision. MR-036 AC asserts every rendered `data-id` matches `/^c[A-Za-z0-9]{10}$/`. Legacy note *data* still readable via the comment-aware `GET /feedback`.
- 2026-06-19 (author) **SHOULD-4** — Added to MR-036's AC and a new CDP step: a `comments_updated` poll re-renders the **Resolved panel** threads too, so an agent reply to a *resolved* comment surfaces a new `.gentry` under `#resolved` for the human.
- 2026-06-19 (author) **NIT (comment_id chars)** — Fixed prose to **11 chars** (`"c"+secrets.token_hex(5)`); regex `(c[A-Za-z0-9]{10})` left unchanged.
- 2026-06-19 (author) **NIT (anchor offset)** — Anchor `start`/`end` description changed to **text-node-local** (matching `highlightNote`'s `nodeValue` search), not block `innerText`.
- 2026-06-19 (author) **NIT (comments_updated default)** — MR-033 AC/verification now asserts `comments_updated == 0` **before** the first comment and `> 0` after.
- 2026-06-19 (author) **NIT (mcp_smoke)** — MR-035 verification now requires updating **both** the `expected` tool-name set literal **and** the `== 10`→`14` count at mcp_smoke.py:60-63 (a count-only bump would fail `names == expected`).

## Round 2 (re-review) — delta verdict

Re-verified the deltas against the code (`summary()` app.py:120-135; `GET /feedback` app.py:355-359; `_read_json` defaults; viewer.html `#panel`/`#items`/`#count`/`buildMd`/`addbtn`/`renderComments` at 70/350/348/393/362/458 with `dataset.id=i` at 444/466; mcp_smoke.py:60-63). Each condition judged on its delta only; settled architecture not reopened.

- **BLOCKER-1** — **ACCEPTED.** Per-surface fate table (plan:308-315) is complete and unambiguous: popover+gutter→`POST /comments`; `#panel`/`#items` retired; `#count`→open comments; `buildMd`/Collect retired; `save`/`sync`→`/feedback` removed. Plan asserts "exactly one author surface, one store" (305/317-319); MR-036 AC asserts no viewer path writes `notes.json` and `data-id`=`/^c[A-Za-z0-9]{10}$/` (327-328). No described surface still writes `notes.json`.
- **BLOCKER-2** — **ACCEPTED.** (a) Dashboard floor met: status rule (plan:182-184) makes a review with any open comment read `feedback`/non-zero, never `0/awaiting`. (b) Read-time only: `_comment_as_note` is a pure no-write fn (163-166); union/fold computed per request; no double-count because a fresh review's `notes.json` is `[]` so legacy∪comments are disjoint. (c) No leftover self-contradiction: every surviving "byte-for-byte" now qualifies the on-disk store or the no-comment case (174/425-429/501), the non-goal is flipped (134), and the Product-goal sentence (33-38) is TRUE under projection. (d) Scope on MR-033 (186-191/479/497). Total-counting rule (all→total, resolved→addressed) mirrors the existing `summary()` invariant exactly and keeps `resolved` requiring every unit addressed; sound to ship — the open-only alternative is correctly flagged as a one-line MR-033-local change. No pinning needed before MR-033.
- **SHOULD-1** — **ACCEPTED.** No-UI-resolve is a recorded decision with PART-1 citation (658-664) + matching non-goal (401-402); resolve-reflection stays testable via the out-of-band CDP `POST /resolve` labelled as simulating MCP (621-623).
- **SHOULD-2** — **ACCEPTED.** Seed gone from sprint scope, not relabelled: removed from MR-036 (Phase 4:388; ticket table:482), pushed to backlog (115-122/408-409/669-671), and explicitly excluded as a split candidate (489-490).
- **SHOULD-3** — **ACCEPTED.** Legacy rendering retired; cards/highlights key on `comment_id`; MR-036 AC asserts the `data-id` shape (321-328). Collision is structurally impossible (one namespace).
- **SHOULD-4** — **ACCEPTED.** MR-036 AC + CDP step 4 assert a reply on a resolved comment re-renders the Resolved panel, not just the gutter (349-354/626-629).
- **NITs** — **ACCEPTED (all 4).** 11-char `comment_id` (197/679-680); text-node-local offsets (216-218); `comments_updated==0` before / `>0` after (526-535); mcp_smoke updates both the `expected` set and count→14 (287-290/583-585).

**Round-2 verdict: PASS.** All 2 BLOCKER + 4 SHOULD + 3 NIT conditions resolved and verified against the code. No STILL-OPEN items; G1 passes. Tickets MR-033–037 may spawn.
