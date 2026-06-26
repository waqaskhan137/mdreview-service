---
review_of: sprint-26
gate: G7
reviewer: staff-critic
independent: true
verdict: PASS
date: 2026-06-24
---

# Sprint-26 close review (G7) — viewer-transparency epic (#27)

Independent gate. I re-drove the agent-turn lifecycle against a **rebuilt throwaway container**
(`mdreview-sprint26-gate` on scratch port **8186**, throwaway `MDREVIEW_DATA` under `.scratch/`),
**never** the live `:8139`. The container/image/data were torn down after the run. Drive method:
a node-CDP driver (the `agent_smoke.py:112-148` built-in-`WebSocket` pattern) that opens
`/review/{id}` in headless Chrome and walks the lifecycle by POSTing the real
`/handoff` / `/source` / `/comments` endpoints between CDP DOM reads, asserting the live DOM —
`viewer.html` is JS-rendered and signal-sequenced, so `render-smoke.sh` cannot prove it.

Evidence (drivers + captured runs + both-pane screenshots): `reviews/sprint-26-render-evidence-2026-06-24/`.

## Verdict: **G7 PASS — ships.**

Every AC of MR-073 and MR-075 verified against a re-driven viewer. No blocking findings. The
signal-honesty contract (the load-bearing correctness claim — "Resolved" never appears on a
reply-then-blocked turn) holds under a live drive, as do the baseline guard, the new-turn reset,
the fetch-free single-instance timer, the reopen-after-done duration guard, XSS safety, and full
no-regression of MR-062/066/067/068. Both panes and both reduced-motion settings render correctly.

---

## MR-073 — live progress timeline + elapsed/duration timer — **PASS**

| AC | Result | CDP evidence |
|----|--------|--------------|
| Derived timeline (Connected → Editing → Updating comments → Done), no new endpoint/field | **PASS** | A1: `#turnbanner` gains `steps`; steps = [Connected **active**, Editing pending, Updating pending] off `/status` only. Diff confirms no `app.py` change. |
| Cumulative, baselined against `turn_updated`; stale prior-round signal must NOT light a step | **PASS** | A1: first claim shows Editing/Updating **pending** (creation `source_updated` < `turn_updated`). **I-stale-edit**: after a full round-1 edit+comment+done, a fresh round-2 claim shows `["active","",""]` — the round-1 high `source_updated`/`comments_updated` do **not** re-light Editing/Updating on the new turn (new `turn_updated` exceeds them). New-turn reset (`tu!==_turnId`) verified. |
| Signal-honest labels: "Updating comments" off the generic bump; "Resolved" only on terminal `done`; a reply-then-`blocked` turn must NEVER claim "resolved" | **PASS** | **B** (reply-then-blocked): comment step reaches via `comments_updated` (reply bumps it), but the word **"Resolved" never appears** in the banner while working **or** after `blocked`; banner is "Agent needs you" (not a crash, `.warn` absent). A5: relabel to "Resolved comments" appears **only** on `done`. |
| Live timer `now - turn_updated`, ticking ~1s via a single fetch-free interval, no-op outside working | **PASS** | A1 timer `M:SS`. **A2**: with **no** POST/`/status` feed, timer advanced `0:02 → 0:04` (proves the fetch-free clock). **H-ticker**: a second turn on the same page advances single-rate (delta 3s over ~2.1s, no double interval — the `if(_timerIv)return` guard holds); the interval no-ops when `turn!=='agent'`. |
| Final duration "Agent revised in M:SS" client-captured; a page loaded AFTER done shows none | **PASS** | A5: "Agent revised in 0:09" on done. **C** (fresh page load after a done with no page open during the turn): done banner shows, **no** "revised in" duration (`_turnStartAt` null → documented limitation honoured, never a wrong number). |
| No regression of MR-062/066/067/068 | **PASS** | **D1** crash: "Agent run stopped: agent process exited 1…" + `.warn`, not `steps` (MR-068). **D2** parked pre-grace: "Sent — waiting for an agent" + `loading` spinner, `steps`/timer cleared (MR-062). **E/F** `>PICKUP_GRACE_S`: "No agent has picked this up" `.warn` (MR-066); stale lease (`as.at` past `STALE_S`): "Agent may have stopped" `.warn`, not `steps` (MR-066). All arms still fire; the timeline **wraps**, not replaces. |
| `agent_status.message` set via `textContent` (no HTML injection) | **PASS** | **G**: a `<img onerror=...><b>` payload via `hand_back message` renders as **literal text**; `window.__XSS` false, 0 injected `<img>/<b>` in the banner. `msg` reaches the DOM only via `tt.textContent` (line 353). |
| Reduced-motion respected; spin only on the active step | **PASS** | **E** (reduce on): active step `::before` computed `animationName === 'none'`. **F** (motion on): `=== 'turnspin'` (liveness). Computed style, not screenshot, per the hidden-tab memo. |
| Local validation | **PASS** | `python3 -m py_compile app.py watch.py` OK. |
| Both panes legible | **PASS** | `preferredColorScheme=1`/`=0` (never `--force-dark-mode`): timer + step colors resolve in each (dark: `rgb(241,239,236)` on the neutral mat; light: `rgb(26,26,26)`). Screenshots `timeline-working-{light,dark}.png` confirm the dot/spinner/hollow-circle states read in both. |

