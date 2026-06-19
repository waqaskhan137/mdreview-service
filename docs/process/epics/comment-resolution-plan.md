---
epic: comment-resolution
status: active         # draft | active | done  (stays draft until G1 passes)
created: 2026-06-19
source: requirements/comment-resolution.md
gate: passed 2026-06-19  # G1 (Plan Gate): passed (round 2, staff-critic PASS) — tickets unblocked
review: reviews/comment-resolution-plan-review-2026-06-19.md
related_sprints: [sprint-11]
related_tickets: [MR-033, MR-034, MR-035, MR-036, MR-037]
---

# Comment Resolution Workflow Plan

A Google-Docs-style comment-resolution workflow for mdreview: threaded comments anchored to a
highlighted span, agent-side resolve (with optional justification), a Resolved-history panel with
reviewer reopen, and four MCP tools — all over **shared server-side state** with one
`open → resolved → reopened → resolved …` state machine enforced by the service and reflected
identically in the viewer and over MCP. Full history; replies and transitions append, never
overwrite. This is the largest epic in the repo to date and spans **service + viewer + MCP**.

**Source requirement:** [`requirements/comment-resolution.md`](../requirements/comment-resolution.md)
— the original brief, kept verbatim.

## Product goal

A reviewer highlights text and starts a comment; the comment opens as a thread in the side margin.
The agent (over MCP) lists open comments, replies to discuss, or resolves — optionally with a
justification appended to the thread. On resolve, the comment and its highlight leave the active
document and move to a **Resolved** panel that shows the full thread and a resolved count. The
reviewer can **reopen** a resolved thread from that panel (restoring the highlight and adding an
optional reply), after which the agent can resolve again. The state machine is consistent whether
the action came from the browser or from MCP, because both write the **same** server-side store. No
existing behaviour regresses: the current highlight-to-comment surface **evolves into** the threaded
comment (the old single note becomes the first entry of a thread), and the agent's `GET /feedback`
read path and the dashboard's counts/status **stay live** because they become comment-aware — a
review with open comments still reads as "awaiting/feedback" with a non-zero count, and `GET
/feedback` still returns the human's current input. Legacy `notes.json` data on disk is never
rewritten and old reviews with no comments behave exactly as today.

## Core design principle

**One shared, append-only comment store per review; the server is the single source of truth and
the only place transitions are validated; the viewer and MCP are thin, equal clients of it.**

Everything else serves that: the viewer never decides a status locally (it renders what the server
returns and POSTs intent); MCP never holds state (it wraps the same routes); history is preserved
because every reply and every transition is an **append**, and `status` is a derived pointer over an
immutable `thread` + `status_history`.

## The load-bearing fork — how the new comments relate to the existing `notes.json`

This is the decision the whole epic turns on. I mapped the current model against the code first.

### Current model (verified against the code)

| Surface | Shape / behaviour | Evidence |
|---|---|---|
| Note store | `notes.json` = `[{num, quote, note, addressed}]`, default `[]` | `create_review` writes `"[]"` (app.py:176); `POST /feedback` overwrites it (app.py:364) |
| Agent read | `GET /feedback` → `{markdown, notes[], ...meta}` | app.py:355-359 |
| Dashboard counts | `summary()` derives `notes_total`/`notes_addressed`/`status` from `notes.json` | app.py:120-135 |
| History | `snapshot_round` copies `notes.json` into `history/round-N/` on each PUT | app.py:155-164 |
| Viewer authoring | highlight → `addbtn` → `openPop` → `notes.push({num,quote,note,addressed})` → `save()` → localStorage **and** `POST /feedback` | viewer.html:363-389, 340-344 |
| Viewer gutter | `renderComments()` is a **projection of the same `notes` array** — `.gcard` cards beside `mark.cmt` highlights, keyed by array **index** `i`; `render` is monkeypatched to re-run it | viewer.html:444 (`mk.dataset.id=i`), 458, 498 |
| Viewer anchor | quoted text is re-located each render by `indexOf` within a single text node inside `.blk[data-num]`; spanning inline tags falls back to block anchor | `reconcile()` viewer.html:327-335; `highlightNote()` viewer.html:433-449 |

So today a "note" is a **single** authored remark with no replies, no status beyond a boolean
`addressed`, no author/role, and it is the agent's only feedback channel and the dashboard's only
counter. Crucially there is **one** data model (`notes.json`) with **two views** (the side `#panel`
list and the MR-006 gutter), not two systems — the gutter *is* today's highlight-to-comment surface,
a projection of `notes`.

### Decision: **Option (a) — a NEW `comments.json` store, the thread model lives entirely in it, the
viewer's authoring evolves onto it as the single comment surface, and the legacy read paths
(`GET /feedback`, `summary()`) become comment-aware at the read layer (no disk migration).**

`comments.json` is a sibling of `notes.json` under `_dir(rid)`, `_lock`-guarded, back-compat default
`[]`. The threaded-comment model (status machine, replies, roles, resolve/reopen) lives **entirely**
in `comments.json`. `notes.json` **data on disk** and `snapshot_round`/history are left untouched (zero
migration), but `GET /feedback` and `summary()` are made **comment-aware by read-time projection** so
the agent's documented read path and the dashboard stay live once authoring moves to comments
(BLOCKER-2). The projection is computed per request; no file is rewritten.

Why (a) and not (b)/(c):

- **(b) migrate/extend notes into the comment model** would still need a data migration of every
  `notes.json` on disk (the live instance has real ones) and a rewrite of the on-disk shape. Option
  (a) achieves the same user-visible result (the agent reads live human input; counts are truthful) by
  *projecting* at read time instead of *migrating* on disk — strictly less risk.
- **(c) hybrid (notes.json as the persisted count/feedback projection, comments.json as the thread
  layer)** keeps two stores *coupled on every write* — each comment write must also mutate `notes.json`
  to keep counts truthful, re-introducing the overwrite/locking surface (c) was meant to avoid and
  risking divergence. Option (a)'s read-time projection gets truthful counts/feedback **without** a
  second write per comment — the dashboard/feedback are derived, never persisted in two places.
- **(a)** keeps the stores *decoupled at the write layer*: only `comments.json` is written by comment
  paths; the legacy file is never rewritten. "Preserve all existing commenting/highlighting
  functionality and data" is met because (i) old data on disk is untouched and (ii) the old read
  endpoints keep returning the human's live input by being made comment-aware — not by freezing them
  while authoring drains away from them.

