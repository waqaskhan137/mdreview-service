# sprint-38: G7 independent close review

Reviewer: staff-critic, independent. I did not plan, grow or build any part of sprint-38, and I did
not sit on any of its G1-G5 gates. Date 2026-07-29 (Europe/London). Epic: #255. Milestone:
sprint-38.

Verdict: **PASS**, with four deviations named below. Every work ticket shipped, merged and closes
against its acceptance criteria; the deviations are records and doc-consistency defects, and one of
them removed a gate record from git. None of them unships code.

Everything below was read from `origin/dev` @ `e276005`, in a clean worktree cut from it, never from
the author's working tree (which sat on `21a6081` with an uncommitted run-log edit). That is P6 of
`autonomous-run.md` applied to the review itself.

This is the first use of `docs/process/evidence/sprint-NN/`, the layout the working agreement
prescribes. Earlier sprints wrote to `docs/process/reviews/sprint-NN-*`, which is now in the frozen
zone and read-only.

## Scope versus delivered

Original scope was #254 -> #243 -> #241 with the 5-10 sprint floor waived at three. The owner added
#257, #261 and #262 mid-run; #265 split out of #261 when grooming found a shipped defect underneath
it. Final shape: seven work tickets.

| Ticket | Claimed | Verified on `origin/dev` | PR | Closed at G5 | AC |
|---|---|---|---|---|---|
| #254 | stage-8 key-delivery route + park procedure | present in `autonomous-run.md` under "Stage 8: real input, and what to do when it will not arrive" | #258 #259 #260 | 2026-07-29 | met, one internal contradiction (DEV-3) |
| #243 | viewport route + trap list | present under "The route that produces a specified viewport width", four traps tabulated | #263 | 2026-07-29 | 3 of 5 met, 2 partial (DEV-2) |
| #241 | design system §01-§10 as markdown | `docs/design/design-system-spec.md`, 333 lines, all ten `## §NN` headings resolve | #264 | 2026-07-29 | met |
| #257 | README 544 -> 107 lines, 81 -> 0 em dashes | `README.md` is 120 lines with 0 em dashes; four runbooks live under `docs/operations/` | #269 | 2026-07-29 | met, see the note on the line count |
| #262 | account menu, account page, `GET /api/account/shares` | endpoint present and authorising; all five `#acct` mount pages served from the rebuilt image | #268 | 2026-07-29 | met |
| #261 | palette polish + the invisible selected row | `var(--accent-soft)` has zero consumers; the selected row reads `var(--accent-bg)` plus a non-colour marker | #270 | 2026-07-29 | met |
| #265 | the palette really is full-screen at narrow widths | measured 606x752 at (0,0) with 0px radius; 384px and centred at 1280 | #271 | 2026-07-29 | met |

Two notes on that table rather than in it. #257's README is 120 lines on `origin/dev`, not the 107
its stage-9 comment recorded; the gap is #262's and #261's later commits adding links, it is still
well inside the 150-line cap, and the check enforces the cap rather than the snapshot. And #241's
extract records three divergences from shipped code instead of silently reconciling them, which is
what its ACs asked for.

## Verification method, per claim

I re-ran the sprint's own checks rather than reading their authors' reports. Full transcripts:
`runnable-checks.txt` and `container-smoke.txt` in this directory. The one em dash in this file
is inside a verbatim quote of the deleted D4 heading.

| Claim | How I checked it | Result |
|---|---|---|
| G7's own container condition | `docker build -f infra/Dockerfile`, throwaway container on a free port with a throwaway `MDREVIEW_DATA`, then `curl /healthz`, `GET /api/reviews`, `POST /api/reviews`, re-`GET` | build OK; healthz 200; list 200 empty then carrying the created review |
| the sprint's `web/app` changes reached the image | the same container served `/`, `/account` and `/review/<id>`; `docker exec` grep of `/app/web/dashboard.html` and `/app/web/static/account.js` | 200 on all three; `var(--accent-soft)` consumers 0; the `<=720px` block targets `.command-dialog>.command` |
| #262 degrades on a local build | `GET /api/account/shares` on the non-hosted image | 404, as designed; `SharingModule` is `build_hosted`-only and the page renders the section empty rather than erroring |
| #254 + #243 doc clauses | `python3 tests/stage8_doc_selfcheck.py` | exit 0, all clauses, including the four-reason park taxonomy and the constructed-`KeyboardEvent` ban with its #222 citation |
| #241 citation target | `python3 tests/design_spec_selfcheck.py` | exit 0, ten numbered headings, the standing reduced-motion rule carried with its attribution, method and falsifier |
| #257 README shape | `bash tests/readme_shape_selfcheck.sh` | exit 0, cap and zero em dashes and every `docs/` link resolving |
| #261 tokens | `node tests/css_tokens_selfcheck.js` | exit 0, every bare `var(--token)` on all five pages resolves |
| #261 bindings | `node tests/keys_selfcheck.js` | exit 0, and the vacuous `100vw` text case is gone: `grep -F 100vw tests/keys_selfcheck.js` returns nothing |
| #262 menu | `node tests/account_menu_selfcheck.js` | exit 0, including the retired `#7c6cff` removed and the reduced-motion guard declared where it can actually win |
| #262 endpoint | `python3 tests/account_shares_selfcheck.py` | exit 0, including 401 anonymous, a second user seeing none of mine, and a review with neither right absent |
| #265 rendered geometry | `bash tests/palette_fullscreen_selfcheck.sh` | exit 0: 606px panel at (0,0) with 0px radius, 384px still centred at 1280 |
| #265's own falsifier | the AC demands the check fail when the selector reverts to `.command-dialog` | the check reads `getBoundingClientRect()` and nothing else; the geometry assertions cannot pass on a transparent wrapper |
| PRs merged, checks green before merge | `gh pr view` head SHA against `gh api .../check-runs`, completion time against merge time | all ten PRs merged into `dev`; `pr-checks` `completed/success` on the merged head SHA, concluding before the merge in every case |
| no orphaned PRs | `gh pr list --state open` | one open PR, #248, which is the sprints 35-36 run log and not this sprint's |
| board integrity | the README drift query, plus `gh issue view` on the two findings filed | zero open issues off contract; #266 and #267 both exist, both on sprint-39, each with exactly one `status:` label |
| carry-overs | milestone sprint-38 | seven work tickets closed, zero carry-overs; the only open item is epic #255 itself, held for this review |

