---
epic: process-hardening
status: draft          # draft | active | done  (stays draft until G1 passes)
created: 2026-06-08
source: requirements/process-hardening.md
gate: G1 not passed
review:
related_sprints: []
related_tickets: []
---

# Process Hardening Plan

The first delivery cycle (`review-dashboard`, sprint-01) shipped cleanly but exercised only half
the new process machinery: G7's render-smoke earned its keep by catching a container-packaging bug,
while G1's planner-then-critic loop was never run on a real plan, and the cycle retrospective
surfaced six concrete hardening suggestions. This epic applies those six suggestions to the
**delivery process itself** — the docs under `docs/process/`, the `feature-cycle` skill, and the
`mdreview-planner` agent — so the next product cycle inherits a tighter validation bar and a
sharper planner. It changes **no product behavior** (`app.py`, `viewer.html`, `dashboard.html` are
untouched).

**Source requirement:** [`requirements/process-hardening.md`](../requirements/process-hardening.md)
— the six verbatim retrospective suggestions, kept verbatim.

## Product goal

The "done" state: every suggestion in the brief is durably resolved in the process artifacts, so a
future cycle does not re-improvise the same calls.

1. A `ui`-ticket cannot pass G4 on a local-file render alone — it must rebuild the image and assert
   the expected DOM nodes exist, via a single canonical, reusable check (suggestions 1 + 2).
2. The G1 planner-then-staff-critic loop has been exercised on a real plan (suggestion 3 — see
   "Suggestion 3 is discharged by this epic" below).
3. The Definition of Done and the docs-sweep pattern no longer contradict each other; the README
   states one resolution unambiguously (suggestion 4).
4. The `mdreview-planner` agent carries a fit-based-layout rule and a Dockerfile-COPY footgun, so
   it stops emitting hard-coded breakpoints and remembers that a new served file needs a Dockerfile
   edit (suggestions 5 + 6).

## Core design principle

**The README is the single source of truth for the gates; the skill and the agent point at it,
never restate it.** (`SKILL.md:17-18`: "This skill does **not** redefine the gates — it
executes them.") Every change here lands the *rule* in exactly one place and makes the other
surfaces reference it, so the process cannot drift between README, skill, and agent. The concrete
expression of this principle is suggestions 1+2: the render-smoke command lives in one executable
script (`scripts/render-smoke.sh`), and both `README.md` Development-flow step 5 and
`references/03-implement.md` step 4 point at that script rather than each spelling out a
`chrome --dump-dom | grep` invocation that would inevitably diverge.

## Assumptions & open questions

I am invoked autonomously and proceed on the assumptions below. None is a BLOCKER-FOR-HUMAN: every
one has a safe default, and the brief itself (`requirements/process-hardening.md`) pre-decides the
contested ones.

- **(load-bearing) Suggestions 1+2 become a standing rule *and* a reusable script, not a rule
  alone.** Assumption: add `scripts/render-smoke.sh <url> <css-selector...>` (the only canonical
  copy of the `chrome --headless --dump-dom | grep -q` invocation), then rewrite the two
  `ui`-validation bullets (`README.md:117-118`, `references/03-implement.md:18-20`) to call it.
  Justification: the rule otherwise has to be spelled out in both files and they will drift; one
  script is the single-source-of-truth expression of the core principle.

- **(load-bearing) Suggestion 4 is resolved by *blessing* a bounded same-sprint docs-sweep, not by
  forbidding sweeps.** Assumption: the README DoD permits a ticket to defer durable docs to a
  trailing docs-sweep ticket **within the same sprint**, provided the deferring ticket names the
  sweep ticket in its Work log and G7 does not pass with stale docs. Justification: the brief's own
  two options (`requirements/process-hardening.md:30-33`) are *both* forms of blessing the sweep;
  the brief is the contract. The gate that actually enforces docs accuracy is G7 (sprint close),
  not per-commit, so per-sprint-close accuracy is consistent with the repo-as-source-of-truth
  philosophy. **This is the decision I am least sure about** — see Risks.

- **(load-bearing) Suggestion 3 is discharged by this epic's own G1 review; it gets no ticket.**
  Assumption: this plan going through the `mdreview-planner`-authors / `staff-critic`-reviews G1
  path IS the deliberate exercise the retrospective asked for, so I create no "exercise the loop"
  ticket (a process-act ticket has nothing to validate). Justification: a verifiable discharge
  (the recorded G1 review file) beats an unverifiable commitment ticket. A one-line note in the
  skill that both gate rails are now exercised is optional polish, folded into the skill ticket.

- **(minor) Where the two planner footguns attach.** Assumption: the Dockerfile-COPY footgun
  becomes a new numbered item in the planner's footgun list (after `mdreview-planner.md:56`); the
  fit-based-layout rule attaches to footgun 6 (JS-rendered surfaces, `mdreview-planner.md:51-52`)
  and to the verification guidance in Method step 4 (`mdreview-planner.md:80-81`). Justification:
  both are additive, default-safe edits to standing instructions.

- **(minor) The script targets the published container port, 8137.** Assumption: `render-smoke.sh`
  is documented to run against the rebuilt container's published port (`SKILL.md:107`,
  `references/04-close-and-ship.md:8-11` already standardize `localhost:8137`), not a local file.
  Justification: the whole point of suggestion 1 is to surface packaging gaps at the ticket.

