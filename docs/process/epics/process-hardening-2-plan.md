---
epic: process-hardening-2
status: draft          # draft | active | done  (stays draft until G1 passes)
created: 2026-06-09
source: requirements/process-hardening-2.md
gate: G1 not passed    # G1 (Plan Gate): not passed | passed YYYY-MM-DD — tickets blocked until passed
review:                # reviews/process-hardening-2-plan-review-YYYY-MM-DD.md once reviewed
related_sprints: []
related_tickets: []
---

# Process Hardening 2 Plan

The `process-hardening` cycle (sprint-02) ran cleanly — the first real G1 planner<->critic loop
caught five blockers before any ticket existed — but its retrospective surfaced one *recurring*
class of friction that survived two cycles: new rules keep landing in prose / DoD / G5 instead of
the gate pass-condition row that enforces them, and line-number anchors into process docs keep going
stale (off by ~7 here after the README grew). This epic applies the four retrospective suggestions
that target that class. It tightens **the delivery process itself** — the `mdreview-planner` agent's
standing instructions, the README's gate/citation conventions, and the `feature-cycle` skill's close
step — so the next cycle inherits a sharper planner and a self-reconciling close. It changes **no
product behavior**: `app.py`, `viewer.html`, `dashboard.html`, and `static/**` are untouched, and
this epic ships **no code** (every ticket is `layer: docs`).

**Source requirement:** [`requirements/process-hardening-2.md`](../requirements/process-hardening-2.md)
— the four verbatim retrospective suggestions, kept verbatim.

