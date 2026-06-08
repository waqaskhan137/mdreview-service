# mdreview-service — Process & Ticketing

A local, file-based delivery process. All state lives in this repo as markdown and is
**committed and pushed** so any future session (or clone) reconstructs where things stand from
frontmatter + filenames + git, not from a chat it cannot see. Tickets are files, sprints are
files, the board is a file, gate evidence is a file.

Adapted from the `yeoward-boatyards` feature-cycle process. That repo is a Next.js/Supabase team
app and keeps its `docs/process/` git-ignored; this repo is a stdlib-only solo micro-service and
does the opposite on purpose (see Divergences). The gate philosophy is identical; the app-specific
rails are swapped.

| Concept | Local equivalent |
|---------|------------------|
| Issue | a file in `tickets/` (`MR-###-*.md`) |
| Milestone | a file in `sprints/` (`sprint-##.md`) |
| Status label | `status:` field in ticket frontmatter |
| Priority label | `priority:` field |
| Comments / notes | the **Work log** + **Validation** sections in the ticket |
| Project board | `TRACKER.md` |
| Epic / planning doc | a file in `epics/` |
| Gate sign-off / critique | a file in `reviews/` |

## Layout

```
docs/process/
  README.md        this file: the working agreement + gates
  TRACKER.md       the board: every ticket grouped by status
  backlog.md       parking lot for deferred / not-yet-groomed ideas
  templates/       copy these to start a new ticket / sprint / epic
  requirements/    verbatim source briefs, kept untouched
  epics/           scoping docs: <slug>-plan.md
  tickets/         one file per ticket: MR-###-slug.md
  sprints/         one file per sprint: sprint-##.md
  reviews/         independent critiques (gate evidence): <artifact>-review-YYYY-MM-DD.md
```

## Divergences from the source process (deliberate)

- **This tree is committed + pushed.** The whole point is cross-session durability, so the
  process must travel with the repo.
- **No database / no Next build.** The validation gate is `python3 -m py_compile app.py`
  (+ `docker build` for infra changes) and a curl/browser render smoke, not `npm run build` or
  authenticated RSC renders.
- **Single-flight.** One developer, one cycle at a time. The source's multi-agent collision and
  worktree-contention rails are dropped.
- **One lightweight sprint per epic.** No concurrent-milestone machinery.
- **Commits keep the `Co-Authored-By: Claude` trailer** (matches this repo's baseline + the
  harness default). Conventional subject with the ticket ID: `feat(svc): add list endpoint (MR-002)`.

## Requirements (source of record)

When a brief or spec arrives, capture it **verbatim** in `requirements/<slug>.md` before
grooming.

- **Never edit the brief.** It is the record of what was originally asked. Grooming, scope cuts,
  and decisions happen in the epic plan and tickets, not by rewriting history.
- If the requirement genuinely changes later, append a dated note under an **Amendments**
  section rather than altering the original text.
- Every epic links back to its brief (`source:`); every brief links forward to its epic
  (`related_epic:`). That round-trip lets any session trace ticket -> epic -> original ask.

## Ticket IDs

- Format `MR-###`, zero-padded to 3 digits, **sequential across the whole project**.
- Next ID is `(highest existing ID) + 1`. IDs are never reused.
- Filename `MR-###-kebab-summary.md`.
- Every ticket carries a **layer** tag:

| `layer` | Means | Typical files |
|---------|-------|---------------|
| `svc` | the service: HTTP server, router, API, storage | `app.py` |
| `ui` | the human-facing pages and assets | `viewer.html`, `dashboard.html`, `static/**` |
| `infra` | container, compose, config, deploy | `Dockerfile`, `docker-compose.yml`, `.env*`, `vercel`/host config |
| `docs` | documentation, this process | `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/**` |

## Status lifecycle

```
backlog -> ready -> in-progress -> review -> done
                        ^v
                     blocked
```

| `status` | Meaning |
|----------|---------|
| `backlog` | Captured, not groomed. Not eligible to pick up. |
| `ready` | Groomed: acceptance criteria written, no open questions. Eligible once its `depends_on` are `done`. |
| `in-progress` | Actively being worked. One at a time unless genuinely independent. |
| `review` | Implemented and locally validated; awaiting approval. |
| `done` | Definition of Done met. |
| `blocked` | Has an unmet prerequisite. Record the blocker and blocking ticket in the Work log. |

