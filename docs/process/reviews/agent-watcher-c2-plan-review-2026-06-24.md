---
review_of: epics/agent-watcher-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 Plan-Gate Review — agent-watcher C2 (Watcher core)

Independent review of the **"C2 — Watcher core (full plan)"** section of
`epics/agent-watcher-plan.md` only. C1 (MR-054, MR-055) is shipped and out of scope; I gate whether
C2's tickets (MR-056, MR-057) may be spawned. C2 introduces the first credentialed process-spawner,
so the security analysis is the heart of this review.

Every load-bearing code claim below was read against the working tree: the shipped C1 contract in
`app.py` (`_wait` at app.py:419-458, the `?turn=` filter at app.py:501-509, the `/handoff`
`{state:working}` arm at app.py:635-662, `/status` at app.py:581-596) and `mcp_server.py`'s
`http()` helper (mcp_server.py:376-389).

## Verdict

**PASS-WITH-NITS.** G1 passes; MR-056/MR-057 may be spawned. The security crux — the fail-closed
trusted-base check — is correctly designed: it parses the host (no substring trap), refuses-and-exits
rather than warning, exact-matches the operator vouch, and ships **no** C3 relaxation. The injection
surface is clean: env-as-interface, argv-not-shell, no attacker-influenceable interpolation.
Claim-before-spawn is the right single-flight primitive and it maps onto the shipped `/handoff` 200/409
exactly. The scope split is right and no missing server primitive is hidden in `watch.py`.

I am **not** blocking, but two findings are real and must be folded into the tickets at G2 because the
plan currently asserts something the shipped code contradicts:

- **B1 (the crash-loop model is backwards).** The plan repeatedly claims a child that crashes before
  `hand_back` will be "re-claimed and re-spawned" by a later watcher tick, bounded by the hourly cap.
  Against the shipped code that is **false**: `turn_updated` is bumped *only* on a real reviewer→agent
  flip (app.py:630-634); the `{state:working}` arm explicitly does **not** bump it. A crashed child
  leaves `turn==agent` with `turn_updated` unchanged, so the edge-triggered `/wait?since=cursor` loop
  (which the watcher advanced past on the first claim) **never re-surfaces it**. The real failure mode
  is the opposite of a relaunch storm: a crashed child **silently strands the baton at `turn==agent`
  forever** with no relaunch and no human signal. This is not unsafe (it under-spawns, not over-spawns),
  so it is a NIT not a blocker — but the plan's stated bound is wrong and the honest gap (a stranded
  baton) must replace it, or the C2 close will claim a safety property the loop does not have.

These are SHOULD-fix-in-ticket items, not a second G1 round.

## The security crux — fail-closed trusted-base (verified sound)

I pinned every hole the brief asked me to. The check as written (plan lines 334-348) holds:

- **(b) loopback identification is correct, not a substring trap.** It does
  `urllib.parse.urlparse(base).hostname` and tests membership in `("localhost", "127.0.0.1", "::1")` —
  an exact host-token compare, not `"localhost" in base`. So `localhost.evil.com` parses to hostname
  `localhost.evil.com`, which is not in the set ⇒ refuse. The substring trap the brief flagged is
  avoided. **Credit it.**
- **(c) it refuses-and-EXITS.** Step 0 says "prints a one-line reason to stderr and **exits non-zero**
  (it does not warn-and-continue)," and runs "before any network call, before the loop." Correct shape
  for a fail-closed control.
- **(d) no bypass path.** There is no env that skips the check. `WATCH_TRUSTED_BASE` does not *disable*
  the check — it supplies an exact-match comparand that the check still enforces. C3's arming (the
  relaxation) is explicitly named a non-goal (plan lines 360-361, 643-645). The relaxation does not
  leak into C2. **This is the property the requirement demanded and it holds.**
- **(a) normalization — adequate, with one stated gap (WC-1 below).** Both sides go through the same
  `.rstrip("/")`, so a trailing-slash mismatch is handled. The exact-match is deliberately strict:
  `http`/`https`, `localhost`/`127.0.0.1`, and `host` vs `host:port` are treated as *distinct*. For a
  fail-closed control that is the **correct** direction — a brittle match refuses a legit base (operator
  fixes their env and re-runs), it never lets an untrusted base through. The only residual is a
  usability paper-cut, noted below; it is not a security finding.

The assertable test (plan lines 362-364, 583-586) points the watcher at a non-loopback base with no
vouch (refuse) and at a mismatched vouch (refuse), asserting **non-zero exit** — not just a log line.
That is the right assertion. PASS on the crux.

