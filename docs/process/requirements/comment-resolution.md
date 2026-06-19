---
slug: comment-resolution
captured: 2026-06-19
source: user request 2026-06-19 (waqas) — "new feature brief"; chose the full feature-cycle. "Show me the result when done."
related_epic: epics/comment-resolution-plan.md
---

# Google-Docs-style comment resolution workflow (UI + MCP)

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> Add a Google Docs–style comment resolution workflow to mdreview — both the UI in the document
> view AND the MCP tools the agent uses to act on comments. Highlight-to-comment already works; this
> adds threaded replies, agent-side resolution, a resolved-history panel, and reviewer reopen.
>
> **PART 1 — UI (document view)**
>
> **COMMENT THREADS**
> - Each comment is anchored to its highlighted text span and opens as a thread in the side
>   margin/panel.
> - A thread holds multiple entries (replies): author, role (reviewer vs agent), text, timestamp.
>   Visually distinguish my comments from the agent's.
>
> **AGENT RESOLUTION**
> - The agent can mark any open comment "resolved".
> - Justification is OPTIONAL: resolve with a note OR with no note. If given, the justification
>   appears as the final agent-attributed entry in the thread before it's marked resolved. Record
>   who resolved it and when.
>
> **RESOLVED STATE (hide + history)**
> - On resolve, the comment and its highlight leave the active document view.
> - Resolved threads move to a "Resolved" history panel showing the full thread (original comment,
>   replies, justification). Show a resolved count.
>
> **REOPEN + REPLY (reviewer only)**
> - From the Resolved panel I can REOPEN a thread: highlight restored, status back to open. I can
>   add a reply when reopening (e.g. to reject the agent's justification). The agent can then resolve
>   again.
> - Track status transitions (open → resolved → reopened); preserve full history, never overwrite.
>
> **POLISH**
> - Consistent with the existing dark theme and dense styling. Open comments easy to scan; resolved
>   ones out of the way but one click away.
>
> **PART 2 — MCP TOOLS (so the agent knows what to do)**
>
> Expose these tools on the mdreview MCP server. Encode the workflow in the tool descriptions so the
> agent follows it without extra prompting.
>
> **list_comments** — Desc: List comments on a document. Call FIRST to see what needs attention.
> Params: `document_id` (req), `status` (open|resolved|reopened|all, default open). Returns:
> `[{ comment_id, status, anchor:{quoted_text,start,end}, thread:[{author, role:"reviewer"|"agent", text, ts}], created_by, resolved_by, resolved_at }]`
>
> **get_comment** — Desc: Fetch one comment thread in full (all replies + status_history).
> Params: `comment_id` (req)
>
> **reply_to_comment** — Desc: Add a reply WITHOUT resolving. Use to ask a clarifying question or
> respond before deciding. Params: `comment_id` (req), `text` (req)
>
> **resolve_comment** — Desc: Mark a comment resolved. `justification` is OPTIONAL — provide it to
> explain (appended to thread, attributed to agent) or omit to resolve silently. On resolve, comment
> is hidden from the document and moved to the Resolved panel. Params: `comment_id` (req),
> `justification` (optional). Returns: `{ comment_id, status:"resolved", resolved_by:"agent", resolved_at }`
>
> (reopen is reviewer-only and lives in the UI — not an agent tool.)
>
> **AGENT EXPECTATIONS (put in server instructions / tool descriptions):**
> - Always `list_comments(status="open")` before acting; only address what the reviewer raised.
> - Use `reply_to_comment` when a comment is a question or needs discussion; use `resolve_comment`
>   only when the issue is actually addressed.
> - `justification` is optional but recommended — the reviewer can reopen, so a clear note reduces
>   back-and-forth.
> - The agent never reopens. After a reviewer reopen, the agent sees it via `list_comments`
>   (status reopened/open) and can reply or resolve again.
>
> **CONSTRAINTS**
> - Preserve all existing commenting/highlighting functionality and data.
> - Keep the resolve → reopen → resolve state machine consistent between UI and MCP (shared backend
>   state).
> - Show me the result when done.

## Scope notes (for grooming, not changes to the ask)

- Multi-component: **service** (shared backend comment store + state machine + routes), **viewer**
  (`viewer.html` — threads, agent-resolution display, Resolved history panel, reviewer reopen),
  **MCP** (`mcp_server.py` — `list_comments`/`get_comment`/`reply_to_comment`/`resolve_comment` +
  server/tool-description instructions). Likely several MR tickets.
- `document_id` (MCP) = the review `id`. Comments live server-side (shared by UI + MCP), not just
  browser localStorage.
- Roles `reviewer`/`agent` are **attribution, not auth** (no-auth, id-only tenancy) — "reviewer
  only" reopen is a UI affordance, not an enforced authz boundary. State this honestly.
- Must preserve the existing highlight-to-comment + `POST/GET /feedback` notes flow + dashboard note
  counts (or cleanly migrate). The load-bearing fork: how the new threaded-comment model relates to
  the current `notes.json` (`[{num,quote,note,addressed}]`).

## Out of scope

- Auth / real per-user identity (roles are attribution only).
- Real-time push (poll/live-reload is acceptable, matching the existing viewer).

## Amendments

_None yet._
