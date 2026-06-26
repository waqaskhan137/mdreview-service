---
review_of: epics/history-version-fix-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 independent review — history-version-fix plan

**Verdict: PASS-WITH-NITS.** The design is sound and reconciles correctly; the Defect-B
removal is safe and breaks no programmatic reader. Two things must be fixed before MR-065 can
close (not before the tickets spawn): (1) the render-smoke recipe as written cannot open the
modal — and this repo has already *proven* that gap once (sprint-07) — so the ticket's core
assertion is unverifiable with the named tool; (2) README.md:55 documents the per-round
`{round, ts, notes_total, notes_addressed}` shape the plan removes, and the plan asserts "no
documented field is touched" — that assertion is wrong and the doc must be updated. Neither
sinks the design; both are scoped to MR-065's AC and the doc sweep. Everything verifiable
against code checked out.

## Consumer analysis (the load-bearing check) — CONFIRMED

There are **two distinct `notes_total`**, and the plan correctly separates them:

1. **`summary()` per-review total** (`app.py:160-161`), comment-aware, read by
   `dashboard.html:112` via `noteLabel(r)` — uses `r.notes_total||0` (default-safe).
   **Untouched** by this plan. Good.
2. **`snapshot_round()` per-round count** (`app.py:199-200`) written into `round.json`, read
   by exactly one consumer: `viewer.html:679` (the history-list label), via bare
   `r.notes_total` (NO default — string-concatenated directly).

I grepped every consumer (`grep -rn notes_total app.py *.html mcp_server.py docs/`). The
per-round `round.json` count has **only** the `viewer.html:679` consumer the plan names.
`mcp_server.py get_history` (`:410-413`) is a pure passthrough of `/history` and reads no
field — dropping the keys breaks nothing in MCP. `/history` (`app.py:684-688`) appends whole
`round.json` dicts; `/history/{n}` (`app.py:698`) spreads `round.json` then adds source body
— neither indexes `notes_total`, so **no KeyError risk** in the service. Confirmed: removal is
safe and complete at the code level.

## Findings

### [blocking] MR-065's render-smoke cannot open the modal — and the repo has already proven this exact gap
`scripts/render-smoke.sh` does a single `--dump-dom` after a virtual-time budget. It **cannot
click and cannot eval** (I read the whole script — no `--run-before`, no CDP eval, no
query-param support). The History modal is `display:none` and `#histbody` is an **empty static
div** (`viewer.html:199`); `.histitem`/`.histdoc`/`.histlist` exist only after `openHistory()`
runs on a `#histbtn` click (`viewer.html:692`). So the plan's recipe
`render-smoke.sh "$BASE/review/$id" '#histbody' '.histitem' '.histdoc'`:
- `#histbody` **false-passes** (it's in the served HTML whether or not the modal ever opens),
- `.histitem` and `.histdoc` **always match 0 → exit 1**, even for a perfectly correct build.

This is not speculative. `reviews/sprint-07-close-review-2026-06-18.md:39-41,86-88` records a
prior critic's CDP attempt to open *this same modal* failing: "the headless-command target
would not execute page JS in scope, so I could not capture the modal shot." For MR-027 that
modal assertion was *cosmetic* and was waived. For MR-065 the modal DOM — the `current (vN)`
label reconciling with the badge, and the **absence** of "0 notes"/"notes that round" — **is
the entire deliverable** and cannot be waived.

The plan gestures at this ("if the smoke harness cannot click... see ticket AC for the exact
open mechanism") but pins nothing. **Pin a concrete, demonstrated mechanism in MR-065's AC
before it can prove its render.** Viable options, in order of least new surface:
- A headless-Chrome **CDP/`Runtime.evaluate`** script (or `chrome --headless` with a small
  driver) that loads the page, calls `openHistory()`, waits, then serializes — the prior CDP
  attempt failed; whoever writes the AC must show it actually works here, not assume it.
- A **`?history=1` (or `#history`) auto-open hook** added to `viewer.html` (a few lines reading
  `location.search`/`hash` and calling `openHistory()`), then `render-smoke.sh` against that
  URL. This is the cleanest fit for the existing tool but adds viewer code — call it out, it's
  not free.
- A negative-assertion fallback for Defect B (grep the *served `viewer.html`* for the absence
  of the `+r.notes_total+' notes'` template) is **not** a render proof and must not be the only
  evidence — the whole point of render-smoke is that source-grep false-passes.

Until one of these is demonstrated, MR-065 has no working acceptance test for its primary
behavior.

### [worth-considering] README.md:55 documents the field the plan removes — the "no documented field" claim is wrong
The plan (Defect-B decision, Risks table) asserts removal touches no documented contract. It
does: `README.md:55` lists `/history` as returning `{round, ts, notes_total, notes_addressed}`,
and `README.md:56` says `/history/{n}` returns `{..., ...round meta}`. AGENTS.md/CLAUDE.md only
document the *`summary()`* `notes_total` (the dashboard one, unchanged), so those are fine — but
README.md:55 is specifically the per-round shape being dropped. No programmatic reader breaks,
but the doc now lies. **MR-064's AC should update README.md:55** to `{round, ts}` (and note the
historical keys are inert on old rounds). Small, but the plan's correctness rests on having
swept consumers, and this is one it missed.

### [worth-considering] `openHistory` early-returns on empty rounds (`viewer.html:678`) — the revision-0 current-draft entry will be skipped unless that branch moves
Q2 says a never-PUT review should still show `current (v0)`. But `openHistory` at
`viewer.html:678` `return`s with "No earlier versions yet" **before** rendering any entry when
`rounds.length===0`. The plan's "prepend a synthetic top entry" must be placed **before** that
early return, or every revision-0 review shows no current entry at all (the opposite of Q2's
intent). The fix is trivial, but the early-return line is a concrete landmine the MR-065 AC
should name explicitly, not leave to "prepend." Also reconcile the Q2 ambiguity: dashboard
**hides** the badge when `revision==0` (`dashboard.html:127`), so `current (v0)` in the modal
*disagrees* with a badge-less card. Either is defensible; pin one in the AC so the
"badge == top entry" smoke assertion isn't self-contradicting at v0.

### [nit] `showRound`'s reconciliation arithmetic is right, but pin the test at N>=2
The off-by-one derivation (current = `revision` = vN; `round-k` = the draft that was vk;
archived rows vN-1..v0) checks out against `snapshot_round` (`app.py:189` archives `round-n`
then `:202` bumps to `n+1`). The shared fixture uses 2 PUTs → revision=2, round-0/round-1, top
`current (v2)`, archived v1, v0 — a good discriminating case (a 1-PUT review can't distinguish
vN from vN-1 labeling). Keep the fixture at >=2 PUTs; it's correct as written.

### [nit] svc/ui split and `depends_on` are right; don't fold
MR-064 (two-dict-key removal in `snapshot_round`) is tiny, but folding it into the ui ticket
would mix a curl-validated service change with a render-validated UI change under one AC, and
the plan's own "UI must not show a count the service still emits" ordering is the correct
reason MR-065 `depends_on` MR-064. The split is justified; leave it. #19 (version-picker/diff)
is not painted into a corner — it needs trustworthy labels (delivered), not per-round counts.

## What's good (load-bearing)
- The consumer separation (per-review `summary()` total vs per-round `round.json` count) is the
  one thing that had to be right for "remove the count" to be safe, and the plan got it exactly
  right — the only per-round consumer is `viewer.html:679`, confirmed by grep.
- "Reconcile by *including* the current draft, not renumbering `round-n`" correctly preserves
  the `/history/{n}` path key — renumbering would have been the tempting wrong move.
- The remove-don't-fake decision for Defect B is correctly forced (comments never per-round
  snapshotted; retroactive count is genuinely impossible, would show 0), not a shortcut.

