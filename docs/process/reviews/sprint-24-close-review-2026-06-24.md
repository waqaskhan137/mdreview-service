---
review_of: sprint-24
gate: G7
reviewer: staff-critic
independent: true
verdict: PASS
date: 2026-06-24
---

# sprint-24 close review (G7) — watcher-observability (#26)

Independent re-drive of MR-066 / MR-067 / MR-068 against a **rebuilt throwaway container**
(`docker build -t mdreview-s24-g7 .`, run on scratch port **8182**, ephemeral `/data`; never
8137/8139, never `docker compose up`, never the live volume). The implementer's G4 was from-source;
this gate is the container re-drive plus a diff scrutiny. All three tickets **PASS**. Two non-blocking
findings (one AC wording miss, one pre-existing cosmetic nit) and a couple of accepted-risk notes.

**Verdict: G7 PASS — the cycle ships.**

## Re-drive environment

- Image `mdreview-s24-g7` built from the working tree; container on `:8182`, `MDREVIEW_DATA=/data`
  (ephemeral). `viewer.html` is served from disk inside the image, so the container serves the
  committed bytes; `watch.py` runs on the host against the container (it is the non-containerized
  sibling, by design).
- node-CDP banner driver (`.scratch/cdp_banner.js`, the `agent_smoke.py` `Runtime.evaluate` pattern):
  headless Chrome, `Emulation.setEmulatedMedia` for `prefers-color-scheme` (dark/light) and
  `prefers-reduced-motion:reduce` — **never `--force-dark-mode`**. Reads `#turnbanner.classList`,
  `#turntext.textContent`, and `getComputedStyle(#turntext,'::before').animationName`.
- `py_compile app.py` + `py_compile watch.py` both pass; an unconfigured watcher still exits 2;
  loopback base is accepted without a `WATCH_TRUSTED_BASE` vouch (confirmed).
- Evidence retained under `reviews/sprint-24-render-evidence-2026-06-24/` (the `g7-*` files). All
  drivers/stubs/throwaway data lived in `.scratch/` (cleaned).

---

## MR-066 — pickup-timeout `.warn` cue (viewer) — **PASS**

Fixture: review flipped to `turn=agent`/`agent_status=null`, `turn_updated` back-dated 300s in the
container `meta.json` (confirmed `/status` returned the back-dated value: elapsed 300.2s). A first
attempt with the back-date silently not applied (a `docker exec python3 -` heredoc that did not run)
showed the *within-grace* spinner — re-running with the back-date actually persisted produced the
warn state, a useful confirmation that the transition is genuinely `turn_updated`-driven.

| Pane | classList | text | `::before` animationName |
|---|---|---|---|
| past-grace / light | `turnbanner show warn` (warn, **not** loading) | "No agent has picked this up — is a watcher running? Take back the turn." | `none` |
| past-grace / dark | `turnbanner show warn` | same | `none` |
| past-grace / reduced-motion | `turnbanner show warn` | same | `none` |
| within-grace / light | `turnbanner show loading` | "Sent — waiting for an agent to pick this up." | `turnspin` |

- `reclaimVisible=true` in every agent-turn row; `PICKUP_GRACE_S=60` constant present next to
  `STALE_S=180`. `.warn` reduced-motion-safe by construction (no `::before`, nothing to suppress).
- **Extra (beyond strict AC, plan-sanctioned):** the stale-working row (`agent_status.state=working`,
  `at` older than `STALE_S`) now also adopts `.warn` — re-driven: `warn`, "Agent may have stopped —
  Take back the turn?", no spinner, reclaim available. The decision table marked this "may adopt
  `.warn`"; it is correct and consistent.
