---
id: MR-020
title: Publish to GitHub Pages — gh-pages pipeline, one-time Pages/DNS/HTTPS runbook, record canonical URL in README
status: ready
layer: infra
priority: P1
sprint: sprint-05
epic: landing-page
depends_on: [MR-019]
branch:
created: 2026-06-09
updated: 2026-06-09
---

## Goal

Put MR-019's page live at `https://mdreview.waqasrana.space` via GitHub Pages, with a repeatable
documented publish pipeline (decoupled from the dev->main G8 flow) and an auditable runbook for the
one-time human steps. Record the canonical URL in the README only once the live page verifies.

## Acceptance criteria

- [ ] `gh-pages` orphan branch exists with the **contents of `site/`** at its root (including
      `CNAME`), created and published via the pinned worktree sequence (epic plan, Decision 3):
      ```bash
      git worktree add --orphan -b gh-pages ../mdreview-gh-pages   # needs git >= 2.42
      # (if gh-pages already exists remotely: git worktree add ../mdreview-gh-pages gh-pages)
      rsync -a --delete --exclude '.git' site/ ../mdreview-gh-pages/
      git -C ../mdreview-gh-pages add -A
      git -C ../mdreview-gh-pages commit -m "publish: site -> gh-pages (MR-020)"
      git -C ../mdreview-gh-pages push origin gh-pages
      ```
      Re-publishes are idempotent (`rsync --delete`).
- [ ] **One-time setup runbook** recorded in this ticket (Work log) with each step marked
      done/automated/human-pending: (1) enable Pages, source `gh-pages` branch root; (2) custom
      domain set to `mdreview.waqasrana.space` (Pages reads `CNAME`); (3) DNS `CNAME` record
      `mdreview` -> `waqaskhan137.github.io` exists and is verified with
      `dig +short CNAME mdreview.waqasrana.space` — **wildcard coverage is not sufficient**; the
      record must point at GitHub Pages; (4) HTTPS enforced once the cert issues.
- [ ] **Publish verification block green** (or each blocked item explicitly recorded as
      human-pending with the exact command to re-run):
      ```bash
      dig +short CNAME mdreview.waqasrana.space          # waqaskhan137.github.io.
      curl -sI https://mdreview.waqasrana.space/ | head -1   # HTTP/2 200
      scripts/render-smoke.sh https://mdreview.waqasrana.space/ \
        .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link
      curl -s https://mdreview.waqasrana.space/CNAME     # mdreview.waqasrana.space
      ```
- [ ] README records the canonical URL — **only after** the verification block passes (the README
      must never assert a URL that 404s). This is the folded DoD docs change, not deferred.
- [ ] Local validation passes: `python3 -m py_compile app.py` (untouched).

## Notes / context

- Epic: `docs/process/epics/landing-page-plan.md` (Decisions 1, 3, 4; Rollout phases -> Phase 1;
  Verification -> Publish verification). Brief Amendments fix the domain.
- Branching rule honored: publishing rides the dedicated `gh-pages` branch; `dev`/`main` and the
  G8 promotion are untouched. `docs/process/` is not disturbed.
- Repo owner `waqaskhan137`; domain `waqasrana.space` offered by the product owner in brief review
  (treated as same-owner-confirmed; the dig verify step covers the residual risk).
- `git worktree add --orphan` needs git >= 2.42 (2023); the existing-remote-branch fallback is in
  the AC block.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

- Optional later: automate `site/` -> `gh-pages` on push (GitHub Action) — rejected for this epic
  as a hidden build step; revisit only if manual publishes become a burden.