## Priority

`P0` urgent · `P1` high · `P2` normal · `P3` nice-to-have. When several tickets are `ready`,
start the highest priority first.

---

## Working Agreement

### Task pickup rule

A ticket may be started only if **all** hold: it belongs to the **active sprint**; its `status`
is `ready`; every ticket in its `depends_on` is `done`; it is groomed enough to start
immediately. If several are eligible, pick the highest `priority` first.

### Development flow

1. Pick exactly one ticket; set `status: in-progress`, update `updated:`.
2. **Restate the goal and acceptance criteria** before touching code.
3. Verify dependencies are actually `done` in the tracker and reflected in the code.
4. Implement on a ticket branch (`MR-###-slug`) cut from `dev` (small changes may commit to
   `dev` directly).
5. Validate locally: `python3 -m py_compile app.py`; for `infra`, `docker build`; for `ui`,
   rebuild from the image and assert the rendered DOM nodes with
   `scripts/render-smoke.sh <url> <selector>...` (a 200 is not a render; a screenshot proves
   first-paint only). See `CLAUDE.md` "Run".
6. Commit referencing the ticket ID (conventional subject).
7. Fill the ticket's **Work log** (what changed, files) and **Validation** (what you checked).
8. Set `status: review`. On approval, set `status: done`.

### Branching rule

- **All work integrates into `dev`, never directly into `main`.** `dev` is the long-lived
  integration branch; `main` advances only on explicit user go-ahead (G8).
- A **single standing `dev -> main` PR** accumulates unmerged work and is updated each cycle, not
  duplicated.

### Definition of Done

A ticket is `done` only when: all acceptance criteria met; local validation passes; durable
behavior changes are reflected in `README.md` / `AGENTS.md` / `CLAUDE.md` **in the same change**
**or** deferred to a trailing **docs-sweep ticket within the same sprint** (the deferring ticket
must name its sweep ticket in its Work log); the ticket's Work log + Validation are filled in; the
work is committed (and pushed).

A **docs-sweep ticket is not eligible for carry-over** — it must be `done` before its sprint
closes (see G7), so deferred docs cannot cross a sprint boundary.

### Blocking rule

If a ticket reveals a missing prerequisite: **stop**, set it `blocked`, and either widen the
ticket's scope deliberately or create a new prerequisite ticket. Never bury a prerequisite fix
inside an unrelated ticket.

---

## Gates

A **gate** is a checkpoint work cannot pass until its condition holds. Gates make review happen
by default, not by memory. A failed gate is the gate doing its job.

