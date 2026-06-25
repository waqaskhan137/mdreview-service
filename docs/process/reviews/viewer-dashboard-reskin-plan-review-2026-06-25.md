---
review_of: epics/viewer-dashboard-reskin-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-25
verdict: PASS-with-conditions
status: resolved   # all 4 conditions folded into the plan; see Resolution log
---

# G1 independent review — Viewer & Dashboard Re-skin Plan

Scope of this review: the design forks the planner resolved (D1–D5), whether the
verification recipe actually proves the re-skin rendered AND that no live behavior
regressed (with correct capture flags), and any load-bearing JS contract the re-skin
could silently break. I read the plan, the requirement, `dashboard.html` (274 lines),
the load-bearing slices of `viewer.html` and `app.py`, the render-smoke grammar, and the
mockup labels.

**Verdict: PASS-with-conditions.** The plan is prescriptive, the IA forks are correctly
resolved, and every data-backing claim I spot-checked is true. The forks are sound; the
gap is in *verification completeness* for one surface (the comment-rail fit geometry),
and two smaller framing issues. None is a design-level BLOCKER. Conditions C1–C2 are
cheap and should land in the relevant ticket ACs before implementation, not re-plan.

## What I verified true (so the author knows the foundation held)

- **D1/D2 data-backing.** Every field the inbox + badges need is on each `GET /api/reviews`
  row. `summary()` (`app.py:147`) does `m = dict(meta(rid))` first, so `agent_status`
  (`{state,message,owner,at}`) and `turn_updated` ride along; `summary()` adds `turn`
  (default `"reviewer"`, `app.py:165`), `status`, `notes_total/addressed`, `revision`,
  provenance. Nothing strips `agent_status` between `meta()` and the JSON response
  (`app.py:511`). The plan's `summary()` citation is accurate.
- **D2 badge state-space is closed.** I checked the `/handoff` arms (`app.py:618–662`):
  at `turn === "agent"`, `agent_status` is only ever `None` (parked, line 634) or
  `{state:"working"}` (lease, line 661). `done`/`blocked` are only written on the
  hand-back arm, which always sets `turn="reviewer"` (line 626). So D2's coarse fallback
  ("Waiting for agent" = `turn==="agent"` and not fresh-working) cannot mislabel a
  `blocked`/`done` review — those never coexist with `turn==="agent"`. The table is correct.
- **D3 line cites.** `layoutComments()` fit test `window.innerWidth>=rect.right+320` is at
  `viewer.html:693`; `deletable` at line 645. The gutter mechanics (positioned at
  `rect.right+24`, `width:284px`, `body.gutter-on` toggle) are as the plan describes.
- **D4 capture recipe.** `preferredColorScheme=1` light / `=0` dark, never
  `--force-dark-mode`, matches the documented repo footgun verbatim (MR-027/031/032/052/
  062/066/073 all encode the same rule; bare headless resolves dark). Correct.
- **Key-constraint #4 id inventory.** Every id/class the plan lists as load-bearing
  (`#turnbanner`, `#turntext`, `#turnsteps`, `#turntimer`, `#sendbtn`, `#reclaimbtn`,
  `#dock`, `#count`, `#resbtn`, `#histbtn`, `#article`, `#addbtn`, `#pop`, `#filename`,
  `#doctitle`, `#docmeta`, `#gutter`) exists in `viewer.html`. The list is not aspirational.
- **render-smoke grammar.** `scripts/render-smoke.sh` supports exactly `tag` / `.class` /
  `tag.class` / `#id` and rejects combinators loud (exit 2). Every selector in the plan's
  Verification §2/§3 is flat. Correct.
- **STALE_S mirror.** `app.py:57–58` and `viewer.html:250` already carry the
  single-source-of-truth comment pair. (But see MINOR M1 — the framing of R1 understates
  the failure mode.)

## Findings

### C1 (MAJOR / condition) — D3 verification does not actually prove the comment-rail fit decision landed

`docs/process/epics/viewer-dashboard-reskin-plan.md` — **Verification §3** and **Risk R3**.

The plan's regression guard for the highest-risk surface is `render-smoke.sh … '.gcard'`
plus a both-pane screenshot at `--window-size=1400,1000`. That does **not** prove the
re-derived fit geometry is correct:

