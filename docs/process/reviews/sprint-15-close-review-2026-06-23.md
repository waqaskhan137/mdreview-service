---
review_of: sprints/sprint-15.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: PASS
status: resolved
---

# Sprint-15 close review (G7) — agent-handoff-baton Chunk 2 (MR-052 viewer turn UI)

Independent G7 gate. Reviewer is not the implementer. Verifies the shipped MR-052 change
(`viewer.html`, commit `1f6a71c`) against each acceptance criterion, runs an independent
render-smoke + per-state banner drive on a throwaway instance, the container/healthz/list
smoke, and confirms the screenshot evidence is genuine.

**Verdict: PASS.** Sprint-15 closes. All seven ACs are met in the shipped code and independently
re-verified end to end. Three NITs, none blocking — recorded for a future touch, not gating.

## What was verified

Method note: `app.py:710` serves `viewer.html` from disk on every `GET /review/{id}`, so a
from-disk `python3 app.py` run serves the exact shipped `viewer.html` — equivalent to a rebuild
for a JS/HTML change. I ran a throwaway instance via
`MDREVIEW_DATA=$(mktemp -d) PORT=8155 python3 app.py` (port 8155 confirmed free with
`lsof -iTCP:8155 -sTCP:LISTEN` first; never 8137/8139). Scope (commit `1f6a71c`): `viewer.html`
+ ticket + evidence only — no `app.py`, no `mcp_server.py`, no `dashboard.html`, no `static/`,
no new served file.

### AC1 — Send button (turn-gated) — PASS
`.btn.primary.sendagent#sendbtn` added to `#dockbar` (`viewer.html:181`). `renderBanner`
sets `send.disabled=true` + relabels "Sent — agent's turn" on `turn==='agent'` and
`send.disabled=false` + "Send to agent" on a reviewer turn (`viewer.html:237,244`). The onclick
optimistically disables, POSTs `/handoff {to:'agent'}`, then re-renders from a fresh `/status`
(`viewer.html:249-254`). Independently observed: in an agent turn the rendered button is
`disabled` and reads "Sent — agent's turn"; re-enabled after reclaim (smoke transcript c/).