- Screenshots: `g7-mr066-pastgrace-{light,dark}.png` (amber left-bordered banner, "Take back the
  turn" button, no spinner — legible on both mats).

All MR-066 ACs met. **PASS.**

## MR-067 — watcher stderr capture + structured log + guarded crash signal (watch.py) — **PASS (one AC-wording miss, non-blocking)**

Three host watcher runs against `:8182`, `WATCH_LOG_FILE` set, `WATCH_WAIT_TIMEOUT_S=2`, distinct
owners. Logs retained as `g7-watch-{crash,falsepos,happy}.log`.

- **Crash** (stub claims the lease via the child env, writes `BOOM-CRASH-MARKER` to stderr, exits 1,
  no hand_back): log captured `exited 1` **and** the stderr marker; `_signal_crash` re-checked
  `/status`, saw `turn=agent`, POSTed the signal. Resulting `/status`: `turn=reviewer`,
  `agent_status={state:blocked, message:"agent process exited 1 without finishing", owner:watcher-crash}`.
  **PASS.**
- **False-positive guard** (the conflation guard — most important): stub POSTs `hand_back{done}`
  **then** exits 1. Log: *"crash-signal: review … already handed back (turn=reviewer state=done) — no
  false 'stopped'"*; signal **SKIPPED**; `/status` stayed `turn=reviewer`/`state=done` with the
  child's original message. The stderr tail was still captured to the log (diagnosable even on skip).
  **PASS** — a successful `done` is never stomped.
- **Happy path** (hand_back `done`, exit 0): exit-0 branch, no signal, review stays `done`. **PASS.**
- Full `print()`→`logging` migration confirmed: `grep "print("` on `watch.py` returns **zero** hits
  (all ~15 sites migrated, message strings preserved minus the now-redundant `watch.py:` literal moved
  into the formatter). `WATCH_LOG_FILE`/`--verbose` documented in both the README runbook and the
  module docstring Config block.
- stderr capture uses `tempfile.TemporaryFile` (a real OS file), so a chatty multi-minute child can
  never deadlock on a full 64KB PIPE buffer. `_read_errtail(proc)` is called on **every** reap
  (exit-0 and non-zero) and closes the temp file in its `finally` — **no fd leak on the exit-0 path**
  (confirmed by the clean happy-path reap). The re-check and POST are best-effort: a failed `/status`
  read or non-200 handoff logs and returns, never crashing the reap loop.

**Finding F1 (worth-fixing, non-blocking): the structured crash record omits the resolved argv.**
Both the MR-067 AC and the epic plan say the non-zero-exit record carries "review id, exit code, **the
resolved argv**, and the captured stderr tail." The emitted record carries rid + exit code + stderr
tail, but **not** the argv. Impact is low — the argv is a module constant the operator can read from
`WATCH_LAUNCH_CMD`, and diagnosability (the headline goal) is satisfied without it — but the AC
explicitly lists it and it is absent. Add the resolved `_launch_argv()` to the crash `log.warning`
(or drop the clause from the AC). Does not block the gate.

All other MR-067 ACs met. **PASS.**

## MR-068 — render the "agent run stopped" crash signal (viewer) — **PASS**

End-to-end: the review left `blocked` by the MR-067 crash run (a **real** watcher-emitted signal,
not a hand-posted fixture) was loaded in the viewer.

| Case | classList | text | animationName |
|---|---|---|---|
| crash signal / light | `turnbanner show warn` | "Agent run stopped: agent process exited 1 without finishing. Your turn." | `none` |
| crash signal / dark | `turnbanner show warn` | same | `none` |
| crash signal / reduced-motion | `turnbanner show warn` | same | `none` |
| no-regression: agent question | `turnbanner show` (**no** warn/loading) | "Agent needs you: Do you mean X or Y here?." | `none` |
| no-regression: done | `turnbanner show` (**no** warn) | "Agent updated the draft: tightened intro. Your turn." | `none` |

- Crash-vs-question discrimination (`as.message.indexOf('agent process exited')===0`) works: the
  crash signal gets `.warn` + "Agent run stopped…", a deliberate question stays "Agent needs you…"
  with no warn, and `done` is untouched. Copy correctly says "Your turn" (the watcher's hand_back
  already flipped the turn to the reviewer) so `send` is enabled and reclaim is hidden, as expected.
- Screenshots: `g7-mr068-crash-{light,dark}.png` (amber `.warn` "Agent run stopped" banner, both mats).

All MR-068 ACs met. **PASS.**

---

## Findings

- **F1 (worth-fixing):** MR-067 crash record omits the **resolved argv** that the AC/plan name. Low
  impact (recoverable from env; diagnosability intact). Add the argv to the crash log line or amend
  the AC. See MR-067 above.
- **F2 (nit, pre-existing):** the deliberate-question banner reads "Agent needs you: Do you mean X or
  Y here?**.**" — a double terminal punctuation (`?.`) from the original blocked arm's unconditional
  trailing period. Untouched by this cycle and cosmetic; fix opportunistically.
- **F3 (nit, accepted):** crash-vs-question keys on the message **prefix** `agent process exited`. An
  agent that authors a question whose message *starts with* that exact string would render as a crash.
  Low stakes — the agent controls its own message text and has no reason to spoof the watcher's fixed
  phrase; the watcher's reason is the only producer of that prefix in practice. Note, do not fix.
- **F4 (accepted risk, not introduced here):** the server's blocked hand-back arm (`app.py:623-629`)
  is **unconditional** — it ignores turn/owner/lease and always writes `blocked`. So the watcher's
  client-side `/status` re-check in `_signal_crash` is the *sole* guard against stomping a `done`, and
  there is a (tiny, single-watcher) TOCTOU window between its GET and POST in which a human reclaim or
  a late child hand_back could be overwritten by a false "stopped." This is inherent to the plan's
  "no `app.py` change" decision and is the safe direction (a missed signal self-heals via the 180s
  stale banner + the MR-066 pickup cue; a rare false "stopped" only offers "Take back the turn," which
  is non-destructive). Acceptable for v1. **Revisit trigger:** if a server-side guard is ever added to
  the blocked arm, or if multi-watcher contention on one review becomes real, close the window
  server-side. Not blocking.

## Scope check (the plan promised none of these)

Clean. The three commits touch **only** `viewer.html`, `watch.py`, `README.md` — no `app.py`, no new
`meta.json` key, no Dockerfile/compose, no auto-relaunch (the "retry" call sites are all
capacity-deferral, B1 intact), no #27 progress/streaming. No out-of-scope creep.

## Verdict

**G7 PASS.** All three tickets meet their acceptance criteria on an independent container re-drive,
including the conflation guard (the load-bearing check) end-to-end. The headline live bug ("Send to
agent" with no watcher → ~20-minute silent spin) is fixed by MR-066 alone; the crash-surfacing chain
(MR-067 → MR-068) is proven watcher→service→viewer. The cycle ships. F1 (missing argv in the crash
record) is worth folding into a quick follow-up but does not block.

## Finding resolution (post-review, orchestrator)

- **F1 (worth-fixing) — RESOLVED 2026-06-24** (commit on dev): the crash `log.warning` in `_reap` now
  carries the resolved argv (`proc._argv`, captured at spawn), completing the structured record the AC
  names (review id, exit code, **argv**, stderr tail). Re-smoked: the crash record reads
  `… exited 1 (…); argv=['bash', '…/crash.sh']`. AC satisfied.
- **F2 (pre-existing nit)** — the question banner's `"…here?."` double period predates this cycle
  (original blocked arm) and is out of scope; left for a separate cosmetic pass.
- **F3 (accepted nit)** — crash-vs-question message-prefix keying; low stakes, no change.
- **F4 (accepted risk)** — the server blocked-handback arm is unconditional, so the watcher's
  client-side `/status` re-check is the sole guard (tiny single-watcher TOCTOU window). Inherent to the
  pinned "no app.py change" decision and the safe direction; revisit only if a server-side guard or
  multi-watcher contention becomes real.
