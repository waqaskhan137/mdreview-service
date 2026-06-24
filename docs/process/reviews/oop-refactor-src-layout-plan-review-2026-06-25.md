---
review_of: epics/oop-refactor-src-layout-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-25
verdict: CHANGES-REQUESTED
status: resolved   # all r1 findings addressed; G1 closed by the r2 re-review (PASS-WITH-NITS)
---

# G1 Review: OOP Refactor + `src/` Restructure Plan

**Verdict: CHANGES-REQUESTED.** This is a strong, unusually well-verified plan: the
move-first/decompose-second split is the right risk decomposition, the seven-module mapping is
checked against the real code (most boundary lines and the cited `app.py` lines hold up), the
golden-transcript-as-oracle instinct is correct, and the IoC seam (handler reads
`self.server.app` off a `ThreadingHTTPServer` subclass) is feasible exactly as described. The MR-054
lock model and the path/container-stability claims are sound. But the plan's single load-bearing
question ("does the router stop reaching `/data` directly?") is answered **incompletely**: it
enumerates most inline store calls but misses two comment arms the handler mutates/reads inline, the
objective acceptance grep it proposes provably does **not** catch them, and the golden transcript
omits those same endpoints, so a regression there is invisible. That triad is one defect with three
faces, and it would spawn a wrong comments ticket and a server ticket whose green grep certifies a
boundary that is still dirty. Fix that and the plan is G1-ready; the remaining items are SHOULDs/NITs.

Independence note: I am not the plan's author. I verified the plan's claims against `app.py`,
`mcp_server.py`, `watch.py`, the two Dockerfiles, `docker-compose.yml`, `watcher/agent-mcp.json`,
the two smokes, and `docs/process/README.md` rather than trusting its line numbers.

## Findings

### [BLOCKER] 1: The router/service boundary is incomplete: two comment arms reach `/data` inline and the plan neither maps them to a service nor catches them in its acceptance check

The plan's own "load-bearing question #1" is whether `route()` stops calling store primitives. Its
boundary prose ("The router must call services, not store primitives") enumerates: the existence
guard, raw document reads (source/feedback/history), static/asset bytes, and `bump`. It misses two
handler arms that reach `/data` directly and are **comment state**, not framing:

- **`DELETE /api/reviews/{id}/comments/{cid}` (`app.py:765-772`)** does a full comment mutation
  *inline in the handler*: `_read_json(_comments_path(rid))` → filter → `_write_comments(rid, kept)`
  → `bump(rid, "comments_updated")`, all under `_lock`. The `CommentService` row maps source range
  `app.py:276-382`, but this delete logic lives at **765-772, outside that range**, and no
  `CommentService.delete_comment(rid, cid)` method is named anywhere in the plan. As written, the
  decomposed `server.py` keeps doing inline comment I/O here, the exact "IoC is a rename" outcome
  the plan says it prevents.
- **`GET /api/reviews/{id}/comments/{cid}` (`app.py:760`)** calls `_find_comment(list_comments(rid),
  cid)` inline. `_find_comment` is listed as moving *into* `CommentService`, but the plan never gives
  the handler a `CommentService.get_comment(rid, cid)` to call, so this arm is left reaching into
  service-internal helpers.

