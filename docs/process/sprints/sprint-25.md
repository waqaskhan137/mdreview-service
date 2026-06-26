---
id: sprint-25
name: watcher-container — opt-in containerized watcher with subscription auth
status: closed         # planning | active | closed
start: 2026-06-24
end: 2026-06-27
goal: Make the watcher an opt-in docker service (`docker compose --profile watcher up`) authenticated by the user's Claude subscription, so a deploy can auto-action reviewer comments — gated on proving headless subscription auth works inside a no-keychain Linux container.
close_review: reviews/sprint-25-close-review-2026-06-24.md   # G7 PASS 2026-06-24 (staff-critic, independent — rebuilt the image, re-ran both auth gates + the compose e2e; W1/N1 resolved)
---

## Goal

Land the four-ticket `watcher-container` batch (GH #30): promote the working agent-launch prototype
into `watcher/`, build `Dockerfile.watcher` (Node + the `claude` CLI) and **prove headless
subscription auth in-container** (the make-or-break gate), wire an **opt-in** compose `profile` (off by
default) with an end-to-end Send→action test, and document the `setup-token`/`.env`/rotation runbook.
Success: `docker compose up` still starts only the service; `docker compose --profile watcher up`
auto-actions a Sent review off the user's subscription. Sprint closes at G7.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-069 | Promote the watcher launch prototype into `watcher/` (+ .env.example, gitignore .env) | infra | P1 | done |
| MR-070 | `Dockerfile.watcher` + headless subscription-auth proof (the gate) | infra | P1 | done |
| MR-071 | compose `watcher` profile (off by default, health-gated) + end-to-end Send→action; closes #30 | infra | P1 | done |
| MR-072 | Operator runbook: setup-token / .env / rotation / startup auth-probe | docs | P2 | done |

## Preferred execution order

Dependencies: MR-069 → none; MR-070 `depends_on` MR-069; MR-071 `depends_on` MR-070 (the auth + MCP
proofs must pass before compose builds on them); MR-072 `depends_on` MR-071.

1. **MR-069** (infra) — promote the prototype into `watcher/`, `.env.example`, gitignore `.env`.
2. **MR-070** (infra) — `Dockerfile.watcher` + the in-container auth + MCP-round-trip proofs. **The
   gate.** Needs a real `setup-token` (`TEST_TOKEN`) from the operator at test time.
3. **MR-071** (infra) — opt-in compose profile + end-to-end. Closes GH #30.
4. **MR-072** (docs) — the operator runbook. References #30 (does not re-close).

## Notes / retro

- G1 PASS 2026-06-24 (staff-critic GO-WITH-NITS, 6 nits folded — see
  `reviews/watcher-container-plan-review-2026-06-24.md`). Auth path verified viable
  (`CLAUDE_CODE_OAUTH_TOKEN` + `setup-token` subscription-billed); the one residual unknown
  (in-container headless auth) is isolated to MR-070's gate.
- **Human dependency:** MR-070/MR-071 need a real `setup-token` the operator mints
  (`claude setup-token`); supplied at test time via a gitignored file, never committed or echoed.
- 2026-06-24 — all 4 tickets implemented + G4-validated. **The make-or-break (in-container headless
  subscription auth) PASSES:** MR-070's auth proof (`exit 0/OK`) and MCP round-trip (`exit 0`, agent
  calls `list_reviews`); MR-071's opt-in gate (default `up` = service only) + **end-to-end in ~27s**
  (`--profile watcher up` → in-container agent fixed a typo, resolved the comment, handed back) on a
  throwaway project, live :8139 untouched. Operator supplied a `setup-token` (gitignored, never
  committed). Awaiting G7 (staff-critic re-drive against a fresh build).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-069/070/071/072 done, no carry-overs;
- [x] a **staff-critic sprint-close review** exists at `reviews/sprint-25-close-review-2026-06-24.md`,
      verifying shipped work against each ticket's acceptance criteria — **including `docker build
      -f Dockerfile.watcher`, the opt-in-off-by-default compose assertion, and the in-container auth +
      end-to-end Send→action proofs** (infra epic ⇒ docker build/compose are the gates; no UI ⇒ no
      render-smoke) — with findings resolved or carried;
- [x] retro + carry-overs recorded above, and `close_review:` set in frontmatter.

**Closed 2026-06-24, G7 PASS** (staff-critic, independent — `reviews/sprint-25-close-review-2026-06-24.md`;
rebuilt the watcher image, re-ran both gating proofs + the compose e2e). MR-069/070/071/072 `done`, no
carry-overs. **This closes the `watcher-container` epic.** Closes GH #30 (via MR-071's working profile).

- **Shipped (GH #30):** the watcher is now an OPT-IN docker service — `docker compose --profile watcher
  up` brings up the service + an agent runner authed by the user's Claude **subscription**
  (`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, no API key); plain `docker compose up` starts
  only the service. The make-or-break (headless subscription auth in a no-keychain Linux container) was
  proven in-container before any compose work built on it; the full loop runs end-to-end (~27s).
- **Headline lesson — the human-dependency gate.** MR-070's auth proof needed a real `setup-token` the
  operator alone can mint (interactive OAuth); the cycle correctly isolated that as the gate and paused
  for it rather than building on an unverified assumption. The expired-keychain-token detour (a fast
  `401`, cleanly distinguished from a trust hang) confirmed the proof's failure modes are legible.
- **G7 findings folded:** W1 (unverified Linux creds-mount + wrong `:ro`) softened to verify-on-host +
  writable mount, `setup-token` reaffirmed as proven; N1 (probe is auth-only) clarified; N2 accepted.
- **Carry-overs:** none. (Fast-follow if ever on Linux: positively verify the `~/.claude` bind-mount path.)

**G7 scope note.** This is an `infra` epic: the gates are `docker build -f Dockerfile.watcher`, the
compose opt-in proof (default `up` starts only the service), and the end-to-end Send→action against a
**throwaway** compose project (never the live `mdreview`/`mdreview-data`/:8139/:8137, never plain
`docker compose up` against the live volume). MR-070's in-container auth proof needs a real
`setup-token`; if it can't be supplied, the cycle parks at MR-070 pending the token. All temp under
the gitignored `.scratch/`; no token ever committed or printed.
