# sprint-39: G7 independent close review

Reviewer: staff-critic, independent. I did not plan, groom or build any part of sprint-39, I did not
sit on #273's G1, and I did not sit on any of this sprint's G2-G5 gates. Date 2026-07-30
(Europe/London). Epic: #275. Milestone: sprint-39.

Verdict: **PASS**, with five deviations named below. All eleven work tickets shipped, merged and
close against their acceptance criteria; every runnable check they cite passes on current
`origin/dev`; the container smoke is green; and staging demonstrably serves a build of `origin/dev`
HEAD, which every ticket's commit is an ancestor of. The deviations are one broken stage-7
attribution, two classes of overstated record, a missing error log, and one unfinished housekeeping
item. None of them unships code.

Everything below was read from `origin/dev` @ `ca838f4`, in a clean worktree cut from it, never from
the author's working tree (which sat on `feat/ui-admin-nav` with a staged run-log edit and an
untracked zip under `web/app/`). That is P6 of `autonomous-run.md` applied to the review itself.
Transcripts in this directory: `runnable-checks.txt`, `container-smoke.txt`,
`staging-deploy-chain.txt`. The two em dashes in this directory are both inside verbatim tool output:
`3a14d61`'s commit subject, and one `ok` line printed by `pr_checks_guard.py`.

## Scope versus delivered

The epic opened with five tickets (#272, #266, #187, #267, #144) and named #273's slices as
contingent on its G1. G1 landed the same day (round-3 verdict "proceed with named risks", owner
sign-off accepting all three), so #288-#291 were adopted. #299 (sprint-38's four G7 deviation
repairs) and #302 (the magic-link 502 plus the dead P5 route, found inside #288's own stage 8) were
adopted on 2026-07-30. Eleven work tickets; the 5-10 floor was met by the original five, so no
waiver was needed here. The G3 one-in-progress rule was waived at G6 for parallel mode.

| Ticket | Claimed | Verified on `origin/dev` | PR | Closed at G5 | AC |
|---|---|---|---|---|---|
| #272 | `reconcile.py` persists the human custody decision | `custody_reviewed_at` in `reconcile.py`, quarantine stamps it without binding an owner | #292 | 2026-07-30 | met |
| #266 | CSRF on `/account/tokens` mint and revoke | `_csrf_ok` guards both arms in `server.py`, four `#266` markers | #293 | 2026-07-30 | met, stage 7 broken (DEV-1) |
| #187 | manual resolve, approval-class, human-only | `POST /api/reviews/{id}/resolve` cookie-plane arm, `ReviewService.set_resolved`, `resolved_by_human`, `.res` row action in `dashboard.html` | #296 | 2026-07-30 | met |
| #144 | auth audit read endpoint + admin console view | `AdminRoutes._audit_read` on `GET /admin/audit`, `#auditcard` / `#auditpanel` + Load more in `admin.html` | #297 | 2026-07-30 | met |
| #267 | shares payload carries grantee email | `SharingModule._shares` resolves via `users.email_for`, `_shareLabel` prefers `email` in both viewers | #298 | 2026-07-30 | met, after a stage-3 park |
| #288 | revision precondition, 409 contract, `can_edit` | `ETag` on `GET /source`, compare inside `ReviewService.put_source`, `revision` + `can_edit` on `/status`, optional `expected_revision` on the MCP tool | #300 | 2026-07-30 | met |
| #289 | session-keyed CSRF on `PUT /source` + attribution lifecycle | `check_csrf` composed in `build_hosted`, `source_updated_by` set by reviewer writes and deleted by agent writes | #304 | 2026-07-30 | met |
| #290 | markdown viewer edit UI | `#editpane` + `#editbtn` gated on `setEditVisible(!!st.can_edit)`, logic factored into `web/app/static/editguard.js` | #308 | 2026-07-30 | met |
| #291 | latex viewer edit UI, 400 vs 409 distinct | `#editpane` over `#srcscroll`, `_NOT_TEX` 400 path and stale-revision 409 path separate, guard wins | #306 #307 | 2026-07-30 | met, G5 record wrong (DEV-3a) |
| #299 | sprint-38's four G7 deviation repairs | D4 and the digest chain restored in the sprint-38 run log, `autonomous-run.md` states #254's conclusion once, permitted-headless clause present, mermaid edge relabelled | #301 | 2026-07-30 | met |
| #302 | magic-link SMTP failure keeps the constant 200, P5 true in both modes | `magiclink_send_failed` audit + byte-identical 200 in `authroutes`, P5 rewritten with both email modes and the `select_email_sender` precedence | #305 | 2026-07-30 | met |

