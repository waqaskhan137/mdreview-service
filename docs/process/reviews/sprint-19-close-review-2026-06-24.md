---
review_of: sprints/sprint-19.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# Sprint-19 G7 close review — agent-watcher Chunk 3 (FINAL)

Independent staff-critic review of the SHIPPED `watch.py` + README/CLAUDE docs on `dev`
(commits `057054b`, `b5ce523`, `4dc8e22`; tip `4dc8e22`). I did not implement this. I read
`watch.py` in full, both tickets' ACs/Work log/Validation, the README "Watcher" runbook, the
CLAUDE.md pointer, and the relevant `app.py` seams (`/wait`, `/handoff`, `RID`), then
re-exercised every load-bearing behavior against a throwaway service in `.scratch/` on port
8156 (never 8139/8137, no `docker compose up`). Scratch cleaned up after.

**Verdict: PASS-WITH-NITS.** Both tickets' acceptance criteria are met. The C2 fail-closed
no-regression is preserved byte-for-byte, arming is local-only (no HTTP route, no self-arming),
the wildcard is dropped, un-armed reviews are skipped without a lease claim and never strand or
enter `pending`, and the per-review cap is per-id and uses the corrected B1 framing. The single
finding is a **doc defect in the README arming example** (worth-considering, not blocking): the
worked example arms ids that cannot match the id shape, so a copy-paste operator arms nothing.

## What I independently re-ran (with results)

| Test | What it proves | Result |
|------|----------------|--------|
| A | untrusted base + NO arming ⇒ EXIT 2 (C2 preserved) | **exit 2**; stderr names base + arming hatch |
| A2 | row-4 refusal names arming as the escape | present (`WATCH_ARMED_FILE/WATCH_ARMED`) |
| B | untrusted base + arming (X armed, Y not) ⇒ only X spawns | marker = X only; **Y turn=agent, agent_status=null (never claimed)** |
| B2 | un-armed never enters `pending` even at `MAX_CONCURRENT=0` | "not armed — skip" logged **exactly once**; Y never in a "deferring" line; armed X correctly deferred |
| B3 | configured-but-empty ⇒ run-but-gate, spawn nothing | RAN (no exit), notice `0 ids armed … spawn NOTHING`, marker empty |
| C | no HTTP arm route | `/arm`, `/armed`, `/api/arm` all **404**; `grep arm app.py` = comment text only |
| F | `*`/`ALL` dropped, never match-all | both dropped-and-logged; arms nothing; lease stays null |
| D | cap=2, re-Send one review 3× ⇒ exactly 2 spawns | **2 spawns**; 3rd capped, no claim; log says "re-Send … not a crash-loop" |
| E | distinct review unaffected by another's cap | B spawned its own **2** while A over cap (per-id) |
| Rows 1/2 | loopback & exact-vouch ⇒ RUN past Step 0 | both ran; vouch mismatch (http vs https) ⇒ **exit 2** |
| Unit | `_is_armed` True when unconfigured; deque prune; cap boundary; wildcard union | all pass |
| Server | no-regression (server unchanged) | `/healthz` 200, `/api/reviews` 200 |
| `py_compile` | `watch.py` + `app.py` | both OK |

The non-loopback base used the service's own `0.0.0.0` bind reached via the LAN IP
(`http://100.65.0.151:8156`), which `urlparse` sees as non-loopback — the same fixture the
ticket validation used.

## MR-058 — arming / allowlist (Step-0 relaxation)

**All ACs met.** Findings:

- **[verified] C2 fail-closed preserved byte-for-byte (the critical no-regression).** Test A:
  untrusted base, no arming ⇒ exit 2 before any network call. Decision table verified on all four
  rows in code (`require_trusted_base_or_exit`, watch.py:181-209) and at runtime. The relaxation is
  exactly one `return` gated on `arming_configured()` (watch.py:198-199); `check_trusted_base` is
  untouched.
- **[verified] No self-arming / not HTTP-settable.** Test C: arm-probe endpoints 404; no `app.py`
  change this sprint (git diff: only `watch.py`, `README.md`, `CLAUDE.md`, process files). The
  allowlist is file/env only, re-read from disk (`_file_armed_ids`, watch.py:130-150). A review
  cannot arm itself.