| Gate | Boundary | Pass condition |
|------|----------|----------------|
| **G0 — Requirement captured** | brief -> grooming | Verbatim source exists in `requirements/` and is not edited after capture. |
| **G1 — Plan Gate** | epic plan -> tickets | The epic plan has a recorded **independent** review in `reviews/` (reviewer is NOT the plan's author: the `staff-critic` agent, or the product owner), **all blocker questions answered**, and explicit sign-off. Only then does the epic move to `status: active`/`gate: passed` and tickets may be created. |
| **G2 — Definition of Ready** | ticket -> `ready` | Acceptance criteria written, dependencies identified, `layer` + `priority` set, no open questions, roughly sized. |
| **G3 — Pickup** | `ready` -> `in-progress` | Active sprint + every `depends_on` is `done` + the one-in-progress rule. |
| **G4 — Review** | `in-progress` -> `review` | `python3 -m py_compile app.py` passes (and `docker build` for `infra`); **for `ui` tickets, a render-smoke from the rebuilt image passes** — `scripts/render-smoke.sh <url> <selector>...` asserts the expected DOM nodes rendered (a 200 is not a render; see Development flow step 5); author self-checked the acceptance criteria. |
| **G5 — Definition of Done** | `review` -> `done` | All AC met + validation + docs updated (in the same change, or deferred to a same-sprint docs-sweep ticket named in the Work log) + Work log/Validation filled + committed. |
| **G6 — Sprint open** | -> sprint `active` | Every committed ticket is `ready`; the sprint has a goal and a committed-ticket list. |
| **G7 — Sprint close** | sprint -> `closed` | Every committed ticket is `done` or explicitly carried over (**a docs-sweep ticket is NOT eligible for carry-over**); **no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done`** (deferred docs are force-closed at sprint close, never carried across cycles); an **independent `staff-critic` sprint-close review** is recorded in `reviews/` (reviewer is NOT the implementer), verifying shipped work against each ticket's acceptance criteria, **including a render smoke** (rebuild the container, `curl /healthz` + `/api/reviews`) — and, **only if a product page (`viewer.html` / `dashboard.html` / `static/**`) was touched this sprint**, `scripts/render-smoke.sh` against each touched page asserting its DOM nodes plus a screenshot under `reviews/sprint-NN-render-evidence-*`; a docs/infra-only sprint that touches no product page is **not** non-compliant for lacking the per-page DOM assertion and screenshot, but still owes the container rebuild + `curl /healthz` + `/api/reviews` smoke; retro + carry-overs are written into the sprint file. |
| **G8 — Promote to main** | `dev` -> `main` | **Explicit user go-ahead.** `dev` holds all work; `main` advances only when the user approves. A single standing `dev -> main` PR accumulates work until then. |

**Two gates require a recorded independent review: G1 (before tickets exist) and G7 (before a
sprint closes).** G1 stops a plausible-looking plan from spawning a dozen wrong tickets; G7 stops
a sprint being declared done when the shipped work does not meet the tickets' acceptance criteria.

**Independence rule:** the reviewer must NOT be the artifact's author or the sprint's
implementer. Use the `staff-critic` agent or the product owner. An author self-review may exist
as a labelled, non-gating pre-pass (`independent: false`) but never satisfies the gate.

### Reviews (gate evidence)

Independent critiques live in `reviews/`, one file per review, named
`<artifact-slug>-review-YYYY-MM-DD.md` (round suffix `-r2`, `-r3` for re-reviews). A review
carries frontmatter: `review_of`, `gate`, `reviewer`, `independent` (`true`/`false`, must be
`true` for G1/G7), `timestamp`, `verdict`, `status` (`open`|`resolved`); links to the artifact
and the specific files it cites; and ends with a **Resolution log** updated as blockers are
answered. Set `status: resolved` only once every blocker is closed.

Naming by gate:
- **G1 (plan):** `<epic-slug>-plan-review-YYYY-MM-DD.md`.
- **G7 (sprint close):** `sprint-NN-close-review-YYYY-MM-DD.md`.

**Citation convention.** In process docs, reviews, and plans, **cite gates and sections by name**
(e.g. "the G7 pass-condition row", "the Definition of Done section"), not by line number — these
docs grow and numeric anchors drift. **Reserve line numbers for code citations** (`app.py:NNN`).

## The board

`TRACKER.md` is the at-a-glance view, maintained by hand. The ticket frontmatter is the source of
truth; whenever a ticket's `status` changes, move its row to the matching section in `TRACKER.md`.

## Starting things

- **New ticket:** copy `templates/ticket.md` -> `tickets/MR-###-slug.md`, fill it in, add a row
  to `TRACKER.md`.
- **New sprint:** copy `templates/sprint.md` -> `sprints/sprint-##.md`, set its goal, list
  committed tickets, set `status: active` when it starts.
- **New epic:** copy `templates/epic-plan.md` -> `epics/<slug>-plan.md` and scope it. **Do not
  create its tickets until it clears G1.**
- **New review:** write `reviews/<artifact-slug>-review-YYYY-MM-DD.md` per the Reviews section.

## Automation

`.claude/skills/feature-cycle/` drives these gates end-to-end (see its `SKILL.md`). It does not
redefine the gates; this README is the source of truth. The `cycle-retrospective` agent runs at
the end of every cycle and is enforced by a `Stop` hook
(`.claude/hooks/enforce-cycle-retro.sh`). If a run ever gets stuck behind that hook, the manual
unstick is `rm .claude/.feature-cycle-pending-retro`.

## Dates

Dates in process files are `Europe/London`.