> **Dogfooding note (this plan practices suggestions 1 + 2).** Per suggestion 2, this plan cites
> gates and process sections **by name** (e.g. "the **G7** pass-condition row", "the **Definition of
> Done** section", "the **Reviews (gate evidence)** section") and contains **zero `README.md:NNN`
> line anchors**. Per suggestion 1, every rule this plan proposes names the gate row that enforces
> it. Line numbers are reserved for code citations (there are none here, since this epic touches no
> code).

## Product goal

The "done" state: every suggestion in the brief is durably resolved in the process artifacts, so the
next cycle does not re-improvise the same calls.

1. The `mdreview-planner` agent carries a standing rule that **every new rule must be placed in the
   enforcing gate pass-condition row**, and that any DoD / prose / G5 restatement is a non-enforcing
   pointer (suggestion 1). This pre-empts the whole G1-blocker class from last cycle.
2. The `mdreview-planner` agent carries a standing rule to **cite gates and process sections by
   name, not by line number**, with line numbers reserved for code citations (suggestion 2 — agent
   half). The README's **Reviews (gate evidence)** section states the same as a one-line project
   convention (suggestion 2 — process half).
3. The `feature-cycle` skill's close step **reconciles the board to reality before the G7 critic is
   spawned** — all committed tickets `done`, sprint checkboxes checked, TRACKER rows moved — so the
   independent G7 reviewer spends its budget on substance, not bookkeeping (suggestion 3).
4. The **G7** pass-condition row states explicitly that the render-smoke + screenshot requirement is
   **conditional on a product page being touched**, so a docs/infra-only sprint is not read as
   non-compliant for shipping no page screenshots (suggestion 4).

## Core design principle

**Land each rule in the one surface that enforces it, and make every other mention point at that
surface by name.** This is the same single-source-of-truth principle the README and skill already
follow ("This skill does **not** redefine the gates — it executes them", `SKILL.md` **feature-cycle
— orchestrator** intro) — but turned on the *meta-process*. Suggestion 1 makes "name the enforcing
gate row" a standing planner rule; suggestion 2 makes "reference by name, not by brittle line
number" the citation form so those references survive document growth; suggestions 3 and 4 fix the
two surfaces (skill close step, **G7** row) where the enforcement and the reality had drifted. Every
edit is additive and default-safe: it sharpens a standing instruction or clarifies a pass-condition
without changing the gate set, the lifecycle, or any product behavior.

## Assumptions & open questions

I am invoked autonomously and proceed on the assumptions below. **No BLOCKER-FOR-HUMAN items** —
every decision has a safe default, and the brief pre-decides the contested ones.

- **(load-bearing) Suggestion 3's pre-G7 rail reconciles only board-reflects-reality state, NOT
  `close_review`.** Assumption: the new pre-critic checklist covers items that exist *before* the
  critic runs — every committed ticket is `done`, the sprint's committed-ticket checkboxes are
  checked, and TRACKER rows are moved to match ticket frontmatter. It does **not** set
  `close_review:` or `status: closed` or write the retro — those stay in **Phase 8 — second critic
  pass + close** (`references/04-close-and-ship.md`), because `close_review:` names the review file
  the critic *produces*; it cannot exist before the critic is spawned. Justification: the close
  reference's **Phase 8** already sets `close_review:` and `status: closed` on resolution, after the
  G7 critic resolves; a pre-critic checklist that told the orchestrator to "set `close_review`"
  would be self-contradictory. The retrospective's own phrasing — "reconcile ticket statuses, sprint
  checkboxes, and `close_review`" (suggestion 3) — lists `close_review` as a *thing the close step
  owns*, and the safe reading is: the rail ensures the *board* is reconciled before the critic, and
  the existing Phase 8 still owns `close_review`. **This is the decision I am least sure about** —
  see Risks; the G1 reviewer can cheaply confirm the scoping.

- **(load-bearing) Suggestion 2 is in scope in BOTH the agent and the README.** Assumption:
  suggestion 2's `[process] + [agent]` tag means it lands in two surfaces — a standing rule in the
  `mdreview-planner` agent (cite by name; reserve line numbers for code) and a one-line citation
  convention in the README's **Reviews (gate evidence)** section so the convention is not only in the
  agent's private instructions. Justification: the brief explicitly double-tags it `[process]` +
  `[agent]`; a convention that lives only in one agent's prompt is invisible to a future
  human/reviewer reading the process docs. The README note is small (one sentence) — recommend
  **yes, in scope**. This pairs with suggestion 1 (agent-only) on the same agent file, so suggestions
  1 + 2 collapse to one agent ticket plus one README line.

- **(minor) Suggestions 1 + 2 (agent half) are one ticket.** Assumption: both add standing rules to
  the same file (`.claude/agents/mdreview-planner.md`) and are read-diff-validated together, so they
  ship as a single agent ticket (two new rules) rather than two near-identical tickets touching the
  same paragraph. Justification: one shippable read-diff surface; splitting would create an
  artificial `depends_on` on the same file.

- **(minor) Where the two new agent rules attach.** Assumption: both rules attach to the planner
  agent's **Method** section — the "name the enforcing gate row" rule extends the plan-authoring
  guidance (Method step 4), and the "cite by name, not line number" rule sharpens the existing
  "Cite real `path:line` references" instruction in Method step 2 (which today tells the planner to
  emit `path:line` for *all* claims; it must be narrowed to **code** claims). A pointer also belongs
  in the **Project footguns** framing so the planner treats stale anchors as a known footgun.
  Justification: additive, default-safe edits to standing instructions; Method is where the planner's
  authoring behavior is specified.

- **(minor) Suggestion 4 reuses the existing render-smoke vocabulary.** Assumption: the conditional
  is expressed as "a **product page** (`viewer.html` / `dashboard.html` / `static/**`)", matching the
  `ui`-layer definition in the **Ticket IDs** layer table, so "product page touched" is unambiguous.
  Justification: the layer table already defines `ui` as exactly those files; reusing it avoids a new
  term.

## Recommended approach

All edits are to process / agent / skill markdown. There is no `app.py`, `viewer.html`, or
`dashboard.html` change, and **no script** is added. The work splits by artifact rather than by
service/UI; every ticket is `layer: docs`.

### Service (`app.py`)

- **No change.** This epic ships no code. `python3 -m py_compile app.py` is not a gate here because
  `app.py` is untouched (it still passes trivially, the file being unchanged).

### UI (`viewer.html` / `dashboard.html` / `static/`)

- **No change.** No product page is touched; no render-smoke or screenshot evidence is produced by
  this epic (and suggestion 4 below makes exactly that case explicitly compliant going forward).

### Agent (`.claude/agents/mdreview-planner.md`) — `docs` (suggestions 1 + 2, agent half)

- **Suggestion 1 — "name the enforcing gate row" standing rule.** Add a standing instruction to the
  planner's **Method**: for every new rule a plan proposes, **name the gate pass-condition row that
  enforces it**; treat any **Definition of Done** / prose / G5 restatement as a non-enforcing
  pointer, never the enforcement. Rationale to cite in the rule: all five G1 blockers last cycle
  collapsed to this one class — rules landing in prose / DoD / G5 instead of the enforcing gate row
  (`reviews/process-hardening-cycle-retro-2026-06-09.md`, suggestion 1; the three same-defect
  blockers in `reviews/sprint-02-close-review-2026-06-09.md`, the line-anchor SHOULD-FIX).
- **Suggestion 2 — "cite by name, not line number" standing rule.** Add a standing instruction: in
  process docs and plans, **cite gates and sections by name** (e.g. "the **G7** pass-condition row",
  "the **Definition of Done** section"); **reserve line numbers for code citations**. Narrow the
  existing Method-step-2 instruction that currently tells the planner to "Cite real `path:line`
  references … for each claim" so that `path:line` applies to **code** claims only. Rationale to
  cite: line-number anchors went stale in BOTH cycles (off by ~7 here after the README grew —
  `reviews/process-hardening-cycle-retro-2026-06-09.md`, suggestion 2;
  `reviews/sprint-02-close-review-2026-06-09.md`, the stale-anchor SHOULD-FIX, already resolved at G7
  by re-citing rows by name).

### Process (`docs/process/README.md`) — `docs` (suggestion 2 process half + suggestion 4)

- **Suggestion 2 (process half) — citation convention in the README.** Add a one-line convention to
  the **Reviews (gate evidence)** section (where the naming/citation conventions for review files
  already live): cite gates and sections **by name** in process docs, reviews, and plans; reserve
  line numbers for code citations, since process docs grow and numeric anchors drift. This makes the
  convention visible to any future reader of the process, not only to the planner agent.
- **Suggestion 4 — scope the G7 render clause to product-page changes.** Reword the render clause of
  the **G7** pass-condition row so the render-smoke + screenshot requirement is explicitly
  **conditional on a product page being touched**. Exact before/after below (this is a deliverable):
  - **Current G7 render clause (verbatim):** *"… including a render smoke of any page touched
    (rebuild the container, `curl /healthz` + `/api/reviews`, then `scripts/render-smoke.sh` against
    the touched page asserting its DOM nodes, plus a screenshot under
    `reviews/sprint-NN-render-evidence-*`); …"*
  - **Replacement wording:** *"… and, **only if a product page (`viewer.html` / `dashboard.html` /
    `static/**`) was touched this sprint**, a render smoke of each touched page (rebuild the
    container, `curl /healthz` + `/api/reviews`, then `scripts/render-smoke.sh` against the touched
    page asserting its DOM nodes, plus a screenshot under `reviews/sprint-NN-render-evidence-*`); a
    docs/infra-only sprint that touches no product page is **not non-compliant** for this clause; …"*

    (The whole render parenthetical is kept verbatim from the current row; the **only** change is to
    prepend the product-page condition to the entire block, so a docs/infra-only sprint owes none of
    it. The brief scopes suggestion 4 to the screenshot/render requirement, so this reword adds **no
    new unconditional obligation** — it does not promote the `curl /healthz` + `/api/reviews` smoke
    to a per-sprint requirement (the prior cycle only "exercised render-smoke.sh" because it
    *shipped* it, which does not generalize). The implementer adjusts the final phrasing to read
    cleanly within the existing G7 sentence, preserving every other G7 clause — the "done or
    explicitly carried over", docs-sweep-ineligible-for-carry-over, independent-`staff-critic`-review,
    and retro clauses are untouched.)