`#273` (the edit-in-place epic) closed correctly. All four children are closed, its closing comment
lists each with its PR and its verification comment, and it declines to stand in for this G7. Two
notes: it carries no milestone, which its own close states and which matches #241's relationship to
#255; and it went `status:in-progress` straight to closed without passing through `status:review`.
The label contract binds open issues only, so that is a skipped state rather than drift. Item 4 of
that comment repeats #291's wrong evidence claim (DEV-3a).

## The staging-deployment claim, checked rather than accepted

Every G5 comment in this sprint asserts "staging's `.deployed-digest` confirmed serving that build".
It holds, and here is the chain rather than the assertion. `.deployed-digest` reads
`ghcr.io/ranawaqas-ai/mdreview-service-latex@sha256:251a9d0b...`, mtime 01:08 UTC. That image's
config `Created` is `2026-07-30T00:55:07Z`, thirteen seconds inside the `staging-image.yml` run for
`ca838f4` which concluded `00:55:20Z`; no staging-image run has run since; the container was created
`01:08:11Z`. The decisive evidence is not the timing, it is the bytes: the running container carries
`/app/web/static/editguard.js`, a file that exists only from `ca838f4`, which is `origin/dev` HEAD.
An image containing it can only have been built from HEAD. `git merge-base --is-ancestor` confirms
all eighteen ticket-bearing commits are ancestors of `ca838f4` (18/18), and `docker exec` grep found
each ticket's own symbol in the running container. Staging `/healthz` answers 200.

So the claim is **confirmed**, at the sprint level. What is *not* confirmed is per-ticket
attribution, which is stage 7's actual exit criterion. Nine of the eleven tickets rest on "a later
build contains my merge". Only #288 (D6 in the run log) and #302 carry a genuine
this-merge-then-this-digest record, and #266's own build never happened at all (DEV-1).

## Verification method, per claim

I re-ran the sprint's own checks rather than reading their authors' reports. Fourteen checks, all
exit 0, all on `origin/dev` @ `ca838f4`.

