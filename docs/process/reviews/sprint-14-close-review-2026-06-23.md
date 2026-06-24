---
review_of: sprints/sprint-14.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-23
verdict: PASS
status: resolved
---

# G7 sprint-close review — sprint-14 (agent-handoff-baton Chunk 1, MR-051)

Independent gate review. Reviewer is not the implementer. Shipped change verified against
MR-051's acceptance criteria; an independent smoke was run on a throwaway container (Docker
image rebuilt from source) on scratch port 8170 — never the live 8139 instance nor compose 8137.

**Verdict: PASS.** MR-051 meets every acceptance criterion. The sprint may close.

## Scope check

Sprint-14 commits MR-051 only (`svc`). The shipped commit `aade026` touches `app.py` (+60
lines) and the MR-051 ticket file. No `viewer.html` / `dashboard.html` / `static/**` was
touched, so per the G7 pass-condition row this `svc`-only sprint owes the container rebuild +
`curl /healthz` + `/api/reviews` smoke, **not** a per-page DOM assertion or screenshot. No MCP
change, no new storage file, no scope leak versus the epic's locked Non-goals.

## AC verification (against `app.py`)

1. **Route placement / POST-only / non-shadowing — PASS.** New arm
   `re.fullmatch(r"/api/reviews/" + RID + r"/handoff", path)` at `app.py:526`, guarded by
   `m == "POST"`, sits after the `/status` arm (`app.py:503`) and before `/history`
   (`app.py:575`). `handoff` is a distinct literal segment and not a valid `RID`
   continuation (`RID = [A-Za-z0-9]{4,40}`, `app.py:47`), so the matched paths are disjoint.
   Smoke [12]: `GET /handoff` → 404 `{"error":"no route"}` (falls through; POST-only holds).

2. **Locking / no bare `bump()` — PASS.** Handler opens `with _lock:` (`app.py:535`), reads
   the current `meta.json` via `_read_json(p, {})` (`app.py:536`), decides off the current
   `turn`/`owner`, mutates the in-memory dict, and `_write`s the whole dict once inside the
   lock (`app.py:570`). It never calls `bump()` (the unlocked read-modify-write at
   `app.py:120-124`). Mirrors the `PUT /source` discipline. A read-error or unrecognized body
   takes no write (the `if err is None:` guard at `app.py:569`), so a 400/409 never mutates
   `meta.json` — confirmed by smoke [3] (owner unchanged after 409).

3. **Pinned dispatch order + guards — PASS.** Order in code is reclaim (`to==reviewer &&
   by==reviewer`, `app.py:538`) → hand-back (`to==reviewer && state in {done,blocked}`,
   `app.py:543`) → flip (`to==agent`, `app.py:550`) → lease (`state==working`, `app.py:557`)
   → else `400` (`app.py:567`). Verified:
   - Determinism for `{to:reviewer,by:reviewer,state:done}`: smoke [5b] — reclaim ran, the
     pre-set `agent_status` sentinel (`working`/`sentinel`) was left untouched, proving
     hand-back did **not** run.
   - `400` on unrecognized body: smoke [7] — both `{foo:bar}` and non-JSON → 400.
   - `409` on foreign-owner lease: smoke [3] — `sess-B` claim over `sess-A` → 409
     `{"error":"lease held","owner":"sess-A"}`, owner unchanged.
   - `{to:agent}` idempotent: smoke [6] — 2nd flip leaves `turn_updated` byte-identical.
   - Lease claim bumps `agent_status.at` but **not** `turn_updated`: smoke [2] —
     `turn_updated` equals T1 after the working claim; `agent_status.at` is set.

4. **`/status` surfacing — PASS.** `GET /status` (`app.py:509-518`) adds `turn`
   (default `"reviewer"`), `turn_updated` (default `0`), `handoff` (default `null`),
   `agent_status` (default `null`), all `.get(...)`-defaulted and additive (no removed keys).
   `summary()`/`list_reviews()` untouched — the new meta keys flow through `dict(meta(rid))`
   (`app.py:134`). Smoke [8] (all four present, legacy keys intact) and [9] (`turn` surfaced
   in `GET /api/reviews`).

5. **Back-compat / legacy defaults — PASS.** A never-touched review reads `turn=reviewer`,
   `agent_status=null` (smoke [11]); `PUT /source` + `GET /source` on a handoff-touched
   review still 200 (smoke [13]). The whole-dict write never drops existing keys (the handler
   reads the full meta before mutating).

6. **Owner is client-supplied — PASS.** `owner = b.get("owner", "")` (`app.py:560`); the
   server mints no identity. An absent `owner` on a `working` claim is accepted as an unowned
   claim recorded as `owner:""` (smoke [14]).

7. **Scope — PASS.** `app.py` only; no UI, no MCP, no new storage file, no Non-goal leak.

## Process / gate

- `python3 -m py_compile app.py` → OK.
- Docker image `mdreview-g7` rebuilt from source (satisfies the G7 "rebuild the container"
  clause).
