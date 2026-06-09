---
id: MR-020
title: Publish to GitHub Pages — gh-pages pipeline, one-time Pages/DNS/HTTPS runbook, record canonical URL in README
status: blocked
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

- [x] `gh-pages` orphan branch exists with the **contents of `site/`** at its root (including
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
- [x] **One-time setup runbook** recorded in this ticket (Work log) with each step marked
      done/automated/human-pending: (1) enable Pages, source `gh-pages` branch root; (2) custom
      domain set to `mdreview.waqasrana.space` (Pages reads `CNAME`); (3) DNS `CNAME` record
      `mdreview` -> `waqaskhan137.github.io` exists and is verified with
      `dig +short CNAME mdreview.waqasrana.space` — **wildcard coverage is not sufficient**; the
      record must point at GitHub Pages; (4) HTTPS enforced once the cert issues.
- [x] **Publish verification block green** (or each blocked item explicitly recorded as
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
- [x] Local validation passes: `python3 -m py_compile app.py` (untouched).

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

- `2026-06-09` — Published: created the orphan `gh-pages` branch via the pinned worktree sequence
  (`git worktree add --orphan -b gh-pages ../mdreview-gh-pages`, git 2.50.1), rsynced `site/`
  contents to its root (`CNAME`, `demo.png`, `index.html`), committed (`a528282`) and pushed.
  The worktree at `../mdreview-gh-pages` is kept for future re-publishes.
- `2026-06-09` — GitHub **auto-enabled Pages on the branch push** (the explicit
  `gh api -X POST .../pages` returned 409 "already enabled"): source `gh-pages` root, custom
  domain `mdreview.waqasrana.space` picked up from the CNAME file, build went `building` ->
  `built`.
- `2026-06-09` — **Runbook correction:** GitHub Pages *consumes* the `CNAME` file; it does not
  serve it. The planned `curl .../CNAME` verification 404s by design and is replaced by
  `gh api repos/waqaskhan137/mdreview-service/pages --jq .cname`.
- `2026-06-09` — **One-time setup runbook status:**
  1. Enable Pages, source `gh-pages` root — **done** (auto, confirmed via API).
  2. Custom domain `mdreview.waqasrana.space` — **done** (API reports `cname` set;
     `waqaskhan137.github.io/mdreview-service` 301s to it).
  3. DNS `CNAME mdreview -> waqaskhan137.github.io` — **HUMAN-PENDING.** Asked the product owner
     2026-06-09; answer: "can't right now." Current state: no CNAME record; the wildcard
     `*.waqasrana.space` A-records the host to `72.62.4.70` (not GitHub Pages). A specific CNAME
     record overrides the wildcard once added.
  4. HTTPS enforce — **pending on (3)** (cert can only issue once DNS points at GitHub):
     `gh api -X PUT repos/waqaskhan137/mdreview-service/pages -F https_enforced=true`.
- `2026-06-09` — **BLOCKER (status: blocked):** the unmet prerequisite is step (3), a record only
  the domain owner can add. **Resume sequence once DNS is added:**
  ```bash
  dig +short CNAME mdreview.waqasrana.space        # expect: waqaskhan137.github.io.
  curl -sI https://mdreview.waqasrana.space/ | head -1   # expect 200 (cert may take a while)
  scripts/render-smoke.sh https://mdreview.waqasrana.space/ \
    .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link
  gh api repos/waqaskhan137/mdreview-service/pages --jq .cname   # mdreview.waqasrana.space
  gh api -X PUT repos/waqaskhan137/mdreview-service/pages -F https_enforced=true
  # only after ALL green: record https://mdreview.waqasrana.space/ in README (hero/Run section)
  ```
  Per-publish update sequence (unchanged): edit `site/` on `dev`, then
  `rsync -a --delete --exclude '.git' site/ ../mdreview-gh-pages/ && git -C ../mdreview-gh-pages add -A && git -C ../mdreview-gh-pages commit && git -C ../mdreview-gh-pages push origin gh-pages`.

## Validation

- `2026-06-09` — **Deployment verified at GitHub's edge, bypassing DNS:**
  `curl http://mdreview.waqasrana.space/ --resolve mdreview.waqasrana.space:80:185.199.108.153`
  -> `200` and the served `<title>` is the landing page's
  ("mdreview — human-in-the-loop markdown review for AI agents"). Pages API reports
  `status: built`, `cname: mdreview.waqasrana.space`, source `gh-pages` `/`.
- `2026-06-09` — `waqaskhan137.github.io/mdreview-service/` -> `301 location:
  http://mdreview.waqasrana.space/` (custom domain registered with GitHub).
- `2026-06-09` — `python3 -m py_compile app.py` OK (untouched).
- `2026-06-09` — README canonical-URL edit **deliberately NOT made** (AC gates it on the live
  verification passing; the URL would 404 today). It is part of the resume sequence above.

## Follow-ups

- Optional later: automate `site/` -> `gh-pages` on push (GitHub Action) — rejected for this epic
  as a hidden build step; revisit only if manual publishes become a burden.
