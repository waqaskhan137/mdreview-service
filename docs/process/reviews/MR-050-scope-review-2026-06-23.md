---
review_of: tickets/MR-050-viewer-delete-comment.md
gate: scope
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: READY-WITH-TWEAKS
status: resolved   # tweaks applied to the ticket 2026-06-23 (see Resolution log)
---

# MR-050 scope review — viewer delete-comment affordance

> **Resolution log (2026-06-23).** All findings applied to `tickets/MR-050-viewer-delete-comment.md`;
> ticket moved to `ready`. No product-owner decision was required (the safe fork-#2 default unblocks
> implementation).
> - **BLOCKER-1 (smoke AC names a tool that can't click):** AC split into Presence
>   (`render-smoke.sh`, node-count only), Behaviour (curl create→DELETE→list→re-delete-404, mirroring
>   MR-045), and Interaction (node-CDP click-through, the `agent_smoke.py`/MR-049 pattern). The
>   render-smoke.sh "click-through" claim is removed.
> - **BLOCKER-2 (inline confirm races the 2s poll):** AC + design now require extending the MR-049
>   poll-skip guard (`viewer.html:567`) to bail while a delete-confirm is pending; native `confirm()`
>   noted as the synchronous alternative.
> - **Fork #2 → "delete only when the thread has no `agent` entry"** (was "delete anything"); the
>   broader variant is flagged as a product-owner decision, not taken.
> - **Fork #5** clarified (delete won't appear on resolved cards since `resolve` writes an agent
>   entry — accepted). **NIT:** dead `.gcard .gx` CSS (`viewer.html:87`) noted for the implementer.