| Claim | How I checked it | Result |
|---|---|---|
| G7's own container condition | `docker build -f infra/Dockerfile`, throwaway container on a free port with a throwaway `/data`, then `curl /healthz`, `GET /api/reviews`, `POST /api/reviews`, re-`GET` | build OK; healthz 200; list 200 empty then carrying the created review |
| the sprint's `web/app` changes reached the image | the same container served `/`, `/account`, `/review/<id>` and `/static/editguard.js`; `docker exec` grep of the image's own `web/` and `src/` | 200 on all four; every ticket's symbol present. `/admin` 404s on a local build, correctly: the admin console is a hosted-plane module |
| #288 seam visible end to end on a real build | `curl -D-` on `GET /source` and `GET /status` against that container | `ETag: "0"`; `/status` carries `revision`, `can_edit`, `source_updated_by` and #187's `status` |
| #272 custody | `python3 tests/custody_regression_smoke.py` | exit 0, 19 cases, including quarantine stamping `custody_reviewed_at` without binding an owner and refusing an owned record |
| #266 token CSRF | `python3 tests/account_tokens_csrf_selfcheck.py` | exit 0, 13 cases, including the token surviving a blocked revoke and proxy/bearer planes unchanged |
| #187 manual resolve | `python3 tests/manual_resolve_smoke.py` | exit 0, 25 cases, including an agent token that can write the source being refused on `/resolve`, and no resolve MCP tool existing in any plane |
| #144 audit read | `python3 tests/admin_audit_selfcheck.py` | exit 0, 16 cases, including the `before` cursor boundary with no overlap and malformed `before` 400 |
| #288 precondition | `python3 tests/revision_precondition_selfcheck.py` | exit 0, 36 cases, including 409-writes-nothing, the raw-vs-envelope `get_source` split, and `can_edit` false for a comment-share grantee and for an anonymous public reader |
| #289 CSRF + attribution | `python3 tests/source_csrf_attribution_selfcheck.py` | exit 0, 33 cases, including CSRF not shadowing #288's precondition and the agent write deleting the key again |
| #267 shares email | `python3 tests/review_shares_email_selfcheck.py` | exit 0, 6 cases, including `""` for an unresolvable subject rather than an invented address |
| #291 latex edit contract | `python3 tests/latex_edit_ui_selfcheck.py` | exit 0, 25 cases, including 400-with-nothing-written and the guard winning over the precondition when a body is both invalid and stale |
| #290 editor logic | `node tests/editguard_selfcheck.js` | exit 0, 22 cases, including `parseRevision("0") === 0` (the `if (!rev)` trap) and `If-Match` sent for revision 0 |
| #302 magic-link failure | `python3 tests/magiclink_send_failure_selfcheck.py` | exit 0, 9 cases, including the byte-identical 200 and a non-SMTP exception still propagating |
| #299 doc clauses | `python3 tests/stage8_doc_selfcheck.py` | exit 0, 33 cases, including the frontmost cause stated once and the permitted-headless clause present |
| the seam oracle | `python3 tests/access_seam_oracle.py` | exit 0, byte-identical both tiers, hosted denials correct. Degenerate here by construction: before and after are the same tree, so this reproduces the re-blessed baseline rather than the re-bless itself |
| pr-checks wiring is real, not just claimed | `python3 tests/pr_checks_guard.py` plus reading `pr-checks.yml` from `origin/dev` | exit 0; ten steps wired, including #266, #187, #144, #288, #289, #267 and #291's checks |
| PRs merged, checks green before merge | `gh pr view` head SHA against `gh api .../check-runs`, completion against merge time | thirteen PRs merged into `dev`; `pr-checks` `completed/success` on every merged head SHA, concluding before the merge in every case (tightest: #306 by 13 s) |
| no code arrived outside a PR | `git log --first-parent e276005..ca838f4` | every first-parent commit is a merge commit or a squash carrying its `(#NNN)` |
| board integrity | the README drift query | one hit, #311, filed by the owner at 04:29Z today with no labels; not a sprint-39 artifact, see the note below |
| carry-overs | milestone sprint-39 | eleven work tickets closed, zero carry-overs; the only open item is epic #275 itself, held for this review |

`pr-checks` is a floor and the working agreement says so: both its original smokes are server-side
and none of its ten steps reads `web/app/**`. Five of this sprint's eleven tickets touch `web/app`,
so the rebuilt container plus `editguard_selfcheck.js` (which `require()`s the shipped file) are the
only mechanical evidence for the UI half. That is why the container smoke greps the image.

### The Chrome-verified group

I cannot re-run a browser session, so for #144, #187, #267, #290 and #291 I checked that the
described behaviour exists in the code as claimed. All five read true, and three are tight enough to
be near-conclusive.

- #187: "hovered the row to reveal the resolve icon, Yours 8 to 7, Resolved 1 to 2, row moved into
  the collapsed Resolved group with no page reload". `dashboard.html` has the hover-revealed `.res`
  button one slot left of `.del`, `setResolved()` refetches and re-renders in place, `#ct-resolved`
  and the `needs` count are recomputed per render, and the resolved group is collapsed unless asked
  for by name. Matches.
- #290: quoted `"70 words · ~1 min read · v1"`. `#docmeta` is composed as
  `words + " words · ~" + minutes + " min read" + (rev ? " · v" + rev : "")`. A format that specific
  is hard to fabricate.
- #144: "opened Admin console, scrolled to Audit log, table renders newest-first with raw email and
  IP". `#auditcard` exists with exactly that shape and `_audit_read` returns raw fields per the
  owner's stated policy.
- #267: "the panel displayed the real email under Share with people". `_shareLabel` returns
  `s.email` when present, under a `<h4>Share with people</h4>` heading. Matches.
- #291: "`#srcscroll` swapped for a textarea", plus an async compile failure showing an expandable
  Tectonic error while the last good PDF kept serving. The code path exists. See DEV-3a for what
  that comment does *not* record.

Session provenance is accounted for, which mattered because the epic itself pre-declared a
`no-session` park: all five tickets first parked `no-session` on staging's real-SMTP mode, then were
unparked in one sitting with the owner signed in via a magic link redeemed from Gmail, with Chrome
frontmost for #290's typed half. That is the honest route, recorded as two comments per ticket
rather than one retrospective claim, and it is the process working.

## Deviations

### DEV-1. #266's stage-7 exit criterion was never met, and cannot be under parallel mode

Stage 7 requires "the CI run for **your** merge SHA concluded successfully". For #266 it did not.
`staging-image.yml` run `30497750870` on merge `f254d7a` reports `conclusion=cancelled`, with
`boot-smoke=success` and `image=cancelled`: the next `dev` push landed about two minutes later and
`concurrency: cancel-in-progress` killed the image job. No staging image was ever published for
#266's merge. Its code did reach staging inside a later build, and I confirmed it in the running
container (four `#266` markers in `server.py`), so this is attribution, not correctness. The
failure protocol's obligation to note that "`dev` carries code that never reached staging" was never
triggered, because a sibling's build silently covered it.

The structural point matters more than the instance. `cancel-in-progress` on a static group plus
merges two minutes apart makes stage 7's per-merge-SHA half unattainable by construction. Sprint-38
met this as a deliberate trade (D4, one digest across three tickets) and recorded it. Sprint-39 hit
it as an accident and recorded nothing: only #288 and #302 carry a real stage-7 record, and the other
nine G5 comments say "staging's `.deployed-digest` confirmed serving that build", which is a
statement about the sprint, not about the ticket.

Direction: pick one and write it down. Either serialise the adoption windows for tickets that need
per-ticket attribution, or amend stage 7 to accept "a successful staging-image run for a descendant
commit that contains my merge, plus a functional check only my change can pass" (which is exactly
what #288's D6 already does well) and say so in `autonomous-run.md` instead of leaving nine tickets
resting on an unstated reading.

### DEV-2. The "N/N pass" figures in the stage-9 comments are not measurements

No check in this repo prints a case count. Every `N/N pass` in a stage-9 comment is the author's own
tally, and seven of eleven do not match the number of `ok` lines the check actually emits on
`origin/dev`.

| Check | stage-9 comment | `ok` lines, measured | |
|---|---|---|---|
| `custody_regression_smoke.py` (#272) | 19/19 | 19 | match |
| `account_tokens_csrf_selfcheck.py` (#266) | 13/13 | 13 | match |
| `review_shares_email_selfcheck.py` (#267) | 6/6 | 6 | match |
| `magiclink_send_failure_selfcheck.py` (#302) | 9/9 | 9 | match |
| `manual_resolve_smoke.py` (#187) | 13/13 | 25 | differs |
| `admin_audit_selfcheck.py` (#144) | 13/13 | 16 | differs |
| `revision_precondition_selfcheck.py` (#288) | "40 cases" | 36 | differs |
| `source_csrf_attribution_selfcheck.py` (#289) | 21/21 | 33 | differs |
| `latex_edit_ui_selfcheck.py` (#291) | 13/13 | 25 | differs |
| `editguard_selfcheck.js` (#290) | 17/17 | 22 | differs |
| `stage8_doc_selfcheck.py` (#299) | 22/22 | 33 | differs |

Every check passes, so nothing is unshipped and no acceptance criterion turns on the number. It is
still the same defect sprint-38's G7 named on #257's README line count: a figure reported from
somewhere other than the artifact it claims to describe, in a gate record. Six of the seven
understate, which is the tell that they are recollections rather than readings.

Direction: quote the check's own final line (`all #291 latex edit UI cases pass`), or paste the
count. A number that cannot be reproduced from the run it cites is worse than no number.

### DEV-3. Two G5 records assert evidence their cited comments do not contain

Both are on the closing record, which is the part of the history a later reader trusts most.

**(a) #291's rejected-write path was never exercised in a browser.** The G5 comment on #291 and item
4 of #273's closing comment both read "both save paths (rejected-write and async-compile-failure)
exercised for real". The cited stage-8 comment records something else: an async compile failure
(save returned 200 at v3, the PDF pane kept serving the last good v1, an expandable Tectonic error
appeared) and then a success path at v5. A 400 rejected-write never happened in the browser. It is
covered server-side, and well: `latex_edit_ui_selfcheck.py` asserts 400 with nothing written, 409
with nothing written, and the guard winning when a body is both invalid and stale. I re-ran it. So
the AC is met; the sentence describing how is wrong, in two places.

**(b) "live-curl verification on the record" is boilerplate.** The G5 comments on #266, #272, #289
and #299 all carry that phrase. None of the four cited comments contains a curl against anything.
#272's says the opposite in as many words ("Stage 8 ... was not independently re-run"), and #299's
says "no staging deploy verification applies". Only #302's use of the phrase is backed: its cited
comment records `/healthz` 200 and a `POST /auth/magic-link` returning 200 where it previously
returned 502.

Direction: DEV-3a is a dated correction comment on #291 and on #273 saying which path was actually
exercised and where the 400 evidence lives. DEV-3b is a template fix: the closing comment should
name the evidence the ticket has, not a fixed pair of nouns. Sprint-38's G7 named exactly this
failure mode inside a process doc; it has migrated to the G5 template.

### DEV-4. The sprint-39 run log has no error entries

`autonomous-run.md` on the run log: "One entry per decision: what was decided, why, and **what would
falsify it**. Own errors recorded explicitly, that is the part that pays for the document." The log
has nine decisions, D1 to D9, each with a falsifier, and they are good. It has zero error entries,
and this run generated at least three worth having.

1. #267 parked at stage 3 because rule-8 verification found its grooming claim ("client-only after
   #262") false on `origin/dev`. The park procedure says in terms: "Record it in the run log as an
   error entry, with what would falsify the diagnosis." It is recorded on the issue and on the epic,
   not in the log.
2. Nine of eleven tickets needed a coordinator stage-9 recovery because the build agent "stopped
   without reporting" (#144, #187, #266, #267, #272, #289, #290, #291, #299, #302 all say so). A
   failure mode that hit nine times in one run is the most instructive thing that happened, and it
   is invisible in the log.
3. Five stage-8 `no-session` parks and their later unpark in a single owner sitting. Sprint-38's log
   carried E1, E2, E3 for less.

The #267 park is also worth one sentence on its own cause: the false grooming claim came from a
line-number citation, `hosted/sharing.py:95`, and the re-groom's own confession is that "my grep
found `email_for` and never checked which handler it was in". Hard rule 8 bans exactly that ("Cite
code by **symbol**, not line number"). The rule earned its keep here, and #302's grooming body still
cites five line ranges.

Direction: append E1 to E3 to the sprint-39 log before the milestone closes. This is history, not
prose, and the stage-9 recovery pattern in particular is a process finding that deserves its own
ticket.

### DEV-5. PR #248 is still open, unresolved, and it is the epic's own housekeeping item

The epic body carries it under Housekeeping with an explicit instruction: "Resolve during the
sprint: rebase or recut onto current `dev`, merge if green, and do not let the run log rot unmerged."
It is still `OPEN` with `mergeable=UNKNOWN`, on the stale branch name `fix/206-latexguard-inline-spans`,
which is where sprint-38's G7 left it. The sprints 35-36 run log is therefore still not on `dev`
after being carried through two sprints as a checklist item.

Direction: recut it onto current `dev` and merge it, or close it and file the run log as its own
`docs(process)` ticket. Leaving it as a checklist line that survives its own sprint twice is how it
reaches a third.

## Not deviations, recorded so a later reader does not re-find them as defects

All eleven tickets are closed while still carrying `status:review`. The label contract binds open
issues only, and done is closed. Sprint-38's G7 settled this; not drift.

`magiclink_send_failure_selfcheck.py`, `editguard_selfcheck.js` and `stage8_doc_selfcheck.py` are
not wired into `pr-checks`. Neither ticket's ACs asked for it, and precedent is consistent (sprint-38
did not wire `stage8_doc_selfcheck.py` either; `pr-checks` has no node step at all). Worth one line
under follow-ups rather than a deviation, because #302's constant-200 property is an anti-enumeration
guarantee and an unwired check is one nobody notices decaying.

`access_seam_oracle.py` is degenerate for a close reviewer: it diffs `origin/dev` against the working
tree, so on a clean worktree at HEAD it compares the tree with itself. It confirms the re-blessed
baseline still holds and the hosted denials still fail closed. It cannot independently confirm the
re-bless, which was named risk 3 and was accepted by the owner at #273's G1 sign-off. Stated so the
green is not read as more than it is.

#302's grooming has a Scope section with checkable items rather than a heading called Acceptance
criteria. Substance over shape; G2 is met.

`3a14d61`'s commit subject contains an em dash, against the owner's standing ban that names commit
messages. One line, no more.

Issue #311 ("pressing ?") is the drift query's only hit, filed by the owner at 04:29Z on 2026-07-30
with no labels. It is not a sprint-39 regression, and it is worth naming here anyway, because
sprint-39 enlarged it. `keys.js` registers `["mod+/", "?"]` with `keepInField: true` and its
dispatcher calls `e.preventDefault()` when a binding runs, and the file states the intent out loud:
"The sheet must be reachable WHILE TYPING." So `?` opens the help sheet and swallows the character in
any input, textarea or contenteditable, by design. That design predates this sprint. What this sprint
did was ship two new textareas into pages carrying that binding: #290's markdown editor and #291's
LaTeX editor, both of which exist to have prose typed into them. When #311 is groomed, its fix
should be scoped to every field including the two new editors, not just the comment composer the
owner happened to hit it in.

## Risk this sprint hands forward

The keyboard-and-viewport risk sprint-38 handed to sprint-39 was retired the cheap way rather than
the durable way: the owner was at the machine with Chrome frontmost for #290's typed half, so it
never had to be solved. The one-line experiment that would settle whether a specified viewport width
and real key delivery can coexist is still unrun, and it is still written into `autonomous-run.md`.
The next sprint with a narrow-width keyboard criterion inherits the same open question.

Staging's email mode is now load-bearing on a decision the owner has not made. Real ACS SMTP means no
agent has a route to a cookie session, which parked five of this sprint's tickets at stage 8 and will
park every future browser criterion the same way. #302's adoption comment asked the owner for a
one-liner naming the intended mode; that answer is still outstanding. Until it lands, "the owner
signs in during the sitting" is the process, and it should be said that way rather than discovered
per ticket.

Edit-in-place shipped with all three of #273's G1 risks intact and accepted: an agent that answers a
409 by resending its buffered draft still overwrites the human's edit, mitigated by tool-description
wording only; local-tier attribution rests on a spoofable client header; and the golden-transcript
baseline was re-blessed for both drifts. The first is now reachable from a real UI by a real
reviewer, which raises its likelihood without changing its severity.

## Recommended follow-ups, not filed

A close reviewer recommends; the owner or the product-owner agent files. DEV-2, DEV-3 and DEV-4 are
one `docs(process)` ticket plus two dated correction comments: the run-log error entries, the G5
comment template, and the corrections on #291 and #273. DEV-1 is its own ticket and the only one with
a design decision inside it, because it changes what stage 7 means under parallel mode. DEV-5 is a
decision, not work: merge PR #248 or close it. The unwired checks and #311's scope are worth a line
each on whatever ticket picks them up.

## Milestone disposition

Eleven work tickets closed, zero carry-overs, `pr-checks` green on every merged PR before its merge,
container smoke green, fourteen runnable checks reproduced independently, and staging confirmed
serving a build of `origin/dev` HEAD that contains all eleven. G7 passes.

Epic #275 and milestone sprint-39 are deliberately left **open** by this review. Closing them is the
owner's, executed through the product owner.
