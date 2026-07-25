# Night run — decision log (2026-07-25 → morning 2026-07-26)

Sprint: **sprint-34** (#176–#182), epic #152.
Plan: https://app.mdreview.space/review/d3b3487540 — critic-cleared in 3 rounds, owner-approved.
Worktree: `.claude/worktrees/design-system`. Owner asleep; no approvals available until morning.

---

## The ceiling: G4, not "sprint done"

`docs/process/README.md` puts three gates behind the owner, and none of them can be self-served:

| gate | needs | tonight |
|---|---|---|
| **G5** Done (`review` → closed) | **owner approval** | ✗ — issues land at `status:review`, none closed |
| **G7** Sprint close | independent close review + `evidence/sprint-34/` committed | ✗ |
| **G8** Promote to main | **explicit owner go-ahead** | ✗ — nothing goes near `main` |

So the night run's deliverable is: **every sprint-34 ticket at `status:review`, merged to `dev`, with evidence in an issue comment**, ready for a single morning pass of G5 acks. Merging to `dev` is inside the working agreement (dev takes PRs, 0 approvals, self-merge OK) and matches the 2026-07-23 run's precedent.

---

## Decisions taken before starting — review these

### D1 · Nothing is closed, nothing reaches `main`
Above. If every ticket succeeds the morning state is seven issues at `status:review` and a `dev` that is seven PRs ahead. The sprint stays open.

### D2 · One ticket in progress at a time, branch-per-ticket off `dev`
G3 says one in-progress at a time. Each ticket gets its own branch cut fresh from `origin/dev`, its own PR, self-merged, then the next branch cuts from the updated `dev`. No stacking — a stack means one bad ticket blocks six.

### D3 · Order is the plan's, unchanged
#177 → #178 → #179 → #180 → #181 → #182. #182 (`dashboard.html`) stays last because it is contended with another agent's work. **Not reordered forward, not pulled early even if I finish ahead of schedule.**

### D4 · Contention rule for #182
Before starting it: `git fetch` and diff `dashboard.html` on `origin/dev` against what I planned from. If another agent has touched that file since 7193c88, I **stop and park #182** at `status:blocked` with the diff in a comment rather than merge on top of work I did not read. Losing one ticket is cheaper than silently clobbering someone.

### D5 · Verification runs against a throwaway container, never the live instance
The live instance on **:8139** is not touched, and `docker compose up` is never run (compose says 8137 and would fight it). Each verification spins a throwaway container on a free port against a scratch `MDREVIEW_DATA` dir under `.scratch/`, and tears it down. Tools: `tests/render-smoke.sh` for R2's functional-DOM assertions, `scripts/cdp-shot.mjs --resize --eval` for computed-style and breakpoint checks.

### D6 · `.empty` takes **control-8**, not card-12
The plan leaves this to the implementer. Choosing 8: `.empty` is Basecoat's empty-state block, which on our pages sits *inside* a container rather than being one, and §04 draws it as flush content, not as a raised card. It also keeps it consistent with `.alert`, the other `--radius-lg` consumer we actually use. Recorded in #177's PR description.

### D7 · `--r-panel` is not retired tonight
#177 ships it unconditionally (§02 declares "16 · panels"). #180 records whether `.sharepop` wants it; #183 (⌘K, **not in this sprint**) would record `.command`. Since the second consumer's ticket is out of the milestone, **no ticket tonight is the last one to touch it**, so nothing removes it. An unused token is harmless; a token removed before its second consumer is evaluated is a bug.

### D8 · A ticket that cannot meet its AC is parked, not forced
`status:blocked` + a comment saying exactly which criterion failed and what I tried. I do not weaken an acceptance criterion to make it pass — those were fought over across three critic rounds and are the main thing standing between this sprint and a silent breakage.

### D9 · Scope is frozen at the seven sprint tickets
#183 and #184 are deliberately outside the milestone; #185 and #186 are deferred by owner decision. **I do not pull any of them in**, even if the sprint finishes early. Changing sprint scope is the owner's call, and "we had time" is not a reason.

### D10 · Tactical calls go to `user-proxy`; its hard-escalation list means park
Low-stakes implementation choices get decided. Anything on the proxy's escalation list — design changes, new dependencies, scope changes, secrets, gate decisions — is parked with a note, not guessed at.

### D11 · Realistic expectation
Six code tickets, each with a real verification gate, is optimistic for one unattended run. **#177–#179 are the confident set**; #180's 63-literal conversion is wide and its R3 breakpoint check is fiddly; #182 is large, contended, and mostly hand CSS. If the run ends partway, it ends on a merged ticket with the next one untouched, never mid-edit.

---

## What is deliberately NOT touched

- The **seven issues already at `status:review`** awaiting the owner's G5 (#86, #88, #136, #75, #78, #44, #15) — not mine.
- **`sprint-32` / `sprint-33`**, both open with zero open issues pending a G7 close review. Flagged, not actioned; G7 needs an independent reviewer.
- **#163**, the one drift violation (no `status:` label). Adding a label is a triage decision on someone else's bug.
- `docs/process/epics/viewer-dashboard-reskin-plan.md` — frozen archive, marker lives on #152 (done in #176).
- `web/site/`, any backend or API change, `main`.

---

## Run-time decisions

Appended as the run proceeds. Each entry: ticket, decision, why, and what would falsify it.

### #176 · Reskin epic superseded — DONE, `status:review`
Completed before the run began. #152 retitled off the stale "Next.js + shadcn" framing (original preserved in a collapsed `<details>`), Adopted section added recording the predecessor epic and carrying its R2/R3/R7 forward as gates, child task list wired, dated amendment comment posted. `docs/process/` unmodified, as required.

**Correction recorded:** the plan's §1a said that epic's viewer half had not shipped. It had — `viewer.html` carries the breadcrumb, `body.gutter-on` (`:648`), `#dock` (`:255`) and `#resolved` (`:262`), and sprint-28 closed under a recorded G7. So §1a shrank from "reconcile live work" to "write the marker". Two further citation errors found at the same time: `scripts/render-smoke.sh` is `tests/render-smoke.sh`, and the `gutter-on` toggle is `viewer.html:648`, not `:694`. Errata posted to the review.
