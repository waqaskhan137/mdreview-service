# Run: session lifetime, keyboard shortcuts, per-session records

Tickets: #221, #222, #223. Process: `docs/process/autonomous-run.md`. Driver: `/loop`.
Owner reviews everything at the end; no check-ins between tickets.

## CURRENT POSITION — read this first, update it last

Every `/loop` firing is a fresh context. This block is the only handoff between wakeups.

```
ticket:    #221
stage:     4 done (implemented + check written; 8278deb, 42c3baa)
next:      stage 5 — validate locally: node tests/session_selfcheck.js, then
           tests/render-smoke.sh against a throwaway container for the dashboard + admin surfaces
branch:    fix/221-session-lifetime  (cut from origin/dev @ 8498542)
worktree:  .scratch/wt-221
pre-merge .deployed-digest: (not yet recorded — record at stage 6, BEFORE merging)
notes:     Shipped: web/app/static/session.js (new, dual browser/node export like linediff.js),
           callers rewired in dashboard.html boot(), account.js mount(), admin.html boot().
           session.js loads BEFORE the inline block on dashboard + admin (parse-time boot()).
           tests/session_selfcheck.js: 10 cases, verified to fail (exit 1) when the bug returns.
           Host-side .env.staging edit happens AFTER stage 7, not in the PR.
           NOT touched: viewer.html:937 also swallows /auth/session, but only to read a CSRF
           token for the share button. Different failure, not a false logout. Left alone.
```

Wakeup protocol: read this block, do the next stage, rewrite this block, commit. The **first**
commit on the first branch must include this file, so the log is recoverable from git and never
depends on an untracked file in a stale tree.

## Preconditions (checked 2026-07-28, before stage 1)

| # | Check | Result |
|---|---|---|
| P1 | Tickets identified, dependencies closed | PASS. #221 `status:ready`, #222 `status:ready`, #223 `status:backlog` (stage 1 grooms it). None blocks another. |
| P2 | A driver exists | **PENDING — the owner must invoke `/loop`.** There is no daemon; an agent executes only when a message arrives. The run does not begin until this is true. |
| P3 | One worktree per agent | Satisfied by construction: tickets run **sequentially**, each in its own worktree under `.scratch/wt-<issue>/`. No two agents share a tree. |
| P4 | Staging timer live + `auto-update.sh` carries the #163 fix | PASS. `systemctl is-active mdreview-staging-autoupdate.timer` = `active`; `grep -c repo_digest` = 2. |
| P5 | Route to a signed-in staging session | PASS. Staging sets `MDREVIEW_ALLOW_STUB_EMAIL=1`; magic links are read from `ssh kapture 'docker logs mdreview-staging'`. Accepted risk, restated: anyone who can read that log can complete a login as any email on staging. |
| P6 | CI/deploy facts read from `origin/dev` | Enforced per stage 3. The working tree is on `feat/ui-admin-nav` and is stale; every claim about CI, images or deploy uses `git show origin/dev:<path>`. |

## Order and why

Sequential, `#221 -> #222 -> #223`.

`#221`'s UI half and `#222` both edit `web/app/dashboard.html`. Running them in parallel makes it a
contended file (hard rule 9) and buys nothing: each ticket is hours, not days. `#223` runs last
because it is the largest and the only one that touches the authentication path.

## Blast radius

Prod (`app.mdreview.space`) runs the `:latest` image, built from `main`. Staging runs `:dev`. Every
merge in this run lands on `dev`, so nothing reaches prod without the owner's G8 go-ahead. Verified
2026-07-28 via `ssh kapture-agent ps`.

## Per-ticket plan

### #221 — session expires in hours, not weeks

**One PR, two commits** (see D5). Two halves:

1. **TTL.** The repo half is documenting the key and its default in
   `infra/deploy/.env.staging.example` and the prod runbook. The live half is
   `MDREVIEW_SESSION_TTL_S=2592000` in `~/mdreview-staging/.env.staging` on the host, applied over
   ssh and **not** part of the image. Staging only (D1). It persists across auto-updates because
   compose reads the env file. Verify by decoding the live staging cookie: `exp - iat == 2592000`.
