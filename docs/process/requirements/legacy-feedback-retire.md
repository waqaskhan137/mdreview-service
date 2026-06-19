---
slug: legacy-feedback-retire
captured: 2026-06-19
source: reviews/ponytail-audit-2026-06-19.md (repo-wide ponytail over-engineering audit, staff-critic-corrected) + this session
related_epic: epics/legacy-feedback-retire-plan.md
---

# Brief — act on the ponytail audit's actionable findings

The full source brief is the audit at
[`reviews/ponytail-audit-2026-06-19.md`](../../../reviews/ponytail-audit-2026-06-19.md) (read it
in full — it carries the verification evidence and a v1→v2→v3 revision history). The actionable
content is reproduced verbatim below so this requirement is self-contained.

## What was asked (verbatim instruction)

> Take its actionable findings through the full delivery cycle. Note: the audit's own corrected
> verdict is that most cuts are "deprecate-with-contract," not free deletes — the planner must
> respect that (e.g. retiring POST /feedback + feedback_updated requires landing app.py + both
> docs + the MCP get_status description together, and the GET /feedback / summary / history read
> path must NOT be removed because 12 live reviews depend on it). Treat the live-data constraint
> in memory `[[legacy-notes-feedback-load-bearing]]` as a hard requirement.

## Actionable findings (verbatim from the audit, ranked)

**Finding 1 — Frozen notes/feedback write path (`delete:` the bumps, **deprecate** the
field/route).** The viewer authors comments now (`comments_updated`). The notes/feedback
machinery is frozen — no path *writes* it post-MR-036 (`26411e4`) — but it is **not** safe to rip
out as a no-op, because the field and route are still documented, surfaced over MCP, and backed by
live data:

- `POST /api/reviews/{id}/feedback` (`app.py:495–501`) — no caller in this workspace or the
  running container, and the post-MR-036 viewer doesn't use it. **But** it died ~24h ago, the
  service is **no-auth and public-ish**, and `CLAUDE.md`/`AGENTS.md` still publish the `curl`
  recipe that invites callers. Safe basis for removal is "no *deployed* pre-MR-036 viewer + stop
  documenting it," **not** the grep alone.
- `feedback_updated` — the *bump* is dead, but the **field is not reader-less**:
  - `CLAUDE.md:84` **and** `AGENTS.md:40` document it as the canonical "human is done" signal.
  - `mcp_server.py:108` — the `get_status` tool description advertises it to every MCP client.
  - `dashboard.html:117` — `activity()` sorts by it; **12 live reviews have `feedback_updated > 0`**.
  - `summary()` `app.py:143` — `if not m.get("feedback_updated") and total == 0` gates the
    `awaiting` status. Deleting the field silently changes the "human cleared feedback" case back
    to `awaiting`. Delete that branch deliberately if you go ahead.

  Removing `feedback_updated` is a **documented-contract change**: it must land with edits to both
  docs + the MCP `get_status` description, and you accept that any agent still running the old poll
  loop loses its round-complete signal (comments superseded it via `comments_updated`).

  **Read path stays:** `GET /feedback`'s `notes[]` union + `markdown` (`app.py:488, 492–493`),
  `summary()` counting (`app.py:135–148`), `GET /history` read-back (`app.py:540–541`). The live
  volume holds real persisted reviewer notes these surface. `feedback.md` is write-dead but
  read-live — a frozen legacy artifact, not a deletable field.

**Finding 2 — `AGENTS.md` ⟂ `CLAUDE.md` overlap (NOT a clean win).** 61 of 104 non-blank lines are
byte-identical. Real drift risk, but collapsing `AGENTS.md` to a pointer has costs: `README.md:186`
names it as *the* agent-integration doc; `docs/future-mcp.md:61` references its "human is done"
heuristic; the delivery process treats README/CLAUDE/AGENTS as three docs updated together
(`docs/process/README.md`, MR-026). Honest move: flag the duplication as a drift risk and propose
**one source with a generated/condensed view**, not "delete one outright." A preference with
trade-offs.

**Finding 3 — `_CTYPES` speculative entries (`yagni:` leave it).** `.bmp` / `.avif` / `.ico`
unexercised (`app.py:81–96`). Trivial; image-attach is open-ended enough to justify. Not a cut.

**Finding 4 — Two smoke harnesses, under-explored.** `mcp_smoke.py` (317) and `agent_smoke.py`
(239) overlap in surface. Probably justified (protocol vs HTTP+render proof) — flag for a look,
not asserting a cut.

## Net (verbatim)

- **Genuinely free:** remove the dead `feedback_updated` *bump* call sites (~3–5 lines).
- **Deprecation (contract change, do deliberately):** retire `POST /feedback` + `feedback_updated`
  end-to-end — ~-25 lines across `app.py` + 2 docs + `mcp_server.py`, landed together, after
  confirming no pre-MR-036 viewer is deployed.
- **Preference with trade-offs:** single-source `AGENTS.md`/`CLAUDE.md` (drift fix), not a delete.
- **Withdrawn:** collapsing the GET /feedback / summary / history **read** path (would erase 61
  files of real reviewer notes + drop 12 reviews' `feedback_updated`).
- **Deps:** -0 (already stdlib-only).

## Amendments

(none yet)
