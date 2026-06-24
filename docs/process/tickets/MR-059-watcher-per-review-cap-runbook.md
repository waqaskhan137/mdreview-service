---
id: MR-059
title: "`watch.py` per-review attempt cap + full operator runbook (`docs`) — bound the re-Send loop, document the public-instance arming story"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: svc             # svc | ui | infra | docs  (svc; ships the docs runbook in the same change)
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-19
epic: agent-watcher
depends_on: [MR-058]
branch:                # MR-059-slug, once work starts
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Bound a **non-converging** review so it cannot monopolize the global budget, and ship the **full
operator runbook** the public-instance story needs. The per-review cap stops one review id from eating
the `WATCH_MAX_LAUNCHES_PER_HOUR` budget across many **re-Sends** (a human who keeps pressing "Send", an
agent that hands back and is re-Sent, a `--backlog` re-seed), while **distinct** reviews are unaffected.
The corrected B1 model is load-bearing: under C2's edge-triggered design a **crashed** child *strands*
its review (`turn_updated` unchanged ⇒ `/wait` never re-surfaces it), so the cap guards the legitimate
**re-Send / re-surface loop**, **NOT** a crash-loop — C3 adds **no** auto-relaunch (explicit non-goal).
This ticket also carries, **in the same change**, the full runbook in `README.md` + `CLAUDE.md` (the
public-instance / arming story C2 deferred). No `app.py` change.

## Acceptance criteria

- [ ] **Per-review cap — `WATCH_MAX_ATTEMPTS_PER_REVIEW` (default 5) over a rolling
      `WATCH_ATTEMPT_WINDOW_S` (default 3600s) window.** Once a review id's spawn count in the window
      reaches the cap, the watcher **stops spawning for that review** (logs it once) until the window
      slides / the review ages out — distinct reviews unaffected. Both env-overridable.
- [ ] **Data structure (pinned).** A module-level `dict[review_id] -> collections.deque[timestamp]`,
      mirroring the existing global `_launch_times` deque (`watch.py:153`). On each successful `_spawn`
      (`watch.py:218-233`), append `time.time()` to that review's deque. The cap check evicts entries
      older than `WATCH_ATTEMPT_WINDOW_S` (same slide as `_at_capacity`'s hourly eviction,
      `watch.py:189-191`) then compares `len(deque) >= WATCH_MAX_ATTEMPTS_PER_REVIEW`.
- [ ] **Prune empty deques (memory-leak guard).** When a review's deque empties on eviction, **delete the
      key**, so the dict does not grow unbounded across many one-shot reviews on a long-running watcher.