### Diff scrutiny (the things the ticket flagged)

- **Steps class never leaks onto a non-working banner.** `renderBanner` clears `'loading','warn','steps'`
  and empties `#turnsteps`/`#turntimer` at the top of every call (lines 296-297); only two arms re-add
  `steps` (working; done-with-captured-start). Verified by D1/D2/E/F all showing no `steps`.
- **Cumulative/baseline + new-turn reset are sound** (I-stale-edit, above). The guard is `source_updated
  > turn_updated`, and `create_review` sets `source_updated=now` at creation (< the later flip's
  `turn_updated`), so Editing never false-fires on first claim.
- **1s interval is single-instance, fetch-free, no-leak, no-op outside working** (A2, H). It is never
  `clearInterval`'d, but the body guards on `turn==='agent' && agent_status`, so the one interval idles
  harmlessly when not working and does **not** clobber the final "revised in" text (H: preserved across
  3 tick cycles). Acceptable — see nit N1.
- **XSS-safe** (G).

## MR-075 — docs sweep — **PASS**

`CLAUDE.md` turn-baton section (lines 113-120) documents: the derived live timeline (Connected →
Editing → Updating comments → Done), the ticking timer + "Agent revised in M:SS", that it is
**derived from existing `/status` signals** (agent does nothing extra), the **client-captured**
final-duration limitation (a page opened after finish shows no duration), and the **deferred**
per-tool-call stream (step-level only). No stale "static/opaque banner" claim remains. `py_compile`
OK. All four content ACs satisfied by grep + read.

---

## Findings

### Blocking
None.

### Worth fixing (non-blocking; do not gate the ship)
- **W1 — "elapsed" counts from Send, not from claim.** `_turnStartAt = turn_updated`, and a lease
  claim (`state==working`) does **not** bump `turn_updated` (`app.py:638`). So the live timer and the
  final "revised in" include any pickup lag (time the review sat parked before an agent claimed it).
  For a watcher-driven flow that lag is seconds; for a parked-then-late-pickup it overstates the agent's
  work. The ticket spec literally says `now - turn_updated`, so this is *as-specified*, but the label
  "Agent revised in M:SS" reads as agent work time, not wall-clock-since-Send. Either relabel (e.g.
  "Turn took M:SS") or baseline the timer on `agent_status.at` of the first working observation. Author's
  call — flagging the semantic mismatch, not asserting a defect.

### Nits
- **N1 — the ticker interval is never cleared.** One `setInterval` is created on first working render
  and lives for the page lifetime. It is correctly idempotent (`if(_timerIv)return`) and no-ops off the
  working state, so it neither leaks multiples nor clobbers (verified H). Leaving it is fine; if you
  ever want it tidy, `clearInterval` it when leaving the working arm. Pure preference.
- **N2 — `else if` source/comments branch in `poll()`** (`viewer.html:761-762`): if a single 2s poll
  lands both a `source_updated` and a `comments_updated` change, only the source branch runs that tick
  (the comment re-render waits one more tick). Pre-existing, unrelated to MR-073, and the *timeline*
  is unaffected (`renderBanner(s)` runs every tick regardless). Noting only because the diff touches
  this function's neighbourhood.

## What's good (load-bearing)
The signal-honesty design is the right call and it holds under drive: keying the comment step off the
generic `comments_updated` bump but gating the word "Resolved" on terminal `done` means a
reply-then-blocked turn cannot lie — which was the one place this feature could have eroded trust. The
baseline-against-`turn_updated` guard correctly prevents a prior round's stale edit from lighting the
new turn, and the client-capture limitation is handled honestly (no number rather than a wrong one).

## Teardown / hygiene
Throwaway container `mdreview-s26` (:8186), image `mdreview-sprint26-gate`, and `.scratch/s26-data`
all removed. Live `mdreview` (:8139) and `mdreview-watcher` were never touched. CDP drivers and run
logs preserved under `reviews/sprint-26-render-evidence-2026-06-24/`.

**G7 PASS.**

## Finding resolution (post-review, orchestrator)

- **W1 (worth-fixing) — RESOLVED 2026-06-24** (commit on dev): the timer now baselines on the **agent
  claim** (the first observed working `agent_status.at` this turn), not the Send time (`turn_updated`),
  so "Agent revised in M:SS" is the agent's work time, not work + pickup lag. Verified with a 6s
  simulated pickup lag: the timer tracked time-since-claim (~36s), not since-Send (~42s). This matches
  the owner's intent ("how much time it takes the agent to revise").
- **N1 (nit) — accepted:** the 1s `setInterval` is not `clearInterval`'d; verified idempotent + no-op
  off the working state — harmless.
- **N2 (nit) — accepted:** the pre-existing same-tick comment-render `else if` in `poll()` is unrelated
  to MR-073; the timeline is unaffected.