### Skill (`.claude/skills/feature-cycle/`) — `docs` (suggestion 3)

- **Suggestion 3 — pre-G7 board-reconciliation rail.** In `references/04-close-and-ship.md`, **Phase
  6 — render-smoke + independent close review (G7)**, add a reconciliation step that runs **before**
  the `staff-critic` is spawned (i.e. before the existing "Independent review (staff-critic)" step).
  The checklist, enforced by **G7** (which the reconciled board is the precondition for):
  - every committed ticket is `done` in its frontmatter (not still `ready`/`review`);
  - the sprint file's committed-ticket checkboxes are checked to match;
  - `TRACKER.md` rows are moved to the section matching each ticket's `status` (the README's **The
    board** section makes ticket frontmatter the source of truth and TRACKER the hand-maintained
    view).
  - **Explicitly NOT in this rail:** setting `close_review:`, setting `status: closed`, or writing
    the retro. Those remain in **Phase 8 — second critic pass + close**, because `close_review:`
    names the review file the critic *produces* and cannot exist before the critic runs.
- **One-line SKILL.md invariant.** Add a one-line invariant to the **Invariants (assert at every
  step)** list in `SKILL.md`: *reconcile the board to reality (all committed tickets `done`, sprint
  checkboxes checked, TRACKER rows moved) **before** spawning the G7 critic; `close_review` and
  `status: closed` are set post-review in Phase 8.* This points at the Phase 6 detail rather than
  restating it (core principle: one surface owns the detail).