- `curl /healthz` → 200 `{"ok":true}`; `curl /api/reviews` → 200 (smoke header).
- Dashboard-status invariance (G1 SHOULD-2): smoke [10] — a flip to `turn=agent` mid-handoff
  leaves `status`/`notes_total`/`notes_addressed` identical (`awaiting 0 0`).

## Findings

No BLOCKERs. No SHOULDs that gate the close.

- **NIT (no action):** the malformed-body 400 is reached two ways — a syntactically valid JSON
  object with unrecognized keys (`{foo:bar}`) falls through the dispatch chain to the `else`
  (`app.py:567`), and a non-JSON body is silently coerced to `{}` by `_body_json()`
  (`app.py:382-388`, which swallows `JSONDecodeError` and returns `{}`) which then also falls
  through to the same `else`. Both yield the contracted 400, so the AC holds; just note the 400
  for non-JSON is "empty dict → unrecognized" rather than an explicit parse-error path. Not a
  defect — `_body_json()`'s swallow is the pre-existing repo convention shared by every POST
  handler, and the observable contract (`400 {"error":"unrecognized handoff body"}`) is correct
  for both. Recorded for the implementer's awareness, not as a change request.
- **NIT (no action):** `agent_status.at` uses raw `time.time()` float seconds, consistent with
  the other `*_updated` stamps in `meta.json`; the viewer's staleness math (MR-052) must use the
  same unit. Out of scope for MR-051; flagged so MR-052 does not assume ms.

## Smoke transcript

Throwaway Docker container `mdreview-g7-run` (image `mdreview-g7`, rebuilt from source),
published `-p 8170:8080`, ephemeral data. Port 8170 confirmed free before start; 8139 (live)
and 8137 (compose) untouched throughout; container removed and port freed after.

```
# health/list
GET /healthz      -> HTTP 200  {"ok": true}
GET /api/reviews  -> HTTP 200  {"reviews": []}

# state machine (review ID 55c68cd5be)
[0] fresh /status        -> turn=reviewer turn_updated=0 handoff=null agent_status=null     PASS
[1] {to:agent}           -> turn=agent  turn_updated=T1(bumped)  agent_status=null
                            handoff={by:reviewer,at:...}                                     PASS
[2] {state:working,
     owner:sess-A}        -> owner=sess-A state=working at>0  turn_updated==T1 (unchanged)   PASS
[3] {state:working,
     owner:sess-B}        -> HTTP 409 {"error":"lease held","owner":"sess-A"};
                            owner after=sess-A (unchanged, no write)                          PASS
[4] {to:reviewer,
     state:done,message}  -> turn=reviewer state=done message="revised section 3"
                            turn_updated=T2 > T1                                              PASS
[5] re-flip {to:agent}
     then reclaim
     {to:reviewer,
      by:reviewer}        -> turn=reviewer turn_updated=T3 > T2                               PASS
[5b] {to:reviewer,
      by:reviewer,
      state:done,...}     -> reclaim wins: turn=reviewer, agent_status left as
                            working/sentinel (hand-back did NOT run) — dispatch precedence    PASS
[6] {to:agent} x2         -> 2nd flip leaves turn_updated byte-identical (idempotent)         PASS
[7] {foo:bar}             -> HTTP 400 {"error":"unrecognized handoff body"}                   PASS
    non-JSON body         -> HTTP 400 {"error":"unrecognized handoff body"}                   PASS
[8] /status keys          -> turn,turn_updated,handoff,agent_status all present;
                            legacy source/feedback/comments_updated intact                   PASS
[9] GET /api/reviews      -> turn surfaced via summary() (["agent"])                          PASS
[10] invariance           -> flip mid-handoff: status/counts "awaiting 0 0" unchanged         PASS
[11] never-touched review -> turn=reviewer agent_status=null (legacy default)                 PASS
[12] GET /handoff         -> HTTP 404 (POST-only; falls through, non-shadowing)               PASS
[13] PUT+GET /source      -> both 200 on a handoff-touched review (existing flow unchanged)   PASS
[14] {state:working}
     (no owner)           -> HTTP 200; agent_status.owner="" (unowned claim accepted)         PASS
[15] handoff to unknown
     review id            -> HTTP 404 {"error":"not found"}                                   PASS

# teardown
docker rm -f mdreview-g7-run -> removed ; port 8170 free ; live 8139 untouched
```

py_compile: `python3 -m py_compile app.py` -> OK.

## Resolution log

- 2026-06-23 — Independent G7 review complete. All MR-051 ACs verified against `app.py` and an
  independent 15-step smoke (health/list + full handoff state machine, including dispatch
  precedence, 409 back-off, idempotency, 400, surfacing, invariance, and legacy defaults) on a
  rebuilt throwaway container. Verdict **PASS**, no open blockers. `status: resolved`. Sprint-14
  is clear to close (subject to the implementer recording the retro + carry-overs and setting
  `close_review:` in the sprint frontmatter, per the G7 checklist — those are author/process
  steps, not review findings).
