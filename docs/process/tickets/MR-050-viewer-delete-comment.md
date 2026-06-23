---
id: MR-050
title: Viewer — let a reviewer delete a comment they made by mistake (wire the existing DELETE endpoint into the UI)
status: ready          # staff critique resolved (READY-WITH-TWEAKS applied) — docs/process/reviews/MR-050-scope-review-2026-06-23.md
layer: ui
priority: P2
sprint:                # unscheduled — scoped/groomed, not yet committed to a sprint
epic:                  # none — standalone bug/usability fix (GitHub issue #12)
depends_on: []
branch:
created: 2026-06-23
updated: 2026-06-23
---

## Goal

A human reviewer who posts a wrong/junk comment (fat-fingered selection, mistaken note) has **no way
to remove it from the viewer** — comment cards only offer Reply and Reopen. The backend already
hard-removes comments (`DELETE /api/reviews/{id}/comments/{cid}`, plus the `delete_comment` MCP tool
from MR-045); this is a **UI gap only**. Add a delete affordance in `viewer.html` wired to the
existing endpoint, so a reviewer can self-serve a mistake without asking the agent.

GitHub issue: #12.

## Design (resolved — staff critique `MR-050-scope-review-2026-06-23.md`, verdict READY-WITH-TWEAKS)

1. **Deletable scope = the thread has NO `agent` entry** (changed from the draft's "delete anything").
   Delete is offered only on a comment whose thread contains no `role: 'agent'` entry — i.e. the
   reviewer's own un-engaged comment, the exact "I made a mistake" case from issue #12. This is
   strictly narrower than "delete anything" and avoids the human hard-nuking *engaged* agent feedback
   — which is precisely what the `delete_comment` tool warns agents off (`mcp_server.py:251-253`); the
   ticket must not let the human do to the agent what the agent is told not to do to the human. The
   predicate is trivial — `renderAll()` already iterates `c.thread`/`e.role` (`viewer.html:407-410`).
   A broader "human can delete anything" variant would need an explicit product-owner decision — **not
   taken**.
2. **Confirm = inline two-step, and the poll must not wipe it.** "Delete" → the button becomes
   "Confirm?" (~3s) → second click deletes. **BLOCKER (critique):** `renderAll()` rebuilds `.gcard`
   from scratch (`G.innerHTML=''`, `viewer.html:449`) on every `comments_updated` poll tick
   (`viewer.html:571`), and an agent polls/acts concurrently — so a pending inline confirm would be
   silently wiped mid-window. Fix: **extend the existing poll-skip guard** (added in MR-049, which
   bails while `#addbtn`/`#pop` is open, `viewer.html:567`) to also bail while a delete-confirm is
   pending. (Acceptable alternative: native `confirm()`, which blocks synchronously — viable now that
   validation no longer depends on a headless click-through; inline preferred for UX consistency.)
3. **Whole-thread only.** The API deletes the whole comment thread (`app.py:602-610`); no per-reply
   delete (out of scope — no API). With the no-agent-entry rule a deletable thread is reviewer-only
   anyway, so "removes replies too" rarely bites; the confirm copy still says it's permanent.
4. **Placement:** a small, muted **secondary** affordance (text "Delete" or 🗑 in the card header),
   clearly distinct from Reply/Reopen. Implementer note: the `.gcard .gx` CSS at `viewer.html:87` is
   **dead/pre-existing — do not assume it's wired**.
5. **Cards it appears on:** wherever the no-agent-entry predicate holds. In practice that's active
   `.gcard`s the agent hasn't touched; resolved `.rcard`s almost always carry an agent entry (resolve
   writes one, `app.py:621-622`) so delete won't show there — **accepted** (if an agent resolved it,
   it wasn't junk).

## Acceptance criteria

- [ ] A small, secondary **Delete** affordance (distinct from Reply/Reopen) renders on a comment card
      **only when the thread has no `agent` entry** (the reviewer's own un-engaged comment).
- [ ] Clicking it requires an explicit **inline two-step confirm** before issuing
      `DELETE /api/reviews/{id}/comments/{cid}`; the confirm copy states the comment is removed
      permanently (no undo).
- [ ] The 2s poll does **not** wipe a pending confirm — the poll-skip guard is extended to bail while
      a delete-confirm is open (mirrors the `#addbtn`/`#pop` guard, `viewer.html:567`).
- [ ] On success: `deleteComment(cid)` → `fetchComments()` → `renderAll()` (the existing
      `replyTo`/`reopenComment` pattern) so the card **and** its inline `mark.cmt` highlight disappear
      and the counts update; `toast('Comment deleted')`. On failure (non-2xx / network): no optimistic
      removal — the card stays and `toast('Could not delete')`.
- [ ] No backend change — `app.py` untouched.
- [ ] **Validation (G4 ui), split by what each tool can actually prove** (BLOCKER from critique: the
      old AC asked `render-smoke.sh` to click — it's a DOM-node counter, it can't):
  - **Presence** — `scripts/render-smoke.sh <url> .gcard '[data-act=delete]'` asserts the affordance
    rendered (presence only; the tool cannot click or assert absence).
  - **Behaviour** — a curl round-trip (mirrors MR-045's validation): create a review + a
    reviewer-only comment → `DELETE /comments/{cid}` → `{"deleted":cid}` → `GET /comments` no longer
    lists it → a second `DELETE` 404s.
  - **Interaction** — a node-CDP check (the repo's `agent_smoke.py` / MR-049 pattern): load the
    viewer, click Delete → Confirm, assert the `.gcard` **and** its `mark.cmt` are gone and
    `GET /comments` is empty. Screenshot + evidence under `reviews/`.

## Notes / context

- Backend already present: `app.py` `DELETE /api/reviews/{id}/comments/{cid}` (the route returns
  `{"deleted": cid}`); `delete_comment` MCP tool (`mcp_server.py`). MR-045 shipped these for agents.
- Viewer wiring to mirror: `viewer.html` — comment cards built in `renderAll()` (`.gcard` greply /
  `.rcard` reopenbox), button wiring just below; the action functions `createComment` / `replyTo` /
  `reopenComment` are the pattern a new `deleteComment(cid)` should follow (POST→`fetchComments()`→
  `renderAll()`→`toast`). Add a `deleteComment` that calls `DELETE` then the same refresh.
- This is the human/no-auth surface: roles are attribution, not auth — so any per-author restriction
  (fork #2) is a UX convention, not an enforced boundary.

## Work log

_Not started — scoped + groomed for critique only._

## Validation

_Pending implementation._

## Follow-ups

- If fork #2 lands as "reviewer-authored only", a future ticket could add an agent-comment delete
  path. Capture only if chosen.