`pr-checks` is a floor and the working agreement says so: both its smokes are server-side and neither
reads `web/app/**`. Four of this sprint's seven tickets touch `web/app`, so the rebuilt container and
the two CDP geometry checks are the only end-to-end evidence that exists for them. That is why the
container smoke above greps the image rather than trusting the build.

## Deviations

### DEV-1. The D4 decision record was written, then deleted from git

`a357143` is titled "docs(process): resolve run-log conflict, record D4 (merges de-serialised)
(#265)" and it did add the entry. `df1c1a8` ("sprint-38 complete, final scorecard and the run's
lesson", PR #274) then replaced the whole `CURRENT POSITION` block, and D4 went with it. On
`origin/dev` the run log's decision log holds D1, D2, D3, E1, E2, E3 and no D4.

What was deleted:

> ### D4 — one-ticket-per-adoption-window dropped, owner's explicit call 2026-07-29
> ... Owner chose the trade: coarser attribution (one digest covers four tickets) for all of them on
> staging in one cycle.
> **Cost accepted:** if that adoption misbehaves, it cannot be attributed to a single ticket.
> **Falsified if:** an adoption fails and the ambiguity actually costs more than the 45 minutes saved.

The same commit also replaced the per-ticket digest chain with the single line "Final staging digest
9ac5cdc4". The chain the issues still carry is `14b2396f` -> `5c1fc5e7` (#243) -> `fd87b2ca` (#241)
-> `bff42241` (#257 **and** #262 **and** #261) -> `9ac5cdc4` (#265).

That shared `bff42241` is the trade made visible. Stage 7's exit criterion is the CI run for *your*
merge SHA plus a digest differing from *your* recorded pre-merge value, and hard rule 4 says "a
digest change on its own is not *your* deploy". For #257, #262 and #261 the second half holds only
jointly: one adoption, three tickets, no per-ticket attribution. The owner made that call knowingly.
The record of him making it is now the only decision in the sprint with no entry, and the epic's own
scorecard comment still cites "(D4)", so that citation dangles.

`autonomous-run.md` requires of the run log: "One entry per decision: what was decided, why, and
**what would falsify it**." The closing edit overwrote gate evidence instead of appending to it.
`df1c1a8` is also the only non-merge commit in the sprint whose subject carries no `(#N)`, against
the working agreement's "Commits reference their issue in the subject". One commit, both defects.

Direction: restore D4 to the decision log with its accepted cost and falsifier, and restore the
digest chain, in a `docs(process)` commit referencing #255. This is history, not prose.

### DEV-2. #243's amended AC5 is unmet, and was unsatisfiable as written

AC5 asked for the winning route exercised against a shipped width-specific surface: "the dashboard's
narrow-width behaviour from #184 (44px tap targets + headline ramp) observed at `window.innerWidth`
~= 1180 on staging, quoting the value measured in the page **and the computed property that proves
the ramp applied**."

The stage-8 comment on #243 records `innerWidth` 1180 exactly on attempt 2, which satisfies AC4. It
records no computed property, at any width. And the AC could not have been satisfied at 1180:
`dashboard.html` contains exactly one breakpoint, `@media (max-width: 720px)`, and
`tests/dashboard_narrow_selfcheck.sh` asserts the ramp at 606 with 1400 as the unchanged control
(`.nu-title` 32px -> 24px). At 1180 there is no ramp to prove, by construction.

So the honest reading is that the AC was wrong, not merely skipped: it named a width at which the
behaviour it wanted evidence of is inactive. The capability it was reaching for does exist and was
demonstrated, just on a different ticket: #265's stage-8 record measures a real 606px window with a
real `Cmd+K` and the panel at 606x752 at (0,0).

Direction: no reopen. Amend #243 with a dated comment saying AC5's stated width contradicted the
shipped breakpoint, and point at #265's 606px reading as the evidence that lands. Naming a wrong AC
is cheaper than leaving a closed ticket that reads as if a measurement were taken.

### DEV-3. `autonomous-run.md` states #254's load-bearing conclusion two ways

Inside one section, "Stage 8: real input, and what to do when it will not arrive":

> This shape is necessary but NOT sufficient. ... Delivery is **intermittent** and the trigger is
> not understood.

and then:

> **Confirmed 2026-07-29: the key goes to whichever window the OS considers frontmost.** ... That is
> the whole variable.

Both cannot be true. An agent at 3am reading the first sentence parks; reading the second, it asks
the owner to bring Chrome forward and retries. The later paragraph is the corrected one and the
earlier survives uncorrected, which is the same shape as the stale claim this sprint exists to have
fixed. E2 in the run log has the matching gap: its falsifier reads "Falsified if: the OS-frontmost
hypothesis is confirmed", the doc says "Confirmed 2026-07-29", and E2 was left standing. E1 also
still records the burst as "reproducibly (3/3)" where the doc says 4/4 and not reproducible.

Direction: mark the intermittency paragraph as superseded by the frontmost finding, keeping the
history visible, and close E1/E2 with the outcome their falsifiers fired on.

### DEV-4. Two #243 doc clauses landed in substance but not as specified

Both are small and both are in the artifact rather than around it.

AC1 asked the doc to state that "a headless/CDP check is legitimate as the stage-4 runnable check and
never as stage-8 evidence". `autonomous-run.md` mentions headless twice and both are prohibitions:
"Never headless, never a synthetic event" and "do not fall back to headless". The permitted half is
absent, and this repo's own runnable checks are headless CDP:
`tests/palette_fullscreen_selfcheck.sh`, `tests/css_tokens_selfcheck.js`,
`tests/dashboard_narrow_selfcheck.sh`. #261's groomer had to re-derive the distinction in an issue
comment ("that headless run is grooming reconnaissance, not stage-8 evidence"), which is the
re-litigation the AC existed to stop.

AC2 named the flowchart: "The flowchart's stage-8 failure branch covers **more than 'no session'**".
The four-reason taxonomy table was added and is what `stage8_doc_selfcheck.py` asserts, so the
substance is there, but the mermaid edge still reads `S8 -.no session.-> PARTIAL`.

Direction: one `docs(process)` commit adding the permitted-headless sentence and relabelling the
mermaid edge, plus a `stage8_doc_selfcheck.py` clause for the headless sentence so it cannot decay.
Worth folding into DEV-1's restore commit.

## Not deviations, recorded so a later reader does not re-find them as defects

The 5-10 sprint floor was waived at three by the owner (D1), with #187 and #70 accounted for rather
than missing. Scope grew from three to seven mid-run; #257 got a dated comment at the time, #261,
#262 and #265 did not, and the product-owner agent recorded that gap explicitly at G5 rather than
letting the milestone's history read as if they had always been in scope. Both are the process
working.

The owner approved #254 at G5 without the frontmost re-test. That is his call, recorded on the
ticket, and the intermittency plus the retry-then-park procedure stand documented as merged.

All seven tickets are closed while still carrying `status:review`. The label contract binds open
issues only ("Exactly ONE `status:` label per open issue"), and done is closed. Not a drift.

Open PR #248 is the sprints 35-36 run log, not this sprint's, and is opened on a branch whose work
already merged as #247. Out of scope here; naming it so sprint-38 is not charged with it.

## Risk this sprint hands forward

Clause 1 of the epic was "stage 8 can verify what it claims". It delivered the two halves
separately, and `autonomous-run.md` says plainly that they have never been obtained together: "A
specified viewport width and real key delivery have never been obtained in the same window." Being
honest about that was an AC, and it was met. The consequence is that a narrow-width keyboard
criterion is still not agent-verifiable, and key delivery at any width needs the owner at the machine
with Chrome frontmost.

The epic held #187 for sprint-39 on the grounds that clause 1 would repair the capability its ACs
need. Clause 1 repaired it conditionally. Whether #187 is now verifiable, or is a ticket that will
park on the owner's presence, is worth answering before sprint-39 picks it up rather than at stage 8.
The experiment that settles the width-and-keys question is one line of owner time and is already
written into the doc.

## Recommended follow-ups, not filed

I am not filing these; a close reviewer recommends and the owner or the product-owner agent files.
DEV-1, DEV-3 and DEV-4 are one `docs(process)` ticket together, all three being record and
doc-consistency repairs on the same two files. DEV-2 is a dated comment on #243, not a ticket. The
already-filed findings #266 (production CSRF gap on `DELETE /account/tokens/{id}`) and #267 (raw uid
where the comment promises an email) are correctly on sprint-39 and are outside this review.

## Milestone disposition

Seven work tickets closed, zero carry-overs, `pr-checks` green on every merged PR before its merge,
container smoke green, and every runnable check reproduced independently (eight, being the
sprint's seven new ones plus `keys_selfcheck.js`, which #261 modified). G7 passes.

Epic #255 and milestone sprint-38 are deliberately left **open** by this review. Closing them is the
owner's, executed through the product owner.