**Resolving the brief's "one comment UI" honestly — this evolves the surface, it does not replace a
rival.** The brief says "highlight-to-comment already works; this **adds** threaded replies." That
existing highlight-to-comment surface *is* the MR-006 gutter — a projection of `notes`, not a separate
system. So the work is a **superset**: the old single `note` becomes the **first entry of a thread**
(entries[], status, roles) living in a new `comments.json`. The viewer's gutter authoring repoints
from `notes.push`/`POST /feedback` to `POST /comments`. "Preserve all existing commenting
functionality" is satisfied because the gutter-thread *is* the evolved highlight-to-comment, and the
agent read/dashboard paths are kept live by being made comment-aware (BLOCKER-2 below) — **not**
because notes were frozen and walled off behind a dead UI.

There must be exactly **one** human author surface after Phase 4 (see "Legacy authoring surfaces"
below). The new store is decoupled at the *data* layer (legacy `notes.json` is never rewritten — no
disk migration), but at the *read* layer `GET /feedback` and `summary()` project comments so nothing
the human says is lost to a non-comment-aware agent or the dashboard.

**No client-side legacy-note seed (dropped to backlog).** An earlier draft proposed a one-time
client-side seed of legacy notes into `comments.json` on first load. That is **removed from this epic**
(see SHOULD-2 in Review resolutions): the store has no compare-and-set, so two tabs (or one tab + an
MCP create) racing first-load would double- or partially-seed, and a mid-seed failure leaves a
half-migration with the flag possibly set — worse than not seeding. If a seed is ever wanted it must be
a **single server-side `POST /comments/seed` route, idempotent under `_lock`** (not N client POSTs);
that is a backlog follow-up, out of this epic. Removing it also eliminates the "legacy notes render
alongside comments" case entirely.

**Back-compat guarantees (explicit):**

1. Existing reviews on disk have **no** `comments.json` — readers default to `[]` (`_read_json(path,
   [])`), so `GET /comments` returns `{"comments": []}`, the viewer shows zero threads, and the
   comment-aware `summary()`/`GET /feedback` projections (below) are empty and reduce to today's
   behaviour exactly. No 500, no KeyError.
2. **`summary()` becomes comment-aware (BLOCKER-2).** `notes_total`/`notes_addressed`/`status` now
   reflect both legacy notes **and** open comments, so the dashboard never shows "0 notes / awaiting"
   for a review that has open comments. A review with *no* comments derives identically to today
   (comment contribution is zero). Mapping specified in the Service section; the old "comments don't
   feed dashboard counts" non-goal is **flipped** (it was load-bearing for "no behaviour regresses").
3. **`GET /feedback` becomes comment-aware (BLOCKER-2), read-time, no disk migration.** It still
   returns `{markdown, notes[], ...meta}`, but `notes[]` is now the **union** of legacy `notes.json`
   entries and a read-time **projection of comments** into the note-like shape (`quote`=
   `anchor.quoted_text`, `note`=thread text, `addressed`=`status=="resolved"`). So an agent's
   documented `get_feedback` read path keeps returning the human's live input even though authoring
   moved to comments. `notes.json` on disk is **not** rewritten — the projection is computed per
   request. The structured comment thread is still also available via `GET /comments` / MCP
   `list_comments`.
4. `snapshot_round` is **not** extended to copy `comments.json` — comments are *live* state, not a
   per-revision artifact (see "Are comments history-snapshotted?" below). History rounds keep
   snapshotting `source.md`/`feedback.md`/`notes.json` exactly as today.
5. Existing reviews lack `comments.json`; all readers default the missing file to `[]`. (No new
   `meta.json` keys are added — the client-side seed flag is gone with the seed.)

## Recommended approach

### Service (`app.py`)

A new comment store + helpers + a `/comments` route family + the state machine. All writes go through
`_lock`, mirroring `attach_asset` (app.py:214-226).

**Storage.** `comments.json` under `_dir(rid)`, sibling of `notes.json`/`assets.json`/`history/`,
default `[]`. Helpers alongside the asset helpers:

- `_comments_path(rid)` → `os.path.join(_dir(rid), "comments.json")`
- `list_comments(rid, status="all")` → `_read_json(_comments_path(rid), [])` filtered by status
- `_write_comments(rid, arr)` → `_write(_comments_path(rid), json.dumps(arr))` (caller holds `_lock`)
- `_find_comment(arr, cid)` → the dict or `None`
- `_comment_as_note(c)` → a read-time projection of one comment into the legacy note shape:
  `{"num": c["anchor"].get("block_num",""), "quote": c["anchor"].get("quoted_text",""),
  "note": <last thread entry text, or the joined thread>, "addressed": c["status"]=="resolved"}`.
  Pure function, no write.

**Comment-aware read projections (BLOCKER-2 — the load-bearing change).** Because viewer authoring
moves onto comments, the legacy agent/dashboard read paths must reflect comment state or they go
stale. Two **read-time** changes, no disk migration:

- **`GET /feedback`** (app.py:355-359): `out["notes"]` becomes the **union** of the on-disk
  `notes.json` entries and `[_comment_as_note(c) for c in list_comments(rid)]`. Existing reviews (no
  `comments.json`) project nothing extra and behave byte-for-byte as today. The structured thread/
  status data is still read via `GET /comments`. This keeps the documented `get_feedback` contract
  returning the human's live input.
- **`summary()`** (app.py:120-135): fold comments into the counts/status. Concrete mapping —
  `notes_total = len(notes.json) + len(open-or-reopened comments)` (or simply all comments; pick and
  state one — recommend counting **all** comments toward total, **resolved** toward addressed, so it
  mirrors note semantics); `notes_addressed += count(status=="resolved")`. Status derivation: if any
  comment is open/reopened → `"awaiting"`/`"feedback"` (use `"feedback"` once any comment or feedback
  exists, `"awaiting"` only when there is zero feedback *and* zero comments); if all comments are
  resolved **and** all notes addressed → `"resolved"`. A review with no comments derives exactly as
  today. The dashboard thus **never** shows "0 notes / awaiting" while open comments exist.

**Scope of the projections.** Both live in `svc` tickets. The `GET /feedback` union and the
`summary()` count fold land in **MR-033** (they touch the read paths the store ticket owns), but the
`addressed=status=="resolved"` half of the mapping is only meaningful once the resolve transition
exists (**MR-034**); MR-033 ships the union with `addressed` keyed on the create-time status (`open`
⇒ false), and MR-034's AC re-asserts that a resolve flips both the `GET /feedback` projection's
`addressed` and the dashboard `status`/count. Stated in both tickets' ACs.

**Comment model** (one object in the array):

