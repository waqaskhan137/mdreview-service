---
review_of: epics/watcher-container-plan.md
gate: retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-24
verdict: Smooth run — a load-bearing auth unknown pre-resolved before planning, a correctly-isolated human-dependency gate (operator-minted setup-token) paused implementation rather than guessing, G1 1 round / G7 1 round, 0 parks, 0 carries. The reusable pattern (a gate whose proof needs an operator-supplied credential) is unwritten.
status: resolved
---

# Cycle retrospective — watcher-container (sprint-25, GH #30)

**Verdict:** Smooth. A four-ticket `infra` epic shipped to G7 PASS in one G1 round and one G7
round, zero parks, zero carry-overs. The run's standout is structural, not a bug: the make-or-break
gate (headless subscription auth in a no-keychain Linux container) needed a credential **only the
operator can mint** (`claude setup-token`, interactive OAuth), and the cycle correctly isolated that
into one ticket (MR-070), **paused** implementation for the operator to supply the token via a
gitignored `.scratch/.test-token`, and built compose (MR-071) only on the *proven* result. That
worked — but it leaned on ad-hoc orchestration the process/skill does not name. This retro reviews
the run and proposes turning that one-off into a written pattern.

## What went well (load-bearing)

- **The load-bearing unknown was pre-resolved against reality before planning, not assumed.** The
  planner falsified the auth question against the installed CLI *before* writing the plan: the
  Keychain (not a mountable file) reality, `setup-token` being subscription-billed, and the exact
  env var `CLAUDE_CODE_OAUTH_TOKEN` (110 occurrences in the native binary, cross-checked against the
  npm `cli.js`). The G1 critic re-verified each claim independently and found them accurate. A
  brief's "central risk" arrived at G1 already de-risked to a single named build-time test — the
  ideal shape for a load-bearing question.
- **The risk was isolated to its own ticket and retired before anything depended on it.** MR-070
  proved auth + the first MCP round-trip *before* MR-071 added compose, so MR-071's failure surface
  narrowed to compose wiring alone. The G7 critic re-ran both gating proofs and the e2e from a fresh
  build (not on report), confirming exit-0 auth and a ~27s end-to-end Send→action.
- **Security hygiene held end-to-end and was verifiable.** Token piped from a gitignored file, never
  echoed, `sk-ant-` scrubbed from outputs, `.env` gitignored + `.env.example` empty, prompt
  interpolation safe under `shell=False`. The G7 review carries a clean security sign-off. The
  expired-keychain-token detour (a fast `401` vs a trust-hang `timeout` exit 124) made the proof's
  failure modes *legible* — auth failure distinguishable from a trust-dialog hang.

## Top suggestions (prioritized, suggest-only)

