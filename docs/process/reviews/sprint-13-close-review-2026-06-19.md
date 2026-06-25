---
review_of: sprint-13
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-19T22:30:00+01:00
verdict: PASS
status: resolved   # clean PASS; the two NITs were close-step actions, discharged on close 2026-06-19
---

# Sprint-13 (legacy-feedback-retire) — G7 sprint-close review

**Independent** G7 review. The reviewer did **not** implement this sprint. Shipped work verified
against each committed ticket's acceptance criteria, by reading the diff
(`git diff e091509^..HEAD`), byte-comparing the reader regions against the pre-sprint tree
(`e091509^`), reading `mcp_server.py:108-109`, and **independently rebuilding the image and
re-running the behavioural smoke** (throwaway container, never composed over `:8139`).

- Artifact: [`sprints/sprint-13.md`](../sprints/sprint-13.md)
- Tickets: [`MR-046`](../tickets/MR-046-retire-feedback-write-svc.md) (svc),
  [`MR-047`](../tickets/MR-047-retire-feedback-docs-sweep.md) (docs)
- Epic / G1: [`epics/legacy-feedback-retire-plan.md`](../epics/legacy-feedback-retire-plan.md),
  [`reviews/legacy-feedback-retire-plan-review-2026-06-19-r2.md`](legacy-feedback-retire-plan-review-2026-06-19-r2.md)
- Smoke evidence: [`reviews/sprint-13-close-smoke-2026-06-19.txt`](../reviews/sprint-13-close-smoke-2026-06-19.txt)
- Commit range: `e091509^..HEAD` (4 commits: scaffolding `e091509`, svc `cb9ead2`, docs `d5180c2`,
  reconcile+evidence `b95ebf7`).

The sprint goal is framed as **what does NOT change** (zero data lost, zero read behaviour changed,
one write surface retired). That is the right frame and the shipped work meets it. Code/doc files
changed this sprint: `app.py` (16 lines), `CLAUDE.md`, `AGENTS.md`, `README.md`,
`docs/future-mcp.md` — and process files. `mcp_server.py`, `viewer.html`, `dashboard.html`,
`static/**` are **unchanged** (verified `git diff --name-only e091509^..HEAD`).

---

## Verdict

**PASS** — the sprint may close. Every committed ticket's AC is met; every load-bearing
non-regression claim is verified against the rebuilt image and the byte-level diff. The two NITs
below are process-hygiene follow-ups for the close step, not gate blockers.

---

## Findings (prioritized)

No **BLOCKER** and no **SHOULD** findings.

### NIT-1 — `close_review:` frontmatter + sprint `status` not yet set (confidence: high)

`sprints/sprint-13.md` still has `status: active` and an empty `close_review:` field. This is
**expected** at the moment of review — the G7 checklist in the sprint file lists "set
`close_review:` in frontmatter" and the README's G5/G7 flow set `status: closed` *after* the
close review passes. Flagged only so the close step is not forgotten: on accepting this PASS, set
`close_review: reviews/sprint-13-close-review-2026-06-19.md` and `status: closed`, and fill the
retro line in the sprint's Notes/retro section (currently a placeholder "_Filled in as the sprint
runs and at close._"). Not a gate blocker — it is the action the gate authorizes.

### NIT-2 — smoke evidence lives at repo-root `reviews/`, not `docs/process/reviews/` (confidence: medium)

`sprint-13-close-smoke-2026-06-19.txt` is at `reviews/` (repo root), while this close review lives
at `docs/process/reviews/`. The sprint file and G7 row reference the smoke by name without pinning a
directory, and the repo already keeps audit-style evidence (`reviews/ponytail-audit-2026-06-19.md`)
at the root `reviews/`, so this is consistent with existing convention, not an error. Noted only
because a future reader chasing "the G7 smoke for sprint-13" from `docs/process/reviews/` will not
find it co-located. Optional: cross-link it (this review does). No action required.

---

## Per-ticket acceptance-criteria check

### MR-046 — retire the dead `POST /feedback` write (→ 410), keep every reader — **ALL AC MET**

