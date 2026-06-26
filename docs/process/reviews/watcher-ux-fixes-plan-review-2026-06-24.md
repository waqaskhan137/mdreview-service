---
review_of: epics/watcher-ux-fixes-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 independent review — watcher-ux-fixes plan

Scope of this gate: a small 2-ticket batch (MR-062 spinner restore, MR-063 README recipe
reorder). Both designs are decided and product-owner-eyeballed; this review gates
**implementability + validation fidelity**, not the visual or the flag order. I verified the
stash, the four banner-state force recipes against `app.py`, the render-smoke selector contract,
and the README/CLAUDE.md recipe literals against the live tree on `dev`.

**Verdict: PASS-WITH-NITS.** Both tickets are implementable as written and the validation recipes
are runnable. The stash matches the plan exactly and applies cleanly. The README scope is correct
and CLAUDE.md genuinely has no literal to fix (A1 → README-only is the right call). Two
verification examples carry stale literals (a wrong viewer-route path, and a State-C force the
endpoint does not actually support) that the plan already hedges in prose — fixing the examples to
match what I verified would make the recipes copy-pasteable, but neither blocks ticket creation.

## What I verified (the core gate)

- **Stash matches the plan and applies clean.** `git stash apply stash@{0}` applies with no
  conflict on current `dev`; reverted after. The diff is `viewer.html`-only. It removes
  `#turnbanner.working #turntext::after` + `@keyframes turnworking` + the `.working`
  reduced-motion override (current `viewer.html:84-89`), and adds
  `#turnbanner.loading #turntext::before` (11px ring, `border:2px solid var(--muted)`,
  `border-top-color:transparent`, `animation:turnspin .8s linear infinite`),
  `@keyframes turnspin{to{transform:rotate(360deg)}}`, and a reduced-motion static-ring fallback
  via `--muted`. In `renderBanner` it swaps `remove('working')`→`remove('loading')` at the top,
  and adds `loading` in BOTH the `if(!as)` waiting arm AND the working arm, NOT the stale arm nor
  the reviewer branch. Every clause of the plan's UI section and MR-062 AC is faithful to the
  stash. (Cosmetic only: the stash's inline comments are labelled "MR-061", not "MR-062" — a
  carry-over tag in the parked WIP, not a content divergence.)

- **No live code or active smoke references the removed `working` class / `turnworking` keyframe.**
  Every other hit for `turnworking` / `#turnbanner.working` / `::after` is in **history** docs
  (the MR-061 ticket, sprint-21 close review, the cycle retro, sprint-21 evidence) — append-only
  records, correctly untouched. The `state:"working"` strings in `app.py`/`watch.py`/`mcp_server.py`
  are the **lease state**, an unrelated concept from the CSS `.working` class. Nothing strands.

- **Four banner-state force recipes are correct against `app.py`.**
  - State A waiting-for-pickup: `POST /handoff {"to":"agent"}` only — the `to=="agent"` arm
    (app.py:628) sets `agent_status=None` on the reviewer→agent flip, so `if(!as)` fires. Correct.
  - State B working: `POST /handoff {"state":"working","owner":"smoke"}` — the `state=="working"`
    arm (app.py:635) grants on an unset/equal owner and writes `agent_status.state="working"`.
    Correct.
  - State D reviewer: `POST /handoff {"to":"reviewer"}` — note `by` is absent, so this does NOT
    hit the `to=="reviewer" and by=="reviewer"` reclaim arm; with no `state` it falls through to
    the `else` and returns **400 "unrecognized handoff body"**, leaving turn unchanged. The smoke
    that follows (`turn` still agent) would then assert the wrong banner. To force reviewer turn,
    the body must be `{"to":"reviewer","by":"reviewer"}` (the reclaim arm, app.py:616). See nit N3.

- **render-smoke selector contract confirmed.** `scripts/render-smoke.sh` validates selectors with
  `^(#id | tag(.class)* | (.class)+)$`. `.loading` and `div.loading` pass; `#turnbanner.loading`
  is rejected (exit 2) — the plan's `.loading`-not-`#id.class` guidance is exactly right. Absence
  is `.loading` matching 0 nodes → exit 1, and the plan correctly inverts the expected exit AND
  pairs it with a `#turntext` present-check (exit 0) so a vacuous render can't false-pass. Sound.

- **MR-063 scope is correct, A1 holds.** `grep allowedTools/dontAsk/WATCH_LAUNCH_CMD/dangerously`
  finds the three scoped-recipe literals only in `README.md` (`:193`, `:198`, `:208`), all with
  the wrong order `["claude","-p","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","<prompt>"]`
  — `-p` has no argument (immediately followed by `--permission-mode`) and the bare `<prompt>`
  trails the variadic `--allowedTools`, so it is consumed as a tool name. The plan's fix
  (`...,"--allowedTools","mcp__mdreview__*","-p","<prompt>"]`, prompt last) resolves both. The
  full-autonomy recipe at `README.md:217` is already prompt-last (verify-don't-edit — correct).
  `CLAUDE.md:130-138` is prose pointing to the README runbook with **no** recipe literal. The
  plan's grep verification (`'mcp__mdreview__*","-p","<prompt>"'` → 3, `'"-p","--permission-mode"'`
  → 0) is accurate against the current literals.

## A1 recommendation (the one the gate asked for)

**README-only is correct — do NOT add a CLAUDE.md recipe.** I confirmed `CLAUDE.md` contains zero
recipe literals; its watcher paragraph only points to the README runbook. The bug is a
mis-ordered argv that exists in exactly three README spots. Adding a recipe paragraph to CLAUDE.md
would be *additive scope* (a new place to keep in sync, a second source of truth for the same
literal), not a fix — out of scope for a bug-fix ticket. The brief's "both README.md and CLAUDE.md"
is best read as "the recipe as documented," and the recipe is documented only in README. Ship
MR-063 README-only; if the product owner explicitly wants a CLAUDE.md recipe, that is a separate
additive ticket, not part of GH #25.

