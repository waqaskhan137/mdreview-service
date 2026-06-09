---
id: sprint-05
name: landing-page
status: closed
start: 2026-06-09
end: 2026-06-09
goal: Ship the buildless landing page live at https://mdreview.waqasrana.space via GitHub Pages.
close_review: reviews/sprint-05-close-review-2026-06-09.md   # G7 staff-critic PASS, resolved
---

## Goal

By the end of the sprint a person can open `https://mdreview.waqasrana.space` and see the branded
landing page: tagline, a real screenshot of the review loop mid-annotation, the curl flow, how to
run it, the MCP mention, and the repo link — with the canonical URL recorded in the README. The
service, its API, and the MCP wrapper are byte-for-byte unchanged. Any unavoidably-human publish
steps (DNS/Pages settings) are either done or precisely documented as pending with their re-run
commands.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-019 | Author buildless landing page (site/index.html) with dashboard tokens, static demo screenshot, and CNAME | ui | P1 | done |
| MR-020 | Publish to GitHub Pages — gh-pages pipeline, one-time runbook, record canonical URL in README | infra | P1 | blocked |

MR-021 (animated GIF demo) is deliberately **not** committed — `backlog`, next cycle (epic plan,
Phase 2: asset doesn't exist, GIF-vs-video open; committing it would fail G6).

## Preferred execution order

1. MR-019 — the shippable artifact: page + demo screenshot + CNAME, local render-smoke gate.
2. MR-020 — publish pipeline + one-time human steps + README URL (gated on live verification).

## Notes / retro

_Filled in as the sprint runs and at close._

- `2026-06-09` — MR-019 done: page authored, demo captured (procedure b), render-smoke 7/7,
  light+dark evidence committed.
- `2026-06-09` — MR-020 blocked at its one genuinely-human step: the DNS `CNAME mdreview ->
  waqaskhan137.github.io` record (product owner asked, "can't right now"; wildcard currently
  points the host at a non-GitHub IP). Everything automatable shipped: `gh-pages` branch
  published (`a528282`), Pages enabled + custom domain registered (API-confirmed `built`),
  deployment verified at GitHub's edge via `--resolve`. Resume sequence recorded in the ticket;
  README URL deliberately withheld until the live URL verifies (per AC).
- `2026-06-09` — Pre-G7 unconditional smoke (recorded per the brief's carry-over note): rebuilt
  the image from the tree (`docker build -t mdreview-service:smoke-sprint05 .` OK) and smoked a
  **throwaway** container on the free port 8137 — `/healthz` -> `{"ok": true}`, `/api/reviews` ->
  sane JSON. Deliberately did NOT `docker compose up -d --build`: the user's live `mdreview`
  container serves port 8139 (compose file says 8137) and recreating it would have moved/broken
  the live instance the MCP server points at; the throwaway preserves the rebuild+smoke intent
  without touching it. Sprint touched no container-served file (`site/` is outside the image).
- `2026-06-09` — **Closed at G7: staff-critic PASS** (`reviews/sprint-05-close-review-2026-06-09.md`,
  resolved). F1-F6 verified green by reproduction; F7 (MINOR: demo captured on the live 8139
  instance instead of a throwaway — procedure, not artifact) carried into MR-021's notes; F8
  informational (README-URL withholding is correct, not a DoD miss).
- **Carry-overs:** MR-020's remainder (status `blocked`) carries to the next cycle — the DNS
  `CNAME mdreview -> waqaskhan137.github.io` record is the user's to add; then HTTPS enforce +
  live verification + README canonical URL, per the resume sequence in the ticket's Work log.
  MR-021 (animated GIF demo) remains backlog for the same future cycle.
- **Retro:** the plan's pre-resolved decisions (worktree publish sequence, http.server G4 target,
  screenshot-first demo) all executed without surprises; the one mid-sprint discovery was that
  GitHub Pages consumes (does not serve) the CNAME file, so that verification step became an API
  check. Asking the user for the DNS record mid-sprint (they deferred) confirmed the plan's
  call to treat DNS as a G8-like human step rather than a sprint dependency.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where);
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-05-close-review-2026-06-09.md`, verifying shipped work against each
      ticket's acceptance criteria, **including a render smoke** of any page touched, and its
      findings are resolved or carried;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