**Verdict: READY-WITH-TWEAKS.** The ticket is correctly framed as UI-only, the backend ground truth
checks out, and four of the five forks land on the right call. But two AC defects must be fixed before
pickup: the render-smoke AC names a tool (`scripts/render-smoke.sh`) that *cannot* perform the
click-through it asks for, and fork #1's inline-confirm collides with the live poll loop in a way the
ticket does not address. Neither needs a product-owner decision; both are mechanical AC/wording fixes.
Fork #2 (deletable scope) is the one place I change the recommendation — not because the human lacks the
right to curate, but because the ticket's blanket "delete any comment, incl. agent, behind a confirm"
is broader than the bug (#12: *the reviewer's own* mistaken comment) and is cheap to scope down.

## Ground truth — verified against code

- **Backend exists and returns as claimed.** `DELETE /api/reviews/{id}/comments/{cid}` returns
  `200 {"deleted": cid}` (`app.py:610`), `404 {"error":"not found"}` when the review is absent
  (`app.py:595-596`), `404 {"error":"no such comment"}` when the comment is absent
  (`app.py:606-607`), and **bumps `comments_updated`** (`app.py:609`). Confirmed.
- **No author/role check on delete.** The DELETE branch (`app.py:602-610`) filters purely by
  `comment_id`; it never inspects `role`/author. So "the API convention restrains agents" is a
  *documented convention only* (echoed by the `delete_comment` tool description,
  `mcp_server.py:248-253`), not an enforced boundary. The ticket states this correctly.
- **MCP tool exists** (`mcp_server.py:248`, dispatch at `mcp_server.py:397-398`). Confirmed; no MCP
  change is in scope and the ticket does not claim one.
- **The re-render path does remove the inline highlight.** `renderAll()` unwraps every `mark.cmt`
  up-front (`viewer.html:444`) and re-emits highlights only for comments still in the `comments`
  array (`viewer.html:450-451` via `highlightComment`). A deleted comment drops out of the array on
  `fetchComments()` (`viewer.html:359-361`), so the next `renderAll()` leaves its highlight unwrapped
  and gone. The AC's "card + highlight disappear" claim is sound. **Confidence: high.**
- **Pattern to mirror is real.** `replyTo`/`reopenComment` (`viewer.html:370-384`) are exactly
  `fetch → fetchComments() → renderAll() → toast`. A `deleteComment(cid)` mirroring this is correct.

---

## Findings (prioritized)

### BLOCKER-1 — The render-smoke AC asks a DOM-counter to do a click-through it cannot do. (confidence: high)

The AC (fork-#1 smoke bullet) says: "drive headless Chrome … assert the Delete affordance renders …
**then click-through the confirm and assert the comment is gone** (card + highlight removed) and
`GET /comments` no longer returns it." But `scripts/render-smoke.sh` is a **DOM-node counter, not an
interaction driver**: its own contract (`scripts/render-smoke.sh` header, lines 16-19) is
"every selector matches >=1 element -> exit 0 / any selector matches 0 -> exit 1." It runs Chrome
`--headless --dump-dom` once and parses the serialized DOM with a stdlib HTML parser. It **cannot**
click a button, cannot advance a two-step confirm, and cannot assert a node is *absent* (its only
failure mode is a selector matching zero — which is indistinguishable from "the affordance never
rendered"). The AC as written is unsatisfiable with the named tool.

This matters because the prompt's own concern is right: "a 200 is not a render" and, here, *a rendered
button is not a working delete*. The G4 `render-smoke.sh` proves the affordance **exists**; proving the
**click deletes** needs a different mechanism.

**Fix — split the AC into two checks that match the tools that exist:**
1. *Presence (render-smoke):* `scripts/render-smoke.sh <url> '.gcard [data-act=delete]'` (and the
   `.rcard` selector per fork #5) on a seeded-comment review — asserts the affordance rendered. This
   is what `render-smoke.sh` is for.
2. *Behaviour (curl round-trip, mirroring MR-045's accepted validation):* against the rebuilt
   container, `create_comment → GET /comments` (count 1) → `DELETE …/comments/{cid}` → `{"deleted"}`
   → `GET /comments` (count 0) → re-`DELETE` → `404`. MR-045 (`docs/process/tickets/MR-045-delete-comment.md`,
   Validation/AC) validated the identical delete family exactly this way; reuse it.
3. *Optional but ideal:* if the click-through itself must be proven end-to-end, that needs a
   Puppeteer/Playwright-style script — which **does not exist in `scripts/`** (only `render-smoke.sh`).
   Either add that as explicit in-scope tooling work or accept (1)+(2) as the G4 evidence. Do not
   pretend `render-smoke.sh` covers it.

Also: the smoke needs a **seeded comment** to render an affordance against. There is no comment-seeding
helper in `scripts/`; the smoke step must `POST /comments` first (curl). Call that out so the
implementer doesn't discover it mid-G4.

### BLOCKER-2 — The inline two-step confirm (fork #1) collides with the 2s poll; the confirm state will be wiped mid-gesture. (confidence: high)

The poll loop re-renders on any `comments_updated` change every 2s (`viewer.html:571`), and it only
*skips* a tick while the add-comment button or the new-comment popup is open
(`viewer.html:567`: `if(addbtn.style.display==='block'||$("#pop").style.display==='block')return;`).
An inline "Delete → Confirm? (~3s)" state lives **inside a `.gcard`**, which `renderAll()` rebuilds
from scratch (`viewer.html:449-462`, `G.innerHTML=''`). So if an agent replies/resolves/deletes
anything during the human's confirm window, the poll fires `renderAll()`, the card is rebuilt, and the
pending "Confirm?" silently reverts to "Delete." The human's second click then lands on a fresh
"Delete" (no-op) instead of confirming — or, worse, on a card whose `data-id` moved. The ticket's
fork-#1 recommendation ("inline two-step, no modal footguns") is reasonable *but inherits a known
race the codebase already worked around for the popup* and does not extend the guard.

**Fix — one of:**
- Extend the poll-skip guard to also bail while any card is in the confirm-pending state (e.g. a
  `document.querySelector('.gcard.confirming, .rcard.confirming')` check alongside the existing two),
  **and** ensure the in-progress gesture isn't lost if a render does slip through. This is the
  cheapest fix and matches the existing pattern at `viewer.html:567`.
- Or use native `confirm()` — which **does** synchronously block the event loop, so no poll tick can
  interleave. The ticket rejects it for "blocks in headless render-smoke," but per BLOCKER-1 the smoke
  no longer drives the click, so that objection partly dissolves. (Trade-off: `confirm()` is ugly and
  un-stylable; I'd still prefer the guarded inline approach, but the ticket should acknowledge the
  race either way.)

Add an AC: "the confirm state survives a concurrent `comments_updated` poll tick (or the poll is
suppressed while a confirm is pending)."

### SHOULD-1 — Fork #2 is scoped wider than the bug; tighten to "no agent entries in the thread." (confidence: medium)

Issue #12 is "a reviewer made a comment **by mistake**." The ticket generalizes to "delete **any**
comment incl. agent-authored, behind a confirm." The human-owns-their-review argument is legitimate,
and on a no-auth service the boundary is a UX convention regardless (so this is a product/UX call, not
a correctness one — see calibration). But "one-click-confirm nuke an agent's substantive feedback **and
the human's own replies to it** (whole-thread delete, fork #3)" is exactly the action the
`delete_comment` tool description warns agents off of (`mcp_server.py:251-253`: "never to dismiss the
reviewer's feedback (resolve that)") — the ticket would let the *human* do to the agent what the agent
is told not to do to the human, and the symmetric spirit is "resolve real feedback, don't destroy it."

A sharper, still-self-serve rule that covers the actual bug without the footgun:
**allow delete only when the thread has no `agent` entries** (i.e. `c.thread.every(e => e.role !== 'agent')`).
The thread array is right there in render (`viewer.html:407-410` iterates `c.thread` with `e.role`),
so the predicate is trivial. This deletes a fat-fingered reviewer comment (the bug) and a junk
*reviewer-only* thread, but won't let a misclick obliterate an agent's analysis the moment the agent
has engaged. It's strictly narrower than "any comment" and strictly wider than "reviewer-authored
only" (it still cleans a reviewer comment the agent hasn't touched).

I'd **change fork #2 to: delete allowed iff the thread contains no agent entry.** If the product owner
deliberately wants the broader "human can nuke anything they own" — that's a defensible call, but it's
a *decision*, so name it (see calibration) rather than defaulting into it. Confidence is medium because
this is a judgment call, not a defect; the narrower rule is the safer default and the broader one
should be an explicit, owned choice.

### SHOULD-2 — Missing AC: error / 404 / offline handling on the DELETE. (confidence: high)

The sibling functions all wrap the fetch in try/catch with a failure toast (`viewer.html:368,376,383`).
The ticket's success path is specified ("re-fetch + renderAll + toast") but there is **no AC for
failure**: DELETE returns 404 (someone — the agent, or another tab — already deleted it; `app.py:607`),
or the network is offline. Without an explicit AC the implementer may copy the happy path and leave a
confirmed-but-silently-failed delete (the card stays, the human thinks it's gone). The 404-already-gone
case is *common* here precisely because the agent polls and acts concurrently.

**Fix — add AC:** "On non-2xx or network failure, show a failure toast and re-`fetchComments()` +
`renderAll()` so the card reflects true server state (a 404 because it was already deleted should leave
the card *gone*, not stuck)." Note the subtlety: a 404 is "success-equivalent" (the comment is gone) —
the handler should re-fetch and treat the disappearance as the desired end state, not toast an error.

### SHOULD-3 — Optimistic vs server-confirmed removal is unspecified; pick server-confirmed. (confidence: medium)

The ticket says "on success: re-fetch + renderAll" which *implies* server-confirmed, but doesn't say so,
and doesn't forbid an optimistic "remove the card immediately." Given BLOCKER-2's race and SHOULD-2's
404 path, **server-confirmed (await DELETE, then `fetchComments()`, then `renderAll()`) is the correct
choice** — it's what `replyTo`/`reopenComment` do (`viewer.html:375,382`) and it self-heals the
concurrent-delete case. Make it an explicit AC so nobody "optimizes" by removing the node before the
server confirms (which would desync on failure).

### NIT-1 — Placement: there's pre-existing dead CSS the implementer should know about. (confidence: high)

Fork #4 floats "🗑 in the card header." Note `.gcard .gx` already exists as styled-but-unwired CSS
(`viewer.html:87`: absolutely-positioned top-right close button) — `renderAll()` never emits a `.gx`
node. The implementer can either adopt `.gx` (and finally wire it) or add a new class, but should not
assume `.gx` is live. Minor, but it'll cause a "why is there already a close button style?" detour.
Whatever class is chosen, give it a stable hook for the smoke selector (e.g. `[data-act=delete]`,
matching the existing `[data-act=reply]`/`[data-act=reopen]` convention at `viewer.html:460,469`).

### NIT-2 — Accessibility / keyboard + escape for the inline confirm. (confidence: medium)

The reply/reopen buttons are plain `<button>`s (keyboard-reachable). A two-step inline confirm adds a
transient state with a timeout — the AC should require: the affordance is a real focusable `<button>`
(not a clickable `<span>`), Escape (or blur) cancels the pending confirm, and the ~3s auto-revert
doesn't strand focus. Cheap to state now, annoying to retrofit.

### NIT-3 — Empty-state for the active gutter is a non-issue; resolved is fine too. (confidence: high)

The prompt asks whether deleting the *last* comment breaks counts/empty-states. Verified: `#count`
recomputes from `active.length`/`resolved.length` every render (`viewer.html:474-476`) and `#resempty`
toggles correctly (`viewer.html:472`). There is **no** active-gutter empty-state node to break (the
gutter just goes empty). So no new empty-state work is needed — but add a one-line AC asserting counts
update on delete (the AC already implies it; make it explicit so the smoke checks it).

---

## Resolutions for the five forks

1. **Confirm step → AGREE with inline two-step, CONDITIONAL on BLOCKER-2.** Inline two-step is the
   right pattern *only if* the poll-race is closed (extend the `viewer.html:567` guard or accept
   `confirm()`'s synchronous block). As written, the recommendation ships the race. Add the
   confirm-survives-poll AC.
2. **Deletable scope → CHANGE-TO: delete allowed iff the thread has no `agent` entry.** Narrower than
   the ticket's "any comment," wider than "reviewer-only." Covers the actual bug (#12) without letting
   a misclick destroy engaged agent feedback + the human's own replies. If the owner wants the broader
   rule, that's a named decision, not a default (see calibration). The thread predicate is trivial
   (`viewer.html:407-410` already walks `c.thread`/`e.role`).
3. **Whole-thread vs per-reply → AGREE.** API is whole-thread only (`app.py:602-610`); per-reply is
   correctly out of scope. The confirm copy **must** state the whole thread (incl. any replies) is
   destroyed — and under the fork-#2 change, "no agent replies exist" means the copy is honest that
   it's the reviewer's own content being removed. Keep this AC; tighten the copy.
4. **Placement → AGREE (small/muted, distinct from resolve).** Add the `[data-act=delete]` hook for
   the smoke selector; note the dead `.gx` CSS (NIT-1). The "low confusion risk because the human
   doesn't resolve in-UI" reasoning is correct.
5. **Resolved cards too → AGREE.** A mistaken comment can sit resolved; both `.gcard` and `.rcard`.
   Under the fork-#2 change, a resolved thread that an agent resolved-with-justification *does* contain
   an agent entry (`resolve` writes an agent thread entry — `app.py:621-622`, `by="agent"`), so the
   no-agent-entry rule would **block delete on most resolved cards**. That's arguably correct (the
   agent engaged), but it's a direct interaction between forks #2 and #5 the ticket doesn't see:
   "both panels" + "no-agent-entry" means resolved-card delete mostly won't fire. Decide explicitly:
   either accept that (resolved-with-agent-justification is real history, keep it) or special-case it.
   I lean **accept** — if an agent resolved it, it wasn't junk.

---

## Open questions for the author

- **Fork #2 / #5 interaction:** with the no-agent-entry rule, `resolve`-with-justification writes an
  agent thread entry (`app.py:621-622`), so most *resolved* cards become non-deletable. Intended, or
  do you want resolved cards deletable regardless of agent justification?
- **Click-through proof:** is a real end-to-end click-delete test required for G4, or is
  render-smoke (affordance present) + curl round-trip (wire deletes) sufficient? The former needs new
  Puppeteer-class tooling that `scripts/` does not have today — if required, that tooling is in scope
  and the ticket must say so.
- **Confirm copy:** exact wording? It must name that the whole thread is destroyed permanently with no
  undo. Suggest the ticket pin the string so the smoke/AC can assert it.

## Calibration

**P2 + standalone is right; this does not need to become an epic.** It's a one-function UI addition over
an existing endpoint. The only thing that rises to "needs a decision" is **fork #2's breadth** — and
even that is a *small* UX call, not architecture: the safe default (no-agent-entry) lets implementation
proceed without blocking on the owner, and the broader "human can nuke anything" is the variant that
would need an explicit owner sign-off. So I land at **READY-WITH-TWEAKS**, not NEEDS-A-DECISION: fix
BLOCKER-1 (split the smoke AC), close BLOCKER-2 (the poll race), adopt the SHOULD AC additions, and
default fork #2 to no-agent-entry unless the owner consciously wants it wider.

## Resolution log

- 2026-06-23 — Independent scope review filed. Verdict READY-WITH-TWEAKS. Two BLOCKERs (smoke-AC tool
  mismatch; inline-confirm/poll race), three SHOULDs (fork-#2 narrowing, error-handling AC,
  server-confirmed removal), three NITs (dead `.gx` CSS, a11y/escape, empty-state confirmation).
  Forks: #1 agree-conditional, #2 change-to-no-agent-entry, #3/#4/#5 agree (with a #2×#5 interaction
  flagged). Open until the author folds the AC fixes and rules on the open questions.