- A `.gcard` node exists in **both** wide and docked modes (`viewer.html:690–708`): the
  `else` branch hides the gutter but the cards are still in the DOM. So `.gcard` present is
  a true positive in either layout — it cannot distinguish "rail rendered beside the doc"
  from "rail collapsed/docked". R2's principle ("assert the functional node") is satisfied
  while the actual fit bug ships.
- The fit test is `innerWidth >= rect.right + 320` with the gutter at `rect.right+24`,
  `width:284px`. Today `.wrap` max-width is **720px** (`viewer.html:14`). The re-skin
  changes the article column width **and** adds a fixed rail, so `320` and the doc width
  must be re-derived together (the plan says this in D3 prose, correctly). But the only
  capture is at 1400px, where almost any geometry resolves wide — a too-tight pairing that
  only fails at a 1100–1280px laptop width passes the gate.

**Condition:** the comment-rail ticket AC must (a) assert the wide layout actually engaged
at the target width — e.g. render-smoke a positive marker of wide mode (`body.gutter-on`
is a class the existing code toggles at line 694; assert `body.gutter-on` is present at the
capture width), or measure `#gutter` computed `display`/`left` via CDP — and (b) capture at
an **intermediate** width (~1100–1280px), not only 1400px, so the re-derived `320`/doc-width
pair is proven at the boundary it governs, not just where everything fits. DOM-presence of
`.gcard` alone does not discharge R3.

### C2 (MINOR / condition) — D5 prose is self-contradictory on the mermaid/numberBlocks order it forbids reordering

`docs/process/epics/viewer-dashboard-reskin-plan.md` — **D5**.

The text reads: "renderMermaid() runs **before** numberBlocks()? — verified order in
load() (line 508): numberBlocks() then renderMermaid()." The question clause asserts the
opposite of the verified clause. I checked `viewer.html:508–509`: it is `numberBlocks()`
**then** `await renderMermaid()` — the *second* clause is right, the leading rhetorical
question is wrong and will confuse the implementer about which order the "do not reorder"
constraint is protecting. Since D5's entire point is "do not reorder these," the sentence
that states the order must be unambiguous.

**Condition:** strike the misleading question clause; state flatly "load() runs
numberBlocks() (513) then renderMermaid() (509); the re-skin must not reorder them"
(numbering wraps whatever children exist; mermaid replaces `code.language-mermaid` with a
`.mermaid` div afterward). This is a one-line edit; it is a condition only because the
constraint it documents is load-bearing and currently reads backwards.

### M1 (MINOR) — R1 understates the STALE_S drift: the server TTL is env-overridable, the UI mirrors are hardcoded literals

`docs/process/epics/viewer-dashboard-reskin-plan.md` — **D2 / Risk R1 / Key constraint #2.**

R1 frames the second mirror as an *edit-time* drift risk ("drift would mislabel") and
mitigates with a source-of-truth comment — matching the existing viewer precedent. But
`app.py:58` is `LEASE_TTL_S = float(os.environ.get("MDREVIEW_LEASE_TTL_S", "180"))`: the
server's TTL is **runtime-configurable**, while both UI mirrors are hardcoded `180`. If an
operator sets `MDREVIEW_LEASE_TTL_S` to anything but 180, **both** the viewer and the
new dashboard badge are silently wrong, and no comment catches it. This is a pre-existing
condition the viewer already has; the plan *inherits* it rather than creating it, so it is
not a blocker and the comment-parity mitigation is acceptable for v1.

Worth considering, not required: for a purely cosmetic badge, the dashboard could avoid
introducing a second `STALE_S` literal at all by degrading the badge to the coarse
turn-only test (the inbox bucket already is turn-only per D1, line 121) and dropping the
fresh/stale refinement on the *card*. That removes the second mirror entirely for the
cosmetic surface and keeps the staleness clock in exactly one UI file (the viewer, where
it is functional, not cosmetic). If the freshness refinement on the card is kept, name the
env-override blind spot explicitly in the ticket so it is an accepted risk, not an unstated one.

### N1 (NIT) — the Phase-3 docs-sweep target is largely a phantom

`docs/process/epics/viewer-dashboard-reskin-plan.md` — **Phase 3 / Ticket breakdown row 4.**