## Recommended approach

All edits are documentation/tooling. There is no `app.py` or `viewer.html` change. The work splits
by artifact rather than by service/UI.

### Tooling (`scripts/render-smoke.sh`) — `infra`

- New executable `scripts/render-smoke.sh <url> <css-selector>...`. It drives headless Chrome
  (`--headless --dump-dom <url>`), then asserts each supplied selector's expected node text is
  present in the dumped DOM. Stdlib/system-tool only — Chrome is already the render tool the
  process uses; **no new pip/runtime dependency** (footgun: stdlib-only, zero installs).
- Contract: every selector found -> exit 0; any selector absent -> nonzero exit + a clear message
  naming the missing selector. The script must target a served URL (the rebuilt container's
  published port), never a `file://` path, so the Dockerfile-COPY class of bug surfaces here.
- It must **fail loud** if no Chrome binary is found (detect `google-chrome` / `chromium` /
  `Google Chrome` and error with the lookup it tried), not silently pass.
- This is the only ticket with a genuinely runnable check beyond reading the diff: run it against a
  rebuilt container and confirm a present selector exits 0 and a bogus selector exits nonzero.

### Process (`docs/process/README.md`) — `docs`

- **Suggestion 1+2** — rewrite Development-flow step 5 (`README.md:117-118`) so the `ui` clause
  reads: rebuild + serve from the **published container port** (`docker compose up -d --build`),
  then run `scripts/render-smoke.sh <url> <selector...>` asserting the expected nodes
  (e.g. `.gcard`, `mark.cmt`) — "a screenshot proves first-paint only; a 200 is not a render."
  Mirror the same bar into the G4 row of the Gates table if needed for consistency, without
  redefining the gate.
- **Suggestion 4** — amend the Definition of Done (`README.md:131-135`) and the G5 row
  (`README.md:156`). Exact wording to add: durable behavior docs ship in the same change **or** are
  deferred to a trailing **docs-sweep ticket within the same sprint**; a deferring ticket must name
  its sweep ticket in its Work log, and **G7 (sprint close) does not pass with stale docs.** This
  blesses the MR-001 -> MR-007 pattern the retrospective flagged
  (`requirements/process-hardening.md:30-33`) while keeping accuracy enforced at sprint close.

### Skill (`.claude/skills/feature-cycle/`) — `docs`

- **Suggestion 1+2** — in `references/03-implement.md` step 4 `ui` bullet
  (`references/03-implement.md:18-20`), replace the prose "open it in a browser" bar with: rebuild
  + serve, then `scripts/render-smoke.sh` against the published port asserting the expected nodes.
  Point at the README rule rather than restating the gate (core principle).
- **Suggestion 3 (optional polish)** — one line in `references/01-plan-and-critique.md` Phase 2 (or
  a SKILL note) recording that both gate rails (G1 planner<->critic and G7 render-smoke) have now
  been exercised on real artifacts. This is not the discharge — the discharge is this epic's own G1
  review — so it is folded in here, not a standalone ticket.

### Agent (`.claude/agents/mdreview-planner.md`) — `docs`

- **Suggestion 5** — fit-based-layout rule: amend footgun 6 (`mdreview-planner.md:51-52`) and the
  verification guidance in Method step 4 (`mdreview-planner.md:80-81`) so the planner specifies
  responsive **behavior** ("show the gutter only when it physically fits the viewport"), never a
  pixel breakpoint it has not computed. Cite the sprint-01 lesson: a ~820px threshold was
  geometrically wrong (a 284px gutter cannot fit at 820px) and was reconciled to a fit-based test
  at G7 (`sprint-01-close-review-2026-06-08.md:28-34`, `:57-61`).