1. **Name the "operator-credential gate" as a first-class pattern in the process.** `[process]`
   This is the highest-value fix because it is the run's defining structural feature and is wholly
   unwritten — `grep` of `docs/process/README.md` finds no "human-dependency", "operator-supplied",
   or credential vocabulary. The pattern recurred here exactly: *a gate whose proof requires a
   secret/credential only the operator can mint (interactive OAuth, a paid key, a hardware token),
   so implementation must PAUSE for the operator rather than build on an unverified assumption.*
   Codify it as a short rule, e.g.: *When a ticket's acceptance gate needs an operator-supplied
   credential, (a) isolate that gate to its own ticket so nothing downstream builds on an unproven
   assumption, (b) mark the sprint's human dependency up front (sprint Notes), (c) the implementer
   pauses and requests the credential via a gitignored `.scratch/` file — never committed, never
   echoed — and (d) if it cannot be supplied, the cycle PARKS at that ticket, it does not guess.*
   The sprint file already practiced all four (its "Human dependency" note + the "parks at MR-070
   pending the token" G7 scope note); promote that practice to the README so the next
   credential-gated epic inherits it instead of re-deriving it. This generalizes C2's narrower
   "a credential-bearing chunk gets its own focused G1" into the implementation/validation phase.

2. **Write down the credential-handling-in-validation checklist.** `[process]` / `[skill]`
   A security-sensitive thread ran clean through this run purely on operator discipline, not a
   written rail: extract the token to a gitignored file, never echo it, scrub `sk-ant-…` from any
   captured output, prefer a fast-failing probe (the `401` vs trust-hang distinction) so an
   expired/invalid credential is diagnosable. None of this is in the process or the skill; the only
   adjacent rule is the memory note "never `docker compose up` against the live volume." A 4-5 line
   "handling credentials in a validation gate" checklist (pipe-from-gitignored-file, no-echo,
   scrub-outputs, make-auth-failure-distinguishable-from-hang) makes the next token-bearing smoke
   reproducible rather than relearned. Pairs with suggestion 1.

3. **Record the "compose collides with the live standalone container, so compose e2e needs a throwaway override" footgun.** `[process]`
   Verified: `docker-compose.yml` pins `container_name: mdreview` and `8137:8080` (lines 5, 7) —
   **both collide** with the live standalone `mdreview` container (and the live compose port). The
   G7 e2e only worked because the critic applied a throwaway override (`container_name:
   mdreview-wtest`, `8141:8080`, project `mdreview-wtest`). This is the operational twin of the
   existing "never `docker compose up` against the live volume" memory rule, but the *positive*
   instruction — *the live instance is a non-compose `docker run`, so any compose-based test needs a
   `-p <throwaway>` project AND a `container_name`/port override to avoid colliding with it* — is
   written nowhere in `docs/process/`. One line in the README validation/infra note (or the skill's
   smoke recipe) saves the next compose smoke from a name/port collision against the live service.

## Lower-priority / noted

- **Some image-specific unknowns were caught at G1 by the critic, not the planner** (workspace-trust
  dialog hanging headlessly, a writable `$HOME` for the runtime user, the MCP round-trip being a
  *second* unproven delta folded silently into MR-071). All six G1 findings were worth-fixing/nits,
  all folded in one revision — so this is healthy gate behavior, not a miss. Worth noting only as the
  expected division of labor: the planner pre-resolved the *auth* unknown but under-imagined the
  *runtime-environment* unknowns of running a Node CLI headless in a fresh container; the critic
  supplied those. No action beyond awareness. `[agent]` (mdreview-planner, advisory)
- **The one carried fast-follow is real but minor:** the Linux `~/.claude` bind-mount creds path is
  documented-but-unverified (G7 W1, softened to "verify-on-host" with the wrong `:ro` dropped). Not a
  carry-over (docs-only, resolved at G7); a backlog item if ever on a Linux host. `[feature]`
- **The `reviews/` directory split surfaces again** (named across ~6 prior retros, still unwritten).
  Not re-litigated here; flagged only for the running tally. `[process]`

## Metrics

- **G1 rounds:** 1 (GO-WITH-NITS — 0 blockers, 4 worth-fixing + 2 nits, all folded, no round 2).
- **G7 rounds:** 1 (PASS — both gating proofs + the compose e2e re-driven from a fresh build; 1
  worth-fixing doc defect W1 + 2 nits, resolved/accepted post-review, none blocking).
- **Tickets:** 4 shipped (MR-069/070/071 infra, MR-072 docs), 0 carried.
- **Parks:** 0. (The credential-gated MR-070 *could* have parked had the operator not supplied the
  `setup-token`; the cycle was correctly structured to park there rather than guess — it just did not
  need to.)
- **Wrong load-bearing assumptions:** 0. The plan's single biggest residual unknown (in-container
  headless subscription auth) was proven correct at MR-070; the load-bearing arming-off / vouched-base
  posture held. The G7 W1 doc defect (unverified Linux creds-mount, wrong `:ro`) was a secondary-path
  documentation accuracy miss, not a load-bearing design assumption.