The docs-sweep ticket says update README/CLAUDE "where they describe the dashboard's chip
filters." I grepped: there is **no** chip-filter / "Has notes" / "Done" / "Group by project"
description in `README.md` or `CLAUDE.md` (only `README.md:72`, a `meta.json` provenance/
grouping note unrelated to the chip UI). The sweep may legitimately find nothing to edit.
That's fine, but phrase the AC as "grep README/CLAUDE for dashboard-affordance / viewer-UI
references; edit any found; closing condition is the grep, not a mandated edit" so the
ticket doesn't manufacture a doc change to look complete — and so it can close cleanly if
empty (it must be `done` before sprint close per the plan's own G7 note).

## Things I explicitly checked and am NOT flagging

- **D1 lost affordance.** The Project›Session collapsible tree is dropped; the plan records
  it as a non-goal, no API data is lost (project+session+path still render per-card), and
  the user chose "Re-skin + supported IA". Acknowledged correctly, not a silent drop.
- **"Agent working" inbox-vs-badge split (D1 line 121 vs D2).** Coherent: the inbox bucket
  is the coarse turn test (stable count); the card badge refines display via `agent_status`.
  This is intentional and documented, not an inconsistency.
- **Dropped watcher indicator (assumption 3).** Omitted not stubbed; correct — a stubbed
  "connected" dot is a lie with no backing. Matches the requirement's out-of-scope note.
- **Reviewer-side Resolve button (D3).** The mockup's Resolve action is correctly scoped
  out as a behavior change (a human resolving their own thread), not a re-skin. The Resolve
  string appears heavily in the mockup, so this temptation is real and correctly fenced (R6).
- **Ticket sizing.** 4 tickets, viewer optionally split at the comment rail, is right: the
  rail is the highest-risk JS and the split isolates its render-smoke. Not over/under-split.
- **No-new-served-file / Dockerfile COPY tripwire (assumption 6, constraint #7).** Correct;
  inline edits leave `Dockerfile:8` untouched, and the tripwire is named if an asset is extracted.

## Resolution log

- C1 (MAJOR/condition) — comment-rail fit verification proves only `.gcard` presence, not wide-mode engagement at the boundary width: **RESOLVED 2026-06-25 (author).** Strengthened **D3** prose (the `body.gutter-on` marker at `viewer.html:694`, the ~1100–1280px failure band, why `.gcard` cannot distinguish wide-vs-docked), **Risk R3** (now mandates asserting `body.gutter-on` at ~1180px AND 1400px, not `.gcard` at 1400px), and **Verification §3** (added a width-controlled `--dump-dom | grep gutter-on` loop at 1180/1400px + a narrow docked shot, and noted render-smoke's fixed ~800px viewport cannot engage wide mode so `body.gutter-on` is asserted via width-controlled Chrome/CDP, not `render-smoke.sh`). Added an explicit **mandatory AC bullet on the COMMENTS-rail ticket (row 3)** after the ticket table.
- C2 (MINOR/condition) — D5 mermaid/numberBlocks order sentence reads backwards: **RESOLVED 2026-06-25 (author).** Rewrote the **D5** sentence: struck the backwards rhetorical question; now states flatly that `load()` runs `numberBlocks()` (line 508) **then** `await renderMermaid()` (line 509), numbering first / mermaid second, and explains why reordering would skip or double-wrap the mermaid block.
- M1 (MINOR) — R1 understates STALE_S env-override drift (server TTL configurable, UI literals hardcoded): **RESOLVED 2026-06-25 (author) — took the simpler default.** Dropped the dashboard-card freshness check entirely: **D2** badge now uses `agent_status.state === "working"` with **no** `(now − at) <= STALE_S` test, so `dashboard.html` introduces **no** second `STALE_S` mirror; recorded the rationale (dashboard is a glance view, viewer is the authoritative staleness surface, env-overridable `LEASE_TTL_S` makes a hardcoded mirror lie under override, a stale "working" card is an accepted minor cosmetic inaccuracy). Updated **D2 table**, **Risk R1** (now "avoided by design"), **Key constraint #2** (dashboard must NOT introduce `STALE_S`), and **Verification §4** (grep asserts `dashboard.html` has zero `STALE_S`).
- N1 (NIT) — Phase-3 docs-sweep target (chip filters) not present in README/CLAUDE; phrase AC as grep-gated: **RESOLVED 2026-06-25 (author).** Verified by grep: no chip-filter / "Has notes" / "Done" / "Group by project" description exists in `README.md` or `CLAUDE.md` (only unrelated provenance/status/route/exposure mentions, enumerated in the plan). Re-phrased **Phase 3**, the **ticket-table row 4**, and the **execution-order** entry as grep-gated with a clean no-op close as the closing condition, not a mandated edit.
