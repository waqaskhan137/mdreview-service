# mdreview-service — Process & Working Agreement (GitHub-only)

Work is tracked **exclusively on GitHub**: issues are the tickets, labels carry status /
priority / layer, milestones are the sprints, epic issues hold plans and gate evidence. This
file is the working agreement: the gates, the label taxonomy, and the queries that replace the
old board. Migrated 2026-07-22 from the file-based process (per the approved plan, mdreview
review `79fb2c6f6e`; staff-critic gate passed in 2 rounds).

## Two zones in this directory

**Live** (authoritative):

```
README.md        this working agreement
product.md       the product goal + principles: the value yardstick for prioritization
roadmap.md       now/next/later roadmap (created by the product-owner agent on first run)
evidence/        committed gate evidence: render/binary artifacts per sprint (evidence/sprint-NN/)
```

**Frozen** (read-only history of the retired file process; each dir carries `_ARCHIVED.md`):
`tickets/ sprints/ epics/ reviews/ requirements/ templates/ TRACKER.md backlog.md`. Never
edit these; old links must keep working. The archive may be **deleted once the GitHub-only
process has proven stable** (owner's call; phase-out intent recorded 2026-07-22).

## The system

| Concept | Where it lives |
|---|---|
| Ticket | An issue. **done = closed** (wontfix = closed as not-planned) |
| Status | Exactly ONE `status:` label per open issue: `backlog \| ready \| in-progress \| review \| blocked` |
| Priority | One of `P0` (urgent) `P1` (high) `P2` (normal) `P3` (nice-to-have) |
| Layer | `layer:svc \| layer:ui \| layer:infra \| layer:docs` |
| Type | GitHub's default labels (`bug`, `enhancement`, `question`, ...) |
| Sprint | Milestone `sprint-##`: description = the goal; open = G6, close = G7 |
| Epic | An issue labeled `epic`: body = the plan + a task list of child issues; child issues exist only after G1 |
| Dependencies | `Depends on #N` lines in the issue body for live issues; a plain repo link for anything in the frozen archive (frozen tickets have no issue number) |
| Requirement brief | A marked **verbatim** section in the epic issue body under `## Requirement (verbatim, do not edit)`; never edited afterward (GitHub keeps edit history); amendments as dated comments |
| Gate evidence, prose | Comments on the sprint's epic issue |
| Gate evidence, render/binary | Committed under `evidence/sprint-NN/`, linked from the G7 comment (`gh` comments are text-only, and evidence is shipped history that must stay in git) |
| Strategy | `product.md` and `roadmap.md`, in git; entries link issues |

Status lifecycle (unchanged in meaning; closed replaces done):

```
backlog -> ready -> in-progress -> review -> closed
                        ^v
                     blocked
```

**Do not use auto-close keywords** (`closes #N`) in PRs or commits: an issue closes only at G5
(owner approval), never as a merge side effect. Commits reference their issue in the subject:
`feat(svc): add list endpoint (#70)`, with the `Co-Authored-By: Claude` trailer.

## Board queries (replace TRACKER.md)

```sh
gh issue list --state open                              # everything
gh issue list --label status:ready                      # the pickup queue
gh issue list --label epic --state open                 # live epics
gh issue list --milestone sprint-NN                     # a sprint's scope
# DRIFT QUERY — any open issue with zero or 2+ status labels is out of contract:
gh issue list --state open --json number,title,labels \
  --jq '.[] | select(([.labels[].name | select(startswith("status:"))] | length) != 1) | "\(.number) \(.title)"'
```

The drift query is the board's integrity check. Any session can run it; the product-owner
agent runs it on every reconcile.

## Gates

A gate is a checkpoint work cannot pass until its condition holds. A failed gate is the gate
doing its job. **Evidence home rule:** every sprint has exactly one epic and every epic is an
issue, so gate evidence always has a live home. A ticket whose epic is frozen history is
*adopted* into the sprint's epic issue task list (under "Adopted", linking the frozen plan). A
grab-bag sprint mints a lightweight epic issue for the same purpose.

| Gate | Boundary | Pass condition |
|------|----------|----------------|
| **G0 — Requirement captured** | brief -> grooming | Verbatim brief in the epic issue body under the do-not-edit heading; changed only by dated amendment comments. |
| **G1 — Plan gate** | epic -> child issues | Independent review (staff-critic or the owner, never the plan's author) posted as a comment on the epic issue; all blockers answered; owner sign-off comment. Only then are child issues created. |
| **G2 — Definition of Ready** | -> `status:ready` | Issue body has checkable acceptance criteria, linked dependencies, layer + priority labels, a rough size, no open questions. |
| **G3 — Pickup** | `ready` -> `in-progress` | Issue is in the active milestone; every dependency closed; one in-progress at a time. |
| **G4 — Review** | `in-progress` -> `status:review` | Validation passes (below) and the author self-checked the acceptance criteria; evidence summarized in an issue comment. |
| **G5 — Done** | `review` -> closed | All AC met + validation + docs updated in the same change (or a same-sprint docs-sweep issue named in a comment); **owner approval**; then close the issue. |
| **G6 — Sprint open** | -> milestone active | Milestone created with a goal; only `status:ready` issues assigned. |
| **G7 — Sprint close** | milestone -> closed | Independent close review (staff-critic or owner, not the implementer) as a comment on the sprint's epic issue, verifying shipped work against each issue's AC, including the container rebuild + `curl /healthz` + `/api/reviews` smoke; render/binary evidence committed under `evidence/sprint-NN/` and linked from that comment; carry-overs moved to a later milestone (a docs-sweep issue is NOT eligible for carry-over); then close the milestone. |
| **G8 — Promote to main** | `dev` -> `main` | Explicit owner go-ahead. A single standing `dev -> main` PR accumulates work until then. |

## Development flow

1. Pick exactly one `status:ready` issue from the active milestone (highest priority first);
   swap its label to `status:in-progress`.
2. Restate the goal and acceptance criteria (in the issue, as a comment, if they need
   clarification) before touching code.
3. Implement on a branch cut from `dev` (small changes may commit to `dev` directly).
4. Validate locally: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`;
   for `layer:infra`, `docker build -f infra/Dockerfile`; for `layer:ui`, rebuild from the
   image and assert rendered DOM nodes with `tests/render-smoke.sh <url> <selector>...` (a 200
   is not a render). See `CLAUDE.md` "Run".
5. Commit referencing the issue (`(#N)` in the subject, no auto-close keywords).
6. Summarize what changed + what was validated as an issue comment; swap the label to
   `status:review`. On owner approval, close (G5).
7. Blocked? Swap to `status:blocked`, name the blocker in a comment (and file the prerequisite
   as its own issue; never bury a prerequisite fix inside an unrelated one).

### Branching

All work integrates into `dev`, never directly into `main`. `main` advances only on explicit
owner go-ahead (G8) via the single standing `dev -> main` PR.

## Automation

The `product-owner` agent (`.claude/agents/product-owner.md`, local-only: `.claude/` is
gitignored) does triage, RICE/WSJF scoring (stamps land as issue comments), grooming, sprint
and roadmap proposals, and board reconciliation. It is optional: every query and gate above
works by hand, so the process is a repo property, not a machine property.

## Dates

Dates in process artifacts are `Europe/London`. Cite gates and sections by name, not line
number; line numbers are for code.
