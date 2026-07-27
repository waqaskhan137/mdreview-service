# mdreview-service — Process & Working Agreement (GitHub-only)

Work is tracked **exclusively on GitHub**: issues are the tickets, labels carry status /
priority / layer, milestones are the sprints, epic issues hold plans and gate evidence. This
file is the working agreement: the gates, the label taxonomy, and the queries that replace the
old board. Migrated 2026-07-22 from the file-based process (per the approved plan, mdreview
review `79fb2c6f6e`; staff-critic gate passed in 2 rounds).

## Two zones in this directory

**Live** (authoritative):

```
README.md          this working agreement
autonomous-run.md  how an agent executes scoped work unattended (stages, gates, hard rules)
product.md         the product goal + principles: the value yardstick for prioritization
evidence/          committed gate evidence: render/binary artifacts per sprint (evidence/sprint-NN/)
runs/              autonomous-run decision logs (runs/<YYYY-MM-DD>-<slug>.md)
```

The **roadmap** is NOT a file: it is the GitHub Project
[**"mdreview Roadmap"**](https://github.com/users/ranawaqas-ai/projects/3) (linked in the
repo's Projects tab), a single-select **Horizon** field with Now / Next / Later. Entries are
epic issues; the board holds membership + sequencing, the epic issue body holds the why and
the size. Owner decision 2026-07-22, superseding the plan's roadmap.md default.

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
| Strategy | `product.md` in git; the roadmap = GitHub Project "mdreview Roadmap" (Horizon: Now/Next/Later), entries = epic issues |

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
gh project item-list 3 --owner ranawaqas-ai             # the roadmap (Horizon = Now/Next/Later)
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
3. Implement on a branch cut from current `dev`, named `<kind>/<issue>-slug` (e.g.
   `fix/15-comment-anchor`). `dev` accepts changes only via PR, so even a small change rides
   a branch + PR. Self-merge once `pr-checks` is green (see Branching).
4. Validate locally: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`;
   for `layer:infra`, `docker build -f infra/Dockerfile`; for `layer:ui`, rebuild from the
   image and assert rendered DOM nodes with `tests/render-smoke.sh <url> <selector>...` (a 200
   is not a render). See `CLAUDE.md` "Run".
5. Commit referencing the issue (`(#N)` in the subject, no auto-close keywords).
6. Summarize what changed + what was validated as an issue comment; swap the label to
   `status:review`. On owner approval, close (G5).
7. Blocked? Swap to `status:blocked`, name the blocker in a comment (and file the prerequisite
   as its own issue; never bury a prerequisite fix inside an unrelated one).

### Branching (enforced by branch protection, not just convention)

- Cut every branch from current `dev` and open its PR **against `dev`**. **An agent may
  self-merge its own PR once `pr-checks` is green** (owner decision 2026-07-27, superseding the
  earlier "PRs collect until the owner calls a merge gate"). `dev` is protected (PR required,
  0 approving reviews, force-pushes and deletions blocked); direct pushes are rejected either
  way. The 0-approvals setting exists because authors cannot approve their own PRs on a solo
  repo.
- **What replaced the human gate.** The no-self-merge convention was the last second-party look
  before code reached a publicly reachable host, so it was traded for a machine one:
  `.github/workflows/pr-checks.yml` runs the hosted-boot and custody-regression smokes on every
  PR into `dev`. Two limits, both deliberate and both stated rather than implied. It is a
  **floor, not a substitute**: both smokes are server-side and neither reads `web/app/**`, so a
  green run says nothing about a UI diff. And it is **honour-system** until `pr-checks` is made
  a *required status check* on `dev` — as of 2026-07-27 neither classic protection nor rulesets
  require any check, so nothing stops a merge while it is red or still queued.
- The **batch merge gate remains available** when the owner wants one: the product-owner agent
  prepares the queue (mergeability, overlapping files, dependency-aware order), the owner gives
  the go, and merges execute in that order, re-checking mergeability after each. It is now an
  option for queues, not a precondition for every merge.
- **Never open a PR against `main`** except the single standing `dev -> main` PR (G8), which
  accumulates each cycle and is updated, never duplicated. `main` requires 1 approving review
  plus **signed commits**: merge the standing PR by **squash** in the GitHub UI (GitHub signs
  the squash commit); a merge-commit or rebase-merge fails on unsigned agent commits.
  Note the review requirement cannot be satisfied normally on a solo repo (GitHub forbids
  approving your own PR), so the squash lands via the owner's **admin override** ("merge without
  waiting for requirements", or `gh pr merge --squash --admin`). `enforce_admins` is off for
  exactly this reason; `required_signatures` still applies and the squash commit is signed.
- **After every G8 squash, merge `main` back into `dev`.** Squashing means `dev` never becomes an
  ancestor of `main`, so the merge base stops advancing. Files legitimately changed on both sides
  then collide and the NEXT `dev -> main` PR fails on phantom conflicts, even when the real content
  difference is one commit. (Hit for real on 2026-07-24: `dev -> main` conflicted on
  `web/app/dashboard.html` with a merge base three days stale.) The fix restores shared ancestry:

      git switch -c sync-main-into-dev origin/dev
      git merge origin/main          # resolve any conflict by taking dev's side
      # verify it is ancestry-only: `git diff origin/dev` MUST be empty
      # open a PR into dev and merge it with a MERGE COMMIT

  Merge that sync PR with a **merge commit, never squash** — squashing flattens the merge and
  destroys the very ancestry it exists to create. Confirm with
  `git merge-base --is-ancestor origin/main origin/dev` before cutting the next release.
- `main` advances only on the owner's explicit G8 go-ahead. Nothing merges around the flow;
  if `dev` ever trails `main`, something did, reconcile before cutting new branches.

## Automation

The `product-owner` agent (`.claude/agents/product-owner.md`, local-only: `.claude/` is
gitignored) does triage, RICE/WSJF scoring (stamps land as issue comments), grooming, sprint
and roadmap proposals, and board reconciliation. It is optional: every query and gate above
works by hand, so the process is a repo property, not a machine property.

## Dates

Dates in process artifacts are `Europe/London`. Cite gates and sections by name, not line
number; line numbers are for code.
