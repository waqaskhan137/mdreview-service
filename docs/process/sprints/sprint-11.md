---
id: sprint-11
name: comment-resolution
status: closed
start: 2026-06-19
end: 2026-06-19
goal: Ship the Google-Docs comment-resolution workflow — shared server-side comment store + state machine, four MCP tools, and the viewer threads/Resolved-panel/reopen — preserving existing commenting by evolving it onto comments and keeping GET /feedback + the dashboard live (comment-aware).
close_review: reviews/sprint-11-close-review-2026-06-19.md
---

## Goal

By the end of the sprint mdreview has a real comment-resolution workflow: a reviewer highlights text and
starts a **threaded** comment; the agent (over MCP) lists open comments, replies, or resolves (optional
justification); resolved threads hide from the doc and move to a **Resolved** panel with a count; the
reviewer can **reopen**. One `open → resolved → reopened` state machine is enforced server-side and
shared identically by the viewer and MCP. Existing behaviour does not regress: the highlight-to-comment
surface **evolves into** the thread (one author surface, one store), and `GET /feedback` + the dashboard
counts stay live by becoming comment-aware (read-time projection, no `notes.json` disk migration).

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-033 | Comment store + `POST/GET /comments` + `GET /comments/{cid}` + `comments_updated` + comment-aware `GET /feedback` & `summary()` | svc | P1 | done |
| MR-034 | Comment state machine — reply/resolve/reopen routes, `status_history`, 409 on illegal transitions | svc | P1 | done |
| MR-035 | MCP tools `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` + descriptions + `mcp_smoke` round-trip | svc | P1 | done |
| MR-036 | Viewer — threaded `comment_id`-keyed gutter cards, authoring → `POST /comments`, retire legacy author surfaces, Resolved panel + reopen, live-reload | ui | P1 | done |
| MR-037 | Docs sweep — README/CLAUDE/AGENTS/future-mcp + MCP docstring 10→14 + comment-aware feedback/dashboard | docs | P2 | done |

## Preferred execution order

Dependency-ordered: `MR-033 → MR-034 → {MR-035, MR-036} → MR-037`. MR-035 (MCP) before MR-036 (viewer)
so the viewer's CDP test can drive a real agent resolve over MCP.

1. **MR-033** — comment store + create/list/get + `comments_updated` + the comment-aware read
   projections (BLOCKER-2 floor). Curl round-trip.
2. **MR-034** — the state machine: reply/resolve/reopen + 409s + `status_history`; resolve flips the
   projections. Curl proof of each rejection.
3. **MR-035** — the four MCP tools + agent-expectation descriptions + `mcp_smoke` (expected set + count
   → 14) round-trip.
4. **MR-036** — viewer threads + Resolved panel + reopen + retire legacy author surfaces; render-smoke
   + CDP interaction states, both panes.
5. **MR-037** — docs sweep (must close in-sprint; not carry-over-eligible).

## Notes / retro

- `2026-06-19` — **Closed at G7 (staff-critic PASS).** All five tickets shipped to `dev` in
  dependency order. The load-bearing G1 fork (one comment store, viewer authoring evolves onto
  comments, legacy read paths kept live by read-time projection) held up: the close review
  independently confirmed both G1 BLOCKERs shipped — exactly one viewer author surface (no
  `notes.json` write remains) and `GET /feedback`/dashboard stay comment-aware (never "0/awaiting"
  with open comments; `notes.json` on disk never rewritten).
- **Validation:** `py_compile` + `docker build`; `mcp_smoke` (14 tools + comment round-trip, 22
  assertions); `render-smoke` (8 DOM selectors) + a Node-CDP harness (15 interaction checks:
  authoring posts `/comments` not `/feedback`; resolve-on-poll → Resolved panel; reopen restores;
  reply-to-resolved re-renders; role colors differ; `comment_id` keying); dual-pane screenshots
  under `reviews/sprint-11-render-evidence-2026-06-19/`.
- **G7 findings:** 0 BLOCKER / 0 SHOULD / 2 NIT — both NITs fixed in-sprint (empty-reply → 400;
  MR-034 AC reply-body wording). See the close review's Resolution log.
- **Carry-overs:** none. **Backlog spun off:** legacy-note client seed (server-side idempotent
  `POST /comments/seed` if ever wanted); comment-thread markdown export (former Collect); a manual
  viewer resolve affordance; Resolved-panel placement polish (it overlays lower gutter cards when
  open).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-033–037 all `done`;
      no carry-overs;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-11-close-review-2026-06-19.md`, verifying shipped work against each ticket's
      acceptance criteria, **including a render smoke** of `viewer.html` (MR-036), and its findings are
      resolved or carried — **PASS**, 2 NITs resolved in-sprint;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
