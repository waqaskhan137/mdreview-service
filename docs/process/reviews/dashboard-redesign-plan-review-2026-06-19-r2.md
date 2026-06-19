---
review_of: epics/dashboard-redesign-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS
status: resolved
---

# G1 review (round 2) — dashboard-redesign plan

**Verdict: PASS.** The one gating condition (SHOULD-1) and the actioned NITs are genuinely
fixed in the plan body, not just logged. The revision is additive — warning text, a risk row, a
required-artifact list, and math annotations — and introduces no new blocker. G1 passes; the epic
can go `active` and MR-031 can be created.

## Confirmation

- **SHOULD-1 (gating) — RESOLVED.** Grepped the plan: every `--force-dark-mode` occurrence (Fork 5
  line 264, Key-constraints line 331, the 4d code-comment line 482, and the two Resolution-log
  lines) is a "do NOT use" warning or explanation — **none is a live capture flag**. The actual
  capture commands (Verification 4d, lines 487/489) use `--blink-settings=preferredColorScheme=0`
  (dark) / `=1` (light). The correct flag is named in all three required places: Verification 4d,
  Fork 5's dark-pane `getComputedStyle` check, and the Key-constraints "Pane-adaptive theme" bullet.
- **NITs — actioned, present in the plan body.** (1) Keyboard a11y parity: Fork 1 Accessibility
  (lines 168–172) requires the Enter/Space keydown handler to apply the identical
  `closest('a, button')` + non-empty-selection guard, with a matching risk row (375). (2) Manually
  captured screenshots: the Required-artifact block (498–505) enumerates all eight as ticket-AC
  deliverables and the G7 gate-mapping (546–548) checks each file exists, a missing one failing the
  close review. (3) 1600px cap tied to the 5-column math (`5×280 + 4×10 + 2×24 ≈ 1488`; 6th needs
  ≈1778) in Fork 2 (215–219), the risk row (379), and A4 (408–410) — arithmetic re-checked, correct.
- **Accepted-no-change NITs (A3, A4, Open-click, one-ticket).** Confirmed fine as-is; the round-1
  rulings stand and the plan already carried the right disposition.

## Residual non-gating note

- Non-blocking, for the implementer: the expanded card "restates the full notes label," which is
  the same `noteLabel()` string already in the collapsed metadata row — near-zero new information.
  The plan and round-1 review already say the AC must not treat the restatement as a hard must-have;
  just don't let it grow into a redundant second badge during build. Carry into MR-031's AC, no
  plan edit needed.

## Resolution log

- **SHOULD-1** (`--force-dark-mode` in Verification 4d) — verified fixed; live capture uses
  `preferredColorScheme=0/1`, the flag this repo already settled
  (`theme-awareness-plan-review-2026-06-18.md`). No remaining live use of the wrong flag.
- **NIT keyboard parity / NIT required-artifact list / NIT 1600px math** — verified present in the
  plan body (Fork 1 + risk row; Required-artifact block + G7 mapping; Fork 2 + A4 + risk row).
- **NIT A3 / A4 / Open-click / one-ticket** — accepted no-change, confirmed correct.
- No new blocker introduced by the revision. Round-1 review
  (`dashboard-redesign-plan-review-2026-06-19.md`) should move `status: open → resolved`; epic
  frontmatter advances to `gate: G1 passed 2026-06-19` / `status: active`. Ticket count unchanged:
  one `ui` ticket, MR-031 (2-ticket split remains the recorded fallback only).