- [ ] **Checked as a terminal gate in `run()` BEFORE `handle()` (same W1 discipline as arming).** Order:
      `_is_armed` (MR-058) → `_per_review_capped` (this ticket) → *(`handle()`:)* `_at_capacity` (C2 global
      caps) → claim. The per-review cap is a **terminal** skip (it is "this review has had its turns this
      window," not "retry when a slot frees"), so it is checked in `run()` **before** `handle()` and
      `continue`d past — it never reaches `handle()`, the claim, or the `pending` logic. A capped review is
      skipped **without claiming** (no lease side-effect), the **cursor advances**, and it is **not** added
      to `pending` (only a genuinely new edge after the window slides re-spawns it).
- [ ] **Composition with the global caps (pinned).** The per-review cap is **additional**, never a
      replacement. A spawn must pass **both** the per-review cap **and** the two C2 global caps
      (`WATCH_MAX_CONCURRENT`, `WATCH_MAX_LAUNCHES_PER_HOUR`). Three independent ceilings; a spawn happens
      only under all three.
- [ ] **Corrected B1 meaning wired into the log line and docs.** The cap bounds the **re-Send / re-surface
      loop**, NOT a crash-loop: a crashed child does **not** produce a new edge (it strands), so it is
      **not** what this cap guards, and C3 adds nothing to relaunch it (non-goal). The cap's log line and
      the runbook say **"re-Send / re-surface,"** never "crash-loop," so the close evidence cannot claim a
      property the loop does not have.
- [ ] **Full operator runbook (`docs`, in-same-change) — README "Watcher" section.** Replace the
      forward-pointer block (`README:229-231`, "the full arming / untrusted-base runbook … is a later
      increment (C3)") with the real content covering:
  - [ ] **Arming model & file format:** what arming is (a local operator allowlist of review ids the
        watcher may auto-run), the `WATCH_ARMED_FILE` format (one id/line, `#` comments, ignored bad
        tokens), the `WATCH_ARMED` env convenience, and that arming a review is "append a line, no
        restart."
  - [ ] **Local-only & why (the security heart):** the allowlist is operator-local config a service
        request **cannot** influence — there is **no endpoint to arm a review**, so on a no-auth public
        instance a review **cannot arm itself**. State plainly: **provenance is not a trust boundary** on
        the no-auth service, so the only thing between a public Send and a launch on the operator's machine
        is the local allowlist.
  - [ ] **Untrusted / public-instance operation:** arming is **REQUIRED** to run against a non-loopback,
        un-vouched base (un-vouched + no arming ⇒ the watcher EXITs); the run-but-gate behavior; the worked
        example (`WATCH_ARMED_FILE=… MDREVIEW_BASE=https://public.example python3 watch.py`, no
        `WATCH_TRUSTED_BASE`).
  - [ ] **The per-review cap:** `WATCH_MAX_ATTEMPTS_PER_REVIEW` / `WATCH_ATTEMPT_WINDOW_S`, what they bound
        (a non-converging review's repeated re-Sends, **not** a crash-loop — crashes strand by design and
        never auto-relaunch), and how they compose with the global caps.
  - [ ] **Full env-var reference table — product config only (W4).** A single table of **real operator
        config**: `MDREVIEW_BASE`, `WATCH_TRUSTED_BASE`, `WATCH_ARMED_FILE`, `WATCH_ARMED`,
        `WATCH_LAUNCH_CMD`, `WATCH_MAX_CONCURRENT`, `WATCH_MAX_LAUNCHES_PER_HOUR`,
        `WATCH_MAX_ATTEMPTS_PER_REVIEW`, `WATCH_ATTEMPT_WINDOW_S`, `WATCH_OWNER`, `WATCH_SINCE`,
        `WATCH_WAIT_TIMEOUT_S` — default + one-line meaning each. **EXCLUDE `WATCH_LAUNCH_MARKER` (W4):**
        it is a **test-fixture** env read by the validation **stub** (it writes a launch marker so the test
        can count spawns), **not** a `watch.py` config var — it must **not** appear in this table, or a
        reader would mistake a fixture var for a product feature. It stays in the validation fixtures only.
- [ ] **CLAUDE.md pointer update.** The agent-facing note (`CLAUDE.md:130-137`) gains one sentence that the
      watcher can now run against a public instance **only for armed reviews**, pointing at the README
      section; drop the "C3 is later" forward-pointer (`CLAUDE.md:136-137`).
- [ ] **Local validation passes:** `python3 -m py_compile watch.py`, plus the stub-launch end-to-end
      against a **localhost throwaway** mdreview container on a scratch port (e.g. 8155 — never the live
      8139, never `docker compose up`/8137), with a tiny window (`WATCH_ATTEMPT_WINDOW_S=60`) and a small
      cap (`WATCH_MAX_ATTEMPTS_PER_REVIEW=2`):
  - [ ] **D — cap stops the re-Send loop:** ONE review re-Sent 3 times (each a fresh reviewer→agent flip ⇒
        a real new `turn_updated` edge) with the cap at 2 spawns **exactly 2** times (the 3rd re-Send is
        capped: logged, **no claim**).
  - [ ] **E — distinct review unaffected:** a second, different review `ID2` at the cap-edge still spawns
        its full quota **while `ID` is at/over its cap** (the cap is **per-id**, proving it does not
        throttle the whole queue).
  - [ ] The cap log line says **"re-Send"**, never "crash-loop" (the corrected B1 meaning).
  - [ ] Runbook reviewed by reading the rendered README section: documents arming (local-only,
        provenance-is-not-a-trust-boundary), untrusted-base operation (arming REQUIRED), the per-review
        cap, and the full env table (product config only — `WATCH_LAUNCH_MARKER` absent). No render-smoke
        owed (Markdown docs, not a product page).

## Notes / context

- Epic plan: `docs/process/epics/agent-watcher-plan.md` — §"C3 — Watcher safety + ops (full plan)",
  §"2. Per-review attempt cap + convergence guard", §"What C3 is (and what the corrected B1 model means)",
  §"3. Full operator runbook (`docs`)", the C3 Ticket-breakdown row for MR-059, and the §"MR-059
  validation (per-review cap + distinct-review isolation + runbook)" (tests D/E + the stub + the W4
  `WATCH_LAUNCH_MARKER` fixture note).
- Shipped C2 `watch.py` line refs: `_spawn` at `watch.py:218-233` (append the timestamp here); the global
  `_launch_times` deque at `watch.py:153` (the structure to mirror); `_at_capacity()` hourly eviction at
  `watch.py:189-191` (the same window-slide pattern); the `run()` per-row loop / cursor advance at
  `watch.py:299-306` (the terminal-gate sequence MR-058 introduces before `handle()`, where this cap is
  inserted after the arming gate).
- Docs targets: README "Watcher" forward-pointer at `README:229-231` (replaced); the CLAUDE.md
  forward-pointer at `CLAUDE.md:136-137` (replaced) and the agent-facing turn-baton note at
  `CLAUDE.md:130-137` (gains the public-instance / armed-only sentence).
- **`WATCH_LAUNCH_MARKER` is a test fixture (W4), NOT product config** — read only by the validation stub
  (it writes a marker line per spawn so the test can count launches); it must never appear in the runbook
  env table.
- `depends_on: [MR-058]` — the cap sits in the same `run()`-side terminal-gate sequence MR-058 introduces
  before `handle()`, and the runbook documents both. No `app.py` change (flag a blocker if a genuinely
  missing primitive surfaces). No Dockerfile change, no render-smoke (`watch.py` not containerized; the
  runbook is Markdown docs, no product page — footgun #9 does not bite). `collections`/`time` are stdlib
  (footgun #1).

## Work log

_Filled in during implementation._

- `YYYY-MM-DD` — what changed, files touched.

## Validation

_How this was verified._

- `YYYY-MM-DD` — what was checked and the result.

## Follow-ups

Anything deliberately deferred. Move real follow-ups to `backlog.md` or a new ticket.
