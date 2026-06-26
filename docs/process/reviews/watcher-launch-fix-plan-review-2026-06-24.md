---
review_of: epics/watcher-launch-fix-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 Independent Review — Watcher Launch Fix Plan (MR-060)

**Scope of this gate.** The Option-B *design* (B-vs-C, why-not-skip-permissions, the inert
must-configure stub) was critic-gated twice in mdreview (`05ff768234`, verdict GO) and is captured
verbatim in `requirements/watcher-launch-fix.md`. This review does **not** re-litigate it. It gates
the **implementation plan**: is MR-060 implementable as specified against the actual `watch.py` on
`dev`, without footguns?

**Verdict: PASS-WITH-NITS.** The core fix is correctly specified and load-bearing-claim-verified.
The startup-gate placement is right and the rationale checks out against `app.py`. The inert-sentinel
choice is clean and breaks no other reader. The docs table is complete. Two defects in the
*verification scaffolding* (not the fix itself) keep this from a clean PASS: the self-check's
`/handoff` request bodies use the wrong schema (would never pass as written), and the "zero
survivors" sweep-grep is over-narrowed and would miss 4 of the 8 stale doc spots. Both are in the
plan's own deferred-verification surface, so neither blocks G1 — but the ticket author must not copy
the sketch verbatim. Folding the corrections in is cheap and should happen at ticket-authoring time.

---

## What I verified against the code (the load-bearing claims hold)

- **Startup-gate placement is correct.** `main()` (`watch.py:491-498`) runs
  `require_trusted_base_or_exit(BASE)` → `_arming_startup_notice()` → `run()`. The lease claim
  happens only in `handle()` (`watch.py:384-387`) → `_spawn()` (`watch.py:355`), strictly inside
  `run()`. So a gate placed in `main()` before `run()` provably fires before any `/wait` poll and
  before any lease claim — exactly the B1-safe shape.