2. **False logout (code).** A failed `/auth/session` *fetch* must not render the sign-in screen.
   `dashboard.html` `boot()` and `static/account.js` `mount()` both swallow the error and fall
   through to anonymous. Distinguish "server said `authenticated:false`" from "could not ask":
   retry once, then show a connection state.

Check to leave behind: a test that a rejected fetch does not produce the signed-out branch.

Ordering on the host: apply the `.env.staging` change **after** stage 7 confirms the new image was
adopted, so the container recreate that picks up the env var is the last thing that touches staging
and the cookie decode in stage 8 is unambiguous.

### #222 — keyboard shortcuts

`web/app/static/keys.js`: one table of `{keys, label, when, run}`, one listener per page, help sheet
generated from the table. Binds per the issue tables for viewer, latex-viewer and dashboard.
`Cmd/Ctrl + /` and `?` both open the sheet.

Two traps recorded in the issue and repeated here because they are easy to get wrong: `/` and `?`
are the same physical key (branch on `shiftKey`), and the sheet must work while focus is in a text
field, unlike every other bind.

Stage 5 uses `tests/render-smoke.sh`, and hard rule 5 applies: the viewers render through `marked`
plus `setTimeout` fallbacks, so settle explicitly before reading the DOM.

### #223 — per-session records + account UI

`sessions` table in the existing SQLite identity store, `jti` in the minted payload, `verify()`
rejects an absent or revoked `jti`. `GET /auth/sessions` + `DELETE /auth/sessions/{jti}`, both
owner-scoped and CSRF-checked. Account UI copies the existing "Your tokens" card pattern.

Migration: **grandfather** (owner decision D3). A cookie with no `jti` stays valid until its `exp`.

Throttle `last_seen` writes (~5 min) or the table becomes a write amplifier.

Stage 8 for this ticket needs **two** signed-in staging sessions, not one: proving per-device revoke
means showing that ending session B from session A actually lands session B on the sign-in screen.
One session cannot demonstrate it. P5 gives unlimited logins via the container log, so use two
browser profiles or a normal plus an incognito window.

## Decision log

Every entry: what was decided, why, and **what would falsify it**. Own errors recorded explicitly.

### D1 — #221's TTL change is applied to staging only; prod waits for review
**Decided by:** owner, 2026-07-28.
**Why:** a prod config change is outside what an autonomous run may do, and the owner wants to see
the whole run before prod moves.
**Consequence, stated plainly:** the owner keeps logging out every 12 hours until they apply it.
`#221` reaches `status:review` with prod deliberately untouched, and the issue says so.
**Falsified if:** staging's app plane is not representative of prod's. It is: prod no longer runs
`mdreview-oauth2-proxy`, so both are native-magic-link-only. If a proxy container reappears on prod,
this reasoning is void.

### D2 — #223 runs all nine stages unattended
**Decided by:** owner, 2026-07-28.
**Why:** merges land on `dev`, and `dev` deploys to staging, not prod.
**Falsified if:** an auth regression on staging blocks stage 8 for the other tickets, or if the
`:dev` image is ever promoted without a G8 gate.

### D3 — existing jti-less cookies are grandfathered until `exp`
**Decided by:** owner, 2026-07-28.
**Why:** forcing a re-login is the exact annoyance #221 exists to remove.
**Known cost, accepted:** a grandfathered session cannot be listed or revoked per-device, so with a
30-day TTL the account's device list is incomplete for up to a month after deploy. The UI must say
this rather than silently showing a short list.
**Falsified if:** the incomplete list is judged worse than one re-login, or if a security event
makes revoking every old cookie urgent.

### D4 — no mdreview plan gate for this run
**Decided by:** owner, 2026-07-28.
**Why:** the owner reviews the finished work instead.
**Cost:** a wrong plan is discovered after three tickets are built on it.

### D5 — one PR per ticket, including #221
**Decided by:** agent, 2026-07-28.
**Why:** an earlier draft of this plan gave #221 two PRs. Stage 7 attributes a `.deployed-digest`
change to *your* merge SHA, and two merges in flight against one recorded pre-merge digest is
exactly the ambiguity hard rule 4 exists to prevent. One PR with two commits keeps the commits
logically separate without creating two digest races.
**Falsified if:** a ticket's halves turn out to need independent review or independent rollback.

