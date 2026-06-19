---
id: sprint-11
name: comment-resolution
status: active
start: 2026-06-19
end: 2026-06-19
goal: Ship the Google-Docs comment-resolution workflow — shared server-side comment store + state machine, four MCP tools, and the viewer threads/Resolved-panel/reopen — preserving existing commenting by evolving it onto comments and keeping GET /feedback + the dashboard live (comment-aware).
close_review:
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

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-11-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      acceptance criteria, **including a render smoke** of `viewer.html` (MR-036), and its findings are
      resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
