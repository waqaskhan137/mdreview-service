---
id: MR-090
title: Docs sweep — update README / CLAUDE for the re-skinned dashboard & viewer affordances
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: docs            # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-28
epic: viewer-dashboard-reskin
depends_on: [MR-087, MR-088, MR-089]
branch:                # MR-090-docs-sweep, once work starts
created: 2026-06-25
updated: 2026-06-25
---

## Goal

After both screens land, sweep `README.md` / `CLAUDE.md` for any description of the dashboard's old
filter model or viewer affordances that the re-skin changed, and bring them in line with the shipped
reality. **Grep-gated:** the epic's N1 finding verified no chip-filter description exists today, so
this ticket may close as a clean **no-op** if grep finds nothing to update — it documents reality, it
does not mandate an edit. This ticket is NOT carry-over-eligible (a docs-sweep must be `done` before
sprint close, per G7).

## Acceptance criteria

- [ ] Grep `README.md` + `CLAUDE.md` for the enumerated terms and update any that misdescribe the
      shipped UI: `chip`, `Has notes`, `Group by project`, `grouped`, dashboard "filter(s)",
      and any viewer affordance text (the "agent watcher · connected" indicator was dropped; the
      sidebar Inbox replaced the chips). If a match describes the OLD behavior, fix it; if no match
      describes changed behavior, record that the sweep was a verified no-op in the Work log.
- [ ] If any user-facing behavior changed in a way the docs assert (e.g. the dashboard now filters by
      turn-baton inbox, not chips), the doc reflects it. The dropped watcher indicator is not
      documented as present.
- [ ] No stale screenshot/claim about the dashboard/viewer look remains that the re-skin invalidated
      (verify any `site/`-independent doc references; the landing `demo.png` is out of scope).
- [ ] Local validation passes: `python3 -m py_compile app.py` (docs-only, but the gate requires it
      green). No render-smoke (no product page touched by THIS ticket).

## Notes / context

- Epic plan: N1 resolution (grep-verified no chip-filter text in README/CLAUDE as of 2026-06-25 —
  only unrelated provenance/status/route/exposure mentions); Phase 3 (grep-gated sweep).
- Depends on MR-087/088/089 so it documents the shipped reality, not the plan.
- Definition of Done: a docs-sweep ticket is force-closed before sprint close, never carried across
  cycles (process G7 / Definition of Done).

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

None expected.