- **[verified] `*`/`ALL` dropped, never match-all (N2).** Test F + unit: `_valid_id` requires a
  full `[A-Za-z0-9]{4,40}` match (the exact `RID` value from app.py:59), so `*`/`ALL` are
  dropped-and-logged; `armed_ids()` unions env ∪ file and keeps only valid tokens.
- **[verified] Un-armed skipped with no lease side-effect; terminal skip never enters `pending`
  (W1/B2).** The gate is a `continue` in `run()` before `handle()` (watch.py:443-447), not a
  `handle()` early-return. Test B2 with `MAX_CONCURRENT=0` (the case the early-return bug would loop
  forever): un-armed Y logged once, never claimed, never in `pending`; armed-but-capacity X went to
  `pending` as a genuine defer. The two skip paths are cleanly distinct.
- **[verified] Configured-but-empty ⇒ run-but-gate (not "unconfigured").** Test B3 + F: empty/
  all-invalid armed file ⇒ watcher RUNS, startup notice `0 ids armed … spawn NOTHING`, spawns
  nothing. `arming_configured()` reads only "is a source set," never the contents (watch.py:105-108).
- **[verified] Base-independent gate + startup notice (W2/C3-Q1).** `_is_armed` is consulted on
  every base when arming is configured; `_arming_startup_notice` prints the count + base-independence,
  with the explicit empty-allowlist tail.

**[nit, non-blocking] Invalid-token warnings re-log every check.** Because the file is re-read per
`_is_armed` call (the intended freshness design), a permanently-invalid line (e.g. a stray `*`)
re-emits its "ignoring invalid armed id" warning on every poll tick, not once. Functionally correct
(AC asks for "dropped and logged," which it does), but in steady state it is log noise. Not worth a
change; noting for the record.

## MR-059 — per-review cap + operator runbook

**All ACs met**, with one doc nit. Findings:

- **[verified] Per-review cap is per-id and terminal (D/E).** Test D: 3 re-Sends, cap=2 ⇒ exactly
  2 spawns, 3rd capped with no claim. Test E: a distinct review spawned its own quota of 2 *while*
  the first was over cap — the cap does not throttle the queue. `_per_review_capped` (watch.py:307-329)
  is a second terminal gate after arming, `continue`d before `handle()`.
- **[verified] Empty-deque pruning (memory-leak guard).** Unit: a deque holding only stale
  timestamps is evicted and the key deleted (watch.py:326-327); confirmed `rid not in
  _review_attempts` after the check. The per-id dict does not grow unbounded across one-shot reviews.
- **[verified] Composition, not replacement.** The cap is a third independent ceiling; a spawn must
  pass `_is_armed` → `_per_review_capped` → `handle()`'s `_at_capacity` (two global caps) → claim.
  All three enforced; the global caps are byte-for-byte C2.
- **[verified] Corrected B1 framing.** The cap log line reads `bounding the re-Send/re-surface loop,
  not a crash-loop` and never claims crash-loop protection. This matches the C1 seam: `/handoff
  {state:working}` does NOT bump `turn_updated` (app.py:635-636), so a crashed child strands at
  `turn==agent` and the edge-triggered `/wait` (predicate `turn_updated > since`, app.py:443-445)
  never re-surfaces it — there is no crash-loop to bound, and no auto-relaunch (`_reap`,
  watch.py:267-285). The framing is accurate, not aspirational.
- **[verified] Runbook completeness (DoD).** README "Watcher" section (README:180-276) carries the
  arming model + file format, the local-only / provenance-is-not-a-trust-boundary rationale, the
  public-instance operation (arming REQUIRED, worked example), the per-review cap, and a 12-row
  env-var table. `WATCH_LAUNCH_MARKER` (the test-fixture env) is correctly **absent** from the table
  (W4). CLAUDE.md pointer (CLAUDE.md:130-139) gained the armed-only public-operation sentence and
  dropped the "C3 is later" forward-pointer.