## Command/argument injection (verified clean)

- **No `shell=True`.** Plan line 476/479 pins `subprocess.Popen(cmd, env=child_env)` with an argv list
  and explicitly forbids `shell=True` with an interpolated id.
- **Env is the interface, not interpolation.** `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER` reach the
  child via the environment (plan lines 443-447, 466-468); the template "needs no placeholder
  interpolation." `REVIEW_ID` is server-generated `secrets.token_hex` (`[0-9a-f]`, verified
  app.py:33 import + create), so even where it does flow into env it is not attacker-shaped.
- **No attacker-influenceable data in the command.** No review title, comment body, or any human-typed
  field is interpolated into the launch command or a shell. The one convenience escape hatch
  (`{review_id}` placeholder, plan line 468) is gated to the *id* only, which is the safe `[0-9a-f]`
  token. **Credit the env-as-interface design — it is the right call and it keeps the template
  injection-free.** No injection finding.

One thing for the ticket (WC-2): the plan says `WATCH_LAUNCH_CMD` "a single string the watcher splits
with `shlex.split`" (line 464) is an accepted form. `shlex.split` is fine; pin that the JSON-array form
is preferred and that the string form must **never** be passed to a shell — only to `shlex.split` →
argv. That is implied but should be explicit so an implementer does not "helpfully" add `shell=True`
for the string form.

## Findings

### B1 — blocking-to-fix-in-ticket (NIT severity): the crash-loop bound is the wrong model

Plan lines 498-501 and 518-519 and 522-523 state that a child crashing before `hand_back` leaves the
baton at `turn==agent`, the lease goes stale, and "a later watcher tick may re-claim and re-spawn it,"
bounded by `WATCH_MAX_LAUNCHES_PER_HOUR`. **Verified against app.py this does not happen.**

`turn_updated` is bumped only on a real reviewer→agent flip (app.py:630-634). The `{state:working}`
claim/renew/takeover arm does **not** bump it (app.py:635-662; the comment at line 636 says so
explicitly). So after the watcher claims and advances its cursor to that flip's `turn_updated`, a
crashed child leaves `turn==agent` but `turn_updated` **unchanged** ⇒ the edge-triggered
`/wait?turn=agent&since=cursor` (returns only `turn_updated > since`, app.py:445) will **never** return
that review again. There is no relaunch loop for the steady-state watcher. The hourly cap is therefore
bounding a storm that the edge loop cannot produce.

The *actual* failure mode is the opposite and worse for liveness: **a crashed child silently strands
the baton at `turn==agent` forever.** No relaunch, no `hand_back`, no page — the human sees a review
stuck "Agent is working" until the 180s staleness banner, and nothing ever picks it up again unless the
human reclaims and re-Sends (a new flip, new `turn_updated`).

Two sub-cases the ticket must distinguish, because they have *different* relaunch behavior:

1. **Default `now`-seed watcher, steady state:** crashed child ⇒ stranded baton, **no** relaunch
   (the edge never re-fires). The hourly cap is irrelevant here.
2. **`--backlog`/`since=0` cold start (or a watcher restart that re-reads the agent-turn backlog):**
   *here* a stranded `turn==agent` review **does** re-appear (its `turn_updated > 0`), and a restart
   loop of the watcher process could re-claim+re-spawn it each cold start. This is the only path where
   the hourly cap is the actual bound, and it is bounded by **watcher restart frequency**, not by a
   crash loop within one watcher run.

