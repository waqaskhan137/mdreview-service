---
review_of: epics/agent-watcher-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 independent review — agent-watcher **C3** (Watcher safety + ops, FINAL chunk)

Scope: the `## C3 — Watcher safety + ops (full plan)` section only (plan lines 805-1313). C1/C2 are
shipped; this gates spawning MR-058 (arming/Step-0 relaxation) and MR-059 (per-review cap + full
runbook). The security crux is whether the arming relaxation re-opens C2's fail-closed refusal when
arming is unconfigured, and whether the allowlist can be set by any URL-holder on the no-auth service.

**Verdict: PASS-WITH-NITS.** The security model is sound and the relaxation is strictly a relaxation.
I verified the load-bearing claims against the shipped tree (`watch.py` 329 lines, `app.py`
`/handoff` arm and full router). No self-arming hole, no C2 regression when arming is unconfigured, no
crash auto-relaunch. The nits are real wiring gaps the tickets must pin — chiefly the `pending`-set
interaction (W1), which the *literal* implementation of "skip without claim" gets wrong against the
shipped `run()` loop. None blocks; all are fixable inside MR-058/MR-059.

---

## Verification performed (read-only)

- **No self-arming endpoint.** Read the full `app.py` router (app.py:480-820): the route arms are
  `/healthz`, `/`, `/api`, `/api/reviews` (GET/POST), `/api/reviews/wait`, and the per-RID arms
  `source`, `feedback`, `status`, `handoff`, `history`, `history/{n}`, `assets`, `comments`,
  `comments/{cid}`, `asset/{name}`, `/review/{id}`, `/static/{name}`. **There is no `/arm` route and
  no endpoint that writes arming state.** The plan adds no `app.py` change. Self-arming is structurally
  impossible: the allowlist lives only in the operator's filesystem/env, which the service never reads.
  Confirmed.
- **B1 crash model.** Read the `/handoff` arm (app.py:604-673). `turn_updated` is bumped on
  reviewer-reclaim (620), hand-back (627), and a real reviewer→agent flip (634, guarded by
  `if mt.get("turn") != "agent"`); the `{state:working}` lease arm (635-662) **does not** bump
  `turn_updated`. So a child that exits before `hand_back` strands its review and the edge-triggered
  `/wait?since=cursor` never re-surfaces it. The plan's framing — per-review cap guards the *re-Send /
  re-surface* loop, **not** a crash loop — is correct, and C3 adds no relaunch. Confirmed.
- **C2 Step-0 preserved when arming unconfigured.** Read `check_trusted_base` / `require_trusted_base_or_exit`
  (watch.py:74-102). `_is_armed` returning unconditionally True when arming is unconfigured makes
  `handle()` byte-for-byte C2, and the Step-0 exit gating only on "arming configured" leaves the
  `sys.exit(2)` path intact for the un-vouched + no-arming row. Confirmed against the shipped code the
  plan extends.
- **Runbook anchors.** README:229-231 forward-pointer block and CLAUDE.md:136-137 pointer exist exactly
  as the plan cites; the README "Watcher (optional, trusted-base mode)" section (README:180-231) is the
  block MR-059 replaces. Confirmed.
- **Ticket IDs.** On-disk max is MR-057; MR-058/MR-059 continue cleanly. `LEASE_TTL_S` is a single
  server constant (app.py:58). Confirmed.

---

## Findings

### Blocking

None. The three blocking-class hazards I was asked to pin all come out clean:
(a) un-vouched + no-arming still EXITs (`_is_armed` does not touch Step-0; Step-0 gates only on
"arming configured"); (b) un-armed reviews are skipped *before* the claim, so no lease is touched and
no baton is stranded under the watcher's own owner; (c) the relaxation only ever lets MORE run on an
already-untrusted base via local opt-in — it never widens a loopback/vouched base and never lets an
un-armed review through. The relaxation is monotone-safe.

### Worth considering

- **W1 (the one real wiring trap) — "arming-skip does NOT add to `pending`" contradicts the shipped
  `run()` add-condition; the ticket must specify the mechanism, not just the outcome.** The plan
  asserts (lines 915-917, 989-991) that an arming-skip and a per-review-cap-skip advance the cursor and
  are *not* added to `pending` (distinct from a capacity-skip, which *is*). But the shipped `run()`
  decides pending membership by `_at_capacity()`, **independent of why `handle()` returned False**:
  `if rid and not handle(rid): if _at_capacity(): pending.add(rid)` (watch.py:302-304). The obvious
  literal implementation of "skip without claim" — an early `return False` at the top of `handle()` —
  therefore lands the un-armed/capped review in `pending` **whenever the watcher happens to be at
  capacity at that instant**, and `_drain_pending` will then re-attempt it on every idle tick forever
  (an un-armed review that never converges to a spawn). That is not a spend bug (the claim is still
  gated) but it is a silent CPU/log churn loop and it violates the property the plan pins. The fix is
  small but must be named in MR-058: `handle()` needs to distinguish "deferred (capacity)" from
  "rejected (un-armed / per-review-capped)" — e.g. a tri-state return, or move the
  `pending.add` decision inside `handle()`. Pin the mechanism; do not let the implementer ship the
  literal early-return.