```json
{
  "comment_id": "c" + secrets.token_hex(5),
  "status": "open",                         // open | resolved | reopened
  "anchor": {"quoted_text": "...", "block_num": "4", "start": 12, "end": 24},
  "thread": [
    {"author": "reviewer", "role": "reviewer", "text": "...", "ts": 1718800000.0}
  ],
  "created_by": "reviewer",
  "created_at": 1718800000.0,
  "resolved_by": null,                      // "agent" once resolved, else null
  "resolved_at": null,
  "status_history": [
    {"from": null, "to": "open", "by": "reviewer", "ts": 1718800000.0}
  ]
}
```

- `anchor.quoted_text` is the highlighted span verbatim; `block_num` is the `.blk[data-num]` it was
  authored under; `start`/`end` are **text-node-local** char offsets of `quoted_text` (matching
  `highlightNote`'s `node.nodeValue.indexOf` search of a single text node, viewer.html:437-447 — **not**
  block `innerText`), used only to disambiguate a repeated quote. The **viewer re-resolves** the anchor
  each render exactly as `reconcile()`/`highlightNote()` do today — the offsets are a hint, not a
  binding. This deliberately reuses the proven text-node-`indexOf` model rather than inventing a
  fragile global-offset scheme.
- `role` ∈ `{"reviewer","agent"}` is **attribution, not authorization** (see Key constraints). `author`
  is a free display string defaulting to the role.
- `thread` and `status_history` are **append-only**. `status` is a derived pointer; the full transition
  record is in `status_history`.

**The state machine (server-enforced, shared by UI + MCP).** Legal transitions and their writes:

| Action | Pre-state | Effect | Post-state | Writes |
|---|---|---|---|---|
| create | (none) | new comment with one reviewer thread entry | `open` | append comment; `status_history += {from:null,to:"open"}` |
| reply | `open`/`reopened`/`resolved` | append a thread entry (role per caller) | unchanged | `thread += entry` |
| resolve | `open` or `reopened` | if `justification` given, append agent thread entry first; then flip | `resolved` | `thread += {role:"agent"}` (if justif.); `status="resolved"`; `resolved_by="agent"`; `resolved_at=ts`; `status_history += {from:<pre>,to:"resolved",by:"agent"}` |
| reopen | `resolved` | optional reviewer reply appended first; then flip; clear resolved_by/at | `reopened` | `thread += {role:"reviewer"}` (if reply); `status="reopened"`; `resolved_by=null`; `resolved_at=null`; `status_history += {from:"resolved",to:"reopened",by:"reviewer"}` |

Illegal transitions are **rejected** with `409 {"error": "...", "status": "<current>"}`:
- resolve a comment already `resolved` → 409.
- reopen a comment that is not `resolved` (i.e. `open`/`reopened`) → 409.
- any action on a missing `comment_id` → 404.

Reply is legal in **every** state (a reply after resolve does not change status — it just appends; the
brief allows discussion at any time). All transition logic lives in one helper, e.g.
`apply_comment_transition(rid, cid, action, by, text=None)`, called under `_lock`, so the UI route and
the MCP-backed route share one implementation and cannot diverge.

**HTTP routes** (new regex rows in `route()`, `RID` reused). **Insertion point: between the `/assets`
block ending app.py:437 and the `/asset/([A-Za-z0-9._-]+)` block at app.py:439.** The literal segment
`comments` cannot shadow or be shadowed by `assets`/`asset`/`feedback`/`source`/`status`/`history`, and
the per-comment routes use a distinct `comments/{cid}` shape, so no existing route is affected (router
matches in order; confirmed against app.py:323-468).

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| GET | `/api/reviews/{id}/comments` | — (query `?status=open\|resolved\|reopened\|all`, default `all`) | `{"comments":[...]}` | the list MCP/viewer read |
| POST | `/api/reviews/{id}/comments` | `{anchor{quoted_text,block_num?,start?,end?}, text, author?, role?}` | `201 {comment}` | create; role defaults `reviewer` |
| GET | `/api/reviews/{id}/comments/{cid}` | — | `200 {comment}` or `404` | full thread + status_history |
| POST | `/api/reviews/{id}/comments/{cid}/reply` | `{text, author?, role?}` | `200 {comment}` | append; status unchanged |
| POST | `/api/reviews/{id}/comments/{cid}/resolve` | `{justification?}` (role forced `agent`) | `200 {comment}` or `409` | resolve transition |
| POST | `/api/reviews/{id}/comments/{cid}/reopen` | `{text?}` (role forced `reviewer`) | `200 {comment}` or `409` | reopen transition |

`{cid}` regex is `(c[A-Za-z0-9]{10})` (or reuse a permissive `([A-Za-z0-9]{4,40})`); pick a pattern
that cannot collide with the asset `stored` route — `comments/` already prevents that.

**Status bump for live-reload.** Each comment write `bump(rid, "comments_updated")` and `GET /status`
adds `comments_updated` to its response (default `0`), so the viewer can poll a cheap timestamp and
re-fetch comments only when they change — mirroring `source_updated` (app.py:368-377). This is the
mechanism by which an agent's MCP resolve appears in the open browser.

### MCP (`mcp_server.py`)

Four new tools, thin 1:1 wrappers (TOOLS schema entry + `route()` branch), `document_id` = review `id`.
**No `reopen` tool** (reviewer-only by convention; stated honestly as convention, not security):

| Tool | HTTP it wraps | Params | Returns |
|---|---|---|---|
| `list_comments` | `GET /comments?status=` | `document_id` (req), `status` (open\|resolved\|reopened\|all, default **open**) | the comment array |
| `get_comment` | `GET /comments/{cid}` | `document_id` (req), `comment_id` (req) | one thread + status_history |
| `reply_to_comment` | `POST /comments/{cid}/reply` (role=agent) | `document_id` (req), `comment_id` (req), `text` (req) | the updated comment |
| `resolve_comment` | `POST /comments/{cid}/resolve` (role=agent) | `document_id` (req), `comment_id` (req), `justification` (optional) | `{comment_id, status:"resolved", resolved_by:"agent", resolved_at}` |

Encode the brief's **AGENT EXPECTATIONS** into the tool descriptions **and** the server-instructions
docstring (the module docstring + the `initialize`/handshake surface): always `list_comments(status=
"open")` first; `reply_to_comment` for questions/discussion, `resolve_comment` only when actually
addressed; `justification` optional-but-recommended (the reviewer can reopen); the agent never reopens —
after a reviewer reopen it sees the comment again via `list_comments` (status `reopened`/`open`). Update
the docstring **tool count** (10 → 14) and the `tools/call` comment. `route()` adds four branches
following the existing `KeyError`-on-missing-arg pattern (mcp_server.py:165-192). `mcp_smoke.py` must
update **both** (a) the `expected` tool-name set literal **and** (b) the `== 10` count assertion
(mcp_smoke.py:60-63) to **14** — add `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment`
to the `expected` set and change `names == expected` / `"the 10 tools"` → 14, not just the count. Plus
a **round-trip**: create a review + a comment (via HTTP, since comment-create is reviewer-side), then
`list_comments(open)` → `get_comment` → `reply_to_comment` → `resolve_comment`, asserting the status
goes to `resolved` and `resolved_by=="agent"`.