The acceptance check makes this worse, not better. The plan proposes (Risk register, "Router still
calls store primitives" row, and load-bearing assumption #1): grep `server.py` for
`os.path.join(.*DATA_DIR` / `_dir(` to prove the handler does not path-join into `/data`. The DELETE
arm reaches `/data` via `_comments_path(rid)` + `_read_json`, which contains **neither** `_dir(`
**nor** `os.path.join(...DATA_DIR)`. I verified this: the proposed grep passes a `server.py` that
still does inline comment mutation. The objective gate is gameable by construction against precisely
the arm the plan forgot.

**Fix (concrete):**
1. Add to the `CommentService` mapping the two missing methods and the source line they come from:
   `delete_comment(rid, cid) -> (code, payload)` (lifting `app.py:765-772`, including the 404 when
   nothing is removed and the `comments_updated` bump) and `get_comment(rid, cid)` (lifting
   `app.py:760`). Note that `app.py:765-772` is currently outside the `276-382` range the comments
   row cites, extend the cited range or list it explicitly so the ticket author sees it.
2. Strengthen the server-ticket acceptance grep from a `_dir(`/`DATA_DIR` substring check to a
   positive contract: assert `server.py` contains **no** call to any store/service-internal helper by
   name: grep for `_comments_path(`, `_assets_dir(`, `_read_json(`, `_write(`, `_write_comments(`,
   `_find_comment(`, `_read(` / `_read_bytes(` *against a `/data` path*, not just `_dir(`. The clean
   end state is that `server.py`'s only filesystem reads are the three `WEB_DIR` framing reads
   (`/`, `/review/{id}`, `/static/*`); everything else goes through `self.server.app.<service>`.
3. Add the two arms to the golden transcript and the comments ticket curl (see BLOCKER-adjacent
   coverage in SHOULD-2): `GET .../comments/$cid` (200 thread) and `DELETE .../comments/$cid`
   (200 `{deleted}` + a second DELETE → 404).

This is the finding most likely to produce wrong tickets, so it gates G1.

### [SHOULD] 2: The golden transcript (the only behavioural oracle) misses five endpoints/arms, including two mutations

The transcript is the oracle for every pure-refactor commit, so an endpoint absent from it can
regress silently through all eleven commits and only surface (maybe) at the final `mdreview-qc`. The
sweep in "Preferred execution order" / "Verification" covers POST/GET-source/PUT/GET-feedback/
comment-create/reply/resolve/409-resolve/status/handoff-flip/410-feedback/asset-POST/asset-GET/
history/history-0. Verified absent:

- `DELETE /api/reviews/{id}/comments/{cid}` (mutation; see BLOCKER-1).
- `GET /api/reviews/{id}/comments/{cid}` (single-thread read; see BLOCKER-1).
- `POST /api/reviews/{id}/comments/{cid}/reopen` (the `apply_comment_transition` **reopen branch**
  (`app.py:370-378`) is server code in `CommentService`; the transcript drives only resolve. The
  plan correctly notes reopen is a reviewer UI action with no MCP tool, but the *endpoint and the
  state-machine branch still exist* and must be refactored intact. Drive it (resolve → reopen → 200
  `reopened`; reopen-a-non-resolved → 409) so the reopen branch has an oracle.
- `GET /api/reviews/{id}` (meta, `app.py:539-540`) and `DELETE /api/reviews/{id}`
  (`app.py:541-543`). `DELETE` is destructive and trivial to verify (`{deleted}` then 404 on
  re-GET); include it so the review-lifecycle arm is covered.

**Fix:** extend the transcript sweep to these five. They are cheap (a handful of curls) and three of
them exercise mutation/state-machine code that currently has no diff oracle.

### [SHOULD] 3: Pin the "no service re-acquires `store.lock`" invariant; the single-Condition grep does not cover it

The MR-054 mandate (one `Condition`, notify under `store.lock` after a write, `wait()` releases that
lock) is correct and the wake-smoke is the right gate. But once `store.lock` becomes a reachable
member, the natural-instinct bug during the split is a service method "made thread-safe" with
`with self.store.lock:`, e.g. someone wrapping `ReviewService.list_reviews()` or `summary()`. That
matters specifically because `_wait` (`app.py:452-459`) holds the lock and calls `list_reviews()`
**under it**; today `list_reviews`/`summary` take no lock (verified), which is why that nested call
is safe.

I checked the failure mode rather than asserting it: `threading.Condition()` wraps an `RLock`, and
`RLock._release_save()` releases the full recursion count, so a doubly-acquired lock does **not**
deadlock and `wait()` still fully releases. So this is **not** a correctness BLOCKER. I want to be
precise that the "writer runs while a waiter holds the lock" bug does not occur via re-entrancy with
the stdlib RLock-backed Condition. But nested acquisition silently violates the documented
"Caller holds `_lock`" contract on the service writers (`create_comment`, `_write_comments`,
`attach_asset`, `apply_comment_transition`, `snapshot_round`) and is a latent smell that defeats the
single-lock reasoning the plan is built on.

**Fix:** add to the store/server tickets the explicit invariant "services never acquire
`store.lock`; the lock is taken only at the call sites that take it today (PUT /source, /handoff,
POST/DELETE comments, POST assets, `_wait`)," and grep the extracted tree for `store.lock` / `.lock:`
*acquisition* sites, not just for a second `Lock(`/`Condition(` constructor (which is what the plan
greps for now). Confirm `list_reviews`/`summary` stay lock-free so the `_wait`-holds-lock-then-calls-
`list_reviews` path remains the same shape across the module boundary.

### [NIT] 4: Inline-call counts are slightly off; the prose leans on them as if exhaustive

The plan states "8× `_dir`" in `route()`; the actual count is **9** (`app.py:542, 551, 557, 568,
572, 613, 682, 697`, plus `_assets_dir` at 802). Other counts I spot-checked match (13× `_exists`,
6× `_read`, 6× `_read_json`, 5× `meta`, 5× `bump`, 2× `_read_bytes`, 2× `_ctype_for`, 2× `_write`).
The undercount is harmless arithmetically but the prose presents the list as the basis for "names
every inline store call," and it demonstrably does not (the DELETE arm in BLOCKER-1 is the
consequence). Correct the count and, more importantly, stop treating the hand-counted list as the
completeness proof: the grep in BLOCKER-1's fix is the real proof.

### [NIT] 5: `_to_float` is mapped to `Store` but is called from `server.py` framing code

`_to_float` moves into `Store` as `store.to_float` (store row). It is used by `_wait` and by the
`?turn=`/`?since=` query parsing, which live in `server.py`: pure query-string framing with no
`/data` involvement. Routing it through `store.to_float` means `server.py` reaches into the store for
a string-parse helper, which mildly muddies the "store == persistence seam" story. Non-blocking;
either keep it on `Store` (fine, it is tiny) or note it is a free function the server imports
directly. Just call the choice rather than leaving it implicit.

### [NIT] 6: Brief's "~290 historical mentions" is an overcount; the plan inherits the figure

The plan (Non-goals, and assumption #5) cites "~290 historical `py_compile app.py` mentions" to
leave frozen. Actual: 145 `py_compile app.py` occurrences across 83 files under
`tickets/sprints/reviews/epics`. The *approach* is correct and verified: the three live README refs
are exactly the Divergences bullet (`README.md` validation-gate sentence), Development-flow step 5,
and the G4 row, plus the one `CLAUDE.md` bullet; AGENTS.md has no `py_compile` gate ref (only
container run commands), as the plan claims. Only the count is loose. Drop the specific number or
correct it; it has no bearing on the edit scope.

## What I verified and found correct (so the author can rely on it)

- `app.py` is 833 lines (plan correct; brief's 834 is the stale figure the plan already flags).
- IoC seam: `BaseHTTPRequestHandler` exposes `self.server`; the `ThreadingHTTPServer`-subclass-
  carries-`app` pattern works as described.
- MR-054: exactly one `threading.Condition` (`app.py:52`), zero bare `Lock()`; the single
  `notify_all()` is under `_lock` after the write (`app.py:668-672`); `_wait` parks on
  `_lock.wait()` which releases (`app.py:458`). The invariant is stated correctly.
- Path/container stability: `Dockerfile.watcher` `COPY watch.py mcp_server.py ./` flattens to
  `/app/...`; changing the COPY *sources* to `src/watch.py src/mcp_server.py` keeps the
  *destinations* identical, so `watcher/agent-mcp.json`'s `/app/mcp_server.py`, compose's
  `/app/watcher/launch.sh`, and `CMD ["python3", "watch.py"]` need no edit. Confirmed `agent-mcp.json`
  lives at `watcher/agent-mcp.json` (assumption #6 is right).
- `WEB_DIR` arithmetic: three `dirname`s from `src/mdreview/config.py` resolve to repo root, `+ /web`
  → `<repo>/web`. Verified by simulation. Env override + container `ENV MDREVIEW_WEB_DIR=/app/web`
  is the right belt-and-braces.
- `mcp_server.py` and `watch.py` do not import `app` and read no `__file__`-relative web assets
  (verified); safe to `git mv` to `src/` with no internal change.
- Smoke `SERVER` paths are the bare-sibling form at exactly `mcp_smoke.py:19` and `agent_smoke.py:34`
  (assumption #4 is right; the brief quoted the target string, not current code).
- Ticket sequencing is bottom-up and dependency-correct (config → store → comments → assets →
  reviews → handoff → server); Phase 0 leaves a runnable relocated monolith (`CMD python src/app.py`)
  before any decomposition; the entrypoint flip to `python -m mdreview` is correctly isolated to the
  last Phase-1 ticket. No ticket leaves the service unbootable mid-sprint.
- Frontmatter is correct (`status: draft`, `gate: G1 not passed`, `source:` → the requirement);
  dates are Europe/London (2026-06-25); no literal em-dash characters in the plan.

## Resolution log

**2026-06-25, author (mdreview-planner) revision round 1.** All six findings addressed in
`epics/oop-refactor-src-layout-plan.md`. I re-verified each cited line against `app.py` before
revising (the DELETE arm at 765-772, the GET-find at 760, the reopen branch at 370-378, and the
`_dir(` count of 9 at 542/551/557/568/572/613/682/697 + `_assets_dir` at 802 all confirmed). Review
`status` stays `open` for the critic to re-verify on the revised plan (independence: the author does
not close an independent review; the re-review does).

- [x] **BLOCKER-1: incomplete router/service boundary + gameable grep.** Confirmed both arms reach
  `/data` inline (DELETE *mutates* via `_comments_path`+`_write_comments`+`bump`; GET finds via
  `_find_comment(list_comments(rid), cid)`). Resolved three ways: (1) the `comments.py` mapping row
  now lists **`get_comment(rid, cid)`** (lifts `app.py:760`) and **`delete_comment(rid, cid) ->
  (code, payload)`** (lifts `app.py:765-772` including the 404-on-nothing-removed and the
  `comments_updated` bump, under `store.lock`), and notes that 765-772 sits outside the 276-382
  range so the ticket author sees it. (2) Added a "Comment-arm read + mutate" bullet to the boundary
  prose naming both arms. (3) Replaced the gameable `_dir(`/`DATA_DIR` substring grep with a
  **positive no-store-helper contract** (new "Acceptance check for the boundary" paragraph + rewritten
  Risk-register row): `server.py` must have **zero** hits for `_comments_path(`, `_assets_dir(`,
  `_assets_manifest(`, `_dir(`, `_read_json(`, `_write(`, `_write_comments(`, `_find_comment(`,
  `_comment_as_note(`, `_stored_name(`, and `os.path.join(` with a `/data` arg, explicitly noting the
  DELETE arm reaches `/data` via `_comments_path`, which the old grep missed. The only kept reads are
  the three `WEB_DIR` framing reads.

- [x] **SHOULD-2: transcript missing 5 arms.** Extended the golden-transcript sweep with: `GET
  /api/reviews/$id` (meta), `GET .../comments/$cid` (single thread), the **reopen branch** (resolve →
  reopen → 200 `reopened`; reopen-a-non-resolved → 409), `DELETE .../comments/$cid` (200 `{deleted}`
  then second DELETE → 404), and `DELETE /api/reviews/$id2` against a **separate throwaway review**
  (so the destructive delete doesn't kill the rest of the sweep) with a re-GET → 404. Updated the
  normalized-fields note to include `id2` and a sentence stating the sweep now covers every mutation
  with no other oracle.

- [x] **SHOULD-3: pin "no service re-acquires `store.lock`".** Confirmed `list_reviews`/`summary` are
  lock-free today and `_wait` holds the lock while calling `list_reviews()` (`app.py:452-459`). Added
  a dedicated Key-constraints bullet: services never acquire `store.lock`; it is taken only at the
  arms + `_wait` that take it today; `list_reviews`/`summary` **must stay lock-free** so `_wait`'s
  nested call keeps its shape. Noted (per your RLock analysis) that re-acquisition does not deadlock
  and `wait()` still releases, so it's a contract/clarity violation, not a crash, but it's barred
  because it defeats the single-lock reasoning. The Lock/Condition Risk-register row now mandates
  grepping `store.lock`/`.lock:` **acquisition** sites (not just a second `Lock(`/`Condition(`
  constructor), with `list_reviews`/`summary` asserted acquisition-free, on the store + server tickets.

- [x] **NIT-4: `_dir` count.** Corrected 8 → **9** in the boundary prose with the line list
  (`app.py:542, 551, 557, 568, 572, 613, 682, 697` + `_assets_dir` at 802), and added an explicit
  sentence that **the hand-count is illustrative, not the completeness proof; the grep is** (citing
  that a hand-count missed the DELETE arm in round 1).

- [x] **NIT-5: `_to_float`/`to_float` placement.** Called the choice explicitly: it stays on `Store`
  as `store.to_float` but is used **only** by `server.py`'s `_wait`/query parsing (it touches no
  `/data`); added a note to the `store.py` mapping row and a paragraph under the Store-seam exposition
  stating the deliberate choice and that the boundary grep does not flag `to_float`.

- [x] **NIT-6: "~290" overcount.** Confirmed the figure is scope-dependent (my re-count gave 146/84
  for an exact-string match under `docs/process/`, your 145/83 for the tickets/sprints/reviews/epics
  scope). Per your advice I **dropped the specific number** in all three places, describing the surface
  qualitatively ("well over a hundred, in dozens of files") and adding a parenthetical in assumption
  #5 noting the earlier "~290" was dropped as scope-dependent and unimportant.