- **Suggestion 6** — Dockerfile-COPY footgun: add a new numbered footgun after
  `mdreview-planner.md:56`: a new root-level served file (a sibling of `viewer.html` /
  `dashboard.html`) needs a matching `COPY` in the `Dockerfile` (today `Dockerfile:8`,
  `COPY app.py viewer.html dashboard.html ./`); the `ui` ticket that adds the asset **must carry
  that infra change**, or the rebuilt container serves an empty 200 (the sprint-01 bug, commit
  `1326462`, `review-dashboard-cycle-retro-2026-06-08.md:18-21`).

> **Suggestion 3 is discharged by this epic.** This plan being authored by `mdreview-planner` and
> reviewed independently by `staff-critic` at G1 **is** the deliberate exercise of the novel rail
> the retrospective asked for. No ticket is created for suggestion 3.

## Rollout phases

Each phase is independently shippable. Phases are ordered by dependency, not by suggestion number.

### Phase 1 — Planner agent edits (suggestions 5 + 6)

Pure additive edits to `mdreview-planner.md`. Zero dependencies on the other work; can ship first
and immediately sharpens any future plan. Validation: read-diff only (no script, no `py_compile`).

### Phase 2 — Render-smoke script + standing rule (suggestions 1 + 2)

`scripts/render-smoke.sh` lands first (it is the canonical command), then the README and skill
bullets are rewritten to call it. The docs-rule ticket `depends_on` the script ticket. Validation:
the script ticket has a real runnable smoke; the docs ticket is read-diff.

### Phase 3 — DoD / docs-sweep reconciliation (suggestion 4)

README-only wording change to the DoD + G5 row. Independent of Phases 1-2. Validation: read-diff.

> **Suggestion 3** rides this epic's own G1 review and is not a phase.

## Non-goals

- **Not** re-running or re-reviewing the `review-dashboard` (sprint-01) feature work; it is shipped
  and closed.
- **Not** changing any product behavior: `app.py`, `viewer.html`, `dashboard.html`, and
  `static/**` are untouched.
- **Not** restructuring the gates G0-G8 or the status lifecycle — suggestion 4 changes only DoD/G5
  *wording*, not the gate set.
- **Not** creating tickets, opening a sprint, or implementing (the orchestrator does that after
  G1).
- **Not** adding a test framework or any new pip/runtime dependency; the render-smoke script uses
  the Chrome binary the process already relies on.
- **Not** automating the staff-critic G1 loop further — suggestion 3 is satisfied by exercising the
  existing loop, not by building new machinery.

## Key constraints (process footguns made specific)

- **G1 independence (author != reviewer).** This plan is authored by `mdreview-planner`; its G1
  review must be by `staff-critic` or the product owner, never the author (`README.md:152`,
  `:165-167`). Revisions after review are made by the planner (still the author), preserving
  independence.
- **The verbatim brief is never edited.** `requirements/process-hardening.md` is the record;
  grooming and decisions live in this plan, not by rewriting the brief (`README.md:54-60`). Changes
  to the requirement, if any, go under its `## Amendments`.
- **The README is the single source of truth for gates; the skill executes, never redefines.**
  (`SKILL.md:17-18`, `README.md:199-200`.) Every rule here lands in one place and is referenced
  elsewhere.
- **Editing README here is legitimate** precisely because it goes through a normal reviewed `docs`
  ticket. The SKILL autonomy note forbids editing the README *to dodge a gate* (`SKILL.md`
  "Autonomy posture"), not editing it via a reviewed ticket.
- **No new runtime/pip dependency.** `render-smoke.sh` shells out to the existing Chrome render
  tool; nothing is installed (stdlib-only ethos).
- **Back-compat / additive.** Planner footgun edits are additive; the README DoD change widens
  (blesses) an existing pattern rather than invalidating closed tickets like MR-001.
- **Dates are `Europe/London`** in every process file touched.

## Preferred execution order

1. Phase 1 — planner edits (suggestions 5 + 6); no dependencies.
2. Phase 2a — `scripts/render-smoke.sh` (`infra`); the canonical command must exist before docs
   reference it.
3. Phase 2b — README + skill `ui`-validation rewrite (suggestions 1 + 2); `depends_on` 2a.
4. Phase 3 — README DoD / docs-sweep wording (suggestion 4); independent, can run any time after
   Phase 1.

(Phases 1 and 3 are mutually independent and may be reordered; Phase 2b is the only ticket with a
hard `depends_on`.)

## Ticket breakdown