### D6 — worktrees live under the gitignored `.scratch/`
**Decided by:** agent, 2026-07-28.
**Why:** the project's hard rule keeps temp state inside the repo, and the main working tree is on
a stale `feat/ui-admin-nav` with unrelated untracked files that must not be disturbed.
**Verified, not assumed** (hard rule 8): `git worktree add .scratch/wt-probe origin/dev --detach`
succeeded and was removed. A gitignored path is a valid worktree location.

### E1 — error recorded: the plan contradicted #221's own acceptance criteria
**What happened:** D1 scoped the TTL change to staging, but #221's AC still read "prod and staging".
The run would have had to either park the ticket or violate hard rule 6 on its first stage.
**Fix:** #221's AC now names staging as in-scope and prod as explicitly owner-side, citing D1.
**Lesson:** when an owner decision narrows scope, the ticket is edited in the same breath. A
decision recorded only in the run log is invisible to the agent reading the issue.

### E2 — every file #221 touches had moved on `origin/dev` since the evidence was gathered
**What happened:** stage 3's contended-file check compared the four target files against
`origin/dev`. Three of four differed from the tree the issue's evidence was read in
(`feat/ui-admin-nav`): `dashboard.html`, `account.js`, `.env.staging.example`. Only
`RUNBOOK-phase1.md` was identical.
**What was done:** re-read the two code sites on `origin/dev` before trusting them. The defect is
unchanged in substance — `boot()` and `mount()` both still swallow a failed `/auth/session` fetch
and fall through to the anonymous branch — but `boot()` is at :442, not the :422 originally cited.
**Why it matters:** this is precisely hard rule 8. Had the run reasoned from the stale tree it
would have patched line numbers that no longer exist, and the "two readers agreeing" trap was live
here: the issue body and the plan were both written from the same stale tree.
**Standing consequence:** #221's body cites symbols, not line numbers. #222 and #223 must get the
same treatment at their stage 3, and their issue bodies still carry line numbers from the stale
tree. Re-verify before implementing, do not trust those citations.

### D7 — a shared `session.js` rather than the helper duplicated per caller
**Decided by:** agent, stage 4.
**Why:** the ladder says fewest files and shortest diff, which argued for duplicating eight lines.
Two things overruled it. The repo already has this exact precedent: `linediff.js` was extracted out
of the viewers specifically so the self-check could `require()` the bytes the browser runs, and its
header says the old scrape-and-eval approach made "the test drifted from the shipped function"
possible. And there turned out to be three callers, not two. Duplicating auth logic three ways is
how the admin console ended up with the correct pattern and the broken one seven lines apart.
**Cost, paid knowingly:** a `<script src>` line on five pages.
**Falsified if:** a second module wants a different retry policy, at which point the shared default
is wrong for someone.

### D8 — admin.html's boot() was fixed too, though #221's AC named only two call sites
**Decided by:** agent, stage 4.
**Why:** it is the same defect, same fix, three lines, and the file already contained the correct
treatment in `loadUsers()` immediately below it. This widens the fix, it does not weaken an AC
(hard rule 6 guards against the latter), and leaving one caller broken while touching its
neighbours would have been the odd choice to defend.
**Falsified if:** the owner wanted #221 kept strictly to the two named sites for review size.

### D9 — viewer.html's /auth/session call was deliberately left alone
**Decided by:** agent, stage 4.
**Why:** it reads a CSRF token for the share button. A failure there degrades sharing, it does not
render a false sign-in screen, so it is not this ticket's defect class. Recorded rather than
silently skipped.
**Falsified if:** a failed CSRF read turns out to break the share button in a way that reads as a
session problem to the user.

<!-- Entries below are added during the run. -->

## Stop conditions

Beyond the process doc's failure protocol:

- Any stage that needs a judgement this plan did not anticipate: stop and report, do not decide.
- A precondition that cannot be evaluated stops the run. Unevaluable is not true.
- If the run stops after stage 6 but before stage 7 completes, `dev` carries code that never
  reached staging. Say so on both the PR and the issue.
- Never weaken an acceptance criterion to make a ticket green. That is a finding, filed as its own
  issue.
- Stop at G4. `status:review`, never closed, never `main`.