> Note: comment **create** is reviewer-side (viewer), so the MCP smoke seeds a comment via the HTTP
> `POST /comments` route directly (as it already seeds reviews), then exercises the four agent tools.

### UI (`viewer.html`)

Extend the existing MR-006 gutter layer (viewer.html:423-527) — do **not** rewrite it. The gutter
already lays out anchored cards beside `.blk` anchors with a fit-based `gutter-on` test
(viewer.html:478-495); comments reuse that machinery.

**Legacy authoring surfaces — exactly one author surface, one store after Phase 4 (BLOCKER-1).**
Today the viewer has *one* `notes` model with two views (the `#panel` side list and the gutter) plus
its popover authoring and the Collect modal. After Phase 4 every human-author path writes **comments**
(`POST /comments`) and renders the **comment store**; nothing in the viewer still writes `notes.json`.
Per-surface fate:

| Surface (viewer.html) | Today | After Phase 4 |
|---|---|---|
| selection → `addbtn`/`openPop`/`popsave` authoring (363-389) | pushes a `note`, `POST /feedback` | authors a **comment** (`POST /comments`, first reviewer entry) |
| gutter `.gcard`/`mark.cmt` (renderComments 458, highlightNote 433) | projection of `notes`, keyed by index `i` | renders the **comment** list, keyed by **`comment_id`** |
| side `#panel`/`#items` list (350-359) | renders `notes` | **retired** — the gutter thread is the single comment view; `#panel`/`#toggle` removed (or kept only as a gutter-collapse toggle, no separate note list) |
| `#count` header (347-348) | counts active notes | counts **open comments** (open + reopened) |
| `buildMd`/Collect modal (393-409) | serializes `notes` to markdown | **retired** for this epic (the agent reads threads via `GET /comments`/MCP; a comment-thread export is a backlog follow-up, not in scope) |
| `save`/`sync` → `POST /feedback` (340-344) | writes `notes.json` | **removed from the author path** — no viewer code POSTs `/feedback` anymore |

So after Phase 4 there is exactly **one** human author surface (highlight → comment) writing exactly
**one** store (`comments.json`). No page authors a comment from a highlight while still authoring a
note from the same popover.

**Legacy-note rendering is retired in the viewer (SHOULD-3).** The viewer no longer renders index-keyed
`mark.cmt`/`.gcard` from the `notes` array; comment cards and highlights key on **`comment_id`**
(`data-id="cXXXXXXXXXX"`), not the array index `i`. Legacy `notes.json` **data** is still preserved and
still readable via `GET /feedback` (now a union projection — see Service) and `GET /api/reviews/{id}/
history`, but it is not rendered as live threads in the viewer. This makes the old index-vs-`comment_id`
`data-id` collision impossible: there is only one `data-id` namespace (`comment_id`) in the rendered
DOM. **MR-036's AC asserts** `mark.cmt`/`.gcard` `data-id` values match `/^c[A-Za-z0-9]{10}$/` and no
viewer code path writes `notes.json`.

- **Threaded gutter cards.** A `.gcard` becomes a thread: header (anchor ref + quoted snippet) then a
  stack of entries, each `{author, role, text, ts}`. **Reviewer vs agent visually distinct** — distinct
  left-accent / background tint per role, using existing CSS vars (`--accent` for agent, `--noteline`
  for reviewer, or similar), no new palette. A reply box at the bottom of an open card (`POST
  /comments/{cid}/reply`, role reviewer).
- **Authoring (the single author surface).** The highlight → selection → "+ comment" path (the former
  "+ note" popover, repointed) creates a **comment** (`POST /comments` with
  `anchor{quoted_text,block_num,start,end}` + first reviewer entry), *replacing* the `notes.push` +
  `POST /feedback` path entirely — no viewer code writes `notes.json` after this. Anchor resolution
  reuses `highlightNote()`/`reconcile()` (quoted-text within a text node, block fallback) unchanged.
- **Resolve hides + moves to Resolved panel.** When a comment's `status` is `resolved`, its gutter card
  and its highlight `mark.cmt` leave the active document and the thread moves into a **Resolved panel**
  (a new docked panel, sibling of the existing `#gutter`) showing the full thread + a **resolved
  count** header. Resolve is the agent's action (over MCP) — **no client-side resolve button** (recorded
  decision, see Assumptions/Service): the brief assigns *resolve* to the agent and *reopen* to the
  reviewer. The panel and count update from server state on the next `comments_updated` poll.
- **Reviewer reopen.** Each resolved thread in the panel has a **Reopen** control (`POST
  /comments/{cid}/reopen`, optional reply textarea). On success the highlight is restored, the card
  returns to the active gutter, status → `reopened`, and the resolved count drops.
- **Live state — gutter AND Resolved panel both re-render (SHOULD-4).** `poll()` (viewer.html:412-419)
  gains a `comments_updated` watch: when it changes, re-fetch `GET /comments` and re-render **both** the
  active gutter **and the Resolved-panel threads**, so an agent's MCP resolve appears, *and* an agent
  **reply to an already-resolved comment** shows up in the resolved thread for the human (reply is legal
  in every state). MR-036's AC asserts a reply arriving on a resolved comment re-renders its thread in
  the Resolved panel, not just the active gutter.
- **Polish.** Consistent dark theme via the existing `@media (prefers-color-scheme: dark)` vars
  (viewer.html:11) and dense styling; open comments easy to scan in the gutter, resolved ones tucked in
  the panel one click away.
- **Packaging.** No new served *file* is introduced — all UI is inline in `viewer.html`, which the
  Dockerfile already `COPY`s (Dockerfile:8). So **no Dockerfile change is required** by this epic. (If
  any ticket ends up extracting an asset into `static/` or a new root file, that ticket must carry the
  `Dockerfile COPY` change — Dockerfile:8 — but the planned design keeps it inline.)

## Rollout phases

Each phase is independently shippable; service lands before the UI/MCP that consume it.

### Phase 1 — Comment store + create/list/get + comment-aware reads (service foundation)
`comments.json` + helpers; `POST/GET /comments`, `GET /comments/{cid}`; `comments_updated` added to
`bump`/`GET /status`. **`GET /feedback` union projection** (`notes[]` = legacy notes ∪
`_comment_as_note`) and the **`summary()` count/status fold** so the dashboard stays live once
authoring moves (BLOCKER-2). No transitions yet (`addressed` keyed on create-time status). Ships a
usable create/read store with curl round-trips. Proves back-compat: a review with no `comments.json`
returns `[]`, and a review with comments shows them in `GET /feedback`/dashboard.