## Findings

### Blocking
None. The stash is faithful and applies clean; the validation is runnable; no recipe spot is
missed; no selector hits the render-smoke compound-rejection; no force recipe targets a
non-existent endpoint (the State-D body is a real endpoint, just the wrong arm — a copy-paste
example bug, not a design defect; see N3).

### Worth considering
- **N1 — viewer route in the smoke example is wrong (`/r/{id}` does not exist).** Step 2 sets
  `VIEW="$BASE/r/$id"`, but the only viewer-serving route in `app.py` is `/review/{id}`
  (app.py:805; `review_url` is `{base}/review/{rid}`, app.py:526). Copied verbatim the smoke
  404s. The plan hedges this as A3 ("resolve the route at smoke time"), but the answer is already
  knowable now: pin `VIEW="$BASE/review/$id"` and close A3. Cheap, removes a foot-gun for the
  implementer.

### Nits
- **N2 — State C (stale) cannot be forced via the handoff body; only the TTL wait works.** A2 and
  step 5 suggest "set `agent_status.at` to an old epoch via the handoff body." I checked: the
  handoff endpoint never reads `at` from the body — every successful write stamps `at = now`
  (app.py:626, :633, :660). So back-dating is impossible; the only live force is to wait out
  `LEASE_TTL_S` (default 180s) on the throwaway box (which the plan lists as the fallback). Drop
  the "age via body" option and state plainly: State C = claim a lease (State B), then sleep >180s,
  then assert `.loading` absent / `#turntext` present. (Or, if a 180s sleep in the smoke is
  unwelcome, make State C a code-inspection note — the `>STALE_S` arm at viewer.html:241 adds no
  `loading` class, which is statically obvious from the stash — and keep A/B/D as the live render
  assertions.) Either is fine; the "forced-old `at`" path is not.
- **N3 — State D reviewer-turn force is missing `by:"reviewer"`.** `{"to":"reviewer"}` alone hits
  the `else` 400 arm and does not flip the turn (app.py:616 requires `to=="reviewer" AND
  by=="reviewer"` for reclaim; `to=="reviewer" AND state in (done,blocked)` is the hand-back arm).
  Use `{"to":"reviewer","by":"reviewer"}` to force the reviewer turn. Without it the State-D
  assertion runs against an unchanged (still-agent) banner and the result is meaningless.
- **N4 — reduced-motion probe target is correct.** Confirming the gate's check: the spinner is on
  `::before` in the stash, and step 7 probes `getComputedStyle($("#turntext"),'::before')` — right
  pseudo-element (the old MR-061 probe targeted `::after`; this plan correctly updates it). No
  change needed; flagged only because the gate asked.

## Open questions for the author
- Does the product owner want any CLAUDE.md recipe text at all, or is the README the single
  documented home for the recipe? (My recommendation: README-only; raise only if they say
  otherwise.) — A1.
- Will the State-C live assertion accept a ~180s sleep in the smoke, or should State C be a
  code-inspection note instead? — N2.

## What's good (load-bearing)
The plan correctly internalised this codebase's two render-smoke footguns — the compound-selector
rejection (`.loading`, not `#turnbanner.loading`) and the exit-1-on-absence inversion paired with a
present-check — which are exactly the traps that have burned prior UI sprints here. That, plus the
faithful stash pinning and the correct README-only scoping, is why this is a PASS and not a
rewrite. The remaining nits are stale copy-paste literals in the example commands, not design
gaps.

## Resolution log
- 2026-06-24 staff-critic (independent): PASS-WITH-NITS. Stash verified faithful + applies clean;
  4-state force recipes checked against app.py; render-smoke selector/exit contract confirmed;
  README 3-spot scope + A1 README-only confirmed; CLAUDE.md has no literal. Nits N1/N2/N3 are
  stale example literals (wrong `/r/` route, un-forceable State-C `at`, missing `by:"reviewer"`),
  none blocking. Recommendation: pin `/review/{id}`, fix the two force-recipe examples, then spawn
  MR-062/MR-063. Status: open (awaiting author reconciliation of the nits).

## Resolution log

- 2026-06-24 — Independent G1 review (2-ticket batch). Verdict PASS-WITH-NITS; both designs approved.
  Verified: the MR-062 spinner stash (`stash@{0}`) is faithful + applies clean on dev (viewer.html only,
  removes the MR-061 pulse, adds the `.loading` `::before` spinner in both waiting arms, reduced-motion
  static ring, `--muted` theme); nothing else references the removed `working`/`turnworking`; MR-063 is
  README-only (CLAUDE.md has no recipe literal — A1 README-only confirmed) at README:193/198/208, full-
  autonomy recipe already prompt-last. Four nits, all in the MR-062 smoke recipe.
- 2026-06-24 — Planner revised (author preserved). Folded: N1 — smoke route fixed to `/review/{id}`;
  N2 — dropped the impossible live stale-state assertion (handoff always stamps `at=now`, can't
  back-date), now verified by code inspection of the stale arm (adds no `loading`) + State D's live
  render of the same removed-not-re-added path; N3 — State D reviewer flip uses the reclaim arm
  `{to:reviewer,by:reviewer}` (the bare `{to:reviewer}` 400s and never flips); N4 confirmed (probe
  targets `::before`). No second G1 round needed (smoke-recipe fixes, not design). **G1 PASS.**
