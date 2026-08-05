# Run contract: epic #276 — mdreview Polish (design rev 3)

**This file is the instruction set for the autonomous run.** The loop invocation points here and
nothing else, so the contract cannot drift with a re-typed prompt. Read it in full before acting.

It is the CONTRACT, not the state. Mutable state lives in the run log named below. Change this file
only with the owner's agreement; append a dated note when you do.

- Process: `docs/process/autonomous-run.md` (stages, gates, hard rules) — this file narrows it, never overrides it.
- Epic: **#276**. Spine + settled scope decisions: <https://app.mdreview.space/review/dc9e45abe9>
- Design source of truth: claude.ai/design project `38238604`, `mdreview Polish.dc.html` **rev 3**
  (a theme specification: a 13-token contract plus five screens, each in light and dark).
- Run log (state, decisions, errors): `docs/process/runs/2026-07-30-epic-276-polish.md`.

---

## 1. Scope

**Build (5, in this order):**

| Order | Ticket | Why here |
|---|---|---|
| 1 | **#277** tokens + self-hosted fonts | Blocks every visual ticket. Runs SOLO and merges before anything else is cut. |
| 2 | **#278** dashboard (incl. sign-in state, visible heading, "Waiting on you", hover-reveal rows) | |
| 3 | **#279** viewer + floating open-comments dock | |
| 4 | **#280** LaTeX viewer + comments-off rail state | Zoom is OUT (no design coverage). |
| 5 | **#285** theme toggle (light/dark/auto, persisted) | LAST: it rewrites `theme.css` again, and it unlocks the dark sweep. |

**Do NOT build (6):** #281 #282 #283 #284 #286 #287 — `status:blocked`, blocked on design coverage,
their screens exist only in the superseded rev 2. Each cycle, cheaply re-read the design file; if a
blocked ticket's screens have appeared, groom and queue it. Otherwise leave it blocked. **Never build
one of these from the rev-2 mock.**

**Standing scope decisions — settled, do not re-litigate:** the shipped Recompile button stays
despite its absence from rev 3 (a design omission does not remove a shipped feature); admin verb
stays Ban/Unban; fonts are self-hosted, never a CDN.

---

## 2. Phases

**Phase 0 — groom, in parallel.** Five subagents, one per ticket, concurrently. Each verifies its
ticket against `origin/dev` AND design rev 3, and returns a verdict. A ticket enters the run only on
READY/GO. The one structural question — the token contract's names vs shipped `theme.css`
(`--surface`≈`--panel`, `--border`≈`--rule`, `--accent`≈`--brand`, `--text-muted`≈`--muted-fg`,
`--text-subtle`≈`--muted2`, `--code-bg`≈`--inset`, `--accent-muted`≈`--accent-bg`; `--surface-raised`
is new) — goes to the **product-owner**, whose answer is binding and logged.

**Phase 1 — #277 solo.** Implement, merge, adopt. Its check is the token-literal audit: the
contract's rule is *"identical DOM in both themes; only these values change — no component declares
a literal"*, so extend `tests/css_tokens_selfcheck.js` to assert no first-party literal colour
survives, and that every contract token resolves in both themes.

**Phase 2 — #278 / #279 / #280 built in PARALLEL, merged SERIALLY.** Three subagents, three
worktrees, all cut from a `dev` that already carries #277. Zero file contention between them
(`dashboard.html`, `viewer.html`, `latex-viewer.html`). Merge one at a time, one adoption window
each, so every staging digest is attributable to exactly one ticket.

**Phase 3 — #285 solo.** Merge, adopt.

**Phase 4 — the dark sweep (main agent, real browser).** Only possible after #285: before it, dark
is OS-driven and unreachable. On staging, for each of the five surfaces: click the toggle, screenshot
both themes, and verify the **computed** token values against the contract table — not by eye. This
is where "identical DOM, token-swap only" is proven end to end.

---

## 3. Worktree isolation — the main agent's job, and it is absolute

Two agents in one worktree clobber each other. This has bitten this project before. The rule is
mechanical, not trust-based:

1. **The main agent creates every worktree itself, before spawning**, at `.scratch/wt-<ticket>` on
   branch `<type>/<ticket>-<slug>`, cut from current `origin/dev`. A subagent never chooses or
   creates either.