## Rollout phases

The three tickets are **mutually independent** — each touches a different file and has no
`depends_on`. There is no real dependency chain to honor, so this epic is effectively one phase;
it is split into per-artifact phases below only for clarity, and the phases may ship in any order.

### Phase 1 — Planner agent rules (suggestions 1 + 2, agent half)

Additive standing-rule edits to `.claude/agents/mdreview-planner.md`. Zero dependencies; sharpens any
future plan immediately. Validation: read-diff only.

### Phase 2 — README conventions (suggestion 2 process half + suggestion 4)

README-only wording: a one-line citation convention in **Reviews (gate evidence)**, and the **G7**
render-clause rewording. Independent of Phases 1 and 3. Validation: read-diff.

### Phase 3 — Skill close-step rail (suggestion 3)

`references/04-close-and-ship.md` **Phase 6** reconciliation step + a one-line **SKILL.md** invariant.
Independent of Phases 1 and 2. Validation: read-diff.

## Non-goals

Explicit scope boundaries — what this epic is deliberately **not** doing.

- **Not** changing any product behavior: `app.py`, `viewer.html`, `dashboard.html`, and `static/**`
  are untouched. This epic ships **no code**.
- **Not** restructuring the gate set G0-G8 or the status lifecycle. Suggestion 4 only reworks the
  **G7** row's render-clause wording; the gate set, boundaries, pass/fail structure, and lifecycle
  are unchanged.
- **Not** re-running or re-reviewing prior cycles (`review-dashboard` / sprint-01,
  `process-hardening` / sprint-02). They are shipped and closed; their retrospectives are the input
  to this epic, not work to redo.
- **Not** adding a test framework, a script, or any new pip/runtime dependency. This epic is
  markdown-only; there is nothing to install or compile.
- **Not** creating tickets, opening a sprint, or implementing — the orchestrator does that after G1.
- **Not** weakening the G7 render bar: suggestion 4 makes the per-page screenshot/DOM assertion
  *conditional on a product page being touched*, not optional when a page IS touched. A sprint that
  touches a product page still owes the full render smoke + screenshot.

## Key constraints (process footguns made specific)

Hard rules the implementation must not violate.

- **G1 independence (author != reviewer).** This plan is authored by `mdreview-planner`; its G1
  review must be by `staff-critic` or the product owner, never the author (the **G1 — Plan Gate** row
  and the **Independence rule**). Revisions after review are made by the planner (still the author),
  preserving independence.
- **The verbatim brief is never edited.** `requirements/process-hardening-2.md` is the record;
  grooming and decisions live in this plan (the **Requirements (source of record)** section). Any
  requirement change goes under the brief's `## Amendments`.
- **The README is the single source of truth for gates; the skill executes, never redefines.**
  (`SKILL.md` **feature-cycle — orchestrator** intro; the README **Automation** section.) Suggestion
  3's rail is an *execution* step (board reconciliation), not a new gate — it asserts an existing G7
  precondition earlier, it does not redefine G7. Suggestion 4 reweords an existing README gate row;
  it is a reviewed `docs` ticket, which the skill's autonomy posture explicitly permits (it forbids
  editing the README *to dodge a gate*, not editing it via a reviewed ticket).
- **Cite by name, not by line number** (the rule this epic introduces — and which this plan already
  follows). Every gate/section reference in the produced edits cites the **named** row/section;
  numeric anchors are reserved for code, of which there is none here.
- **Back-compat / additive.** Agent edits add standing rules without removing existing ones; the G7
  rewording *widens* the compliant set (a docs/infra sprint that was previously read as borderline is
  now explicitly compliant) without weakening the page-touched case; the skill rail adds a
  precondition check without changing any gate's pass condition.
- **Dates are `Europe/London`** in every process file touched.

## Preferred execution order

1. Phase 1 — planner agent rules (suggestions 1 + 2 agent half); no dependencies.
2. Phase 2 — README citation convention + **G7** rewording (suggestion 2 process half + suggestion
   4); no dependencies.
3. Phase 3 — skill close-step rail (suggestion 3); no dependencies.

All three are independent and may be reordered freely. There are **no `depends_on` edges** in this
epic. Phase 1 is listed first only because the new agent rules are the highest-leverage change (they
pre-empt the recurring G1-blocker class on the very next plan).

## Ticket breakdown

