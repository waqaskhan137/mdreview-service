# #188 — autonomous run decision log

**Date:** 2026-07-27
**Issue:** #188, LaTeX compile fails (reported by @aa1716-exe against prod)
**Plan:** https://app.mdreview.space/review/5653a47820
**Branch:** `fix/188-latex-source-guard` off `dev`

The owner approved the spine, pre-approved the expanded doc and the implementation, and asked for
the run to proceed without further input: *"in case any decision required keep a decision log and
take best decision to your knowledge and present it to me once done."* This file is that log.

## Autonomy boundary

**Ceiling: verified on staging.** The run merges to `dev` (which the working agreement permits at 0
approvals) because staging deploys from `dev` and the owner's own verification requirement is
otherwise unreachable. It does **not** touch G5 (Done ack), G7 (sprint close) or G8 (`dev`→`main`
promote); those remain the owner's.

## What the reporter got wrong, and what I got wrong

The reporter's symptom was real and their diagnosis was not: they believed the compiler picks up a
markdown "reading copy" wrapper instead of the raw source. `compiler._prepare_job` writes
`read_source(rid)` verbatim, and `grep -rn "reading copy"` over the repo returns nothing, so
mdreview never generated that wrapper. Their client did.

I then posted a wrong diagnosis of my own, publicly on the issue: that the guard was one-directional
across *paths* and the fix was to mirror the existing guard onto `PUT /source`. Both halves were
wrong. I had probed create with a *LaTeX* body, which is the direction `looks_like_latex()` already
covers, and read the rejection as proof of symmetry. `POST` with `kind="latex"` and a markdown body
returns 200 as well. Correcting that comment is part of this run's definition of done.

The real asymmetry is in **content type, not route**: LaTeX-submitted-as-markdown is caught,
markdown-submitted-as-LaTeX was caught nowhere.

## Decisions

| id | decision | why |
|----|----------|-----|
| D1 | Self-merge the PR into `dev` | Staging deploys from `dev`, so "verify on staging" is unreachable without it. The working agreement allows `dev` at 0 approvals, and `dev`→`main` stays owner-gated. |
| D2 | Work in-session in a dedicated worktree rather than dispatching a background agent | The run happened inside one turn, so a dispatched agent adds a context boundary and a second verification surface for no gain. Departs from spine rev 1's "one background agent", revised out in rev 2. |
| D3 | Rename in `src/` and `tests/` only; leave the 13 `docs/process/` references | They are dated records of MR-102/MR-103 as shipped, and that file-based process is frozen pending deletion. Rewriting history to match a later rename would make the record false. `errors.py` names the original symbol so a grep from an old ticket still lands. |
| D4 | Do not fix the two adjacent defects found en route | Out of scope per the approved spine. Filed as their own issues instead so they are not lost. |
| D5 | Reject an empty body on `put_source`; allow it on `create` | An empty PUT snapshots and overwrites, wiping a working paper into exactly the failed-compile state #188 is about. A blank *create* is a real starting state; a blank *overwrite* is not. |
| D6 | `is_tex_source` accepts `\input`/`\include`; `looks_like_latex` stays narrow | The two predicates gate opposite decisions. A rejection gate must fail open (a false reject costs a user their work); an intent detector must not (a false positive refuses a legitimate markdown create). |
| D7 | Enforce in the latex decorator, not in core `reviews.put_source` | The guard is about the compile pipeline, which is the module's concern, and core stays free of feature semantics. Cost: the guard is flag-coupled while `meta.kind` is permanent. Accepted because a flag-off instance runs no compile, so #188's symptom cannot occur there. Core placement crosses no new import boundary and is the first thing to revisit if the flag ever varies by deployment. |
| D8 | Bounded 20-minute wait on staging adoption, then stop and report blocked | No ssh is available to this run, and the owner explicitly rejected hand deployments. Normalising a manual recreate would hide the automation defect rather than fix it. |
| D9 | Add a flag-on lane to CI (scope growth beyond the spine) | Without it the rename can ship a green image that then fails to boot, and the #188 regression has no standing guard after this run ends. Smallest form: two cases in a file CI already gates on. |
| D10 | Exercise the guard in-process, not over HTTP | The plan said to put the 400-gate assertions in `hosted_boot_smoke.py`. Reading the file showed its whole shape is "boot a build in a subprocess, read stdout" — there is no server to talk to, so that was hand-waving. In-process against `app.reviews` is also the honest level: the rule lives in the decorator, and `server.py` only renders the exception. |
| D11 | Add an unknown-template assertion rather than drop the coverage claim | Critic round 2 showed `template_smoke.py` never constructs `TemplateService` and never references `UnknownTemplate`, so "unknown template still 400, not 500" was covered nowhere in the repo. That is the one route-level path a botched rename silently breaks, and it was two lines to cover. |

## The critic gate

Round 1 returned **needs revision** with three must-fix findings. The blocking one was a genuine
defect in my plan, not a style note: `_require_tex` had no `kind` gate at either call site.
`server.py:88` rebinds `self.reviews` to `LatexAwareReviews` for **every** review kind, so an
ungated check there would have returned 400 on every markdown `update_source` in the product. I
verified that against the code before accepting it. The other two: §7's staging assertions were
partly unachievable and partly vacuous, and no automated lane ran with the latex flag on.

Round 2 was scoped to verifying the fixes. Its new finding (D11) is folded in.

## Verification performed

- `latexguard` self-check: 7 pre-existing asserts unchanged, 10 new.
- `hosted_boot_smoke.py`: 4 cases green, including the two new flag-on ones.
- **The regression test was confirmed to fail against the pre-fix code**, with #188's own symptom
  (`create latex with markdown` accepted). A test that has never failed proves nothing.
- `custody_regression_smoke.py` and `template_smoke.py`: green.
- `git grep -F "so its source must be a LaTeX document"` returns 0 hits on `dev` and 1 on the
  branch, which is what makes the staging liveness probe meaningful.

## Out of scope, filed separately

- `/api/latex/{rid}/pdf` returns 200 with the previous revision's PDF while the current compile is
  `failed`, and the viewer's Download button stays live, with no staleness signal.
- `latexguard` strips fenced code blocks but not inline code spans, so prose *about* LaTeX trips the
  create guard. Hit while authoring the plan for this very issue, which had to be created with an
  explicit `kind="markdown"`.