| AC | Result | Evidence |
|----|--------|----------|
| POST arm returns 410, no `_body_json`/`_lock`/`_write`/`bump` | **PASS** | `app.py:495-501` — body is a comment + `return self._json(410, {"error": "gone, use comments"})`. The removed lines (two `_write`s + `bump(rid,"feedback_updated")`) are gone in the diff (`cb9ead2`). |
| Returns 410, not 200, not a 404 fall-through | **PASS** | Rebuilt image: `POST /feedback` on an existing review → `{"error": "gone, use comments"} <- 410`. (404 is only for a non-existent id — `_exists` guard at `app.py:484`, confirmed: `POST .../deadbeef00/feedback` → 404 "not found". Correct: the 410 is the deliberate signal for a *real* review.) |
| GET arm byte-unchanged | **PASS** | `diff` of `app.py:486-494` vs `e091509^`: **byte-unchanged**. |
| `bump(rid,"feedback_updated")` gone; `bump()` itself stays | **PASS** | The only `feedback_updated` writer is removed; `bump()` still called for `source_updated` (`app.py:478`) and `comments_updated` (`app.py:589,609,628`). |
| `create_review` no longer seeds `feedback_updated` | **PASS** | `app.py:190-193` diff drops `"feedback_updated": 0`. On-disk check (rebuilt image): a fresh review's `meta.json` keys are `['created','id','project','session','source_path','source_updated','title']` — **no `feedback_updated`**. |
| Readers untouched: `summary()` guard (`:143`) + derivation (`:127-149`); status payload default (`:511`); `GET /feedback` union; `snapshot_round` (`:169`); `GET /history/{n}` (`:539-541`); `feedback_url` (`:449`) | **PASS** | `summary()` region `127-149` and status+history region `503-545` both **byte-unchanged** vs `e091509^`. `feedback_url` still emitted (`app.py:449`); `snapshot_round` still copies `feedback.md`/`notes.json` (`app.py:169`). A changed reader would have been a blocker — none changed. |
| In-file POST docstring updated; GET docstring (`:14`) unchanged | **PASS** | `app.py:15` now `POST … /feedback → 410 (retired MR-036/MR-046; … POST /comments)`; GET line `:13` untouched in the diff. |
| Guard non-regression: fresh review derives `awaiting`; live Pop-B reviews stay `awaiting` | **PASS (fresh review verified independently; 31-count taken on implementer evidence)** | Rebuilt image: fresh review (no notes, no comments) → `status: awaiting`, `feedback_updated: 0`. This is the load-bearing Pop-B case and it holds. The "31 live stay awaiting" count is the implementer's `docker cp`-of-`:8139`-volume run (MR-046 Validation) — I did **not** re-copy the live volume (correctly out of bounds: do not compose over `:8139`), but since the guard region is **byte-unchanged**, no Pop-B review *can* flip: the derivation is identical code on identical data. The count is corroborated by code, not just asserted. |
| Back-compat: fresh `GET /status` returns `feedback_updated: 0`; `GET /feedback` returns markdown+notes | **PASS** | Rebuilt image: `/status` → `feedback_updated: 0` (defaulted via `mt.get(...,0)` at `:511`); `/feedback` → `keys ['markdown','notes']`. |
| Local validation: `py_compile app.py` + behavioural curls | **PASS** | `python3 -m py_compile app.py` → OK (re-run). All behavioural curls re-run on a freshly built image; POST carrying a junk note left `notes == []` and `markdown == ''` (proves **no write**). |
| Docs deferred to same-sprint MR-047 (named) | **PASS** | MR-046 Work log/Validation name MR-047; MR-047 is `done` (frontmatter + TRACKER Done section). Per Definition of Done, a same-sprint docs-sweep that is `done` discharges the obligation. |

### MR-047 — docs sweep: "human is done" → `comments_updated` — **ALL AC MET**

