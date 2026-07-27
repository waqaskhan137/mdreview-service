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

---

## D6 · #189 shipped, and the ticket's own premise was wrong

#189 said the source pane offered "only a download link". `#dlbtn` is **Download PDF** and lives
in the PDF pane; there is no source download in the file at all. So the work was "add the first
control of its kind to the source header", not "add a sibling". Correction posted on the issue
before implementation, so the ticket and the AC do not disagree in the record.

**Falsifiable by:** a source-download control anywhere in `latex-viewer.html` before this change.

## D7 · The check asserts the clipboard, and was verified against the wrong implementation

The AC is "the raw `.tex` reaches the clipboard". A render smoke asserting `#copysrc` exists
would not test that, so `tests/latex_copy_source_smoke.sh` clicks the control, reads the
clipboard back and compares byte-for-byte to `GET /source`.

Verified by breaking it: swapping the handler to copy `#codecol.textContent` — the plausible
wrong implementation, since the rendered column interleaves gutter line numbers — makes the
smoke fail with `CLIP_MISMATCH`. A check never seen to fail is decoration.

This needed `--clipboard` on `cdp-shot.mjs`: headless Chrome rejects even `writeText` with
`NotAllowedError: Document is not focused` without both `Browser.grantPermissions` and
`Emulation.setFocusEmulationEnabled`. Pre-flight established that *before* the AC was written,
per the plan's pre-registration.

**Falsifiable by:** the smoke passing against the `#codecol.textContent` implementation.

## D8 · Stage 8 could not exercise the success path on staging, and this is not a workaround

Chrome-MCP drives the browser through CDP, and `document.hasFocus()` is **false** at the moment
any scripted click lands — measured, not assumed (`focusedAtClick: false`). `navigator.clipboard`
requires a focused document, so on staging every click took the failure branch. Four attempts,
including a real mouse click to focus first; the focus does not survive to the next tool call.
This is the same family as the recorded "backgrounded MCP tabs freeze CSS animations".

What stage 8 **did** establish on the deployed staging build (`ea4b0df`): the control renders in
the source pane header, is labelled `Copy the LaTeX source to the clipboard`, and — with the
clipboard genuinely unavailable — the UI says **"Copy failed — NotAllowedError"**. That is direct
evidence the handler does not share `viewer.html`'s `#pubcopy` defect, which would have said
"Copied". The honest-failure half of the AC was verified *better* by the constraint than it would
have been by a working clipboard.

What stage 8 did **not** establish: the success path on staging. That is verified locally, by the
smoke above, and reported as local-only rather than implied to be staging-verified.

**Falsifiable by:** a Chrome-MCP invocation that lands a click with `document.hasFocus() === true`.

## D9 · The stage-6 digest read came back empty, and the gate survived by luck

Stage 6 requires recording `.deployed-digest` **before** merging. For #189 that `ssh` read
returned an empty string (transient; the same command worked before and after). The merge went
ahead, so the gate briefly had no before-value — the exact "a gate with no before-value is not a
gate" failure the process warns about.

Recovered because the marker was re-read after the merge and **before** adoption and still held
`096c790…`, so the before-value was recoverable. That is luck, not design: had the timer fired
first, stage 7 would have had nothing to compare against.

**Fix owed to the process doc:** stage 6 should treat an empty or failed digest read as a *failed
precondition* and stop before merging, rather than proceeding. Not amended in this run; filed.

**Falsifiable by:** a stage-6 implementation that proceeds to merge on an empty read.