## Resolution log

- **2026-06-24 — Independent G1 review filed (verdict PASS-WITH-NITS).** Design reconciles;
  Defect-B removal verified safe (only `viewer.html:679` reads the per-round count; MCP
  get_history is passthrough; no KeyError — `/history` and `/history/{n}` never index the key).
  One blocking item (render-smoke cannot open the modal; repo proved this in sprint-07 — pin a
  working open mechanism in MR-065 AC) and two worth-considering (README.md:55 documents the
  removed per-round shape; `openHistory` early-return at viewer.html:678 will skip the
  revision-0 current entry). None blocks spawning MR-064/MR-065; all are AC-scoped for MR-065
  (+ a README line for MR-064). Awaiting author.

## Resolution log

- 2026-06-24 — Independent G1 review (#18, two defects). Verdict PASS-WITH-NITS; design sound, Defect-B
  removal verified safe (per-round `notes_total` has exactly one consumer — `viewer.html:679`; MCP
  get_history is a passthrough; no KeyError). One blocking-for-verification gap (render-smoke can't open
  the click-populated History modal — the repo hit this in sprint-07) + 2 worth-considering (README
  `/history` shape; v0/empty-rounds self-contradiction) + nits.
- 2026-06-24 — Planner revised (author preserved). Folded: **(blocking)** MR-065's modal-DOM test is now
  a **node-CDP eval driver** (the proven `agent_smoke.py` WebSocket/Runtime.evaluate pattern) that calls
  `openHistory()`, polls until `.histitem` populates, then asserts the `current (v2)` top entry == the
  dashboard badge, archived `v1`/`v0` newest-first, NO "notes" text, and the current-entry click yields
  `.histdoc`; bare `render-smoke.sh` against modal selectors is explicitly forbidden (false-fail
  explained), `?history=1` auto-open kept as fallback-only. **(wc)** README:55 `/history` shape update
  (`{round, ts}`, dropping `notes_total`/`notes_addressed`) added to MR-064's scope + a grep assertion;
  corrected the "no documented field" claim. **(wc)** v0 edge pinned option (b): the current-draft top
  entry always renders (relocate the `viewer.html:678` early-return), plain `current` (no `(v0)`) at
  revision 0 to match the dashboard hiding its badge below v1. No second G1 round needed. **G1 PASS.**