How this epic decomposes into tickets (create them in `tickets/` after G1, then link here). IDs are
placeholders; the orchestrator allocates the real sequential `MR-###`.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-### | Planner agent: fit-based-layout rule + Dockerfile-COPY footgun (sug 5+6) | docs | 1 |
| MR-### | Add `scripts/render-smoke.sh <url> <selector...>` DOM-node assertion (sug 1+2) | infra | 2 |
| MR-### | README + skill: rebuild-from-image + render-smoke as the `ui` validation bar (sug 1+2) | docs | 2 |
| MR-### | README: reconcile DoD with bounded same-sprint docs-sweep (sug 4) | docs | 3 |

Suggestion 3 has no ticket — it is discharged by this epic's own G1 staff-critic review.

## Risks & mitigations

- **Chrome-path fragility in `render-smoke.sh`.** The render tool's binary name/location varies
  across machines (`google-chrome`, `chromium`, macOS `Google Chrome`). *Mitigation:* the script
  probes a known list and **fails loud** with the paths it tried; it never silently exits 0 when
  Chrome is missing (that would reintroduce the "200 is not a render" class of false pass).
- **Suggestion 4's blessed sweep could become a habitual docs-debt loophole** (the decision I am
  least sure about). *Mitigation:* the wording bounds it hard — same sprint only, the deferring
  ticket must name the sweep ticket in its Work log, and **G7 will not pass with stale docs**, so
  the debt is force-closed at sprint close, not carried across cycles. If the product owner instead
  prefers "docs in the same change, no sweeps," that is a one-line wording flip in the same ticket;
  flagging here so the G1 reviewer can overrule cheaply.
- **README/skill drift on the render-smoke command.** *Mitigation:* the core principle — one
  canonical command in `render-smoke.sh`, both docs reference it — is exactly what removes the drift
  surface. Reviewers should reject any future restatement of the raw `chrome --dump-dom` line.
- **Planner edits could over-specify and become stale.** *Mitigation:* suggestion 5's rule is
  deliberately behavioral ("show the gutter only when it physically fits"), carrying no pixel value
  that could go stale.

## Verification

This epic ships docs + one script; most tickets validate by reading the diff against the cited
anchors. Concrete, runnable checks:

- **`scripts/render-smoke.sh` ticket (the real smoke):**
  1. Rebuild and serve: `docker compose up -d --build`; confirm `curl -s localhost:8137/healthz`
     returns `{"ok":true}`.
  2. Present selector passes: run against a page with a selector known to render there
     (e.g. a dashboard-card class on `/`, or `.gcard` on `/review/<id>` — the ticket confirms
     which selector lives on which page from the UI files):
     `scripts/render-smoke.sh http://localhost:8137/ <known-selector> ; echo "exit=$?"` ->
     prints `exit=0`.
  3. Absent selector fails loud:
     `scripts/render-smoke.sh http://localhost:8137/ .does-not-exist ; echo "exit=$?"` -> nonzero
     exit and a message naming the missing selector.
  4. Missing-Chrome path fails loud (temporarily shadow the binary or run where Chrome is absent):
     the script errors with the lookup paths it tried, exit nonzero — it does **not** print
     `exit=0`.
  - No `python3 -m py_compile app.py` is required: `app.py` is untouched. (If a reviewer wants it
    as a no-op sanity check, it still passes since the file is unchanged.)

- **Planner agent ticket (sug 5+6):** confirm `mdreview-planner.md` now (a) has a new
  Dockerfile-COPY footgun after the existing footgun list, citing that a new root-level served file
  needs a `Dockerfile COPY` and the `ui` ticket must carry it; and (b) states the fit-based-layout
  rule in footgun 6 and Method step 4. Read-diff; no code execution.

- **README + skill `ui`-bar ticket (sug 1+2):** confirm `README.md:117-118` and
  `references/03-implement.md:18-20` both now require rebuild-from-image + `scripts/render-smoke.sh`
  against the published port and reference (not restate) the rule. Grep both files for
  `render-smoke.sh` -> present in both. Read-diff.

- **README DoD ticket (sug 4):** confirm the DoD (`README.md:131-135`) and G5 row (`README.md:156`)
  now permit a bounded same-sprint docs-sweep with the Work-log-naming requirement and the
  "G7 does not pass with stale docs" clause. Read-diff.

- **Epic-level (suggestion 3):** the existence of an independent G1 review file
  `reviews/process-hardening-plan-review-2026-06-08.md` (reviewer != `mdreview-planner`,
  `independent: true`) is itself the evidence that the planner<->critic rail was exercised.