### Phase 2 — State machine (reply / resolve / reopen)
`apply_comment_transition` + `POST .../reply|resolve|reopen`; legal transitions, `status_history`,
409s for illegal transitions. Ships the full server state machine, exercised by curl.

### Phase 3 — MCP tools
`list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` + server-instruction/tool
descriptions; `mcp_smoke.py` extended. Depends on Phases 1-2.

### Phase 4 — Viewer threads + Resolved panel + reopen (single author surface)
Threaded gutter cards (role-distinct), authoring → `POST /comments`, **retirement of the legacy author
surfaces** (`#panel`/`#items` list, `buildMd`/Collect, `save`/`sync`→`/feedback`) so the viewer has one
author surface writing one store, comment cards keyed on `comment_id` (no index `data-id`), Resolved
panel + resolved count, reviewer reopen, `comments_updated` live-reload re-rendering **both** gutter and
Resolved panel. **No client-side legacy seed** (dropped to backlog). Depends on Phases 1-2 (and is
verified against an agent acting via Phase 3).

### Phase 5 — Docs sweep
README API table (+`/comments` rows, `comments_updated` in `/status`), CLAUDE.md contract, AGENTS.md,
`docs/future-mcp.md`, MCP docstring tool count. Must be `done` before the sprint closes (a docs-sweep
ticket cannot carry over — G7).

## Non-goals

- **Auth / real per-user identity.** Roles `reviewer`/`agent` are attribution only; "reviewer-only
  reopen" and "MCP has no reopen tool" are conventions/affordances, **not enforced authz**.
- **A client-side resolve affordance in the viewer.** Resolve is the agent's action (brief: PART-1
  AGENT RESOLUTION; *resolve*→agent, *reopen*→reviewer). The viewer has **no** resolve button; it
  reflects the agent's resolve on poll. Recorded decision (see Assumptions), not an open question.
- **Comments in history rounds.** `snapshot_round` is not extended; comments are live state, recoverable
  in full via their own append-only `status_history`/`thread`, not per-revision snapshots.
- **Real-time push.** Poll/live-reload only (matches the existing viewer).
- **Rewriting/migrating `notes.json` on disk.** The legacy store is frozen at the *data* layer (never
  rewritten); comment state reaches the agent/dashboard via **read-time projection**, not a disk
  migration. The client-side legacy-note seed is **out of this epic** (backlog; if ever done, a single
  server-side idempotent `POST /comments/seed` under `_lock`, never N client POSTs).
- **A comment-thread markdown export (former Collect modal).** Retired in this epic; agents read threads
  via `GET /comments`/MCP. A thread-export affordance is a backlog follow-up.
- **Cross-block / multi-node span anchoring.** A quote spanning inline tags falls back to block-level
  anchoring exactly as today (`highlightNote` returns null → block anchor).

## Key constraints

- **Stdlib-only, zero pip.** No new runtime dependency, service or viewer. The state machine,
  store, routes, MCP tools, and gutter threads are all hand-written over `http.server` + vanilla JS.
  Nothing here tempts a library.
- **Overwrite-based persistence, but append-only semantics for comments.** `comments.json` is written
  whole each time, but the code only ever **appends** to `thread`/`status_history` and flips the
  derived `status` — never drops a prior entry. All writes hold `_lock` (mirroring app.py:214-226,
  app.py:344-348). Back-compat default `[]` on read.
- **Back-compat of `meta.json` and the legacy stores.** Existing reviews lack `comments.json`; readers
  default the missing file to `[]`. `notes.json` on disk and `snapshot_round` are **byte-for-byte
  unchanged** (no disk migration). `GET /feedback` and `summary()` change at the **read** layer only —
  they now *project* comment state into their existing response shapes (BLOCKER-2), and a review with no
  comments derives exactly as today. The behavioural guarantee is "no review regresses," achieved by
  making the legacy read paths comment-aware, **not** by freezing them while authoring moves away.
- **Single-file regex router.** New `/comments` rows insert between app.py:437 (end of `/assets`) and
  app.py:439 (`/asset/{stored}`); `RID` reused; the literal `comments` segment shadows nothing and is
  shadowed by nothing (verified against the ordered matches at app.py:323-468). A new `{cid}` pattern
  must not be broader than necessary.
- **No-auth / id-only tenancy; roles are attribution not authz.** Listing comments widens nothing
  beyond what `GET /api/reviews` already exposes (the service trusts its network). State this in the
  plan, the route docs, and the MCP descriptions honestly: the reopen-is-reviewer-only and
  MCP-has-no-reopen boundaries are **convention**, anyone on the network can call any route.
- **JS-rendered viewer — a 200 is not a render.** G4/G7 for the viewer ticket require
  `scripts/render-smoke.sh` from the **rebuilt container** asserting the new DOM nodes, **plus** CDP
  interaction checks (create → resolve hides + moves to panel; reopen restores; agent-resolve-via-MCP
  appears on poll), measuring with `getBoundingClientRect`/computed style. See Verification.
- **render-smoke is a flat matcher.** Selectors are `tag`/`.class`/`tag.class`/`#id` only — no
  descendant combinators, attributes, or pseudo-classes (a space → exit 2). Assert a node *inside* a
  container with **two** selectors (e.g. `'.gentry' '#resolved'`), never `'#resolved .gentry'`.
- **Dark pane via scheme emulation, never `--force-dark-mode`.** Capture the dark pane with
  `--blink-settings=preferredColorScheme=0` (dark) / `=1` (light), or CDP
  `Emulation.setEmulatedMedia({media:'',features:[{name:'prefers-color-scheme',value:'dark'}]})`.
  `--force-dark-mode` is Chrome's auto-invert (NOT scheme emulation) and bare headless resolves *dark*
  by default, so a no-flag "light" + `--force-dark-mode` "dark" pair is a vacuous proof.
- **Header checks use GET, never `curl -sI`.** There is no `do_HEAD`; a HEAD returns the 501 page. Any
  AC inspecting a response header uses `curl -sD - -o /dev/null <url>` (a GET header-dump).
- **Live instance is on :8139 — never touch it, never `docker compose up`.** Smokes/captures use a
  throwaway container on a different host port (e.g. :8138) with a scratch volume.
- **Commits keep the `Co-Authored-By: Claude` trailer** and reference the ticket ID; process dates are
  `Europe/London`.

## Preferred execution order

1. **MR-033** (svc, Phase 1) — comment store + create/list/get + `comments_updated` + comment-aware
   `GET /feedback` union projection + `summary()` count/status fold (BLOCKER-2).
