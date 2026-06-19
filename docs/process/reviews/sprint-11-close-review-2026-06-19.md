---
review_of: sprints/sprint-11.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G7 sprint-close review — sprint-11 (comment-resolution)

**Verdict: PASS.** All five tickets (MR-033–037) shipped to `dev` and match their acceptance
criteria against the running service, not just the ticket prose. Both G1 BLOCKERs are shipped and
verified on the rebuilt :8138 image: the viewer has exactly one author surface (`POST /comments`,
no `/feedback` write, no `notes.json` write, no legacy `#panel`/`#items`/`#collect`/`#modal`/`#toggle`),
and `GET /feedback`/the dashboard are comment-aware so nothing the human says is lost. My own
render-smoke (8 selectors, real DOM nodes on a seeded open+resolved review) passed, `mcp_smoke`
passed (22 assertions, 14 tools), and the state machine / 409-404 table / append-only invariant / the
BLOCKER-2 projection flips were all reproduced by hand. Two NITs, zero SHOULD, zero BLOCKER.

## Per-ticket AC check

- **MR-033** (store + comment-aware reads) — **MET.** `comments.json` sibling of `notes.json`,
  default `[]`; helpers + pure `_comment_as_note`; create returns 11-char `comment_id`,
  `status:"open"`, `status_history:[{from:null,to:"open"}]`; `GET /status` carries `comments_updated`
  (== 0 before first comment, > 0 after); `GET /feedback` unions legacy notes + comment projection;
  `summary()` folds comments into counts/status. No-comment back-compat reproduced byte-for-byte.
- **MR-034** (state machine) — **MET.** Single writer `apply_comment_transition` under `_lock`
  (app.py:315) backs both the HTTP routes and (via those routes) MCP. Walk + 409/404 table + the
  append-only invariant verified live (see commands). BLOCKER-2 flip both directions verified.
- **MR-035** (MCP tools) — **MET.** 14 tools, the four comment tools present, no `reopen` tool,
  `document_id`=review id, descriptions encode list-first / reply-vs-resolve / justification-optional
  / never-reopen; docstring reads 14; `mcp_smoke` round-trip passes.
- **MR-036** (viewer) — **MET.** Single author surface (BLOCKER-1) confirmed by grep + rendered-DOM
  dump; cards/highlights key on `comment_id` (no bare-integer `data-id`); Resolved panel + reopen +
  role-distinct `.gentry.reviewer`/`.gentry.agent`; live-reload re-renders both panels (reply-to-
  resolved bumps `comments_updated`); no resolve button (recorded decision); dual-pane screenshots real.
- **MR-037** (docs) — **MET.** README has all six `/comments` rows + `comments_updated`; dashboard
  status note is comment-aware; CLAUDE/AGENTS/future-mcp document the four tools + no-reopen convention
  + the union projection; MCP docstring says 14.

## Two G1 BLOCKERs — explicit

- **BLOCKER-1 (exactly one viewer author surface)** — **SHIPPED.** `grep` of `viewer.html`: zero
  `POST /feedback`, zero `notes.push`/`notes.json`; the only write paths are `POST /comments`,
  `/reply`, `/reopen`. Legacy ids `#panel`/`#items`/`#collect`/`#modal`/`#toggle` are absent from
  source and from the rendered DOM. Rendered `data-id` values are exactly the two seeded
  `comment_id`s (no array index). The `data-id="'+id+'"` grep hit is the `focusPair` querySelector
  template (viewer.html:389-390), not a rendered node.
- **BLOCKER-2 (GET /feedback + dashboard stay live, comment-aware)** — **SHIPPED.** A review with one
  open comment and no `notes.json` notes returns `notes_len 1`/`addressed False` from `GET /feedback`
  and `1 0 feedback` on the dashboard (never `0/awaiting`); a resolve flips `addressed→True` and the
  dashboard to `1 1 resolved`; a reopen flips both back. `notes.json` on disk stays `[]` (never
  rewritten) across the whole walk. The legacy `POST /feedback` route is still live and `GET /feedback`
  unions legacy notes + comment projections (verified: 1 legacy + 1 open + 1 resolved = 3 notes).

## Findings

- **[NIT]** `POST /comments/{cid}/reply` with an empty/absent `text` returns `200` and appends a
  blank thread entry (verified: `reply-empty-body 200`). `create_comment` and `resolve` tolerate
  empty text by design, but a blank reply is junk in an append-only thread. Minor; a one-line
  guard (`400` on empty `text` for `reply`) would tidy it. Not blocking.
