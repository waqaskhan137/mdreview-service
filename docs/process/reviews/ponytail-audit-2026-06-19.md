# Ponytail audit — mdreview-service (repo-wide, over-engineering only)

**Date:** 2026-06-19
**Scope:** over-engineering / complexity only (dead code, hand-rolled stdlib, unused deps,
speculative abstractions, duplicated config/docs). Correctness, security, and performance are
explicitly **out of scope** — route those to a normal review.
**Method:** whole-tree scan (not a diff), then **two rounds of verification**: a live-volume check,
then a staff-critic pass that caught a repeated overclaim (see "Revision history" at the bottom).

---

## Summary

The Python is genuinely lean — single-file regex router, stdlib-only, thin file helpers, all
deliberate and load-bearing. The only real over-engineering is **one frozen write-path** left
behind when the viewer moved from notes to comments (MR-036, `26411e4`, ~24h before this audit),
plus **two agent docs that overlap heavily**.

**Key correction (made twice, the second time only after staff-critic review):** the notes/feedback
subsystem is *write-dead but read-live*. The write paths stopped firing in MR-036, but they were
firing **yesterday**, so the live volume carries real reviewer data — and the read paths, the docs,
and the MCP tool surface still expose it. "The current viewer doesn't write X" is **not** "X is
empty/zero." I made that inference error first on `notes.json` (caught via the volume check) and
again on `feedback_updated` (caught only by the critic). Treat every item below as
*deprecate-then-remove-with-the-contract*, not *delete now*.

---

## Findings (ranked, biggest cut first)

### 1. Frozen notes/feedback **write path** — `delete:` the bumps, **deprecate** the field/route
The viewer authors **comments** now (`comments_updated`). The notes/feedback machinery is frozen —
no path *writes* it post-MR-036 — but it is **not** safe to rip out as a no-op, because the field
and route are still documented, surfaced over MCP, and backed by live data:

- `POST /api/reviews/{id}/feedback` (`app.py:495–501`) — no caller in this workspace or the running
  container, and the post-MR-036 viewer doesn't use it. **But** it died ~24h ago, the service is
  **no-auth and public-ish**, and `CLAUDE.md`/`AGENTS.md` still publish the `curl` recipe that
  invites callers. Safe basis for removal is "no *deployed* pre-MR-036 viewer + stop documenting
  it," **not** the grep alone (which can't see other deployments or external scripts).
- `feedback_updated` — the *bump* is dead (nothing calls it post-MR-036), but the **field is not
  reader-less**, contra my first pass:
  - `CLAUDE.md:84` **and** `AGENTS.md:40` document it as the canonical "human is done" signal
    ("Poll `status_url` and watch `feedback_updated` … treat the round as complete").
  - `mcp_server.py:108` — the `get_status` tool description advertises it to every MCP client.
  - `dashboard.html:117` — `activity()` sorts by it; **12 live reviews have `feedback_updated > 0`**
    (verified on `:8139`), so it really feeds the sort for them.
  - `summary()` `app.py:143` — `if not m.get("feedback_updated") and total == 0` gates the
    `awaiting` status. Deleting the field silently changes the "human cleared feedback" case back to
    `awaiting`. Delete that branch *deliberately* if you go ahead, don't let it fall out.

  So removing `feedback_updated` is a **documented-contract break**: it must land with edits to both
  docs + the MCP `get_status` description, and you accept that any agent still running the old poll
  loop loses its round-complete signal (comments superseded it via `comments_updated`).

**Read path stays (unchanged from the correction):** `GET /feedback`'s `notes[]` union + `markdown`
(`app.py:488, 492–493`), `summary()` counting (`app.py:135–148`), `GET /history` read-back
(`app.py:540–541`). The live volume holds real persisted reviewer notes these surface. `feedback.md`
is likewise **write-dead but read-live** — `snapshot_round` copies it and `GET /history/{n}` returns
it; it's a frozen legacy artifact, not a deletable field.

Realistic safe cut: the dead *bump* call sites (~3–5 lines). Removing the field/route end-to-end is
~-25 lines across `app.py` + 2 docs + `mcp_server.py`, and it's a **deprecation with a contract
change**, not a free cut.

### 2. `AGENTS.md` ⟂ `CLAUDE.md` overlap — `delete:`-adjacent, but **NOT a clean win**
61 of 104 non-blank lines are byte-identical (contract / rich-content / comments / MCP sections).
That's a real **drift risk** (they're maintained separately). But collapsing `AGENTS.md` to a
pointer has costs my first pass ignored:
- `README.md:186` names it as *the* agent-integration doc ("For agent integration details, see
  AGENTS.md"); `docs/future-mcp.md:61` references its "human is done" heuristic.
- The delivery process treats `README.md` / `CLAUDE.md` / `AGENTS.md` as **three docs updated in the
  same change** (`docs/process/README.md:135`, MR-026). `AGENTS.md` is the cross-tool convention
  filename some harnesses read by name, and it's a *deliberately condensed* sibling (the other ~43
  lines differ), not pure copy-paste drift.

