# Night run — decision log (2026-07-25 → morning 2026-07-26)

Sprint: **sprint-34** (#176–#182), epic #152.
Plan: https://app.mdreview.space/review/d3b3487540 — critic-cleared in 3 rounds, owner-approved.
Worktree: `.claude/worktrees/design-system`. Owner asleep; no approvals available until morning.

---

## The ceiling: G4, not "sprint done"

`docs/process/README.md` puts three gates behind the owner, and none of them can be self-served:

| gate | needs | tonight |
|---|---|---|
| **G5** Done (`review` → closed) | **owner approval** | ✗ — issues land at `status:review`, none closed |
| **G7** Sprint close | independent close review + `evidence/sprint-34/` committed | ✗ |
| **G8** Promote to main | **explicit owner go-ahead** | ✗ — nothing goes near `main` |

So the night run's deliverable is: **every sprint-34 ticket at `status:review`, merged to `dev`, with evidence in an issue comment**, ready for a single morning pass of G5 acks. Merging to `dev` is inside the working agreement (dev takes PRs, 0 approvals, self-merge OK) and matches the 2026-07-23 run's precedent.

---

## Decisions taken before starting — review these

### D1 · Nothing is closed, nothing reaches `main`
Above. If every ticket succeeds the morning state is seven issues at `status:review` and a `dev` that is seven PRs ahead. The sprint stays open.

### D2 · One ticket in progress at a time, branch-per-ticket off `dev`
G3 says one in-progress at a time. Each ticket gets its own branch cut fresh from `origin/dev`, its own PR, self-merged, then the next branch cuts from the updated `dev`. No stacking — a stack means one bad ticket blocks six.

### D3 · Order is the plan's, unchanged
#177 → #178 → #179 → #180 → #181 → #182. #182 (`dashboard.html`) stays last because it is contended with another agent's work. **Not reordered forward, not pulled early even if I finish ahead of schedule.**

### D4 · Contention rule for #182
Before starting it: `git fetch` and diff `dashboard.html` on `origin/dev` against what I planned from. If another agent has touched that file since 7193c88, I **stop and park #182** at `status:blocked` with the diff in a comment rather than merge on top of work I did not read. Losing one ticket is cheaper than silently clobbering someone.

### D5 · Verification runs against a throwaway container, never the live instance
The live instance on **:8139** is not touched, and `docker compose up` is never run (compose says 8137 and would fight it). Each verification spins a throwaway container on a free port against a scratch `MDREVIEW_DATA` dir under `.scratch/`, and tears it down. Tools: `tests/render-smoke.sh` for R2's functional-DOM assertions, `scripts/cdp-shot.mjs --resize --eval` for computed-style and breakpoint checks.

### D6 · `.empty` takes **control-8**, not card-12
The plan leaves this to the implementer. Choosing 8: `.empty` is Basecoat's empty-state block, which on our pages sits *inside* a container rather than being one, and §04 draws it as flush content, not as a raised card. It also keeps it consistent with `.alert`, the other `--radius-lg` consumer we actually use. Recorded in #177's PR description.

### D7 · `--r-panel` is not retired tonight
#177 ships it unconditionally (§02 declares "16 · panels"). #180 records whether `.sharepop` wants it; #183 (⌘K, **not in this sprint**) would record `.command`. Since the second consumer's ticket is out of the milestone, **no ticket tonight is the last one to touch it**, so nothing removes it. An unused token is harmless; a token removed before its second consumer is evaluated is a bug.

### D8 · A ticket that cannot meet its AC is parked, not forced
`status:blocked` + a comment saying exactly which criterion failed and what I tried. I do not weaken an acceptance criterion to make it pass — those were fought over across three critic rounds and are the main thing standing between this sprint and a silent breakage.

### D9 · Scope is frozen at the seven sprint tickets
#183 and #184 are deliberately outside the milestone; #185 and #186 are deferred by owner decision. **I do not pull any of them in**, even if the sprint finishes early. Changing sprint scope is the owner's call, and "we had time" is not a reason.

### D10 · Tactical calls go to `user-proxy`; its hard-escalation list means park
Low-stakes implementation choices get decided. Anything on the proxy's escalation list — design changes, new dependencies, scope changes, secrets, gate decisions — is parked with a note, not guessed at.

### D11 · Realistic expectation
Six code tickets, each with a real verification gate, is optimistic for one unattended run. **#177–#179 are the confident set**; #180's 63-literal conversion is wide and its R3 breakpoint check is fiddly; #182 is large, contended, and mostly hand CSS. If the run ends partway, it ends on a merged ticket with the next one untouched, never mid-edit.

---

## What is deliberately NOT touched

- The **seven issues already at `status:review`** awaiting the owner's G5 (#86, #88, #136, #75, #78, #44, #15) — not mine.
- **`sprint-32` / `sprint-33`**, both open with zero open issues pending a G7 close review. Flagged, not actioned; G7 needs an independent reviewer.
- **#163**, the one drift violation (no `status:` label). Adding a label is a triage decision on someone else's bug.
- `docs/process/epics/viewer-dashboard-reskin-plan.md` — frozen archive, marker lives on #152 (done in #176).
- `web/site/`, any backend or API change, `main`.

---

## Pre-flight — done before the owner slept

Deliberately validated the verification toolchain first, because a night run that discovers at
03:00 that it cannot verify anything is a night run that ships unverified work.

### D5 amended · Docker is not running on this machine
`docker ps` fails — no daemon. So "throwaway container" becomes **throwaway stdlib process**:
same isolation (own port `:8172`, own `MDREVIEW_DATA` under `.scratch/`), no daemon needed. The
live instance on `:8139` is still untouched and `docker compose up` is still never run, which is
what D5 was actually protecting. Harness checked in at `.scratch/nr-up.sh`.

### The hosted plane needs six env vars and fails closed on each
Discovered one at a time, because each guard refuses to boot rather than defaulting:
`MDREVIEW_SESSION_SECRET`, `MDREVIEW_TOKEN_PEPPER`, `MDREVIEW_OWNER_EMAIL` (without it "a stranger
could self-crown under open membership", #67 H1), `MDREVIEW_ALLOW_PROXY_PLANE=0`,
`MDREVIEW_PUBLIC_BASE` (absolute `https://`), and an email sender — which refuses to boot
"rather than silently leak login tokens". That is good design and tedious bring-up; the script
now encodes all six so it is derived once, not six times.

### What is reachable without a session
`/` 200, `/admin` 200, `/account` **401**. So `/account`'s verification in #178 needs a session
cookie; the pattern exists at `tests/auth_smoke.py` (`cookie(sub, email)`, its own pepper and
session secret). Noted now so #178 does not stall on it.

### Both AC tools work, and fail loudly rather than false-passing
- `tests/render-smoke.sh` — reported `MISSING: .btn (0 nodes)` against a down server rather than
  passing. That is the R2 gate behaving correctly.
- `scripts/cdp-shot.mjs --eval` — reported `eval threw` rather than passing. `--resize 1180x900`
  confirmed `window.innerWidth===1180`, so **R3's breakpoint method is validated** before #180
  depends on it.

### Baseline captured: #177's premise is confirmed empirically
On `/admin` as it stands today, `.btn` computes to **6px** and `.card` to **12px**. That is
exactly the mismatch the critic derived from Basecoat's `calc()` offsets in round 1 — control and
card cannot both be right from one `--radius`. #177's after-state must show `.btn` 8px, `.card`
12px. The before/after now has a measured baseline rather than an assumed one.

---

## The delivery loop (owner-specified, 2026-07-26)

Branch per issue → PR into `dev` → merge → work accumulates on `dev` → deploy to staging →
visually inspect → hand back. The owner holds approval on what happens after.

### D12 · PRs merge sequentially, not batched at the end
The owner said "gather all PRs and merge to dev". Reading that as *the work accumulates on `dev`*,
not *six PRs sit open until the end*, because **#178 consumes #177's tokens and #182 consumes
#178's shell** — an unmerged stack means each ticket is verified against a `dev` that does not
yet contain what it depends on, which is how you get six green PRs and a broken `dev`. Each
ticket therefore: branch from current `dev`, PR, self-merge, next branch from the updated `dev`.
One staging deploy at the end covering everything, per the loop above.

### D13 · Staging does NOT auto-deploy — that assumption is false, and #163 is why
The owner's instruction says "watch if it gets deployed automatically on staging". Half of that
happens:

- `.github/workflows/staging-image.yml` **does** build and push the `:dev` image on a `dev` push. ✓
- The staging host **never adopts it**. That is open bug **#163** — `auto-update.sh` never picks
  up a new `:dev` image under the containerd image store (manifest-vs-config digest mismatch). ✗

So waiting for staging to update on its own would mean waiting all night and reporting nothing.
**Decision: deploy staging by hand**, using the established documented workaround —
`docker pull :dev` then `compose up -d --force-recreate mdreview-staging` on the Kapture host,
**health-gated on `healthz`=200 and `/api/reviews`=401** (the second proves custody is intact and
the instance did not come up unauthenticated). This is staging, not prod, and the procedure is
already the recorded norm rather than something invented tonight.

If the host is unreachable, or the health gate fails, I **restore the previous image and report**
rather than leave staging broken overnight. A broken staging box the owner wakes up to is worse
than an un-deployed one.

### D14 · Chrome-extension inspection is valid for layout, not for animation
Screenshots via the browser extension are the right tool for the shell, the row rules, both
themes, and the narrow-width pass. They are **not** valid evidence for `prefers-reduced-motion`
or any CSS animation: automation tabs are backgrounded, which freezes CSS animations, so a
screenshot of a "static" element proves nothing. #184's reduced-motion AC is therefore verified by
computed `animationName`/`currentTime` stepping under a CDP override, exactly as its AC already
says — and #184 is out of this sprint anyway.

---

## Run-time decisions

Appended as the run proceeds. Each entry: ticket, decision, why, and what would falsify it.

### #176 · Reskin epic superseded — DONE, `status:review`
Completed before the run began. #152 retitled off the stale "Next.js + shadcn" framing (original preserved in a collapsed `<details>`), Adopted section added recording the predecessor epic and carrying its R2/R3/R7 forward as gates, child task list wired, dated amendment comment posted. `docs/process/` unmodified, as required.

**Correction recorded:** the plan's §1a said that epic's viewer half had not shipped. It had — `viewer.html` carries the breadcrumb, `body.gutter-on` (`:648`), `#dock` (`:255`) and `#resolved` (`:262`), and sprint-28 closed under a recorded G7. So §1a shrank from "reconcile live work" to "write the marker". Two further citation errors found at the same time: `scripts/render-smoke.sh` is `tests/render-smoke.sh`, and the `gutter-on` toggle is `viewer.html:648`, not `:694`. Errata posted to the review.