- **[worth-considering, non-blocking] README arming example uses ids that cannot match the id
  shape.** The worked example (README:239) is:
  ```
  printf '%s\n' 'rev_abc123' 'rev_def456' > ~/.mdreview-armed
  ```
  Both `rev_abc123` and `rev_def456` contain an underscore, which fails the `[A-Za-z0-9]{4,40}`
  shape (verified: `re.fullmatch` returns False for both). An operator who copies this pattern would
  have **both ids dropped-and-logged and arm nothing** — exactly the silently-idle footgun the
  startup notice exists to soften. Real server ids are `secrets.token_hex(5)` (app.py:207) = 10 hex
  chars (e.g. `cf6c1ff807`). Fix: change the example ids to the real shape (e.g.
  `printf '%s\n' '6f399adbfd' 'c649283038'`). This is a one-line doc edit, not a code change, and
  not blocking — but it sits in the runbook MR-059 explicitly owns, and the placeholder shape
  contradicts the very validation rule the same section documents two paragraphs above.

## Scope & G7 render-smoke compliance

- **[verified] Scope clean.** No `app.py` / Dockerfile / compose change (git diff confirms
  `watch.py` + `README.md` + `CLAUDE.md` + process files only). No YAGNI over-build: no server-side
  arming store, no crash auto-relaunch, no mtime-cache (the default no-cache re-read was chosen, as
  the AC permits). C3 is the last chunk; nothing leaked from a future chunk (there is none).
- **[verified] Render-smoke compliance.** C3 touches NO product page — `watch.py` is not
  containerized and the docs are Markdown. Per the G7 pass-condition row, **no
  `scripts/render-smoke.sh` DOM assertion / screenshot / `docker build` is owed; its absence is
  COMPLIANT, not a gap.** The owed smoke is `py_compile watch.py` + the stub-launch end-to-end + a
  throwaway-container `/healthz`+`/api/reviews` no-regression — all run above and passing.

## End-to-end epic story (C1+C2+C3 compose)

The full loop holds: the reviewer flips `turn==agent` (C1 `/handoff {to:agent}`, bumps
`turn_updated`); the watcher long-polls C1 `/wait?turn=agent&since=cursor` (edge-triggered); the
arming + per-review gates (C3) decide *which* reviews proceed and the fail-closed base check (C2)
decides *run-vs-exit*; the watcher claims via C1 `/handoff {state:working}` (single-flight, 409 on a
foreign owner); spawns the child with the `REVIEW_ID/MDREVIEW_BASE/MDREVIEW_OWNER` env contract; the
child works and hands back (`/handoff {to:reviewer,state:done}`). I observed the complete
"flip → detect → gate → claim → spawn → hand-back" cycle in Test B (armed X) and the gate correctly
short-circuiting it for the un-armed Y. No seam fails to compose.

## Resolution log

- 2026-06-24 — Independent G7 review authored. Re-ran A/A2/B/B2/B3/C/F (MR-058),
  D/E + cap/prune/composition (MR-059), decision-table rows 1/2 + vouch-mismatch, unit checks, and
  the server no-regression against a `.scratch/` throwaway service (port 8156). All ACs verified
  met. One non-blocking doc nit raised (README arming example ids fail the id shape). Verdict
  **PASS-WITH-NITS**. Scratch cleaned up.

## Resolution log

- 2026-06-24 — Independent G7 review (C3, the final chunk). Verdict PASS-WITH-NITS; the critic
  re-ran the full A/A2/B/B2/B3/F/C/D/E matrix against a `.scratch/` throwaway service: C2 fail-closed
  EXIT preserved byte-for-byte when arming unconfigured, no self-arming (no `app.py` route), un-armed
  skipped without claim and never into `pending`, `*` dropped, per-review cap bounds the re-Send loop
  (corrected B1), distinct reviews independent. C1+C2+C3 compose into the full loop.
- 2026-06-24 — The one worth-considering finding (README arming example used `rev_abc123` ids that
  fail the documented `[A-Za-z0-9]{4,40}` shape) FIXED: example now uses real 10-hex-char ids. The
  re-log-noise nit accepted as-is (intended per-check freshness). Review `status: resolved`; sprint-19
  closed at G7; the `agent-watcher` epic marked `done` (final chunk).