- **W2 — C3-Q1 (base-independent gate): I agree with base-independent, but pin the *startup* surprise,
  not just the per-review one.** Making a configured allowlist gate loopback/vouched bases too is the
  right call — it only ever skips more, so it fails safe, and "all on loopback / armed-only on remote"
  is cleanly two processes. My recommendation is below. The one sharp edge the plan under-states: an
  operator who sets `WATCH_ARMED_FILE` on a **loopback** base expecting "arm a few, run everything
  else" will get a watcher that silently spawns **nothing** until they populate the file. The plan
  handles the *un-vouched* case well (the refusal message names arming as the escape hatch), but the
  *loopback-with-empty-armed-file* case has no such signal — it just idles. MR-058 should log a clear
  one-line startup notice when arming is configured ("arming active: N ids armed; un-armed reviews will
  be skipped on ALL bases") so the base-independent gate is not a silent footgun. This is the cost of
  the C3-Q1 choice; surface it rather than leaving the operator to discover it.

- **W3 — the "empty but configured armed file ⇒ run-but-gate, spawn nothing" degenerate is correct, but
  the *validation* does not test it.** The plan reasons through it well (lines 953-958): configured-empty
  must run-but-gate, not be treated as unconfigured (which would EXIT). That distinction is exactly the
  kind of thing an implementer collapses ("file empty? treat as no arming"). MR-058's validation tests
  un-armed-skip (test B) and no-HTTP-arm (test C) but has **no assertion for the configured-but-empty
  file on an untrusted base ⇒ starts (no exit) AND spawns nothing**. Add it: it is the single test that
  pins "configured means run-but-gate" against the tempting wrong collapse.

- **W4 — `WATCH_LAUNCH_MARKER` is referenced by the cap test (MR-059, line 1141) but is not a `watch.py`
  config var.** The MR-059 test fixture passes `WATCH_LAUNCH_MARKER=/tmp/marker.txt` to the watcher, but
  the marker is written by the **stub** (the C2 crash-stub, plan line 667), not by `watch.py`. That is
  fine — it is a test-fixture env the stub reads — but the env table the runbook owes (line 1031-1034)
  lists only real `watch.py` vars, so a reader could mistake `WATCH_LAUNCH_MARKER` for product config.
  Keep the marker test-only and do **not** let it leak into the runbook env table. Minor, but name it so
  the docs ticket does not document a fixture var as a feature.

### Nits

- **N1 — `_is_armed` re-read freshness vs the mtime-cache, on the single-thread invariant.** The plan's
  "re-read per `_is_armed` check, optional mtime cache" (lines 960-969) is right and composes with the
  single-thread loop (no lock). One thing to pin in MR-058 so the cache is not subtly wrong: if the
  mtime-cache refinement is taken, mtime has 1s granularity on some filesystems, so an arm + immediate
  same-second re-read could miss the edit. At this scale the plain per-check read is fine; if the cache
  is added, key it on `(mtime, size)` not mtime alone. Optional, since the default is no cache.

- **N2 — bad-token policy interacts with the `*`/`ALL` non-goal correctly, but state it in the loader,
  not only the prose.** The plan says a `*`/`ALL` wildcard "is not a valid token … so it is ignored like
  any other bad token" (C3-Q5, lines 1213-1215). Good — that means the wildcard non-goal is enforced
  *for free* by the `[A-Za-z0-9]{4,40}` validation (`*` fails the regex). Make MR-058's loader test
  assert that a `*` line is dropped-and-logged (not armed), so the non-goal is a test, not just prose.

---

## Answers to the scrutiny asks

1. **Decision table** — verified exact and correct (plan lines 932-958): loopback → run; vouched → run;
   un-vouched + arming → run-but-gate (armed spawn, un-armed skipped without claim, no exit); un-vouched +
   no arming → EXIT 2 (C2 preserved). Holes (a)/(b)/(c) all clean (see Blocking, none).
2. **No self-arming** — verified against the full `app.py` router: no `/arm` route, no arming write
   endpoint, no `app.py` change in the plan. Allowlist is local-only. Clean.
3. **C3-Q1** — recommendation below.
4. **Per-review cap** — guards the real re-Send/re-surface loop (B1-correct), `dict[id]->deque[ts]` with
   empty-key pruning is sound and composes as an independent third ceiling with the two global caps.
   Default 5/3600s is sane. It does **not** become a crash-relaunch mechanism (C3 adds no re-trigger).
   The only wiring gap is W1 (the `pending` interaction), shared with the arming skip.
5. **Runbook (DoD)** — fully scoped, not deferred: arming model + local-only rationale +
   provenance-is-not-a-trust-boundary + untrusted/public operation (arming REQUIRED) + per-review cap +
   full env table, in README (replacing the forward-pointer) + CLAUDE.md. Real content, pinned.
6. **Ticket split** — MR-058 (arming/Step-0) / MR-059 (cap + runbook) is the right seam; mirrors C2's
   MR-056/MR-057. No C2 leak-back, no YAGNI over-build (wildcard, server-side store, crash-relaunch all
   explicitly non-goals). IDs continue from MR-057. Correct.
7. **Validation** — proves un-armed-skipped-without-claim (B), C2-EXIT-preserved (A), cap-stops-re-Send
   (D), arm-not-HTTP-settable (C), distinct-review-unaffected (E), each an explicit assertion. **Gaps:**
   the configured-but-empty degenerate (W3) and the `*`-token drop (N2) are not asserted; add both.

## C3-Q1 recommendation (the planner's least-sure fork)

**Keep arming base-independent** — a configured allowlist gates every base, loopback and vouched
included. It is the correct call for three reasons: (1) it is the *only* monotone-safe direction — a
base-independent gate can never widen what runs, it can only ever skip more, so it cannot reintroduce
exposure; a base-*conditional* gate ("ignore the allowlist on loopback") would mean a configured
allowlist is silently disregarded on the very base where a careless operator is most likely to be
running real work — a far worse surprise than "it gated more than I expected." (2) It keeps the two
concerns orthogonal (base → run-vs-exit; arming → which-reviews), which is the simplest correct mental
model and the one the runbook can state in a sentence. (3) "All on loopback, armed-only on remote" is
cleanly expressed as two watcher processes, so the base-conditional flexibility buys nothing the
operator cannot already get. The one cost — a configured-but-empty allowlist silently idles a loopback
watcher — is real but is a **logging** fix (W2), not an argument for base-conditional gating. Ship
base-independent; add the startup notice.

---

## Resolution log

| # | Finding | Severity | Status |
|---|---|---|---|
| W1 | `pending` add-condition keys on `_at_capacity()`, not skip-reason — literal "skip without claim" loops un-armed reviews into pending; pin the tri-state/`handle()`-owned mechanism in MR-058 | worth-considering | open |
| W2 | Base-independent gate silently idles a loopback watcher with an empty armed file; add a startup notice | worth-considering | open |
| W3 | Configured-but-empty armed file degenerate (run-but-gate, spawn nothing) is unwritten in validation; add the assertion | worth-considering | open |
| W4 | `WATCH_LAUNCH_MARKER` is a test-fixture env, not product config; keep it out of the runbook env table | worth-considering | open |
| N1 | If the mtime-cache refinement is taken, key on `(mtime, size)` (1s granularity miss) | nit | open |
| N2 | Assert the `*`/`ALL` token is dropped-and-logged (enforces the wildcard non-goal as a test) | nit | open |

**Disposition:** PASS-WITH-NITS. The security model is sound and verified against the shipped tree —
no self-arming hole, no C2 regression when arming is unconfigured, no un-armed spawn or lease-strand,
no crash auto-relaunch. MR-058/MR-059 may be spawned; fold W1-W4 and N1-N2 into the tickets (W1 is the
one that bites a literal implementation and should be a hard pin in MR-058, not a footnote).

## Resolution log

- 2026-06-24 — Independent G1 review (C3 only). Verdict PASS-WITH-NITS; no blockers. Security model
  verified against the shipped tree (no self-arming hole, no `app.py` change, C2 fail-closed preserved
  when arming unconfigured, B1 crash model holds). C3-Q1: keep arming **base-independent** (monotone-safe).
- 2026-06-24 — Planner revised the C3 plan (author preserved, independence intact). Dispositions:
  **W1 accepted** — pinned the `run()`-side arming/cap gate (un-armed reviews are `continue`d BEFORE
  `handle()`/caps/claim, so they never enter the `_at_capacity()`-keyed `pending` set — `handle()`/
  `pending` stay byte-for-byte C2); the tri-state `handle()` return is named the only acceptable
  alternative (add to `pending` only on an explicit AT_CAPACITY signal). MR-058 val B2 asserts an
  un-armed review is not retried into `pending` even at capacity and never claims a lease.
  **W2/W3 accepted** — base-independent startup notice (armed-id count, all bases) + MR-058 val B3
  (configured-but-empty armed file ⇒ run-but-gate, spawn nothing). **W4 accepted** — runbook env table
  excludes the `WATCH_LAUNCH_MARKER` test fixture. **N1** — default no-cache re-read of the small armed
  file each tick; a cache, if added, keys on `(mtime, size)`. **N2** — wildcard `*`/`ALL` dropped +
  asserted (val F). **G1 PASS.**