2. **MR-034** (svc, Phase 2) — state machine: reply/resolve/reopen + 409s + `status_history`; AC
   re-asserts a resolve flips the `GET /feedback` projection `addressed` and the dashboard status/count.
3. **MR-035** (svc, Phase 3) — MCP tools + descriptions + `mcp_smoke` extension (`expected` set + count).
4. **MR-036** (ui, Phase 4) — threaded gutter (keyed on `comment_id`), authoring → `POST /comments`,
   **retire legacy author surfaces** (panel/Collect/`/feedback` writes), Resolved panel + count,
   reviewer reopen, `comments_updated` live-reload re-rendering gutter **and** Resolved panel.
5. **MR-037** (docs, Phase 5) — README/CLAUDE/AGENTS/future-mcp/MCP-docstring sweep (must close in-sprint).

MR-035 (MCP) and MR-036 (viewer) both depend only on MR-033+MR-034 and could run in either order, but
MR-035 first lets MR-036's CDP test drive a real agent resolve over MCP.

## Ticket breakdown

Create in `tickets/` only after G1. IDs are placeholders the orchestrator allocates (next free is
MR-033, sprint-11).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-033 | Comment store (`comments.json`) + `POST/GET /comments` + `GET /comments/{cid}` + `comments_updated` in `/status` + **comment-aware `GET /feedback` union & `summary()` fold** | svc | 1 |
| MR-034 | Comment state machine: `reply`/`resolve`/`reopen` routes, `status_history`, 409 on illegal transitions; resolve flips `GET /feedback` projection + dashboard status/count | svc | 2 |
| MR-035 | MCP tools `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` + agent-expectation descriptions + `mcp_smoke` round-trip (`expected` set literal **and** count → 14) | svc | 3 |
| MR-036 | Viewer: threaded role-distinct gutter cards keyed on `comment_id`, authoring → `POST /comments`, **retire legacy author surfaces** (`#panel`/Collect/`/feedback` writes), Resolved panel + resolved count, reviewer reopen, `comments_updated` live-reload (gutter **and** Resolved panel) | ui | 4 |
| MR-037 | Docs sweep: README API table (+`/comments`, `/status.comments_updated`), CLAUDE.md, AGENTS.md, `docs/future-mcp.md`, MCP docstring tool count (10→14); document the comment-aware `GET /feedback`/dashboard | docs | 5 |

Five tickets, dependency-ordered: `MR-033 → MR-034 → {MR-035, MR-036} → MR-037`. Each is a vertical
slice validated by `py_compile` + a concrete smoke (curl / `mcp_smoke` / render-smoke + CDP). MR-036
grew with the legacy-surface retirement (BLOCKER-1); if it is too large at grooming, the natural split
is "retire `#panel`/Collect" vs "Resolved panel + reopen" as two ui tickets — but both must land in the
sprint (a viewer authoring two stores is the failure mode the retirement prevents). The legacy-note seed
is **not** a split candidate — it is out of the epic (backlog).

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| **Two live author surfaces** — viewer authors comments from a highlight but still authors notes from the popover / `#panel`, POSTing two stores. | Phase 4 **retires** every legacy author surface (`#panel`/`#items` list, `buildMd`/Collect, `save`/`sync`→`/feedback`); the highlight popover repoints to `POST /comments`. Exactly one author surface, one store. MR-036 AC asserts no viewer path writes `notes.json` and `data-id` is `comment_id`-shaped. |
| **Agent/dashboard read paths go stale once authoring moves off `notes.json` (BLOCKER-2).** | `GET /feedback` returns the **union** of legacy notes + a read-time comment projection; `summary()` folds open/resolved comments into counts/status. No disk migration; a no-comment review derives exactly as today. MR-033 AC asserts a review with only comments still shows in `GET /feedback` and reads "feedback"/non-zero on the dashboard. |
| **Anchor model vs the existing highlight matching** — a new offset scheme could mis-anchor on reflow. | Reuse the proven quoted-text-`indexOf`-within-text-node + block fallback (`reconcile`/`highlightNote`); `start`/`end` are disambiguation hints only, not bindings. Verified via the marked-output probe (one element per block; spanning-inline-tag quotes already fall back today). |
| **State-machine edge cases** — double-resolve, reopen-then-resolve, reply-after-resolve. | One server helper `apply_comment_transition` is the only writer; explicit legal-transition table; 409 for illegal (resolve-resolved, reopen-non-resolved), 404 for missing. AC includes a curl proof of each rejection. |
| **Viewer/MCP state divergence** — UI shows a status the server doesn't have. | The viewer never decides status locally; it renders `GET /comments` and POSTs intent. `comments_updated` poll re-fetches after any MCP action. CDP test asserts an MCP resolve appears in the open browser. |
| **Breaking the legacy data path** — comments code corrupts `notes.json` on disk or `snapshot_round`. | `comments.json` is a separate file; `notes.json` on disk and `snapshot_round` are never written by comment paths. `GET /feedback`/`summary()` change at the read layer only (projection). AC re-checks a no-comment review reads byte-identically to today and an existing `notes.json` is never rewritten. |
| **`mark.cmt`/`.gcard` `data-id` collision** — legacy index `i` vs `comment_id`. | Legacy-note *rendering* is retired (SHOULD-3); the viewer renders only comments, keyed on `comment_id`. One `data-id` namespace. MR-036 AC asserts every rendered `data-id` matches `/^c[A-Za-z0-9]{10}$/`. |
| **Router shadowing** — a new route hijacks `/asset` or `/feedback`. | Insert literal `comments` rows between app.py:437 and :439; `comments` collides with no sibling segment; verified against the ordered matches app.py:323-468. |
| **Append-only violated by a whole-file write** — a refactor drops a thread entry. | Code reads the array, mutates only by appending, writes whole under `_lock`. AC asserts a reply then resolve preserves all prior `thread` + `status_history` entries (count grows, never shrinks). |
| **Resolved highlight not actually removed from the doc** — a 200 ≠ a render. | CDP test: after resolve, assert `mark.cmt[data-id=...]` count drops and the thread node exists under `#resolved`, measured on the rendered DOM, both panes via scheme emulation. |

## Verification

General gate: `python3 -m py_compile app.py` for every `svc` ticket; for the `ui` ticket also a
render-smoke from the **rebuilt** container + CDP. **Throwaway container only** (never :8139, never
`docker compose`):

```bash
docker build -t mdreview:cmt /Users/apple/Dev/personal/tools-utilities/mdreview-service
docker run -d --rm -p 8138:8080 --name mdr-cmt mdreview:cmt
BASE=http://localhost:8138
```

