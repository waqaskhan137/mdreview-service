---
slug: history-version-fix
captured: 2026-06-24
source: GH issue #18 ("document History bug") — groomed, code-grounded, staff-critic-reviewed. Picked as the next high-value contained fix this session.
related_epic: epics/history-version-fix-plan.md
related_issue: "#18"
---

# History version bug (GH #18)

The document **History / revision count is wrong**: the version numbers in the History modal don't reconcile with the dashboard's revision badge, the current draft is unversioned, and every history entry shows "0 notes". Two distinct defects.

## Defect A (the reported symptom) — dashboard `v{revision}` and history `v{round}` never reconcile

- `snapshot_round` (`app.py:181-203`) archives the CURRENT revision `n` into `round-n`, then bumps `revision = n+1` (`:202`). `create_review` doesn't set `revision`; `summary()` defaults it to `0` on read (`app.py:162`). After *N* edits: `revision == N`, history holds `round-0 … round-(N-1)` (the past / outgoing drafts).
- Dashboard badge (`dashboard.html:127`) shows `v${r.revision}` → **vN**. History modal newest entry shows **v(N-1)**. So the dashboard advertises **vN** while the version list tops out at **v(N-1)**, and the **current live draft the human is viewing is never in the history list at all**. Reads as "the revision count is off by one / the versions don't add up". The round index also names the *outgoing* draft, not the change (`round-0`/"v0" = the original posted draft, `round-1` = after the first edit).
- The counter itself is sound — `revision` increments by exactly 1 per PUT under `_lock`, round dirs key on the monotonic `revision` (no dup/overwrite/race). The defect is purely the dashboard-vs-history **labeling** mismatch + the current draft being unlisted.

## Defect B (separate, same modal) — the history list always shows "0 notes"

- `snapshot_round()` records each round's `round.json` (`app.py:197`) with `notes_total`/`notes_addressed` counted from the legacy `notes.json` store — **retired** (the viewer authors **comments** / `comments.json` since MR-036, not notes), and `comments.json` is never snapshotted (only `source.md`/`feedback.md`/`notes.json` are copied). So for any comments-era review `notes_total` is always `0`. The history modal renders that directly: every entry reads "v0 · 0 notes" regardless of actual feedback; `showRound()` renders `d.notes` (always empty) so the per-round notes section never appears.

## Acceptance criteria (from the issue)

- The count shown per history entry **reflects the comments that round actually accumulated** (or the count is **removed** if it cannot be made truthful), not the dead `notes.json`.
- The version numbering is **consistent across dashboard and history**, and the human can tell which entry is the **current draft** (it is either listed, or clearly labelled "current vN").

## Notes / boundaries

- Resolve the design in the plan (the issue is groomed but leaves the exact fix open): Defect A — how to reconcile labels + surface the current draft (least new machinery, least confusing); Defect B — snapshot+count comments vs. remove the untruthful count (YAGNI-correct, justified).
- Relationship to #19 (a future History-modal version-picker / diff needs trustworthy version labels): out of scope here; just don't paint it into a corner.
- This touches product pages (`dashboard.html` / `viewer.html`, JS-rendered) → render-smoke owed for any ticket touching them; a pure-`app.py` ticket owes `py_compile` + a curl smoke of `/history`/`/history/{n}`.