- **[NIT]** MR-034's AC documents the reply body as `{text,author?,role?}`, but the route reads only
  `role`/`text` (app.py:607) and `apply_comment_transition` sets `author=role` (app.py:332); a
  caller-supplied `author` is ignored. Harmless — `author` is documented as a display string
  defaulting to role and the viewer never sends it — but the AC over-promises a field that isn't
  wired. Doc/AC nit, not a code defect.

## Commands run + results

- `python3 -m py_compile app.py mcp_server.py mcp_smoke.py` → **OK**.
- `MDREVIEW_BASE=http://localhost:8138 python3 mcp_smoke.py` → **PASS** (22/22; 14 tools; comment
  round-trip list→get→reply→resolve + open/resolved filter).
- `RENDER_SMOKE_VTB=3000 scripts/render-smoke.sh /review/<seeded> .gcard .gentry .gentry.reviewer
  .gentry.agent #resolved .resolved-count mark.cmt .rcard` → **EXIT 0**, all ≥1 node
  (`.gcard`1 `.gentry`4 `.gentry.reviewer`2 `.gentry.agent`2 `#resolved`1 `.resolved-count`1
  `mark.cmt`1 `.rcard`1) on a review seeded with one open + one resolved comment.
- `--dump-dom` of the same review → `data-id` values are exactly the two `comment_id`s; zero
  bare-integer `data-id`; zero legacy `id="panel|items|collect|modal|toggle"`.
- State machine (curl): reply→`open`/thread 2; resolve+justif→`resolved`/`resolved_by:agent`/thread 3
  (last role agent); double-resolve→**409**; reopen→`reopened`/resolved fields cleared;
  reopen-non-resolved→**409**; silent resolve from reopened→`resolved`; final
  `status_history` = `[null→open, open→resolved, resolved→reopened, reopened→resolved]` (len 4),
  `thread` len 4 (never shrinks); missing comment→**404**.
- BLOCKER-2 (curl): open comment → feedback `addressed False` + dash `1 0 feedback`; resolve →
  feedback `addressed True` + dash `1 1 resolved`; reopen → `addressed False` + dash `1 0 feedback`;
  `notes.json` on disk stayed `[]` throughout.
- summary() edges (curl): all-resolved→`resolved`; feedback-md-with-no-notes keeps `resolved`;
  unaddressed legacy note + resolved comment→`feedback` (not falsely resolved).
- SHOULD-4 (curl): reply to a resolved comment keeps `status:resolved`, grows thread, and bumps
  `comments_updated` (the poll re-render trigger).
- Screenshots `reviews/sprint-11-render-evidence-2026-06-19/comments-{light,dark}.png` — viewed: two
  genuinely distinct panes (light `rgb(250,250,249)` vs near-black), each showing an open gutter
  thread + the Resolved panel with role-distinct (amber reviewer / teal agent) entries, active
  `mark.cmt` highlights, and `2 open · 1 resolved`. Real dual-pane scheme emulation, not a vacuous
  `--force-dark-mode` pair.
- `git log` — MR-033..037 each committed to `dev` in dependency order with ticket IDs; working tree clean.

## Can sprint-11 close?

**Yes.** Verdict PASS; both G1 BLOCKERs shipped; render-smoke + mcp_smoke pass; the two NITs are
non-blocking and can be backlogged. Remaining G7 checklist items (retro recorded in the sprint file,
`close_review:` frontmatter set, carry-overs noted — there are none) are process steps the
orchestrator completes; the review gate itself passes. Clear for the dev→main PR.

## Resolution log

- `2026-06-19` — **NIT-1 (empty reply appends a blank entry) — FIXED.** `apply_comment_transition`
  reply branch now returns `400 {"error":"reply text required"}` when `text` is empty/blank
  (`app.py`), instead of appending an empty thread entry. Verified on the rebuilt :8138: empty
  `{"text":"   "}` → 400, missing text → 400, a normal reply still appends (thread 2, status open);
  `mcp_smoke` (reply uses non-empty text) still PASS.
- `2026-06-19` — **NIT-2 (MR-034 AC over-promised a `reply` `author` param) — FIXED (doc).** MR-034's
  AC reply body corrected to `{text, role?}` (+ "empty `text` → 400"), matching the route (which
  derives `author` from `role`). No code change.
- Both NITs were non-blocking; resolved in-sprint rather than carried. Verdict stands **PASS**;
  sprint-11 cleared to close.

