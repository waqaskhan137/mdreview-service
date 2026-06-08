---
id: MR-010
title: README + skill — rebuild-from-image + render-smoke as the ui validation bar (G4 row)
status: done
layer: docs
priority: P1
sprint: sprint-02
epic: process-hardening
depends_on: [MR-009]
branch: dev (small/solo change)
created: 2026-06-08
updated: 2026-06-08
---

## Goal

Wire the render-smoke into the gate that actually enforces it, so a `ui` ticket cannot pass G4
on a local-file render. (Retro suggestions 1 + 2; resolves G1 finding B1c.)

## Acceptance criteria

- [ ] `README.md`: the **G4 pass-condition row** requires, for `ui` tickets,
      a rebuild-from-image render + `scripts/render-smoke.sh` against the published container
      port asserting the expected nodes. The requirement is scoped **explicitly to `ui` tickets**
      (so `infra`/`docs` tickets are not read as needing it, matching how the G4 row already
      special-cases `docker build` "for infra"). References the rule/script once; does not
      restate the raw command. The old "mirror into G4 if needed" hedge is gone.
- [ ] `README.md` Development-flow step 5 `ui` clause points at `scripts/render-smoke.sh` (the
      canonical command), not a re-spelled `chrome --dump-dom` invocation.
- [ ] `.claude/skills/feature-cycle/references/03-implement.md` `ui` bullet references the same
      README rule / script rather than restating the gate (single source of truth).
- [ ] Both `README.md` and `references/03-implement.md` contain `render-smoke.sh`; neither
      restates the raw Chrome invocation.
- [ ] Validation: read-diff; `grep render-smoke.sh` present in both files.

## Notes / context

Plan: `epics/process-hardening-plan.md` (Process + Skill sections). Depends on MR-009 (the script
must exist before docs reference it). G1 review B1c + the non-blocking scope note:
`reviews/process-hardening-plan-review-2026-06-08.md`.

## Work log

- `2026-06-09` — `README.md`: the **G4 pass-condition row** now requires, for `ui` tickets, a
  render-smoke from the rebuilt image (`scripts/render-smoke.sh`), scoped explicitly to `ui`
  (mirrors how the row special-cases `docker build` "for infra"); the old "if needed" hedge is
  gone. Development-flow step 5 `ui` clause points at the script. `.claude/skills/feature-cycle/
  references/03-implement.md` `ui` bullet references the README G4 rule / the script ("run it, do
  not restate it") instead of "open it in a browser". Single canonical command; no raw Chrome
  invocation restated.

## Validation

- `2026-06-09` — read-diff. `grep render-smoke.sh`: README 2 (step 5 + G4 row), 03-implement 1;
  `grep dump-dom`: 0 in both (no restated raw command); G4 row scopes the smoke to `ui` tickets
  explicitly; the "mirror into G4 if needed" hedge is removed.

## Follow-ups

None.