Honest move: flag the duplication as a drift risk and propose **one source with a generated/condensed
view**, not "delete one outright." Worth doing, but it's a preference with trade-offs.

### 3. `_CTYPES` speculative entries — `yagni:` (leave it)
`.bmp` / `.avif` / `.ico` aren't exercised (`app.py:81–96`). Trivial; image-attach is open-ended
enough to justify. Listed only so the audit is honest about not chasing non-cuts.

### 4. Two smoke harnesses — under-explored, flagged for a look
`mcp_smoke.py` (317) and `agent_smoke.py` (239) overlap in surface. Probably justified (one is
MCP/JSON-RPC protocol, one is the HTTP+render proof), but a whole-repo scan should at least say so.
Not asserting a cut — flagging that the audit didn't originally examine them.

### Non-findings (checked, NOT over-engineered)
- `reopen` HTTP route — **live**, used by the viewer (`viewer.html:363–365`). Not dead.
- Static shims (`marked-footnote.umd.js`, `marked-highlight.umd.js`, katex/mermaid/highlight) —
  legit **vendored** libs, not hand-rolled. No cut.
- `_read`/`_write`/`_read_json`/`_find_comment` — thin, justified. Not stdlib reinventions.
- The `route()` if-ladder router — deliberate single-file design per `CLAUDE.md`. Not a finding.

---

## Verification

**External consumers (workspace grep, vendor dirs excluded):**
- `feedback_updated`: no *external* code consumer. **But** 3 *internal* readers (both docs + the MCP
  `get_status` tool) — so "reader-less" was wrong; it's a published field, not dead telemetry.
- `GET /feedback` / `.markdown`: no external code client; only cross-repo mention is one blog post
  naming the endpoints in prose. *Caveat:* the grep covers `/Users/apple/Dev/personal` + the `:8139`
  container only — it cannot see other deployments, saved old viewers, or scripts using the
  documented `curl` recipe. On a no-auth service that's a real gap, not a clean bill.

**Live volume (`mdreview` container, port 8139):**

| metric | count |
|---|---|
| review dirs | 45 |
| non-empty `notes.json` (current + history) | **61** |
| non-empty `feedback.md` | **61** |
| current (non-history) reviews with live notes | **12** |
| reviews with `feedback_updated > 0` | **12** |

Genuine reviewer feedback (e.g. `0ae054d5bc` — a real note + 497-char `feedback.md`, **zero
comments**, written 2026-06-18, i.e. via `POST /feedback` ~1 day before MR-036 removed it). Proves
both the read path **and** `feedback_updated` are load-bearing for the installed base.

**Lesson:** "dead in current code" ≠ "no live data / no reader." Two checks are needed before
deleting file-backed or API state: (a) scan `/data`, and (b) grep the **docs + MCP tool
descriptions**, not just product code — the contract has readers the code grep misses.

---

## Net

- **Genuinely free:** remove the dead `feedback_updated` *bump* call sites (~3–5 lines).
- **Deprecation (contract change, do deliberately):** retire `POST /feedback` + `feedback_updated`
  end-to-end — ~-25 lines across `app.py` + 2 docs + `mcp_server.py`, landed together, after
  confirming no pre-MR-036 viewer is deployed.
- **Preference with trade-offs:** single-source `AGENTS.md`/`CLAUDE.md` (drift fix), not a delete.
- **Withdrawn:** collapsing the GET /feedback / summary / history **read** path (would erase 61
  files of real reviewer notes + drop 12 reviews' `feedback_updated`).
- **Deps:** -0 (already stdlib-only).

**Total truly-free cut: ~5 lines. Deprecation-gated cut: ~25 more + doc/MCP edits.** (First-pass
headline of "-90, clean" was wrong twice over — corrected down after the live-volume check and the
staff-critic pass.)

---

## Revision history

- **v1 (first pass):** claimed the whole notes/feedback subsystem was always-empty dead code,
  net ~-90 lines clean.
- **v2 (live-volume check):** found 61 non-empty `notes.json`/`feedback.md`; withdrew the read-path
  collapse, kept "delete the write path + `feedback_updated` as a clean cut."
- **v3 (staff-critic, this version):** the *same* overclaim was still live on `feedback_updated` and
  `POST /feedback` — both have live data (12 reviews) and the field has 3 documented/MCP readers, and
  the route died only ~24h ago on a no-auth service. Reframed every "delete now" as
  "deprecate-with-the-contract." Demoted the AGENTS.md "clean win" to a trade-off. The recurring
  error: inferring "empty/zero" from "the current viewer stopped writing it."

_Audit lists findings; applies nothing. One-shot._
