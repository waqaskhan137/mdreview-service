---
review_of: tickets/MR-050-viewer-delete-comment.md
gate: scope
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: READY
status: resolved
---

# MR-050 scope re-review (r2) — viewer delete-comment affordance

Focused re-review of round 1 (`MR-050-scope-review-2026-06-23.md`, READY-WITH-TWEAKS). I read the
current ticket text and re-verified each fix against the code, not the resolution log.

## Round-1 findings — closure

**BLOCKER-1 (render-smoke AC asked a DOM-counter to click) — closed: ✓.** The validation AC is now
split three ways (ticket "Acceptance criteria", Validation bullet): *Presence* via
`render-smoke.sh … '[data-act=delete]'` (presence only — matches the tool's own contract,
`scripts/render-smoke.sh:14-18`: count ≥1 → exit 0, no click/absence), *Behaviour* via curl
create→`DELETE`→`{deleted}`→list-empty→re-delete-404, and *Interaction* via node-CDP. No remaining
text asks `render-smoke.sh` to click. Both lower legs are achievable with existing tooling:
- The curl round-trip is exactly how MR-045 validated this same delete route
  (`MR-045-delete-comment.md` AC + Validation: "curl: create → `DELETE` → `{deleted}`, list count 0,
  re-delete → `404`"). Endpoint behaviour confirmed at `app.py:602-610`.
- The node-CDP leg is real and *can* click and assert absence: `agent_smoke.py:125` exposes
  `ev(x)` = `Runtime.evaluate{returnByValue,awaitPromise}` over the repo's built-in-WebSocket CDP
  pattern, so `ev('…querySelector("[data-act=delete]").click()')` and
  `ev('!document.querySelector("mark.cmt")')` are both in-reach. The split is satisfiable and
  sufficient to prove existence + wire + end-to-end gesture.

**BLOCKER-2 (inline confirm races the 2s poll) — closed: ✓.** Design item 2 and AC bullet 3 both
require extending the MR-049 poll-skip guard (`viewer.html:567`) to bail while a delete-confirm is
pending; native `confirm()` is named as the synchronous alternative. The guard at `viewer.html:567`
does sit before the `renderAll()` call (`viewer.html:571`), so an early-return there genuinely
suppresses the rebuild that would wipe the confirm — the mitigation targets the right line. One
residual hole worth the implementer's eye (does **not** block): the guard only suppresses the
*poll-driven* re-render. A `source_updated` tick takes a different branch (`viewer.html:570`,
`await load()`) and the human's own concurrent action (a reply/reopen in another card) calls
`renderAll()` directly. Extending the *same* `confirming`-state check to those paths — or the
synchronous `confirm()` — fully closes it. The ticket's chosen guard is correct and sufficient for
the dominant case (agent polling); the rarer self-induced rebuild is an implementation detail the AC
language ("bail while a delete-confirm is open") already covers in spirit.

**Fork #2 (delete only when thread has no `agent` entry) — closed: ✓.** Changed from "delete
anything" in both Design (item 1) and AC bullet 1 ("only when the thread has no `agent` entry"). The
predicate is described correctly: a thread containing any `role:'agent'` entry is not deletable, and
`renderAll()` already walks `c.thread`/`e.role` (`viewer.html:407-410`), so it's trivial. The
fork-#2 × fork-#5 interaction is correctly reflected and accepted (Design item 5): `resolve` writes
an agent entry (`app.py:621-622`, `by="agent"`), so resolved cards almost always carry one and won't
show delete — "if an agent resolved it, it wasn't junk." This is the safe default and needs no
product-owner decision; the broader "delete anything" is explicitly flagged as a not-taken decision
(Design item 1, Follow-ups). Correct.

**NIT (dead `.gcard .gx` CSS) — closed: ✓.** Carried as an implementer note (Design item 4:
"`viewer.html:87` is dead/pre-existing — do not assume it's wired"). Verified still dead — no
`renderAll()` path emits a `.gx` node.

## New problems / internal consistency

No contradictions found. Checked specifically:
- No surviving "delete anything" or "render-smoke clicks" wording anywhere in the ticket.
- AC bullets and Design items agree (no-agent-entry, inline two-step + guard, server-confirmed
  refresh, `app.py` untouched, the three-way validation split).
- The success/failure path AC (bullet 4: re-fetch→renderAll on success with `toast('Comment
  deleted')`; no optimistic removal + `toast('Could not delete')` on failure) is consistent with the
  `replyTo`/`reopenComment` pattern it mirrors (`viewer.html:370-384`). The round-1 SHOULD-2/SHOULD-3
  (error handling, server-confirmed) are folded in.
- `.rcard`/fork-5 wording is consistent with the no-agent-entry rule (delete simply won't render
  there in practice; not a contradiction, an entailment).

One micro-note, non-blocking: AC bullet 4's failure copy says "no optimistic removal — the card
stays," while round-1 SHOULD-2 observed a 404 (already-deleted by the concurrent agent) should leave
the card *gone*, not stuck. The ticket's "no optimistic removal" is the right default for a true
failure (network/5xx), but the implementer should treat a 404 as success-equivalent (re-fetch, card
disappears). The AC's own "re-`fetchComments()`" success path already produces this if the handler
re-fetches on 404 — worth a one-line implementer nudge, not a ticket blocker.

## Verdict

**READY.** Both round-1 BLOCKERs are genuinely closed, the fork-#2 narrowing landed in Design and
ACs with the correct predicate and the fork-#5 interaction accepted, and applying the tweaks
introduced no contradiction. The ticket is internally consistent and implementable as-is. This
re-review is the independent sign-off the round-1 verdict was conditional on — MR-050 is approved to
pick up. The two non-blocking nudges above (extend the confirm-guard to the non-poll rebuild paths;
treat a 404 on delete as success-equivalent) are implementer guidance, not gate conditions.

## Resolution log

- 2026-06-23 — r2 re-review. All three round-1 must-fixes (BLOCKER-1 smoke-AC split, BLOCKER-2
  poll-race guard, fork-#2 no-agent-entry narrowing) verified closed against code; no new defect.
  Verdict upgraded READY-WITH-TWEAKS → **READY**. Closed.