### AC2 — 6-state first-match banner, no row shadowing — PASS
`renderBanner` (`viewer.html:226-248`) branches on `turn==='agent'` first (rows 1/2/3 keyed on
`agent_status` presence then staleness), else on `agent_status.state` (`done`→4, `blocked`→5,
otherwise→6). Agent rows and reviewer rows are on opposite sides of the top-level `if`, so no row
can shadow another. **Independently drove all 6 rows via curl + fresh `--dump-dom` page loads and
read `#turntext`; every message matches the ticket text** (see transcript). Row 3 was forced by
backdating `agent_status.at` 600s in `meta.json` (a real fresh-load render, stronger than the
implementer's inspection-only claim).

### AC3 — reclaim "Take back the turn" — PASS
`.btn.reclaim#reclaimbtn` (`viewer.html:167`); shown (`display=''`) only on `turn==='agent'`,
hidden (`display='none'`) on a reviewer turn (`viewer.html:236,243`); onclick POSTs
`/handoff {to:'reviewer',by:'reviewer'}` (`viewer.html:255-258`). Observed visible in the agent
state, hidden after reclaim.

### AC4 — poll: lastTurn + ordering rule + first-paint — PASS (functionally; see NIT-1)
`lastTurn` declared (`:214`). First-paint banner set in `load()` from the same `/status` body
(`:372`). In the poll, the source-change branch runs `await load()` first (`:654`), then
`renderBanner(s)` runs from the **same** `/status` body **after** it (`:660`) — so the
"Draft updated by AI" toast and the banner do not race. Independently confirmed in the done
hand-back + `PUT /source` path: the doc reloaded to the revised source and the banner showed row
4, not clobbered (validation.txt d/; reproduced via the row-4 drive). The banner renders every
tick rather than via an `s.turn !== lastTurn` guard — see NIT-1; functionally correct and in fact
better for the stale row.

### AC5 — staleness uses agent_status.at as epoch seconds — PASS
`STALE_S=180`; check is `(Date.now()/1000-(as.at||0))>STALE_S` (`viewer.html:220,234`).
Server stamps `agent_status.at = time.time()` (epoch seconds, `app.py:548,564`), so the units
match — the sprint-14 NIT is correctly carried and closed. Confirmed live: a 600s-old `at`
rendered row 3.

### AC6 — agent message via textContent (no innerHTML injection) — PASS
Message is concatenated into `msg` and assigned with `tt.textContent=msg` (`viewer.html:240-246`).
**Independently probed** with a `done` message `<img src=x onerror=window.__XSS__=1><b>bold</b>`:
the dumped DOM shows `&lt;img ...` (escaped text), no live `<img>`/`<b>`, no script execution.
Correct for a no-auth control surface.

### AC7 — scope: viewer.html only — PASS
`git show 1f6a71c --name-only` = `viewer.html`, the ticket, and the three evidence files. No
`app.py`/MCP/`dashboard.html`/`static/`/new-file change; no Non-goal leak.

### Render-smoke + container/healthz/list smoke — PASS
`scripts/render-smoke.sh "$B/review/$ID" .sendagent .turnbanner .reclaim` → exit 0, 1 node each.
`GET /healthz` → `{"ok": true}`. `GET /api/reviews` → 200, review listed with `turn` surfaced.

### Screenshot evidence — genuine
Opened both PNGs under `reviews/sprint-15-render-evidence-2026-06-23/`. `reviewer-fresh.png`
shows row 6 ("Your turn…"), Send enabled/green, no reclaim. `agent-working.png` shows row 2
("Agent is working on your feedback…"), "Take back the turn" visible, Send disabled/greyed
"Sent — agent's turn". Both match the claimed states.

## Findings

- **NIT-1 (AC4 literal divergence) — `lastTurn` is write-only / dead.** The AC said "add an
  `s.turn !== lastTurn` branch to the poll's if/else chain." The implementer instead renders the
  banner unconditionally every tick (`viewer.html:660`) and never reads `lastTurn` (set at
  `:252,:256,:372,:661`, read nowhere). This is functionally correct and **better for the stale
  row** — a guarded `s.turn !== lastTurn` branch would not re-render as `at` ages past 180s,
  whereas the unconditional render does. But it leaves `lastTurn` as misleading unused state.
  Either delete `lastTurn` (and update the ticket/Work-log wording, which still describes the
  branch) or use it. Not blocking.

- **NIT-2 (narrow Send re-enable flicker).** The poll's unconditional `renderBanner(s)` writes
  `send.disabled` from raw `/status`. If a 2s tick fires in the sub-200ms window after the onclick
  optimistically disables Send but before the server flip lands, that tick sees `turn=reviewer`
  and briefly re-enables the button; the next tick re-disables it. Self-correcting, cosmetic, not
  a control-flow defect (the server is the source of truth and the flip is guarded under `_lock`).
  Not blocking. If ever touched, gate the poll's banner render behind the in-flight-Send state the
  way `:651` gates on `confirming`.

- **NIT-3 (cosmetic text casing).** Row-3 text is "Agent may have stopped — take back the turn?"
  (`viewer.html:234`); the ticket/epic write "Take back the turn?" (capital T). Cosmetic; the
  other five rows match verbatim. Not blocking.

## Smoke transcript

Throwaway instance: `MDREVIEW_DATA=$(mktemp -d) PORT=8155 python3 app.py` (8155 confirmed free).
`B=http://localhost:8155`. Per-state `#turntext` read from a fresh headless
`--dump-dom --virtual-time-budget=4000` load after each curl (renderBanner runs on load from
`/status`).

```
# render-smoke (rebuilt-from-disk viewer.html)
$ bash scripts/render-smoke.sh "$B/review/$ID" .sendagent .turnbanner .reclaim
  ok : .sendagent (1 node)
  ok : .turnbanner (1 node)
  ok : .reclaim (1 node)
  exit=0

# Banner rows — observed #turntext per server state:
ROW 6  (fresh; turn=reviewer, no agent_status)
       #turntext = 'Your turn. Comment, then Send to agent.'
ROW 1  (POST /handoff {to:agent}; agent_status absent)
       #turntext = 'Sent — waiting for an agent to pick this up.'
ROW 2  (POST /handoff {state:working,owner:sess-X,message:on it})
       #turntext = 'Agent is working on your feedback…'
ROW 3  (turn=agent, agent_status.at backdated now-600s in meta.json)
       status: turn=agent at_age_s=600
       #turntext = 'Agent may have stopped — take back the turn?'
ROW 4  ({to:agent} then {to:reviewer,state:done,message:m})
       #turntext = 'Agent updated the draft: m. Your turn.'
ROW 5  ({to:agent} then {to:reviewer,state:blocked,message:q})
       #turntext = 'Agent needs you: q.'

# Button states (agent turn): sendbtn disabled + 'Sent — agent's turn'; reclaimbtn present.
# Reviewer turn: sendbtn enabled 'Send to agent'; reclaimbtn display:none.

# XSS probe ({to:reviewer,state:done,message:'<img src=x onerror=window.__XSS__=1><b>bold</b>'}):
       turntext inner = 'Agent updated the draft: &lt;img src=x onerror=window.__XSS__=1&gt;&lt;b&gt;bold&lt;/b&gt;. Your turn.'
       live <img: False   escaped &lt;img: True   -> textContent, no injection

# Service smokes:
$ curl -s $B/healthz            -> {"ok": true}
$ curl -s $B/api/reviews        -> 200; count=1; turns=['reviewer']

# Teardown: kill listener on 8155; port freed; temp data dir removed.
```

## Resolution log

- 2026-06-23 — Independent G7 review complete. All 7 ACs PASS; render-smoke exit 0; all 6 banner
  rows independently driven and matched to ticket text (row 3 forced via backdated `at`); XSS
  textContent check passed; healthz + /api/reviews respond; both screenshots confirmed genuine;
  scope is `viewer.html`-only. Three NITs (write-only `lastTurn`; narrow Send-reenable flicker;
  row-3 casing) recorded, none blocking. **Verdict PASS, no open blockers — status: resolved.**
  Sprint-15 may move to `closed` (set `close_review:` and record the retro in the sprint file).
- 2026-06-23 — Implementer addressed the NITs post-review (not gate conditions): **NIT-1** removed
  the write-only `lastTurn` var; **NIT-3** capitalized "Take back the turn?" in the stale row;
  **NIT-2** (sub-200ms Send re-enable flicker) accepted as cosmetic/self-correcting. Re-validated:
  render-smoke 3/3 + row-6/row-2 `--dump-dom`, no regression. Verdict unchanged (PASS). Sprint
  closed.
