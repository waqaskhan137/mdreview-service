---
epic: watcher-ux-fixes
status: done           # shipped: MR-062 + MR-063 (sprint-22), G7 PASS 2026-06-24
created: 2026-06-24
source: requirements/watcher-ux-fixes.md
gate: passed 2026-06-24
review: reviews/watcher-ux-fixes-plan-review-2026-06-24.md (PASS-WITH-NITS — both designs approved)
related_sprints: [sprint-22]
related_tickets: [MR-062, MR-063]
---

# Watcher UX fixes Plan

A small two-ticket batch cleaning up rough edges the product owner hit while testing the watcher
end-to-end live. Both fixes are **already designed and validated** — one is implemented and sitting
in a git stash, the other is a verified one-line reorder. This plan exists to clear **G1** (gate the
implementability + validation, not re-open the designs) so the two tickets can be created and shipped
in one sprint (sprint-22). It deliberately does **not** re-derive either design.

**Source requirement:** [`requirements/watcher-ux-fixes.md`](../requirements/watcher-ux-fixes.md) —
the original brief, kept verbatim.

## Product goal

The watcher (`watch.py` + the viewer's turn baton) is usable end-to-end without two specific snags:

1. A reviewer who pressed **Send to agent** sees an **unambiguous, visible "loading" affordance** in
   *both* agent-turn waiting moments — the "waiting for an agent to pick this up" window and the
   "Agent is working…" window — instead of MR-061's too-subtle pulse that only animated the narrow
   working state.
2. The documented watcher launch recipe **actually runs**: the scoped `WATCH_LAUNCH_CMD` recipe in
   the README no longer mis-orders `--allowedTools` so it swallows the `-p` prompt, and the README
   says why (GH #25 closes).

"Done" at the epic level: MR-062's spinner is restored from stash, re-validated by a render-smoke
from a rebuilt throwaway container, and supersedes MR-061; MR-063's README recipe is reordered
prompt-last with the variadic note; sprint-22 closes at G7.

## Core design principle

**Proportionate restore-and-verify, not redesign.** Both designs are decided and product-owner-
eyeballed. The risk this plan must retire is *implementation + validation fidelity*: that the stash
restores cleanly onto the right lines, that the spinner asserts correctly in a flat DOM matcher, and
that the recipe edit lands on every literal occurrence. Everything below is scoped to make those
checkable, not to revisit the visual or the flag order.

## Recommended approach

### Service (`app.py`)

No service change. `app.py` is untouched by either ticket. The MR-062 render-smoke *drives* the
service's existing `POST /api/reviews/{id}/handoff` endpoint to force the banner states, and MR-063
runs `py_compile app.py` only as an unchanged-sanity gate.

### UI (`viewer.html`)

**MR-062 (ui) — restore the stashed spinner; supersede MR-061.** The change is already implemented,
product-owner-eyeballed, deployed to :8139, and parked in
`stash@{0}` (`git stash list` → `"spinner-wip (MR-062): rotating spinner on both agent-turn waiting
states, replaces MR-061 pulse"`). Implementation = **restore the stash onto the MR-062 branch and
re-validate**, not re-author. The stash touches `viewer.html` only, at these pinned spots:

- **CSS, MR-061 block at `viewer.html:84–89`.** Remove MR-061's opacity-pulse:
  `#turnbanner.working #turntext::after` (`viewer.html:87`), the `@keyframes turnworking` (`:88`),
  and the reduced-motion override scoped to `.working` (`:89`), plus the MR-061 comment (`:84–86`).
  Add the rotating spinner: `#turnbanner.loading #turntext::before` — an 11px ring,
  `border:2px solid var(--muted)` with `border-top-color:transparent`,
  `animation:turnspin .8s linear infinite`; `@keyframes turnspin{to{transform:rotate(360deg)}}`; and
  `@media (prefers-reduced-motion:reduce)` showing a **static ring** (animation removed, ring
  visible). Colour via `--muted` so it reads on both panes.
- **`renderBanner` at `viewer.html:232–255`.** The class the banner toggles moves from `working` to
  `loading`, and is added in **both** agent-turn waiting arms:
  - `viewer.html:237` `bar.classList.remove('working')` → remove `loading` at the top.
  - `viewer.html:240`, the `if(!as)` "Sent — waiting for an agent to pick this up." arm → **add**
    `bar.classList.add('loading')`.
  - `viewer.html:242`, the genuine "Agent is working…" arm → add `loading` (was `working`).
  - `viewer.html:241`, the stale "Agent may have stopped" arm → **no** `loading` class (unchanged).
  - reviewer-turn branch (`viewel.html:245–252`) → no `loading` class (unchanged).

  The exact diff is whatever the stash contains; the implementer restores it rather than retyping it.
  These line numbers are the *current* anchors to confirm the stash applies to the right region; if
  the stash conflicts (it was taken on `dev`, same tree), resolve toward the stash's intent above.

MR-062 **supersedes MR-061** — the pulse and `turnworking` keyframes are deleted, not kept alongside.

No new served file is introduced (the spinner is inline CSS in `viewer.html`, already in the
`Dockerfile COPY`), so **no infra/`Dockerfile` change is owed**.

### Docs (`README.md`)

**MR-063 (docs) — fix the scoped watcher recipe arg order (GH #25).** `--allowedTools` is variadic
(a space-separated tool list), so a trailing `<prompt>` after `mcp__mdreview__*` is swallowed as
another tool name and `claude -p` dies with "Input must be provided … when using --print". The fix
(runtime-verified `exit 0`): move `-p "<prompt>"` to **last**, after the variadic flag:

`["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]`

**Exact recipe spots to fix (enumerated from the current tree).** All three scoped-recipe literals
live in **`README.md`** — the "Watcher (optional) — operator runbook" section:

| File:line | Context | Action |
|-----------|---------|--------|
| `README.md:193` | trusted-base / loopback example `WATCH_LAUNCH_CMD=…` | reorder prompt-last |
| `README.md:198` | non-loopback (`WATCH_TRUSTED_BASE`) example | reorder prompt-last |
| `README.md:208` | "Scoped / recommended" recipe literal in the recipes list | reorder prompt-last |

Plus add the one-line note next to the scoped recipe (at `README.md:208`'s bullet): *"`--allowedTools`
is variadic — keep `-p "<prompt>"` last so the prompt isn't consumed as a tool name."*

**`CLAUDE.md` carries no scoped-recipe literal to fix.** Its watcher paragraph (`CLAUDE.md:130–139`)
is prose that *points to* the README runbook ("See README **\"Watcher (optional) — operator
runbook\"**…") and contains no `--allowedTools` recipe. The grep (`allowedTools`/`dontAsk`) returns
only the README literals above. So this ticket is **README-only**; see the assumption below
reconciling the brief's "fix both README.md and CLAUDE.md" wording.

**Full-autonomy recipe is already correct** (`README.md:217`):
`["claude","--dangerously-skip-permissions","-p","<prompt>"]` — prompt already last. **Verify, don't
edit.**

## Rollout phases

One phase. Both tickets are independent (no `depends_on` between them), small, and ship together in
**sprint-22**.

### Phase 1 — sprint-22 (the batch)
- MR-062 (ui): restore stash, re-validate (render-smoke + reduced-motion probe + both-pane shots).
- MR-063 (docs): reorder the three README recipe literals prompt-last + variadic note; verify the
  full-autonomy recipe; `py_compile` sanity + grep confirmation.

## Non-goals

- **No redesign of either fix.** The spinner geometry/colour and the recipe flag order are decided
  and validated; this plan gates restore + verification, not the design.
- **No `app.py` / service change.** Neither ticket touches the server.
- **No new served file / no `Dockerfile` change** (the spinner is inline `viewer.html` CSS).
- **The rest of GH #27** (behind-the-scenes progress steps; streamed/diff-animated document updates)
  stays in #27.
- **Watcher observability / resilience** (watcher exiting on server restart instead of backing off)
  stays in #26.
- **`CLAUDE.md` recipe rewrite** — it has no recipe literal; not in scope (see assumption A1).

## Key constraints

The project footguns this batch must respect:

- **Stdlib-only, zero pip.** Neither ticket adds a runtime dependency. The spinner is hand-written
  inline CSS in `viewer.html` (a single ring + keyframe), not a vendored asset — acceptable because
  it is ~5 lines, not a library, and there is no upstream file to pin for "a CSS spinner".
- **Single-file viewer; no new served file.** The spinner is inline in `viewer.html`, already in the
  `Dockerfile COPY` (`Dockerfile:8`, `COPY app.py viewer.html dashboard.html ./`). **No
  infra change is owed** — explicitly noted so the ui ticket does not silently strand an asset (the
  sprint-01 `1326462` bug applies only when a *new sibling file* is served; it is not triggered here).
- **JS-rendered surface; a 200 is not a render.** MR-062 verification renders the page from a
  **rebuilt throwaway container** and asserts the DOM class, never a curl 200. The banner is rendered
  by `renderBanner` from the `/status` body, so the smoke must first drive the service into each turn
  state (via `POST …/handoff`) before dumping the DOM.
- **render-smoke is a flat matcher.** Selectors are `tag` / `.class` / `tag.class[.class…]` / `#id`
  only — **no `#id.class` combination, no descendant combinators**. The banner is
  `<div id="turnbanner" class="turnbanner show loading">`, so assert the loading state with **`.loading`**
  (or `div.loading`), **not** `#turnbanner.loading` (rejected as bad usage, exit 2). Assert absence by
  the selector matching **0 nodes** (render-smoke exit 1 on 0 — so an absence check inverts the
  expected exit; see Verification).
- **Pane-adaptive screenshots: emulate `prefers-color-scheme`, never `--force-dark-mode`.** The
  spinner colours via `--muted`, which differs per pane. Capture the dark pane with
  `--blink-settings=preferredColorScheme=0` and the light pane with `=1` (or CDP
  `Emulation.setEmulatedMedia`). **Do not** use `--force-dark-mode` (Chrome's auto-invert, not scheme
  emulation) and do not rely on a bare-headless "light" shot (bare headless resolves *dark* by
  default, so both panes would come out wrong and the both-pane proof would be vacuous).
- **Reduced-motion is behaviour, not a screenshot.** Probe the computed `animationName` on the
  pseudo-element via CDP, not by eye: `none` under `prefers-reduced-motion: reduce`, `turnspin`
  without it.
- **HEAD 501 / GET header-dumps.** Not applicable here (no header/MIME assertion in either ticket);
  noted for completeness so a verification author does not reach for `curl -sI`.
- **No `docker compose up`; scratch ports only.** The render-smoke container is a throwaway
  `docker run` on a **scratch port (e.g. 8765), never 8139 (live) or 8137 (compose)**, preserving the
  live instance. Smoke working files go in the **in-project `.scratch/`**, never `/tmp`; evidence is
  then moved to `reviews/sprint-22-render-evidence-2026-06-24/`.
- **Dates `Europe/London`; commits keep the `Co-Authored-By: Claude` trailer + ticket ID.**

## Preferred execution order

1. **MR-063 (docs)** first — trivial, no dependency, retires GH #25 immediately. (Order is a
   convenience; the two are independent and may land in either order.)
2. **MR-062 (ui)** — restore stash, re-validate, evidence under
   `reviews/sprint-22-render-evidence-2026-06-24/`.

## Ticket breakdown

Create these in `tickets/` **after G1**. Next free ID is **MR-062** (highest existing is MR-061,
verified via `ls docs/process/tickets/`); MR-063 follows.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-062 | Replace MR-061 pulse with a rotating spinner on both agent-turn waiting states (restore stash) | ui | 1 |
| MR-063 | Fix the scoped watcher launch recipe arg order — `-p` prompt last (GH #25) | docs | 1 |

### MR-062 acceptance criteria (ui)

- The stash `stash@{0}` ("spinner-wip (MR-062)…") is restored onto the MR-062 branch; `viewer.html`
  is the only file changed.
- MR-061's `#turnbanner.working #turntext::after` opacity-pulse, `@keyframes turnworking`, and its
  `.working` reduced-motion override are **removed** (pulse superseded).
- The spinner `#turnbanner.loading #turntext::before` exists with the pinned properties (11px ring,
  `border:2px solid var(--muted)`, `border-top-color:transparent`,
  `animation:turnspin .8s linear infinite`); `@keyframes turnspin{to{transform:rotate(360deg)}}`
  exists; `@media (prefers-reduced-motion:reduce)` renders a **static** ring (no spin).
- `renderBanner` adds the `loading` class in the `if(!as)` "waiting for pickup" arm **and** the
  "Agent is working…" arm, and **not** in the stale arm nor on a reviewer turn.
- Validation: see the **MR-062 verification** below — render-smoke present in States A/B and absent in
  State D (live), State C verified by code inspection of the stale arm (not force-stampable), plus a
  reduced-motion CDP probe + both-pane scheme-emulated screenshots, from a rebuilt throwaway image on a
  scratch port. Evidence under `reviews/sprint-22-render-evidence-2026-06-24/`.

### MR-063 acceptance criteria (docs)

- The three scoped-recipe literals at `README.md:193`, `README.md:198`, `README.md:208` are reordered
  to `["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]`
  (prompt **last**).
- A one-line note is added by the scoped recipe: "`--allowedTools` is variadic — keep `-p
  \"<prompt>\"` last so the prompt isn't consumed as a tool name."
- The full-autonomy recipe (`README.md:217`) is **confirmed already prompt-last** (unchanged).
- No `CLAUDE.md` recipe literal exists, so `CLAUDE.md` is unchanged (assumption A1).
- Validation: `python3 -m py_compile app.py` passes (unchanged sanity); a grep confirms every scoped
  recipe now ends `…,"mcp__mdreview__*","-p","<prompt>"]` and no occurrence has `"-p"` before
  `"--allowedTools"`. GH #25 closes when the PR is updated.

## Risks + mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Stash conflicts on restore (taken on `dev`, tree may have moved). | Low | Same branch lineage; if it conflicts, resolve toward the pinned intent in the UI section (the exact lines are documented above). |
| AC author writes `#turnbanner.loading` and render-smoke exits 2 (bad usage). | Medium | Verification below pins **`.loading`** / `div.loading`; the `#id.class` form is called out as rejected. |
| Absence check mis-asserted (render-smoke exits 1 on 0 nodes). | Medium | Verification inverts the expected exit for the State D live absence check and shows the exact invocation; State C is code-inspection, not a smoke. |
| Both-pane screenshots vacuous (bare headless = dark; `--force-dark-mode` ≠ emulation). | Medium | Verification mandates `--blink-settings=preferredColorScheme=0/1`, forbids `--force-dark-mode`. |
| MR-063 misses an occurrence (3 literals, easy to fix 2 of 3). | Low | Enumerated table of all three `README.md` line spots; grep-confirm AC counts them. |
| Brief says "fix both README.md and CLAUDE.md" but CLAUDE has no literal. | n/a | Recorded as assumption A1: README-only; flag at review if the product owner intended new CLAUDE prose. |

## Verification

### MR-062 (ui) — render-smoke from a rebuilt throwaway container

Run all smokes against a **rebuilt throwaway image on a scratch port (e.g. 8765), never 8139/8137,
never `docker compose up`**; working files in **`.scratch/`**; move evidence to
`reviews/sprint-22-render-evidence-2026-06-24/`.

1. **Build + run scratch container** (illustrative; pin the actual port the implementer picks):
   ```bash
   docker build -t mdreview-mr062 .
   docker run -d --name mr062-smoke -p 8765:8080 mdreview-mr062
   BASE=http://localhost:8765
   ```
2. **Create a review and capture its id/viewer url:**
   ```bash
   id=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
     -d '{"title":"spinner smoke","markdown":"# x\n\nbody\n"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
   VIEW="$BASE/review/$id"   # the only viewer route is /review/{id} (app.py route(), GET /review/{id} -> viewer HTML)
   ```
3. **State A — "waiting for pickup"** (`turn=agent`, `agent_status` null): force with
   `POST …/handoff {"to":"agent"}` **only** (do not claim a lease):
   ```bash
   curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' -d '{"to":"agent"}'
   scripts/render-smoke.sh "$VIEW" '.loading' '#turntext'      # expect exit 0 — spinner PRESENT
   ```
4. **State B — "Agent is working…"** (`turn=agent`, fresh lease): claim the lease, then assert:
   ```bash
   curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' \
     -d '{"state":"working","owner":"smoke"}'
   scripts/render-smoke.sh "$VIEW" '.loading' '#turntext'      # expect exit 0 — spinner PRESENT
   ```
5. **State C — stale** ("Agent may have stopped"): **verify by code inspection, not a live render.**
   The stale state **cannot be force-stamped** through the handoff endpoint: the only arm that writes
   `agent_status` from a smoke is `{state:"working"}`, which **always** stamps `at = now`
   (`app.py:660`) and never reads an incoming `at`, so there is no way to back-date the heartbeat. The
   only ways to reach the live stale banner are to wait out the 180s `STALE_S` (too slow for a smoke)
   or not at all — so this state is **not** asserted by render. Instead:
   - **Inspect the stale arm of `renderBanner`:** it is the `else if((Date.now()/1000-(as.at||0))>STALE_S)`
     branch (`viewer.html:241`), which sets only `msg` and **adds no class** — provably it does **not**
     `add('loading')`. The top-of-function `remove('loading')` therefore leaves `.loading` off.
   - **The `.loading`-absent code path is already exercised live by State D.** `renderBanner` removes
     `loading` once at the top of the function and re-adds it **only** in the two agent-turn waiting
     arms (`if(!as)` and the genuine "working" `else`); the stale arm and the reviewer-turn branch both
     leave it off. State D's live reviewer-turn render (above) drives exactly the "loading removed and
     not re-added" path, so `.loading` absence is proven by a real render there **plus** this stale-arm
     inspection — without a 180s TTL wait.

   No `render-smoke` invocation is listed for State C: its assertion is the inspection above, signed
   off in the evidence notes (cite `viewer.html:241` post-stash), not a DOM dump.
6. **State D — reviewer turn** (`turn=reviewer`): reclaim the turn, then assert spinner absent.
   Use the **reclaim arm** `{"to":"reviewer","by":"reviewer"}` — a bare `{"to":"reviewer"}` hits the
   400 `else` arm and does **not** flip the turn (`app.py:616` vs `app.py:664`):
   ```bash
   curl -s -X POST "$BASE/api/reviews/$id/handoff" -H 'Content-Type: application/json' \
     -d '{"to":"reviewer","by":"reviewer"}'
   scripts/render-smoke.sh "$VIEW" '.loading' >/dev/null; test $? -eq 1   # spinner ABSENT (PASS)
   scripts/render-smoke.sh "$VIEW" '#turntext'                            # banner present
   ```
   This is the live render that proves the spinner leaves the DOM: the reviewer turn takes
   `renderBanner`'s `else` branch (`viewer.html:245`), which runs the top-of-function
   `remove('loading')` and re-adds **no** class — the same "loading removed and not re-added" code
   path the stale arm relies on (see State C).
   > Selector note: assert the loading **class** with `.loading` (or `div.loading`). The banner is
   > `<div id="turnbanner" class="turnbanner show loading">`; render-smoke's flat matcher does **not**
   > support `#turnbanner.loading` (it rejects `#id` carrying a class as bad usage, exit 2). Absence
   > is `.loading` matching **0 nodes**, which render-smoke reports as **exit 1** — so an absence
   > check passes when the smoke exits 1 (inverted), as shown above.

7. **Reduced-motion CDP probe** (computed style, not a screenshot). With Chrome emulating
   `prefers-reduced-motion: reduce` (CDP `Emulation.setEmulatedMedia` features
   `[{name:'prefers-reduced-motion',value:'reduce'}]`, or `--blink-settings` equivalent), read the
   pseudo-element's animation in State A or B:
   `getComputedStyle($("#turntext"),'::before').animationName` → **`none`** under reduce, **`turnspin`**
   without reduce. Record both outcomes. (The probe correctly targets `::before`: the spinner moved
   from MR-061's `::after` to `::before` in this stash — confirmed at G1 review.)

8. **Both-pane screenshots** (first-paint sanity, in State B so the spinner is on):
   - dark pane: `--blink-settings=preferredColorScheme=0`
   - light pane: `--blink-settings=preferredColorScheme=1`

   **Never `--force-dark-mode`** (auto-invert, not scheme emulation) and never a bare-headless
   "light" shot (bare headless resolves dark by default). Save both under
   `reviews/sprint-22-render-evidence-2026-06-24/`.

9. **Teardown:** `docker rm -f mr062-smoke`.

| State | How forced | `.loading` | Expected smoke result |
|-------|------------|-----------|------------------------|
| A waiting-for-pickup | `handoff {to:agent}`, no lease | present | exit 0 |
| B agent working | `handoff {state:working,owner:smoke}` | present | exit 0 |
| C stale | not force-stampable — `{state:working}` always stamps `at=now` (`app.py:660`) | absent | **code inspection** (`viewer.html:241` adds no class) + State D's live `.loading`-absent render; no smoke invocation |
| D reviewer turn | `handoff {to:reviewer,by:reviewer}` (reclaim arm) | absent | exit 1 on `.loading`, exit 0 on `#turntext` |

### MR-063 (docs) — py_compile sanity + grep confirmation

```bash
python3 -m py_compile app.py     # unchanged sanity (no code touched) → exit 0

# every scoped recipe now ends prompt-last; no occurrence has -p before --allowedTools:
grep -n 'mcp__mdreview__\*","-p","<prompt>"' README.md      # 3 hits (lines were 193,198,208)
grep -n '"-p","--permission-mode"' README.md                # 0 hits (old wrong order gone)
grep -n 'allowedTools is variadic' README.md                # 1 hit (the note)

# full-autonomy recipe unchanged + already prompt-last:
grep -n 'dangerously-skip-permissions","-p","<prompt>"' README.md   # 1 hit (README:217)

# CLAUDE.md carries no recipe literal (confirm it stays clean):
grep -n 'allowedTools' CLAUDE.md                            # 0 hits
```

GH #25 closes when the standing `dev → main` PR is updated.

## Assumptions & open questions

Recorded; proceeding on each (no BLOCKER-FOR-HUMAN — neither has a sprint-wasting fork).

- **A1 (load-bearing, safe default chosen). The brief says "fix BOTH the scoped recipe in
  `README.md` and `CLAUDE.md`," but `CLAUDE.md` contains no recipe literal.** Verified: `grep
  allowedTools/dontAsk CLAUDE.md` returns only the prose pointer at `CLAUDE.md:130–139` ("See README
  … operator runbook"), no `WATCH_LAUNCH_CMD` array. The three scoped-recipe literals are all in
  `README.md` (`:193`, `:198`, `:208`). **Assumption:** the brief's "both files" refers to the README
  being the only place the recipe is *written*, and MR-063 is **README-only**; `CLAUDE.md` needs no
  change. Justification: there is nothing to reorder in `CLAUDE.md`, and inventing a recipe there
  would *add* surface, not fix a bug. Flag at G1 review if the product owner actually wants a new
  CLAUDE.md recipe paragraph (that would be additive scope, not a fix).
- **A2 (resolved at G1). State C (stale) is verified by code inspection, not render.** Confirmed
  against `app.py`: the only smoke-writable arm (`{state:"working"}`) always stamps `at = now`
  (`app.py:660`) and never reads an incoming `at`, so the stale heartbeat cannot be force-stamped, and
  a 180s `STALE_S` wait is too slow for a smoke. **Resolution:** drop the live State-C render
  assertion; verify the stale case by inspecting that `renderBanner`'s stale arm (`viewer.html:241`)
  adds no `loading` class, and lean on State D's live render for the "loading removed and not re-added"
  code path. Same DOM outcome, no TTL wait. (See Verification step 5.)
- **A3 (resolved at G1, no longer open). The viewer path used as the render-smoke URL is
  `/review/{id}`.** Confirmed against `app.py` `route()` (`GET /review/{id}` -> viewer HTML,
  `app.py:24` doc-table and the `re.fullmatch(r"/review/" + RID, …)` at `app.py:805`). The smoke uses
  `VIEW="$BASE/review/$id"`; there is no `/r/{id}` route.
- **A4 (minor). Scratch port for the throwaway container.** **Assumption:** any free non-8139/8137
  port (8765 used illustratively). Justification: the only hard rule is "never the live/compose
  ports."

## Review resolutions

Independent staff-critic G1 review
[`reviews/watcher-ux-fixes-plan-review-2026-06-24.md`](../reviews/watcher-ux-fixes-plan-review-2026-06-24.md)
returned **PASS-WITH-NITS** — both designs approved (the stash is faithful; MR-063 README-only scope
confirmed). The nits were all in the MR-062 render-smoke **recipe** (so the ticket author doesn't
write a smoke that 404s or can't run); resolved 2026-06-24:

- **N1 (viewer route).** The smoke used `$BASE/r/$id`, but the only viewer route is `/review/{id}`
  (`app.py:805`, `re.fullmatch(r"/review/" + RID, …)`; doc-table `app.py:24`). **Fixed:** the smoke now
  sets `VIEW="$BASE/review/$id"`; A3 reclassified from open question to a confirmed fact.
- **N2 (stale state can't be force-stamped).** State C tried to back-date `agent_status.at` via the
  handoff body — impossible: the `{state:"working"}` arm always stamps `at = now` (`app.py:660`) and
  never reads an incoming `at`, and the 180s `STALE_S` wait is too slow for a smoke. **Fixed:** dropped
  the live State-C render assertion; State C is now verified by **code inspection** of the stale arm
  (`renderBanner` `else if(…>STALE_S)`, `viewer.html:241`, adds no class) plus State D's live render
  exercising the same "loading removed and not re-added" path. Updated verification step 5, the state
  table row C, the AC validation line, and assumption A2.
- **N3 (reviewer flip body).** State D used `{"to":"reviewer"}`, which hits the 400 `else` arm
  (`app.py:664`) and does not flip the turn. **Fixed:** State D now posts the reclaim arm
  `{"to":"reviewer","by":"reviewer"}` (`app.py:616`), so the turn actually returns to the reviewer and
  the banner leaves the loading state; updated step 6 and the state table row D.
- **N4 (reduced-motion probe).** Confirmed correct — the probe targets `::before`, matching the
  spinner's move from MR-061's `::after` to `::before`. Noted as confirmed in verification step 7; no
  change needed.