2. **Each subagent's prompt names exactly one worktree path and one branch** as the only place it
   may read or write.
3. **No subagent may** touch another agent's worktree or branch, run `git checkout` / `switch` /
   `branch` / `worktree` at all, or write anywhere in the repo-root checkout.
4. **Verify before and after.** Before spawning: `git worktree list`. After each returns: its
   branch's diff must contain only files assigned to that ticket.
5. **A diff touching an unassigned file is a finding.** Discard the work, re-run the subagent with
   the violation named. Do not untangle it by hand and do not merge it.

Spawn every subagent with `model: fable` and `isolation: worktree`.

---

## 4. Division of labour — keep the main context clean

**Subagents do the reading and writing.** Grooming passes and implementations. Each returns a diff
summary, its check, and its mutation-test results — not file dumps.

**The main agent does not implement.** It orchestrates, reviews each returned diff, judges whether
each check actually bites, merges, records digests, watches adoption, and owns **all** stage-8
browser verification (the Chrome extension lives in the main session, so this is not delegable).

---

## 5. Decision authority

- **product-owner is the owner's proxy for every decision through dev and staging**, including the
  token-naming question. Its answer is binding; log it with what would falsify it.
- **Only two things stop for the owner personally:** `dev -> main` promotion, and mutating
  production data. Prod is another agent's; hands off.
- Never re-ready the blocked pool (#236 #235 #113 #215). Never guess at the parked questions
  (#96 risk posture, #114/#116 sequencing, #66 scope).

---

## 6. Standing rules — earned in the 2026-07-28/29 runs, carried verbatim

- **Assert the rendered outcome, never the presence of a declaration.** A CSS-text regex passed for
  two days while the palette was never full-screen (#265). Geometry and computed style, not source
  greps.
- **Mutation-test every check.** A check that stays green when the rule is gutted is not a check,
  and a crash is not a catch. Prove the mutation is semantic.
- **Stage 6:** record the staging `.deployed-digest` BEFORE merging. An empty or failed read stops
  the run before the merge — unevaluable is not the same as true.
- **Stage 7 needs BOTH halves:** CI concluded for your merge SHA **and** the digest moved off the
  recorded value. A move while your CI runs is someone else's build: re-baseline.
- **Stage 8 is the claude-in-chrome extension only. No headless, ever. Never a constructed
  `KeyboardEvent`.** The only evidence a key arrived is a `keydown` observed in the page; the tool
  reports success either way. Real key delivery needs Chrome **frontmost** — overnight it will not
  be, so park `no-key-delivery` after three bounded attempts and put it on the morning residue list.
  Verify the throwaway click target with `elementFromPoint`; a click that lands on a link navigates
  away and looks like key failure.
- **Viewport:** close all tabs -> `createIfEmpty` -> resize -> THEN navigate. Budget two attempts;
  attempt one often lands maximised. The requested width is a request, the measured `innerWidth` is
  the fact. Measured floor on this display: 606px.
- **Motion cannot be verified by screenshot** — automation tabs are backgrounded and CSS animation
  freezes. Use computed `animationName`/`currentTime` under CDP emulated media. Any new motion ships
  its `prefers-reduced-motion` fallback in the same change (standing rule, epic #152, homed in
  `docs/design/design-system-spec.md`).
- **Never weaken an acceptance criterion** to make a ticket green — that is a finding, filed as its
  own issue.
- **Never close a ticket** (G5 is the owner's). Stop at `status:review`.
- **Driver:** fixed-interval `CronCreate`. Never a dynamic-mode `ScheduleWakeup` — one-shots
  silently vanish.
- **Temp files** go in `.scratch/` inside the project, never `/tmp` or a session scratchpad.
- **Record your own errors explicitly** in the run log, with what would falsify the diagnosis.

---

## 7. Ending the run

Stop when the five are at `status:review` and the dark sweep is done, or when nothing can advance.
Then: post the scorecard on epic #276, write the run log's final block, stop the cron driver, and
report — evidence per ticket, the decision log, findings filed, and the **morning residue list**
(anything parked, with the seconds-long human action each needs).