### MR-033 — store + create/list/get
```bash
python3 -m py_compile app.py
ID=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"markdown":"# T\n\nHas a target phrase here.\n","title":"cmt"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
# back-compat: a brand-new review has an empty comment list, no 500
curl -s "$BASE/api/reviews/$ID/comments"            # {"comments":[]}
# comments_updated is present and == 0 BEFORE the first comment (NIT)
curl -s "$BASE/api/reviews/$ID/status" | python3 -c 'import sys,json;print("cu_before",json.load(sys.stdin)["comments_updated"])'  # cu_before 0
# create
CID=$(curl -s -X POST "$BASE/api/reviews/$ID/comments" -H 'Content-Type: application/json' \
  -d '{"anchor":{"quoted_text":"target phrase","block_num":"2","start":6,"end":19},"text":"clarify this"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["comment_id"])')
curl -s "$BASE/api/reviews/$ID/comments"            # one comment, status "open", thread len 1
curl -s "$BASE/api/reviews/$ID/comments/$CID"       # full comment + status_history [{to:"open"}]
# comments_updated is now > 0 AFTER the create
curl -s "$BASE/api/reviews/$ID/status" | python3 -c 'import sys,json;print("cu_after",json.load(sys.stdin)["comments_updated"]>0)'  # cu_after True
# BLOCKER-2: comment-aware GET /feedback — the open comment projects into notes[] (no notes.json on disk)
curl -s "$BASE/api/reviews/$ID/feedback" | python3 -c 'import sys,json;d=json.load(sys.stdin);n=d["notes"];print("notes_len",len(n),"quote",n[0]["quote"],"addressed",n[0]["addressed"])'  # notes_len 1, quote "target phrase", addressed False
# BLOCKER-2: comment-aware dashboard — NOT "0 / awaiting"; counts/status reflect the open comment
curl -s "$BASE/api/reviews" | python3 -c 'import sys,json;[print("dash",r["notes_total"],r["status"]) for r in json.load(sys.stdin)["reviews"] if r["id"]=="'$ID'"]'  # dash 1 feedback
```
Expected: empty list on a fresh review; `comments_updated == 0` before the first comment, `> 0` after;
create returns `201` with a `comment_id`; status `open`; one `status_history` entry
`{from:null,to:"open"}`. **Comment-aware reads (BLOCKER-2):** `GET /feedback` projects the open comment
into `notes[]` (`quote`=anchor text, `addressed=false`) with **no** `notes.json` rewritten on disk; the
dashboard shows `notes_total≥1`/`status="feedback"` (never `0`/`awaiting`) for a review with an open
comment. A separate fresh review with *no* comment still reads `0`/`awaiting` (no-comment back-compat).

### MR-034 — state machine
```bash
python3 -m py_compile app.py
# reply (status unchanged, thread grows)
curl -s -X POST "$BASE/api/reviews/$ID/comments/$CID/reply"  -H 'Content-Type: application/json' -d '{"text":"a question"}'   # status open, thread 2
# resolve with justification (agent entry appended, then resolved)
curl -s -X POST "$BASE/api/reviews/$ID/comments/$CID/resolve" -H 'Content-Type: application/json' -d '{"justification":"fixed in v2"}'
#   -> {status:"resolved", resolved_by:"agent", resolved_at:...}; thread 3 (last role agent); status_history += {to:"resolved",by:"agent"}
# illegal: resolve an already-resolved -> 409
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/reviews/$ID/comments/$CID/resolve" -d '{}'   # 409
# reopen (reviewer, optional reply) -> reopened, resolved_by/at cleared
curl -s -X POST "$BASE/api/reviews/$ID/comments/$CID/reopen" -H 'Content-Type: application/json' -d '{"text":"justification rejected"}'  # status reopened
# illegal: reopen a non-resolved -> 409
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/reviews/$ID/comments/$CID/reopen" -d '{}'    # 409
# resolve again from reopened -> resolved
curl -s -X POST "$BASE/api/reviews/$ID/comments/$CID/resolve" -d '{}'   # status resolved (silent, no justification)
# append-only: thread and status_history only ever grow
curl -s "$BASE/api/reviews/$ID/comments/$CID" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("thread",len(d["thread"]),"hist",len(d["status_history"]))'
# BLOCKER-2: resolve flips the comment-aware projection + dashboard (comment now resolved)
curl -s "$BASE/api/reviews/$ID/feedback" | python3 -c 'import sys,json;n=json.load(sys.stdin)["notes"];print("addressed",n[0]["addressed"])'  # addressed True
curl -s "$BASE/api/reviews" | python3 -c 'import sys,json;[print("dash",r["notes_total"],r["notes_addressed"],r["status"]) for r in json.load(sys.stdin)["reviews"] if r["id"]=="'$ID'"]'  # dash 1 1 resolved
# missing comment -> 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/api/reviews/$ID/comments/cZZZZZZZZZZ/resolve" -d '{}'  # 404
```
Expected: reply keeps `open` and grows `thread`; resolve flips to `resolved` with an agent thread entry
+ `resolved_by:"agent"`; double-resolve and reopen-non-resolved → `409`; reopen clears resolved fields;
the `open→resolved→reopened→resolved` walk leaves `status_history` length 4 and `thread` never shrinks;
missing id → `404`. **BLOCKER-2:** after the final resolve the `GET /feedback` projection's `addressed`
flips to `true` and the dashboard reflects it (`notes_addressed` grows; once all comments resolved and
all notes addressed → `status="resolved"`).

### MR-035 — MCP tools
```bash
MDREVIEW_BASE=$BASE python3 mcp_smoke.py    # exit 0; asserts the 14 tools + comment round-trip
```
Update **both** the `expected` set literal and the count assertion at mcp_smoke.py:60-63 (add the four
tool names to `expected`; change `"the 10 tools"`/`== 10` → 14) — a smoke that only bumps the count but
leaves `expected` at 10 names would fail `names == expected`, so both must move together.
The extended smoke: `tools/list` returns exactly 14 tools incl. the four comment tools; seeds a review
+ a comment via HTTP; then `list_comments(status="open")` returns it, `get_comment` returns the thread,
`reply_to_comment` grows the thread, `resolve_comment` (no justification) returns `status:"resolved",
resolved_by:"agent"`; `list_comments(status="open")` then excludes it and `status="resolved"` includes
it. Also assert each new tool description contains the agent-workflow guidance (list-first; reply vs
resolve; justification optional-but-recommended; never reopen).