Direction: rewrite the lifecycle section (Step 4 "Lease renewal / lifecycle" and Step 5) to state the
real model — (a) a crashed child strands the baton with no auto-relaunch under the default seed, so
liveness on crash depends on the human or on C3's convergence logic; (b) the hourly cap meaningfully
bounds only the cold-start/backlog and watcher-restart re-claim path. Do **not** claim "the global cap
bounds a crash-loop's total spend" as the C2 safety story when the dominant crash path produces a
*stranded baton*, not a loop. If "crashed child should retry" is wanted behavior, that is genuinely C3
(it needs a per-review attempt counter and a re-trigger that does not exist in C1's edge model) — and
the plan should say the watcher has **no** crash-retry in C2, by design, not "bounded retry."

This is a NIT (not a blocker) because the error is in the *direction of under-spawning* — C2 ships
*safe* (it will not over-spend), it just ships with a mis-stated bound and an unstated liveness gap.
But left unfixed, the C2 close review will assert a property the code does not have.

### WC — worth considering

- **WC-1 (normalization usability, not security): `WATCH_TRUSTED_BASE` exact-match will bite a real
  operator.** A vendor who sets `MDREVIEW_BASE=https://mdreview.example.com` and
  `WATCH_TRUSTED_BASE=https://mdreview.example.com/` (trailing slash — handled) is fine, but
  `WATCH_TRUSTED_BASE=mdreview.example.com` (no scheme) or a `:443`-vs-bare-host difference **refuses**.
  That is the *correct* fail-closed direction, but the refusal message must print **both** the
  configured `MDREVIEW_BASE` and the `WATCH_TRUSTED_BASE` it compared against, so the operator sees the
  exact mismatch and is not left guessing. Pin "the refusal names both strings" in MR-056. Cheap, and it
  turns a frustrating brittle-match into a self-explaining one. (Do not relax the match to fix this —
  the strictness is the control.)

- **WC-2 (shlex string form): pin that the `shlex.split` string form never reaches a shell** — only
  `shlex.split` → argv. Implied by "no `shell=True`," but state it for the string-form path explicitly so
  an implementer does not re-introduce a shell for convenience.

- **WC-3 (cap-skip cursor-stall is a self-inflicted stall risk).** Step 5 (plan lines 511-514) says
  "when at cap, stop processing this batch and do not advance the cursor past the unprocessed rows, so
  they re-return on the next poll." But the next `/wait` with the **un-advanced** cursor returns the
  *same* edge again immediately (it is `> since`), so while at the concurrency cap the watcher
  **busy-loops** `/wait` (returns instantly, re-checks cap, skips, re-polls) instead of long-polling.
  This is a CPU/disk spin (each `/wait` runs the O(all-reviews) `list_reviews()` scan, app.py:448),
  not a spend bug, but it defeats the long-poll while at cap. Direction: when a row is skipped for caps,
  either (a) track skipped ids in-process and add a small sleep before re-polling with the un-advanced
  cursor, or (b) advance the cursor but remember the skipped ids in a pending set the watcher drains as
  slots free — *without* relying on `/wait` to re-surface them (it won't re-surface a level it already
  emitted unless a newer edge lands). Pin the chosen mechanism in MR-057; the current "do not advance,
  it re-returns on the next poll" both spins and is fragile.

- **WC-4 (stub renews then immediately hands back — does not exercise the stale path).** The validation
  stub (plan lines 565-576) renews once and hands back after `sleep 1`. That proves the same-owner
  renew (200) and the happy hand-back, but it does **not** exercise the documented "child dies before
  pinging ⇒ lease goes stale ⇒ self-heals" claim (plan lines 489-492). Given B1, that claim is itself
  questionable for the default seed. Add one stub variant for MR-057 that **exits without
  `hand_back`** (a crash stub) and assert what *actually* happens: the baton stays `turn==agent`, the
  lease goes stale at `LEASE_TTL_S`, and — under the **default `now` seed** — the review is **not**
  re-spawned (proving B1's stranded-baton reality), versus under `--backlog`/restart it *is*
  re-claimed (proving the only real relaunch path). This is the test that would have caught B1.

- **WC-5 (watcher-id stability across a watcher restart).** The owner is
  `WATCH_OWNER` or `"watch-%s-%d" % (gethostname, getpid)` (plan lines 427-433), stable for the
  process life. On a watcher **restart**, the pid changes ⇒ new owner ⇒ a still-live child from the
  previous run renewing under the *old* `MDREVIEW_OWNER` is now a *foreign* owner to the new watcher.
  That is correct (the new watcher will `409` and skip a review the old child still holds — good), but
  pin it: a restarted watcher must not assume it owns leases its predecessor granted; it relies on the
  child's own owner + the stale-takeover, which is exactly the C1 primitive. State this so the restart
  case is not a surprise. (No code change needed; it is a "this is why owner derivation is fine" note.)

### Scope / sequencing (verified correct)

- **No missing server primitive.** I confirmed the loop is buildable on the three shipped surfaces:
  `/wait` edge long-poll (app.py:419-458, hit ⇒ `{"reviews":[...]}` with no `timeout` key, timeout ⇒
  `{"reviews":[],"timeout":true}` — the plan's contract table line 280 matches the code exactly),
  `?turn=` filter (app.py:501-509), `/handoff {state:working}` 200/409 (app.py:635-662). The plan's
  claim "no new server primitive is required by C2" holds. Nothing belongs back in C1.
- **Nothing in C2 is C3's.** The fail-closed refusal is in C2 (correct — it is the chunk that
  introduces the spawner); arming and the per-review attempt cap are deferred to C3 (plan lines 522-523,
  643-645). That matches the requirement's split. The relaxation does not leak forward.
- **MR-056/MR-057 split is clean.** Loop-core+fail-closed+claim (MR-056) vs spawn+child-contract+caps+
  runbook (MR-057), `depends_on: [MR-056]`. The double-spawn proof and fail-closed proof land in
  MR-056; the spend-bound proof in MR-057. Right seam.
- **No YAGNI over-build.** The plan correctly pushes per-child heartbeat timers onto the *child*
  (C2-Q1, child renews) rather than building watcher-side timers — that is the right cut. The in-flight
  `Popen` set for the concurrency cap is the minimum needed, not over-built.

### Validation adequacy

The recipe proves most ACs: the fail-closed test asserts a **non-zero exit** (not just a log) — A and B
at plan lines 583-586 — which is the right assertion for the security crux. The single-flight test
(D, lines 590-599) asserts exactly one stub launch per flip via a launch marker, which proves the
claim-before-spawn 409-skip. The cap tests (F, G) bound concurrency and hourly spawns.

**Gap (folds into WC-4):** no test exercises the **crash-without-hand-back** path, which is precisely
where the plan's stated model (B1) is wrong. Add the crash-stub variant so the close review measures
the *real* behavior (stranded baton under default seed; re-claim only under backlog/restart) rather
than asserting the mis-stated "bounded relaunch." Without it, MR-057's validation green-lights a safety
story the loop does not implement.

## Open questions for the author

- **Crash liveness:** is a stranded `turn==agent` after a child crash (no auto-relaunch under the
  default seed) the *intended* C2 behavior, with crash-recovery explicitly deferred to C3 — or was the
  plan assuming the edge loop would re-surface it? If the former, say so plainly in the lifecycle
  section and the C2 non-goals; if the latter, the loop needs a re-trigger that C1's edge model does not
  provide, and that is a real C2-vs-C3 scoping decision, not a wording fix.
- **Cap-skip while at concurrency cap:** is the busy-spin on `/wait` (WC-3) acceptable for the
  single-operator scale, or should the watcher sleep/track-pending? Either is fine, but pin one.

## What's good (load-bearing)

The fail-closed check is the part that had to be right and it is: host-parse not substring, exact-match
vouch, refuse-and-exit, no bypass, no C3 relaxation. The injection surface is closed by env-as-interface
+ argv. Claim-before-spawn maps onto the shipped atomic `/handoff` grant exactly. The scope split and
the "no missing primitive" claim both hold against the code. The one real correction (B1) is a
mis-stated bound in the *safe* direction, not a hole — which is why this is PASS-WITH-NITS, not BLOCKED.

## Resolution log

- 2026-06-24 — Review authored (independent G1, C2 only). Verdict PASS-WITH-NITS. B1 (crash-loop model
  is backwards; stranded baton is the real failure mode) + WC-1..WC-5 to fold into MR-056/MR-057 at G2.
  No second G1 round required; the findings are ticket-level, not plan-foundational.
- 2026-06-24 — Planner revised the C2 plan (author preserved, independence intact). Dispositions:
  **B1 accepted** — rewrote Step-4 lifecycle with a Crash model bullet (a child that dies before
  `hand_back` STRANDS the review at `turn==agent`, `turn_updated` unchanged, so edge-triggered `/wait`
  never auto-relaunches it — under-spawn, fail-safe; recovery is the human via the 180s stale banner or
  a `--backlog`/restart re-seed); corrected the caps rationale (they bound NORMAL-load spend, not a
  crash-loop, since the crash case is fail-safe); fixed design-principle #3, the epic done-state, and
  the C3 phase text so C3 inherits the correct model; added assumption C2-Q7. **WC-1→MR-056** (refusal
  names both bases, match stays strict). **WC-2→MR-057** (JSON-array preferred; string form `shlex.split`
  → argv, never `shell=True`). **WC-3→MR-056** (advance cursor + pending-set drained as slots free,
  bounded-backoff sleep as sanctioned fallback — replaces the cursor-stall busy-spin). **WC-4→MR-057
  validation** (crash-stub fixture + tests H/H2 measuring the real stranded behavior — the test that
  would have caught B1). **WC-5→MR-056** (pid-derived watcher-id changes on restart; relies on child
  `MDREVIEW_OWNER` + MR-055 stale-takeover, not on owning predecessor leases). **G1 PASS.**
