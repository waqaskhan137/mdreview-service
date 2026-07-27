# Run log — 2026-07-27 · autonomous-run process (#209) + LaTeX source copy (#189)

First run executed under `docs/process/autonomous-run.md`, which this same run wrote. Plan of
record: mdreview `17731f7815`, critic gate closed at 3 rounds, "proceed with named risks
accepted".

Format: what was decided, why, and **what would falsify it**.

---

## D1 · The process document is written from evidence, not from taste

Every hard rule traces to a recorded failure: rules 1-3 and 5 to the 2026-07-25 night run's
own-goals, rule 4 to #163, rules 8 and 9 to failures inside this plan's own review. No rule was
added because it sounded like good practice.

**Falsifiable by:** a rule in `autonomous-run.md` with no incident behind it. That rule is
speculative and should be cut.

## D2 · `pr-checks` is a new workflow, not a trigger on `staging-image.yml`

The plan's first version said "add `pull_request: branches: [dev]` to `staging-image.yml`'s
smoke job". That is not expressible: `on:` is workflow-level in GitHub Actions. The naive
implementation (put it on `on:`) fires the `image` job too, because `needs:` is a dependency and
not a filter, and workflow-level `packages: write` survives on a same-repo PR — so **every PR
would publish its own head as `:dev` and `-latex:dev`**, which the staging timer adopts within
15 minutes. Its static `concurrency: {group: staging-image, cancel-in-progress: true}` would
also cancel in-flight `dev` builds, leaving `:dev` silently stale: #163's failure class
re-entering through the fix for it.

A separate file makes all three structurally impossible rather than guarded against.
`staging-image.yml` is untouched.

**Falsifiable by:** a GHCR push whose originating run was a `pull_request` event.

## D3 · The guard is the check, and it was verified by breaking it

`tests/pr_checks_guard.py` asserts the invariants the safety argument rests on: job key
`pr-checks` (a required status check matches the **job** name, not the workflow name),
`permissions: contents: read` declared in-file rather than inherited from a repo setting, no
`packages:` scope, no image push, both smokes present. Negative control run: renaming the job to
`smoke` makes it exit 1 with the right message. A check never seen to fail is decoration.

**Falsifiable by:** mutating any invariant and finding the guard still green.

## D4 · Two of my own factual claims were wrong, both caught by the review

Recorded because both were stated confidently and one was already in a brief.

**(a) "Staging is fixed in the repo but not on the host."** Carried from the 2026-07-26 note and
repeated to the critic. False as of today: `ssh kapture` answers on :22 again, the host's
`auto-update.sh` contains the #163 `repo_digest()` fix (installed 11:52), the staging timer is
active on a 15-minute cadence, and the pipeline demonstrably ran end to end at 16:48-16:58 —
about ten minutes before I asked for the round-2 review that assumed it had not.

**(b) The CI-image finding that consumed round 1.** The critic and I both read
`staging-image.yml` from the working tree (`feat/ui-admin-nav`, 14 files behind `dev`) and
independently concluded that no workflow builds `mdreview-service-latex:dev`. On `origin/dev` it
plainly does, from `infra/Dockerfile.latex`. Two readers agreeing off the same stale file is not
corroboration — that is now rule 8, and the reason P6 exists.

**Falsifiable by:** any claim in this log about CI or deploy that a `git show origin/dev:<path>`
contradicts.

## D5 · `CLAUDE.md` could not be amended in the PR

The self-merge rule is specified in four places. Three are tracked (`AGENTS.md`,
`docs/process/README.md` twice). The fourth, root `CLAUDE.md`, is gitignored
(`.gitignore:14`) and therefore local-only: it was edited in the working copy but is not part of
this change and will not propagate to another clone.

**Consequence:** anyone cloning this repo fresh gets the amended `AGENTS.md` and README, and no
`CLAUDE.md` at all. That is the existing design, not a regression, but it means `CLAUDE.md` can
drift from the working agreement silently and did exactly that before this run: it said
"self-merge OK" while `AGENTS.md` said "do NOT merge it".

**Falsifiable by:** finding `CLAUDE.md` tracked in git, which would make this a real omission.