How this epic decomposes into tickets (create them in `tickets/` after G1, then link here). IDs are
placeholders; the orchestrator allocates the real sequential `MR-###` (next free is **MR-012**).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-### | Planner agent: "name the enforcing gate row" + "cite by name, not line number" standing rules (sug 1+2) | docs | 1 |
| MR-### | README: citation-by-name convention in Reviews section + scope G7 render clause to product-page changes (sug 2+4) | docs | 2 |
| MR-### | Skill: pre-G7 board-reconciliation rail in 04-close-and-ship Phase 6 + SKILL.md invariant (sug 3) | docs | 3 |

## Risks & mitigations

- **Suggestion 3 rail mis-scoped to set `close_review` pre-critic** (the decision I am least sure
  about). If the implementer reads the brief's "reconcile … `close_review`" literally and puts
  `close_review:` into the pre-critic checklist, the rail becomes self-contradictory (the review file
  does not yet exist). *Mitigation:* this plan scopes the rail to board-reflects-reality only and
  explicitly leaves `close_review:` / `status: closed` / retro in **Phase 8**, citing that Phase 8
  already owns them. If the product owner instead wants `close_review` reconciled at all, the only
  coherent reading is a *post-critic* check, which Phase 8 already does — so no rail change is
  needed. Flagged here so the G1 reviewer can confirm cheaply.
- **G7 rewording accidentally weakens the render bar.** *Mitigation:* the replacement wording makes
  only the per-**page** screenshot/DOM assertion conditional on a product page being touched, retains
  the container-rebuild + `curl /healthz` + `/api/reviews` smoke for every sprint, and leaves every
  other G7 clause verbatim. A non-goal states the page-touched case is unchanged.
- **Two new agent rules over-specify and go stale.** *Mitigation:* both rules are behavioral ("name
  the enforcing row", "cite by name") and carry no numeric value or path that can drift; suggestion 2
  is itself the anti-staleness rule.
- **Suggestion 2 spanning two tickets reads like scope creep.** *Mitigation:* the brief double-tags
  it `[process] + [agent]`; the plan states the split is expected (agent rule + README convention),
  not duplication — each lands in a different file with a different read-diff surface.

## Verification

This epic ships **docs/agent/skill markdown only** — no code, no product page, no script. Therefore
there is **no `py_compile`, no curl, and no render-smoke** in this epic's verification (those existed
in the prior epic only because it shipped `scripts/render-smoke.sh`; this one ships none). Every
ticket validates by **reading the diff** against the named anchors below. (`python3 -m py_compile
app.py` still passes trivially since `app.py` is unchanged, if a reviewer wants a no-op sanity check.)

- **Dogfood self-check (whole plan):** this plan contains **zero `README.md:NNN` line anchors** and
  cites every gate/section by name — the direct evidence that suggestions 1 + 2 are practiced here.
  Grep the plan for `README.md:` and `\.md:[0-9]` -> no process-doc line anchors.

- **Planner agent ticket (sug 1+2):** confirm `.claude/agents/mdreview-planner.md` now states, in its
  **Method**, (a) a standing rule to place every new rule in the **enforcing gate pass-condition
  row** and treat DoD/G5/prose as non-enforcing pointers; and (b) a standing rule to cite gates and
  sections **by name**, with `path:line` narrowed to **code** citations (the prior
  "Cite real `path:line` references … for each claim" instruction is scoped to code). Read-diff.

- **README ticket (sug 2+4):** confirm (a) the **Reviews (gate evidence)** section carries a one-line
  citation-by-name convention (cite gates/sections by name; reserve line numbers for code); and (b)
  the **G7** pass-condition row's render clause now makes the per-page render-smoke + screenshot
  **conditional on a product page (`viewer.html`/`dashboard.html`/`static/**`) being touched**, with
  the exact before/after wording above, and explicitly states a docs/infra-only sprint is not
  non-compliant for lacking page screenshots. Confirm every other G7 clause is byte-for-byte
  unchanged. Read-diff.

- **Skill ticket (sug 3):** confirm `references/04-close-and-ship.md` **Phase 6** now has a
  board-reconciliation step **before** the `staff-critic` spawn (committed tickets `done`, sprint
  checkboxes checked, TRACKER rows moved), that it **excludes** `close_review:` / `status: closed` /
  retro (which remain in **Phase 8**), and that `SKILL.md`'s **Invariants** list carries the matching
  one-line invariant. Read-diff.

- **Epic-level:** confirm no product file (`app.py`, `viewer.html`, `dashboard.html`, `static/**`)
  appears in any ticket's diff; the gate set G0-G8 and the status lifecycle are unchanged (only the
  **G7** render-clause wording moved).