- **The strand mechanism is real (verified in `app.py`).** `app.py:635-636`: the `elif state ==
  "working"` arm (the lease claim `handle()` POSTs) **does not bump `turn_updated`** ("lease
  claim/renew/takeover. turn_updated is NOT bumped (no flip)"). The edge-triggered
  `/wait?since=cursor` keys off `turn_updated`, so a spawn-time exit *after* the `{state:working}`
  200 would strand the review at `turn==agent` with no re-surfacing. The plan's load-bearing
  justification (lines 86-93) is accurate, not folklore.
- **Gate ordering is sound.** trusted-base → launch-configured → arming-notice → `run()`. The
  trusted-base gate must stay first (it is the security crux and gates *whether to touch the network
  at all*); the launch gate is a pure local-config predicate with no I/O, safe to run second; the
  arming notice is informational. Any order with **both** refusals before `run()` satisfies the
  constraint — the plan states this correctly (assumption #2).
- **Inert sentinel breaks nothing else.** `DEFAULT_LAUNCH_CMD` has exactly four readers, all in
  `watch.py` (`:42` docstring, `:83` def, `:335` docstring, `:340` `list(DEFAULT_LAUNCH_CMD)`). No
  `.py`/`.sh`/test/smoke outside `watch.py` references it. `None` would break only line 340, which
  the plan correctly makes defensive (raise/assert) rather than user-facing.
- **`launch_configured()` empty-string handling is coherent.** Proposed
  `bool(os.environ.get("WATCH_LAUNCH_CMD"))` treats `""` as unset; `_launch_argv()`'s existing
  `if not raw` (`watch.py:339`) treats `""` as unset too. So an empty `WATCH_LAUNCH_CMD` is rejected
  by the gate *and* would have fallen to the sentinel — consistent, no gap where the gate passes but
  the resolver hits `None`. Mirroring `arming_configured()` is the right precedent.
- **Self-check infra assumptions hold.** `app.py` honours `MDREVIEW_DATA` (`:41`) and `PORT` (`:42`);
  `/healthz` is a GET route (`app.py:485`); the `run()` banner string `"cursor="` exists
  (`watch.py:408`), so "banner absent ⇒ never entered `run()`" is a valid proxy.
- **MR-060 is the next free ID** (highest existing is MR-059). Scope (1 ticket, `svc` + same-change
  docs, no `app.py`/`Dockerfile`) is right-sized and matches the C1/C2/C3 same-change-docs precedent.

---

## Findings

### worth-considering — Self-check `/handoff` bodies use the wrong schema (would not pass as written)

The `/handoff` endpoint dispatches on **`to` / `by` / `state`** in a pinned order
(`app.py:611-643`), not on a bare `state` value. The self-check sketch gets this wrong in two places:

- **Stub hand-back** (plan lines 284-286): `{"state":"reviewer","owner":...}`. No arm matches
  `state:"reviewer"`. Hand-back is `to == "reviewer" and state in ("done","blocked")`
  (`app.py:625`). As written the body falls through to no-match, the turn never returns, and Arm B's
  `test "$turn" = "reviewer"` **fails**. Correct body:
  `{"to":"reviewer","state":"done","owner":"$MDREVIEW_OWNER","message":"stub done"}`.
- **Flip-to-agent** (plan lines 293-294): `{"state":"agent","owner":"reviewer"}`. The flip arm is
  `to == "agent"` (`app.py:628`), not `state == "agent"`. As written the review never flips to
  `turn==agent`, so the watcher never sees it. Correct body: `{"to":"agent"}` (a reviewer→agent flip;
  the reclaim arm needs `by:"reviewer"`, the flip arm just needs `to:"agent"`).

The watcher's *own* claim (`watch.py:385`, `{"state":"working","owner":OWNER}`) correctly matches
`elif state == "working"` — only the self-check's hand-authored bodies are wrong.

This is **worth-considering, not blocking**, only because the plan already flags it: assumption #5
and the "Notes the ticket must honour" (lines 306-310) explicitly say "confirm the route/field names
against `app.py`/`mcp_server.py` at implementation time." So the plan defers this verification by
design. But the sketch is concrete enough that an implementer may paste it; the body shapes shown are
actively misleading. **Fix at ticket-authoring time:** correct the two bodies in the sketch (or
replace the hand-crafted curls with the real MCP/route shapes), so the deferred "verify" is a
confirmation, not a debugging session against a silently-failing self-check.

### worth-considering — The "zero survivors" sweep-grep is over-narrowed; misses 4 of 8 spots

The docs table (lines 106-115) correctly enumerates all 8 stale spots — I independently grepped and
found exactly those 8, no more. **The table is complete.** The problem is the *verification* grep
(lines 247-248) that AC-5 leans on to prove zero survivors:

```
grep -rn -i -e "default Claude headless" -e "falls back to .*DEFAULT_LAUNCH_CMD" README.md CLAUDE.md watch.py
```

Run against the current stale text, this matches only 4 lines (`CLAUDE.md:132`, `watch.py:7`,
`README.md:185`, `README.md:209`). It **misses** `watch.py:42`, `watch.py:80`, `README.md:190`, and
`README.md:270` — all of which say "(Claude headless)" *without* the adjacent word "default", or use
it as a comment fragment. So an implementer who sweeps from the table but trusts this grep as the
completeness check could leave a survivor at `:42`/`:80`/`:190`/`:270` and the grep would report
clean — shipping a doc that contradicts the new refuse-to-start behaviour (exactly the failure mode
AC-5 exists to prevent).

The plan's own risk-table prose (line 230) lists the *correct* looser terms as three independent
greps ("Claude headless" / "DEFAULT_LAUNCH_CMD" / "falls back"); a plain `-i "Claude headless"` alone
catches all 8. **Fix:** replace the over-narrowed regex in the Verification block with the loose
single-term form from line 230 (e.g. `grep -rn -i -e "Claude headless" -e "DEFAULT_LAUNCH_CMD" -e
"falls back"` and assert zero), so the grep is a real backstop, not a false all-clear.

### nit — `_launch_argv()` defensive branch is a good belt, not dead code

Plan item 3 (lines 77-84) keeps the unset branch of `_launch_argv()` as a raise/assert rather than
deleting it. This is the right call: the startup gate guarantees `WATCH_LAUNCH_CMD` is set by the
time `_launch_argv()` runs, so the branch is unreachable in normal operation — but a future refactor
that drops or reorders the gate would otherwise hit `list(None)` and die with an opaque `TypeError`
deep in `_spawn()`. A clear `raise RuntimeError("launch gate bypassed: WATCH_LAUNCH_CMD unset")`
fails loud at the right layer. Keep it; it is a belt, not dead code. (Single source of truth for the
user-facing exit-2-with-guidance stays in `main()`, as the plan says.)

### nit — runbook recipe documents `dontAsk` + `allowedTools`, correctly (not allowedTools-alone)

The plan documents the scoped recipe as `--permission-mode dontAsk` **plus** `--allowedTools
"mcp__mdreview__*"`, with the explicit rationale that `--allowedTools` alone falls through to the
no-TTY prompt on a stray tool and stalls (a narrowed reprise of the defect), and the glob-free
anchoring rule (`mcp__mdreview__*` valid; `mcp__*`/`*` ignored). That matches the requirement and is
documented as a recipe, not re-verified — consistent with the non-goal (line 152-155) and assumption
#4. No issue; noting it because the gate brief asked to confirm the plan documents the full posture,
not allowedTools-alone. It does.

---

## Answers to the gate's specific questions

1. **Startup-exit placement correct and load-bearing?** Yes — verified against `watch.py:355-393`
   (lease claim is strictly inside `run()`) and `app.py:635-636` (`{state:working}` doesn't bump
   `turn_updated`). A spawn-time exit would strand at `turn==agent`. Ordering (trusted-base → launch
   → arming-notice → run) is correct and the plan's flexibility note is sound.
2. **Inert sentinel clean/detectable; any other reader broken?** Clean. Only 4 readers, all in
   `watch.py`, all accounted for. `None` breaks only `:340`, made defensive. Empty-string
   `WATCH_LAUNCH_CMD` is treated as unset by both gate and resolver — consistent. The defensive
   `_launch_argv()` raise is a good belt, not dead code.
3. **Docs sweep complete?** Yes — independent grep found exactly the 8 spots the table lists, none
   missed. **But** the *verification grep* that proves it is over-narrowed and misses 4 of them (see
   worth-considering #2) — fix the grep, the table is fine.
4. **Validation adequacy?** The 2-arm structure is right and the "banner absent ⇒ never entered
   run()" proxy is sound (banner prints only inside `run()`, before the loop). Arm A also asserts
   no lease was claimed implicitly: it never flips a review to `turn==agent`, so there is nothing to
   strand — that is *stronger* than a per-review lease assertion and is the correct shape. The one
   gap is mechanical: the Arm B `/handoff` bodies are wrong (worth-considering #1) so Arm B would
   not pass as written. Fix the bodies and the validation proves exactly the load-bearing claim.
5. **Scope right-sized?** Yes. 1 ticket, `svc` + same-change docs, no `app.py`/`Dockerfile`. Inert
   default breaks no existing test/smoke (none reference it). The `dontAsk` + `allowedTools` recipe
   is documented correctly (full posture, not allowedTools-alone). No hidden scope.

---

## Resolution log

| # | Finding | Tag | Status |
|---|---------|-----|--------|
| 1 | Self-check `/handoff` bodies use wrong schema (`state:reviewer`/`state:agent` match no arm; need `to:reviewer,state:done` and `to:agent`) — would not pass as written; plan already defers field-name verification (assumption #5) | worth-considering | open |
| 2 | "Zero survivors" verification grep (lines 247-248) over-narrowed; misses `watch.py:42/80`, `README.md:190/270`; table itself is complete; use the loose terms from line 230 | worth-considering | open |
| 3 | `_launch_argv()` defensive raise is a good belt, not dead code — keep | nit | open |
| 4 | Runbook documents full `dontAsk` + `allowedTools` posture correctly (not allowedTools-alone) | nit (confirmation) | open |

**Gate decision: PASS-WITH-NITS.** MR-060 may spawn. The fix is correctly and safely specified; the
two worth-considering items are in the plan's deferred-verification surface (it already says "confirm
against the code at implementation time"), so they are author-time corrections to the self-check
scaffolding, not design defects. The ticket author should fold both into MR-060's acceptance/self-check
before implementation rather than copy the sketch verbatim.

## Resolution log

- 2026-06-24 — Independent G1 review (1-ticket fix). Verdict PASS-WITH-NITS; the core fix (inert
  DEFAULT_LAUNCH_CMD sentinel + startup-exit in main() before run()) verified sound against watch.py
  (lease claim is strictly inside run(); the {state:working} arm doesn't bump turn_updated, so a
  spawn-time exit would strand the review — startup exit is correct); docs-sweep table complete (8
  spots); sentinel breaks no other reader; scope right-sized. Two worth-considering items in the
  verification scaffolding + 2 confirmed nits.
- 2026-06-24 — Planner revised (author preserved, independence intact). Folded: (1) the self-check
  `/handoff` bodies corrected to the real router schema — flip `{"to":"agent"}`, stub hand-back
  `{"to":"reviewer","state":"done",…}` (the lease claim `{"state":"working","owner"}` was already
  correct); (2) the "zero survivors" docs-sweep grep loosened from the narrow "default Claude headless"
  regex (caught 4/8) to a case-insensitive single-term grep (`headless`/`DEFAULT_LAUNCH_CMD`/
  `WATCH_LAUNCH_CMD` across the 3 files), propagated to the validation + AC #5 + the risk row. Both nits
  confirmed (keep the `_launch_argv()` defensive raise; recipe stays `dontAsk` + `allowedTools
  mcp__mdreview__*`). No second G1 round needed (scaffolding fixes, not design). **G1 PASS.**