| AC | Result | Evidence |
|----|--------|----------|
| CLAUDE.md + AGENTS.md "human is done" now watch `comments_updated`, keep "reply 'done'" option | **PASS** | Both diffs rewrite the first bullet to "watch `comments_updated` — the live signal the viewer bumps", with a parenthetical that `feedback_updated` is the retired pre-MR-036 write; the "reply 'done'" bullet is retained. |
| README API table: POST `/feedback` write row removed; GET `/feedback` + `/status` rows kept exactly | **PASS** | README diff removes only the `POST … /feedback … {ok}` row. `grep` confirms 0 POST-feedback rows; `GET /feedback` (`:51`) and `status` (`:52`) rows present and unchanged. |
| `docs/future-mcp.md:61` no longer asserts the heuristic "unchanged"; `:36` `get_status` row kept | **PASS** | Diff repoints the line to "now watches `comments_updated` (… retired … see the legacy-feedback-retire epic)". `grep "unchanged" docs/future-mcp.md` → empty. The `get_status` table row (field still emitted) is left intact. |
| No `mcp_server.py` change; its `get_status` desc already leads with `comments_updated`; no reconnect owed | **PASS** | `git diff e091509^..HEAD -- mcp_server.py` is **empty**. `mcp_server.py:108-109` reads "…source_updated, feedback_updated, and comments_updated timestamps. **Watch comments_updated for new/changed comment threads.**" — it leads the *watch* guidance with `comments_updated` and only *lists* `feedback_updated` as one still-emitted timestamp (factually true; `/status` still emits it at `app.py:511`). Dropped MCP ticket and skipped reconnect are justified. |
| `/status` snippet comment stays accurate (field still emitted) | **PASS** | CLAUDE.md/AGENTS.md `:24` snippet now reads `{"source_updated":…, "feedback_updated":…, "comments_updated":…}` — accurate, the field is still emitted; `comments_updated` added for clarity (the AC's optional improvement). |
| Inspection greps pass; no doc tells an agent to poll `feedback_updated` to detect done | **PASS** | `grep "watch feedback_updated"` across all four docs → empty. Surviving `feedback_updated` mentions are read-shape only: the `/status` snippet (`:24`) and the legacy parenthetical (`:42`/`:86`). README `feedback_url` mentions (`:32,:45`) are the create-response **URL field** (GET semantics), correctly retained per the plan's explicit nitpick. |

---

## The five load-bearing claims (explicit)

1. **Write gone, every reader intact** — verified. POST arm = 3-line 410, no write/`bump`/`_lock`;
   GET arm, `summary()` guard region, status payload, and history read-back all **byte-unchanged**
   vs `e091509^`; `create_review` initialiser dropped (confirmed absent on disk). **PASS.**
2. **Guard non-regression holds** — fresh review → `awaiting`, `feedback_updated: 0` (rebuilt
   image). The guard at `app.py:143` is byte-unchanged, so no Pop-B review can flip. The 31-count
   rests on implementer evidence + the byte-identity argument, which is sound. **PASS.**
3. **Docs match new behaviour** — "human is done" watches `comments_updated` in both agent docs;
   README POST-feedback row gone, GET/status kept; `future-mcp.md` "unchanged" assertion removed;
   no doc tells an agent to poll `feedback_updated` to detect done. **PASS.**
4. **MCP claim** — `mcp_server.py` git diff empty; `:108-109` already leads with `comments_updated`.
   Dropped MCP ticket + skipped reconnect justified. **PASS.**
5. **Atomicity at sprint granularity** — svc (`cb9ead2`) before docs (`d5180c2`), both in sprint-13;
   sprint file + epic frame "land together" as sprint-granularity on a single-deploy/no-CD repo, so
   the inter-commit window is internal-only. No live window where route and docs disagree. **PASS.**

---

## G7 evidence classification (confirmed correct)

This is a **svc + docs** sprint with **no product page touched** (`viewer.html`/`dashboard.html`/
`static/**` all show empty in `git diff --name-only e091509^..HEAD`). Per the G7 pass-condition row,
such a sprint owes the **container rebuild + `curl /healthz` + `curl /api/reviews`** smoke and is
**not** non-compliant for lacking a per-page `scripts/render-smoke.sh` DOM assertion or a screenshot.
The evidence file `reviews/sprint-13-close-smoke-2026-06-19.txt` provides exactly that (healthz 200,
`/api/reviews` sane, 410 on POST, read path intact, fresh review `awaiting` with `feedback_updated 0`,
`py_compile` both modules) and I independently reproduced every line of it on a fresh build. The
classification is correct.

---

## Resolution log

- **2026-06-19** — Review opened. Verdict **PASS**. Both committed tickets `done` with all AC met
  and independently re-verified on a rebuilt image; no BLOCKER/SHOULD. Two NITs are close-step
  hygiene (set `close_review:`/`status: closed`/retro; smoke-file location cross-link), neither
  gating. Awaiting the implementer to perform the close step; this review's `status` flips to
  `resolved` once the sprint is marked `closed` with `close_review:` set. The two NITs need no
  re-review.

---

**Verdict: PASS** — sprint-13 may close.