### MR-036 — viewer (rebuilt container; render-smoke + CDP, both panes)
**render-smoke (rebuilt image, flat selectors, two-selector form for nested nodes):**
```bash
# seed a review with a comment + a resolved comment via the HTTP routes first, open /review/$ID
scripts/render-smoke.sh "$BASE/review/$ID" '.gcard' '.gentry' '#resolved' '.resolved-count' 'mark.cmt'
```
Each selector must match ≥1 node: `.gcard` (a thread card), `.gentry` (a thread entry — role-distinct
class variants e.g. `.gentry.reviewer`/`.gentry.agent` each asserted separately), `#resolved` (the
Resolved panel), `.resolved-count` (the count), `mark.cmt` (an active highlight). Assert a nested node
with two selectors (`'.gentry' '#resolved'`), never `'#resolved .gentry'`.

**Single-author-surface assertions (BLOCKER-1 / SHOULD-3):**
```bash
# the rendered viewer keys highlights/cards on comment_id, not the array index, and no #panel note list
scripts/render-smoke.sh "$BASE/review/$ID" 'mark.cmt' '.gcard'   # match; then via --dump-dom assert:
#   every mark.cmt/.gcard data-id matches /^c[A-Za-z0-9]{10}$/  (no bare integer index)
#   no '#panel'/'#items' legacy note list, no '#collect' modal trigger rendered
```
Assert in the CDP harness that authoring does **not** issue `POST /feedback` (network log) and that no
`notes.json` write occurs — the only author surface is `POST /comments`.

**CDP interaction states (Node built-in WebSocket; measure with `getBoundingClientRect`/computed
style; both panes via `Emulation.setEmulatedMedia` prefers-color-scheme dark/light — never
`--force-dark-mode`):**
1. **Authoring** — select text → "+ comment" → save → assert a new `.gcard` exists and a `mark.cmt`
   anchors it, the request was `POST /comments` (not `/feedback`), and the comment count via `GET
   /comments` grows.
2. **Agent resolve appears on poll** — call `POST /comments/{cid}/resolve` out-of-band **(simulating the
   agent acting over MCP — there is no client-side resolve button by design, SHOULD-1)** → within the
   poll interval assert the card's `mark.cmt` count drops, the active `.gcard` for it is gone, and a
   thread node appears under `#resolved` with the resolved-count incremented.
3. **Reviewer reopen** — click Reopen in the Resolved panel → assert the `mark.cmt` highlight is
   restored (count returns), the card is back in the active gutter, and the resolved-count decremented.
4. **Reply to a *resolved* comment re-renders the Resolved panel (SHOULD-4)** — call `POST
   /comments/{cid}/reply` (role agent) out-of-band on an already-resolved comment → within the poll
   interval assert a **new `.gentry` appears under `#resolved`** for that thread (the resolved thread
   re-renders, not just the active gutter), and the comment stays in `#resolved` (status unchanged).
5. **Role distinction** — assert reviewer vs agent entries have different computed background/border
   (`getComputedStyle`), in **both** panes.

**Header check (if any asset MIME is ever inspected — uses GET, not `-sI`):**
```bash
curl -sD - -o /dev/null "$BASE/review/$ID"     # 200, text/html; charset=utf-8
```

**Capture** a screenshot of an open thread + the Resolved panel in **both** panes (scheme-emulated)
under `reviews/sprint-NN-render-evidence-*` for G7.

### MR-037 — docs
Grep the updated README API table for the `/comments` rows and the `comments_updated` field; confirm
the MCP docstring says 14 tools; `python3 -m py_compile app.py` and `MDREVIEW_BASE=$BASE python3
mcp_smoke.py` still pass (docs-only, but re-run to prove nothing regressed). This ticket must be `done`
before the sprint closes (G7 — docs-sweep is not carry-over-eligible).

**Teardown:** `docker rm -f mdr-cmt`.

## Recorded decisions, assumptions & open questions

No BLOCKER-FOR-HUMAN: the "preserve existing functionality/data" constraint and the chosen model do
**not** conflict — the gutter-thread *is* the evolved highlight-to-comment surface (Option (a)), legacy
`notes.json` is never rewritten on disk, and the agent/dashboard read paths stay live via read-time
projection (BLOCKER-2). No unavoidable product fork. Proceeding on these.

**Recorded decisions (settled by the brief / the G1 review, not open):**

- **No client-side resolve affordance in the viewer (SHOULD-1).** The brief assigns *resolve* to the
  agent (PART-1 "AGENT RESOLUTION") and *reopen* to the reviewer (PART-1); the viewer therefore has
  **no** resolve button — resolve arrives over MCP and the viewer reflects it on poll. This is a
  recorded decision, not an open question. The resolve-reflection path stays testable via the
  out-of-band `POST /comments/{cid}/resolve` in the CDP harness, **explicitly labelled as simulating
  the agent acting over MCP** (MR-036 verification step 2). (If the owner later wants a manual resolve,
  it is additive but touches the model — role attribution must be decided then; out of this epic.)
- **Notes-vs-comments = Option (a): one store, viewer authoring evolves onto comments (G1 review #1).**
  The existing highlight-to-comment gutter is a projection of `notes`; comments are a superset (the old
  note becomes the thread's first entry). Legacy `notes.json` data is frozen on disk; the legacy read
  paths are made comment-aware rather than walled off. Exactly one author surface after Phase 4.
- **No client-side legacy-note seed (SHOULD-2).** Dropped to backlog: the store has no compare-and-set,
  so a client-side first-load seed races (two tabs / tab+MCP double- or partial-seed). If ever done, a
  single server-side idempotent `POST /comments/seed` under `_lock`, not N client POSTs.

**Assumptions (best-effort defaults, low blast radius):**

- **(load-bearing) Anchor model reuses the existing quoted-text + block-fallback matching**; `start`/
  `end` are stored **text-node-local** hints, not authoritative offsets. Justification: inventing a
  global-offset binding would regress on reflow and on inline-tag-spanning quotes, which the current
  code already handles by falling back to a block anchor. Verified via the marked-output probe.
- **(minor) `comment_id` format** = `"c"+secrets.token_hex(5)` → **11 chars** (`token_hex(5)` is 10 hex
  digits + the `c` prefix), matching the regex `(c[A-Za-z0-9]{10})`. Any opaque non-`/` string works.
- **(minor) `GET /comments` default status filter** = `all` for the HTTP route (the viewer wants every
  state to render the Resolved panel); the **MCP** `list_comments` default is `open` per the brief.
- **(minor) `GET /feedback`/`summary()` projection counts all comments toward total, resolved toward
  addressed** (mirrors note semantics). If grooming prefers counting only open comments toward total,
  it is a one-line change confined to MR-033 — does not affect the rest.
- **(minor) Comments are not snapshotted into history rounds.** They are live state with their own
  append-only history; `snapshot_round` is unchanged. If the owner later wants per-revision comment
  snapshots, that is a follow-up epic.
