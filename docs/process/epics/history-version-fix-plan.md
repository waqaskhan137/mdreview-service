---
epic: history-version-fix
status: done           # shipped: MR-064 + MR-065 (sprint-23), G7 PASS 2026-06-24 (closes #18)
created: 2026-06-24
source: requirements/history-version-fix.md   # GH issue #18, groomed + staff-critic reviewed
gate: passed 2026-06-24    # tickets blocked until passed
review: reviews/history-version-fix-plan-review-2026-06-24.md
related_sprints: [sprint-23]
related_tickets: [MR-064, MR-065]
---

# History version-fix Plan

The document History modal mislabels versions and lies about per-round feedback counts. It
advertises a dashboard badge of `vN` while the History list tops out at `v(N-1)`, never shows the
current live draft the human is reading, and stamps every entry "0 notes" because it counts the
retired `notes.json` store instead of the live comments. This epic reconciles the version labels,
surfaces the current draft in the list, and removes the untruthful count — all with the least
machinery, no new endpoint, and no new persisted `meta.json` key. Closes GH #18.

**Source requirement:** [`requirements/history-version-fix.md`](../requirements/history-version-fix.md) —
the verbatim brief (GH #18, groomed).

## Product goal

A human opening the History modal sees a list whose version numbers match the dashboard badge,
where the entry they are currently reading is clearly the top "current (vN)" row, and where no
entry shows a fabricated feedback count. The off-by-one and the "0 notes" lie are both gone.

## Core design principle

**Reuse what already serves the truth; do not invent state.** The dashboard's `v{revision}` badge
is the true count of agent PUTs and is the source of truth — leave it. The current draft is already
served by `GET /api/reviews/{id}/source` (the viewer already fetches it, `viewer.html:376`); the
History modal renders it as the top entry rather than reaching for a new endpoint or persisted key.
The per-round comment count cannot be made truthful for any existing round, so it is **removed**,
not faked. Every change is additive and default-safe: an old round with no comment data, and an
old client, both degrade to today's behavior minus the lie.

## The two defects, grounded in current code

| Defect | Root cause (verified) | Fix |
|--------|-----------------------|-----|
| **A — labels don't reconcile; current draft unlisted** | `snapshot_round` archives the current revision `n` into `round-n` then bumps `revision=n+1` (`app.py:190`, `:202`); `summary()` defaults `revision` to `0` (`app.py:162`). After N PUTs: `revision==N`, history holds `round-0…round-(N-1)`. Dashboard shows `v${r.revision}`=**vN** (`dashboard.html:127`); History newest entry shows `v(N-1)` (`viewer.html:679`) and the live draft (revision N) is in no round. | History lists the **current draft** (from `GET /source`) as the top entry **"current (v{N})"**, archived rounds below as **"v{round} · earlier draft"**. Top of list now reads vN, matching the badge. |
| **B — every entry "0 notes"** | `snapshot_round` writes `round.json` `notes_total`/`notes_addressed` from the legacy `notes.json` (`app.py:196-200`), retired since MR-036; the viewer authors `comments.json`, which `snapshot_round` never copies (`app.py:192` copies only `source.md`/`feedback.md`/`notes.json`). So `notes_total==0` for every comments-era round. The modal renders it verbatim (`viewer.html:679`) and `showRound` renders `d.notes` (always empty, `:688-689`). | **Remove** the count from `round.json`, the list label, and the empty per-round notes block. (See Defect-B decision below for why remove beats count.) |

## Defect-A label design (resolved — what each entry shows, exactly)

Chosen: **Option (i)** — list the current draft as the top entry, relabel archived rounds to
reconcile. Rejected option (ii) (relabel rounds only) because it leaves the current draft, the one
the human is actually reading, absent from a list titled "Version history" — the issue's acceptance
explicitly wants the human able to tell which entry is current.

The reconciliation arithmetic (this is the crux): `revision` is the count of PUTs and equals the
version of the **current** live draft. The dashboard badge `vN` therefore names the *current* draft.
`round-k` archives the draft that was live *before* PUT number `k+1` — i.e. the draft that was
itself version `k`. So:

- **Top entry (the current draft):** label **`current (v{rev})`**, where `{rev}` is `revision` read
  from `GET /api/reviews/{id}` (already in the `summary()` payload as `revision`). Its body is
  `GET /api/reviews/{id}/source` (existing route, `app.py:543`), rendered through the viewer's
  existing `marked.parse` path exactly like `showRound` does today. No new endpoint.
- **Archived entries (below, newest first):** label **`v{round} · earlier draft`** plus the existing
  timestamp. `round-(N-1)` shows `v(N-1)`, down to `round-0` showing `v0`. With the current draft
  pinned at `vN` on top, the list now reads `vN (current), v(N-1), … v0`, and the top number equals
  the dashboard badge. The off-by-one is eliminated by *inclusion of the current draft*, not by
  renumbering rounds (renumbering rounds would desync them from the `/history/{n}` path, which is
  keyed on the on-disk `round-n` and must not change — see Key constraints).

Why this is correct and not slippery: the previous confusion was that the list's top number
(`v(N-1)`) didn't match the badge (`vN`) and the current draft was missing. Adding the current draft
as `vN (current)` fixes both at once, and the word "current" disambiguates it from the archived
`v(N-1)` immediately below. The `· earlier draft` suffix on archived rows replaces the removed
"0 notes" text so the rows still have a descriptor.

### The revision-0 / empty-rounds edge (resolved — pinned, not left to "prepend")

Two concrete landmines, both pinned here so the smoke assertion is not self-contradicting at v0:

1. **`openHistory` early-returns on empty rounds.** At `viewer.html:678` the function `return`s with
   the "No earlier versions yet" copy **before** rendering any entry when `rounds.length===0`. A
   naive "prepend a synthetic top entry" would still be skipped for any never-PUT review. **Resolution
   (option b): the current-draft top entry always renders, so the early-return must move.** The
   current-draft entry is built and injected *before* the rounds-empty check; when there are no
   archived rounds, the "No earlier versions yet" copy renders *below* the current entry (as the
   archived section's empty state), not instead of it. MR-065's AC names `viewer.html:678` as the line
   to relocate, not "prepend."
2. **Reconcile the v0 label with the dashboard's badge-less card.** The dashboard **hides** the badge
   when `revision==0` (`dashboard.html:127`, `(r.revision||0)>0`). So a literal `current (v0)` in the
   modal would *disagree* with a card that shows no version at all. **Resolution: at `revision==0` the
   top entry reads plain `current` (no `(v0)` parenthetical); at `revision>=1` it reads
   `current (v{rev})`.** Both surfaces then agree: no version number is shown anywhere at v0, and at
   v>=1 the badge number equals the parenthetical. This keeps the "badge == top-entry number"
   reconciliation assertion well-defined precisely where it is testable (v>=1) and free of a phantom
   `v0` where the dashboard deliberately shows none.

### Render-observable fork checked (current-draft body source)

The current draft must render in the modal identically to an archived round. The viewer already
fetches `GET /source` as text at `viewer.html:376` and renders archived source via
`marked.parse(d.source)` at `:687`. The top entry reuses that exact path: fetch `/source` text →
`marked.parse` → inject into `.histdoc`. No node-vs-browser gap (it is the same `marked` global the
page already loads and the same `.histdoc` container styled at `dashboard`/`viewer` CSS for history
images). This is a reuse, not a new render surface, so no new client-render risk is introduced.

## Defect-B decision (resolved — remove, not count)

Chosen: **(b) remove the untruthful count** (and the empty per-round notes section). Rejected
**(a) snapshot + count comments** for these verified reasons:

1. **Existing rounds are unrecoverable.** Comments live in a single append-only `comments.json`
   shared across the whole review (`app.py:267-282`); they were never per-round snapshotted. There
   is no stored signal of which comments existed *at the moment* `round-k` was archived. A retroactive
   count for any already-archived round is therefore impossible — it would still be `0`.
2. **A count correct for only future rounds is worse than none.** Option (a) could only stamp a real
   count on rounds archived *after* this change ships; every pre-existing round would still read `0`.
   A list where some rows show a true count and the rest show a false `0` is more misleading than a
   list with no count column — a reader can't tell which `0`s are real. The issue explicitly permits
   removal "if it cannot be made truthful"; it cannot, uniformly, so we remove.
3. **YAGNI.** No consumer needs a per-round comment count today. #19 (a future version-picker/diff)
   needs trustworthy version **labels** — which this epic delivers — not counts; it is not painted
   into a corner. If a per-round count is ever genuinely wanted, snapshotting `comments.json` is a
   clean additive follow-up that this removal does not block.

What "remove" means concretely:
- `snapshot_round` stops writing `notes_total`/`notes_addressed` into `round.json` (`app.py:197-200`).
  `round.json` keeps `round` + `ts`. It no longer needs to read `notes.json` for counts (it still
  copies `notes.json` as a file for back-compat of the archived round body — unchanged).
- The list label (`viewer.html:679`) drops `+r.notes_total+' notes'…` and the `(… done)` clause.
- `showRound` (`viewer.html:688-689`) drops the `notes that round` section (it rendered `d.notes`,
  always the empty legacy notes). The archived round body (`d.source`) still renders.

**One documented contract is touched (corrected from an earlier draft of this plan).** `README.md:55`
documents `GET /history` as returning per-round `{round, ts, notes_total, notes_addressed}`. Dropping
the count keys makes that line wrong, so **MR-064 must update `README.md:55`** to the new shape
`{round, ts}` (and note the historical `notes_total`/`notes_addressed` keys are inert on rounds
archived before this change). No *programmatic* reader breaks (the only per-round consumer is the
`viewer.html:679` label, and MCP `get_history` is a pure passthrough), but the doc must match. The
`summary()`-level `notes_total` documented in CLAUDE.md/README's review-row copy is a **different**
field (the comment-aware per-review total, `app.py:160-161`) and is untouched.

**Back-compat:** existing rounds on disk have `round.json` with the old `notes_total` keys — the new
client simply never reads them, so they are inert; no migration. A round archived after this change
lacks those keys — the new client never references them either. Both degrade cleanly.

## Recommended approach

### Service (`app.py`)
- **`snapshot_round` (`app.py:181-203`):** remove the `notes` read used only for counts (`:196`) and
  the `notes_total`/`notes_addressed` fields from the `round.json` write (`:197-200`). Keep `round`,
  `ts`; keep the file copy of `source.md`/`feedback.md`/`notes.json` (`:192-195`) so archived round
  bodies stay intact. Keep the `revision = n + 1` bump (`:202`) — the counter is sound.
- **`GET /history` (`app.py:675-688`) and `/history/{n}` (`app.py:690-702`):** no behavioral change
  required. `/history` returns the `round.json` array (now without the count keys — naturally
  dropped). `/history/{n}` still returns `source`/`feedback`/`notes`; the client stops rendering
  `notes` but the field stays for back-compat. **No new route, no shadowing** of the id regex
  `[A-Za-z0-9]{4,40}`.
- **`GET /source` (`app.py:543`) and `GET /api/reviews/{id}` (the `summary()` payload, `revision` at
  `:162`):** unchanged, reused by the client for the current-draft entry.
- **`README.md:55` (doc, ships with MR-064):** change the documented `/history` per-round shape from
  `{round, ts, notes_total, notes_addressed}` to `{round, ts}`, noting the dropped keys are inert on
  pre-existing rounds. Same change as the `round.json` write so the doc never lags the code.

### UI (`viewer.html` / `dashboard.html`)
- **`viewer.html` `openHistory` (`:674-682`):** after fetching `/history`, build a synthetic top
  entry for the current draft labeled `current (v{rev})` at `rev>=1` / plain `current` at `rev==0`
  (see the v0 edge above), where `{rev}` comes from a `GET /api/reviews/{ID}` (or is passed in — see
  open question Q1) read once on open. **Relocate the empty-rounds early-return at `viewer.html:678`**
  so the current entry renders even when `rounds.length===0`: inject the current-draft button first,
  then render archived rounds below (or the "No earlier versions yet" copy as the archived section's
  empty state). Render archived rounds as `v{round} · earlier draft · {timestamp}`, dropping the
  notes count. Wire the top entry's click to render `/source` into `#histview` via the same path as
  `showRound`.
- **`viewer.html` `showRound` (`:683-691`):** drop the `notes that round` block (`:688-689`); keep
  the `v{n} draft` heading and the `.histdoc` body render. Add a sibling current-draft renderer (or
  branch `showRound` on a `current` flag) that renders `/source` under a `current (v{rev})` heading.
- **`dashboard.html`:** **no change.** The `v${r.revision}` badge (`:127`) is already the source of
  truth and is what the History top entry is reconciled *to*. Confirm-by-smoke that badge and top
  History entry now show the same number; do not touch the badge.

## Rollout phases

One small, tightly-coupled fix. The service change (Defect B count removal) and the UI change
(Defect A relabel + Defect B label removal) are coupled enough that splitting risks a half-state
(e.g. UI dropping a field the service still emits, or vice versa), but they validate differently
(curl vs render-smoke). Single phase, two ordered tickets.

### Phase 1 — reconcile labels + remove the lie
- **MR-064 (svc):** `snapshot_round` stops writing the legacy count into `round.json`; update
  `README.md:55` to the new `{round, ts}` shape; curl-verify `/history` and `/history/{n}` return the
  corrected fields.
- **MR-065 (ui):** History modal lists the current draft as `current (v{rev})` from `/source`,
  relabels archived rounds, removes the notes count and empty per-round notes section; render-smoke
  the rebuilt container.

Both ship together in one sprint; MR-065 depends on MR-064 (the UI must not display a count the
service may still emit). Each is independently validatable.

## Non-goals

- **No new History endpoint.** The current draft comes from existing `GET /source`; the version
  number from existing `GET /api/reviews/{id}` (`revision`). Adding a route would shadow nothing but
  is unjustified machinery.
- **No retroactive per-round comment count.** Impossible for existing rounds (see Defect-B decision);
  explicitly out of scope, named so #19 can revisit if ever wanted.
- **No renumbering of on-disk `round-n` dirs or the `/history/{n}` path.** Labels are display-only;
  the path key stays `round-n`.
- **No change to the dashboard badge** or to `revision` semantics — the counter is sound.
- **No version-picker / diff UI (#19).** This epic only makes labels trustworthy so #19 can build on
  them.
- **No `meta.json` schema change.** No new persisted key anywhere.

## Key constraints

- **Stdlib-only, zero pip.** No dependency tempted; pure label + count-removal logic.
- **Overwrite-based persistence, no history of state.** `round.json` is a per-round file (not
  `meta.json`); removing fields from new writes is safe and needs no migration. The full
  read-mutate-write rule for `meta.json` is untouched (this epic writes no new `meta.json` key).
- **Back-compat of existing rounds.** Rounds archived before this change carry the old `notes_total`
  keys; the new client must never read them (it doesn't) and must not assume any new key is present
  on an old round (it doesn't — it derives the label from `round` + `ts`, both already present). New
  rounds simply omit the count keys; no reader breaks.
- **Single-file regex router, ordered routes.** No new route; the existing `/history` and
  `/history/{n}` (`app.py:675`, `:690`) and `/source` (`:543`) are reused. The id regex
  `[A-Za-z0-9]{4,40}` is unchanged and nothing is shadowed.
- **No-auth, id-only tenancy.** No new cross-review listing or aggregation; the History modal is
  already per-`id`. Exposure is unchanged.
- **JS-rendered surfaces — and `render-smoke.sh` CANNOT open this modal.** The History modal is
  `display:none` and `#histbody` is an empty static div (`viewer.html:199`); `.histitem`/`.histdoc`
  exist only after `openHistory()` runs on a `#histbtn` click (`viewer.html:692`). `render-smoke.sh`
  does a single `--dump-dom` with no click and no eval, so `render-smoke.sh … '.histitem'` returns 0
  even on a correct build (false fail) — and this repo already proved that headless target cannot
  open this exact modal in sprint-07 (`reviews/sprint-07-close-review-2026-06-18.md`). Therefore
  MR-065's modal-DOM acceptance test is **pinned to a node-CDP eval driver** (the repo's proven
  `agent_smoke.py:112-148` pattern: Node built-in `WebSocket` over CDP, `Runtime.evaluate
  {returnByValue, awaitPromise}` to call `openHistory()` and read the populated modal back). Static
  `render-smoke.sh` is used only for non-modal nodes (`#histbtn`, the dashboard `.badge`). A 200 is
  not a render and `--dump-dom` of a closed modal is not a render either. The `marked` path the top
  entry reuses already renders archived rounds in a browser (same path, no node-vs-browser gap).
- **No new served file.** No sibling of `viewer.html`/`dashboard.html` is added, so **no Dockerfile
  `COPY` change** is needed (the `Dockerfile:8` `COPY` list is untouched). Called out per the
  packaging footgun; it does not apply here.
- **HEAD requests 501.** Any header inspection in verification uses a GET header-dump (`curl -sD -`),
  never `curl -sI`. (Not expected to be needed here, but stated for the verification author.)
- **render-smoke selectors are flat** (`tag`, `.class`, `tag.class`, `#id`; no descendant
  combinators) — relevant only where the static tool is used (`#histbtn`, dashboard `.badge`). The
  modal-internal assertions (`.histitem`, `.histdoc`, top-entry text, absence of "notes") are done by
  the node-CDP `Runtime.evaluate` reads, which are plain DOM queries against the live page, not flat
  render-smoke selectors.

## Preferred execution order

1. **MR-064 (svc)** — remove the legacy count from `snapshot_round`/`round.json`; update
   `README.md:55` to the `{round, ts}` shape; curl-smoke `/history` + `/history/{n}` on a
   multi-revision review.
2. **MR-065 (ui)** — History modal: current-draft top entry (always rendered; relocate the
   `viewer.html:678` early-return) + relabel + count removal; static render-smoke for `#histbtn` +
   node-CDP drive for the modal DOM. Depends on MR-064.

## Ticket breakdown

Create in `tickets/` only after G1. IDs verified next-free: highest existing is MR-063, so this
epic uses **MR-064, MR-065**.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-064 | snapshot_round: stop writing the retired notes count into round.json (+ README.md:55 shape) | svc | 1 |
| MR-065 | History modal: list current draft as `current (vN)`, relabel rounds, drop "0 notes" | ui | 1 |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| **Off-by-one re-derived wrong** (top entry labeled `v(N-1)` or `v(N+1)`). | Pin the rule in the AC: top entry `{rev}` = the `revision` field from `GET /api/reviews/{id}`, archived entry = its own `round`. node-CDP drive of a 2-PUT review asserts top entry == `current (v2)` and the dashboard `.badge` (static render-smoke) == v2 — same number. |
| **Current-draft body fails to render** (node-vs-browser, or `marked` not loaded when modal opens). | Reuse the exact existing `showRound` render path (`marked.parse` → `.histdoc`); the viewer already loads `marked` and renders archived rounds this way. The node-CDP script clicks the current entry and asserts `#histview .histdoc` exists with the current draft text — a real browser render, not a `--dump-dom` of a closed modal. |
| **MR-065's modal cannot be opened by `render-smoke.sh`** (the sprint-07 wall). | Modal-DOM acceptance is pinned to a node-CDP eval driver (the proven `agent_smoke.py:112-148` pattern) that runs page JS in scope to call `openHistory()` and read the modal back; static `render-smoke.sh` is used only for non-modal nodes. Fail-loud (non-zero exit) if Chrome/WebSocket-Node is absent — never a silent pass. |
| **Old client against new service** shows a round with no count. | The old client read `r.notes_total`; on a new round it is `undefined` → renders `undefined notes`. Acceptable transient (server + viewer ship same sprint, same container rebuild); no persisted-data risk. Noted, not blocking. |
| **`round.json` consumers elsewhere** rely on `notes_total`. | Grep confirms the only readers are `/history` (passthrough) and the viewer label. MCP `get_history` returns the same passthrough; no count consumer. Verified by `grep -n notes_total app.py *.html mcp_server.py`. |
| **#19 painted into a corner.** | #19 needs trustworthy labels (delivered) not counts; per-round comment snapshotting remains a clean additive follow-up. Named as non-goal. |

## Verification

All evidence under `.scratch/` (never `/tmp`); scratch ports only (never 8137/8139; never `docker
compose up`). Build a throwaway image, run on a scratch port, force a multi-revision review.

**Shared fixture (both tickets):**
```bash
# rebuild + run a throwaway container on a scratch port
docker build -t mdreview-hist .
docker rm -f mdreview-hist-smoke 2>/dev/null || true
docker run -d --name mdreview-hist-smoke -p 18137:8080 mdreview-hist
BASE=http://localhost:18137
# multi-revision review: 2 PUTs => revision=2, rounds round-0 + round-1 exist
id=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"hist","markdown":"# v0 draft\n"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
# add a comment so the round genuinely carried feedback (exercises Defect B truthfully)
curl -s -X POST "$BASE/api/reviews/$id/comments" -H 'Content-Type: application/json' \
  -d '{"quoted_text":"v0 draft","text":"a real comment","role":"reviewer"}' >/dev/null
curl -s -X PUT "$BASE/api/reviews/$id/source" -H 'Content-Type: application/json' \
  -d '{"markdown":"# v1 draft\n"}' >/dev/null
curl -s -X PUT "$BASE/api/reviews/$id/source" -H 'Content-Type: application/json' \
  -d '{"markdown":"# v2 draft\n"}' >/dev/null
```

**MR-064 (svc) — `py_compile` + curl smoke of `/history` and `/history/{n}`:**
```bash
python3 -m py_compile app.py        # gate

# /history: rounds 1 and 0, newest first; NO notes_total/notes_addressed key
curl -s "$BASE/api/reviews/$id/history"
# EXPECT: {"rounds":[{"round":1,"ts":...},{"round":0,"ts":...}]}
#   - exactly fields round + ts per entry; assert no "notes_total"/"notes_addressed":
curl -s "$BASE/api/reviews/$id/history" | python3 -c \
  'import sys,json;rs=json.load(sys.stdin)["rounds"];assert rs and all("notes_total" not in r and "notes_addressed" not in r for r in rs),rs;print("OK no count keys")'
# /history/0 still returns the archived body (source/feedback/notes preserved for back-compat)
curl -s "$BASE/api/reviews/$id/history/0" | python3 -c \
  'import sys,json;d=json.load(sys.stdin);assert d["round"]==0 and "source" in d, d;print("OK round-0 body")'
# the revision counter is sound:
curl -s "$BASE/api/reviews/$id" | python3 -c 'import sys,json;assert json.load(sys.stdin)["revision"]==2;print("OK revision=2")'

# doc matches code: README.md:55 no longer advertises the dropped per-round count keys:
grep -n 'history' README.md | grep -q 'notes_total' && { echo "FAIL: README still documents per-round notes_total"; exit 1; } || echo "OK README /history shape updated"
```

**MR-065 (ui) — `py_compile` + a *static* render-smoke for the non-modal nodes + a node-CDP modal
drive for the modal DOM (the modal is the deliverable and `render-smoke.sh` cannot open it):**

```bash
python3 -m py_compile app.py        # gate (no app.py change here, but the gate is owed)

# (a) STATIC render-smoke is fine ONLY for nodes present without opening the modal.
#     #histbtn is in the served HTML (viewer.html:189) and proves the page rendered:
scripts/render-smoke.sh "$BASE/review/$id" '#histbtn'
#   DO NOT assert '.histitem'/'.histdoc' here — they are display:none until openHistory() runs on a
#   click, and render-smoke.sh does a single --dump-dom with NO click and NO eval, so those selectors
#   match 0 even on a correct build (false fail). This repo already hit that exact wall: the modal
#   could not be opened by a headless target in sprint-07
#   (reviews/sprint-07-close-review-2026-06-18.md). The modal DOM is asserted in (b) instead.
```

**(b) Modal-open mechanism — PINNED: a node-CDP eval script (the repo's proven pattern).** This is
the same Node-built-in-`WebSocket`-over-CDP driver `agent_smoke.py` already ships (`agent_smoke.py:112-148`):
launch `chrome --headless=new --remote-debugging-port=PORT URL`, pick the `type=="page"` target from
`GET /json`, open the WS, and `Runtime.evaluate{expression, returnByValue:true, awaitPromise:true}`.
Unlike a bare `--dump-dom`, this **runs page JS in scope**, so it can call `openHistory()` and read
the populated modal back. Put the script under `.scratch/`. It must:

1. Navigate to `$BASE/review/$id`, `Runtime.enable`, then `Runtime.evaluate('openHistory()')` (or
   `document.querySelector("#histbtn").click()`).
2. Poll until the modal populates: `document.querySelectorAll('.histitem').length > 0`
   (loop `Runtime.evaluate` like `agent_smoke.py:127`), then settle ~500ms.
3. Read back and assert, all via `Runtime.evaluate(returnByValue)` against the live DOM:
   - **`.histitem` count >= 3** (current + round-1 + round-0 for the 2-PUT fixture).
   - **top entry text == `current (v2)`** — and equals the dashboard badge number (assert below).
   - **archived rows read `v1 …` then `v0 …`** (newest-first) with `· earlier draft`, no count.
   - **NO "notes" count text and NO "notes that round"** anywhere in the modal's `innerText`
     (`!/\bnotes\b/.test(document.querySelector('#histbody').innerText)` — Defect B, asserted on the
     **rendered** DOM, not a source grep).
   - click the top entry (`Runtime.evaluate` a click on the current `.histitem`) → assert
     **`#histview .histdoc` exists** and its `innerText` contains the current draft text (`v2 draft`),
     proving the `/source` body renders through the same `marked` path as `showRound`.
   The script prints a JSON verdict and `process.exit(non-zero)` on any failed assertion (fail-loud,
   like `agent_smoke.py`'s exit-3 skip when Chrome/WebSocket-Node is absent — never a silent pass).

This keeps the fix **pure** (no product behavior added). *Fallback only if node-CDP proves awkward in
the build env:* add a tiny `?history=1` auto-open hook to `viewer.html` (read `location.search`, call
`openHistory()`), then `render-smoke.sh "$BASE/review/$id?history=1" '#histbody' '.histitem'
'.histdoc'`. This is a deep-link product behavior, so it is the **fallback**, not the default — the
node-CDP eval is the primary mechanism. Whichever is used, the AC must NOT be bare `render-smoke.sh`
against the modal selectors.

```bash
# (c) Reconciliation (heart of Defect A): dashboard badge number == modal top-entry number.
#     The dashboard card is a static render (badge is in the served card HTML), so it can use the
#     flat tool; the modal number comes from the node-CDP read in (b). Assert both equal 2:
scripts/render-smoke.sh "$BASE/?id=$id" '.badge'    # dashboard card shows v2 (badge rendered)
#   node-CDP (b) top entry == "current (v2)"  ->  both 2; archived v1 then v0.

# (d) Screenshot of the open modal as G4/G7 evidence (under .scratch/, scratch port). The CDP
#     script can also trigger Page.captureScreenshot after opening the modal; or chrome --screenshot
#     of $BASE/review/$id?history=1 IF the fallback hook exists. A screenshot proves first-paint
#     only — it is evidence, NOT the acceptance test; (b)'s DOM assertions are the acceptance test.
```
The modal is theme-adaptive only insofar as `viewer.html` honors `prefers-color-scheme`; if a
themed capture is taken, emulate the pane with `--blink-settings=preferredColorScheme=0` (dark) /
`=1` (light), **never** `--force-dark-mode` (that is Chrome's auto-invert, not scheme emulation, and
bare headless resolves dark by default — both panes would mis-shoot).

**Teardown:** `docker rm -f mdreview-hist-smoke`.

## Assumptions & open questions

Recorded; proceeding on the stated assumption (none blocks the design).

- **Q1 (minor) — where the current-draft `{rev}` number is read.** Assumption: the viewer fetches
  `GET /api/reviews/{ID}` once on modal open and reads `revision` from the `summary()` payload
  (`app.py:162` guarantees it is present, defaulting `0`). Justification: that endpoint already
  returns `revision`; no new field. Alternative (the page already holds `revision` from an earlier
  fetch) is a pure implementation detail for the `ui` ticket and changes no contract.
- **Q2 (RESOLVED in body — the revision-0 edge).** Now pinned in "The revision-0 / empty-rounds
  edge": the current-draft top entry **always** renders (the `viewer.html:678` early-return is
  relocated so it no longer skips it), and at `revision==0` the entry reads plain `current` (no
  `(v0)`) to agree with the dashboard hiding its badge below v1 (`dashboard.html:127`); at
  `revision>=1` it reads `current (v{rev})` and equals the badge. No longer an open question.
- **Q3 (minor) — `· earlier draft` wording.** Assumption: archived rows read `v{round} · earlier
  draft · {timestamp}`. Justification: replaces the removed count text with an honest descriptor;
  exact wording is a copy choice the `ui` ticket can refine without changing the design.

No **load-bearing** open questions and **no BLOCKER-FOR-HUMAN**: the dashboard badge is the
established source of truth, the current draft has an existing endpoint, and Defect B's removal is
forced by the impossibility of a truthful retroactive count.

## Review resolutions

**2026-06-24 — G1 independent staff-critic review (verdict PASS-WITH-NITS), all findings folded in.**

- **[blocking] MR-065's render-smoke cannot open the modal (sprint-07 wall).** Resolved by **pinning
  a node-CDP eval driver** as MR-065's modal-DOM acceptance test — the repo's proven
  `agent_smoke.py:112-148` pattern (Node built-in `WebSocket` over CDP, `Runtime.evaluate
  {returnByValue, awaitPromise}`) navigates to `/review/{id}`, calls `openHistory()`, polls until
  `.histitem` populates, then reads back the modal: `.histitem` count >= 3, top entry == `current
  (v2)`, archived `v1`/`v0` newest-first, **no "notes" text** on the rendered DOM, and clicking the
  current entry yields `#histview .histdoc` with the draft text. Static `render-smoke.sh` is now used
  **only** for non-modal nodes (`#histbtn`, dashboard `.badge`); the plan explicitly forbids bare
  `render-smoke.sh` against modal selectors and explains the false-fail. `?history=1` auto-open is
  documented as the *fallback only* (it adds deep-link product behavior), with node-CDP as primary.
  Updated: Verification MR-065 block, the JS-rendered-surfaces and flat-selector key constraints, and
  a new Risks row.
- **[worth-considering] README.md:55 documents the removed per-round shape; "no documented field"
  claim was wrong.** Corrected the claim in the Defect-B decision section and **added the
  `README.md:55` → `{round, ts}` update to MR-064's scope** (service section, rollout, execution
  order, ticket table, and a `grep` assertion in MR-064's curl smoke). Clarified that the
  `summary()`-level `notes_total` in other docs is a different, untouched field.
- **[worth-considering] `openHistory` early-return at `viewer.html:678` would skip the revision-0
  current entry; Q2 was ambiguous vs. the badge-less card.** Added a "revision-0 / empty-rounds edge"
  subsection pinning **option (b)**: the current-draft top entry **always** renders (relocate the
  `:678` early-return), and at `revision==0` it reads plain `current` (no `(v0)`) to agree with the
  dashboard hiding its badge below v1. The "badge == top-entry number" assertion is now well-defined
  only where testable (v>=1). MR-065's `openHistory` UI note names `:678` as the line to relocate.
  Q2 marked RESOLVED.
- **[nit] keep the smoke fixture at >=2 PUTs.** Already the case (shared fixture does 2 PUTs →
  revision=2, the discriminating case); unchanged.
- **[nit] svc/ui split + `depends_on` are right; don't fold.** Agreed; kept the split (curl-validated
  svc vs node-CDP-validated ui under separate ACs, MR-065 depends_on MR-064). Unchanged.
