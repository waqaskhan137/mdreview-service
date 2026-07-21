---
id: sprint-29
name: latex-paper-review
status: active
start: 2026-07-21
end: 2026-07-28
goal: Ship the opt-in LaTeX paper review mode (Overleaf-style split viewer, live Tectonic compile) with the core byte-identical flag-off.
close_review:
---

## Goal

By sprint end, a `kind=latex` review created over MCP compiles to a live PDF served beside its
line-numbered source in the new split viewer, comments anchor to source lines through the
unchanged comment system, the PDF downloads, and the slim image plus every markdown flow is
provably untouched (golden-transcript diff empty). The feature lives on `feat/latex-review` and
merges to `dev` only on the owner's explicit approval.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-091 | Capture brief + epic plan + G1 record | docs | P1 | done |
| MR-092 | Core IoC seam + golden-transcript oracle | svc | P1 | done |
| MR-093 | kind plumbing (persisted only when latex) | svc | P1 | done |
| MR-094 | latex_review package: routes, auth, self-heal | svc | P1 | done |
| MR-095 | Hardened Tectonic compile worker + latex smoke | svc | P1 | done |
| MR-096 | Dockerfile.latex + release step (amd64-only) | infra | P1 | review |
| MR-097 | latex-viewer.html per approved mockup | ui | P1 | done |
| MR-098 | Dashboard LATEX chip + kind-aware statusOf | ui | P2 | done |
| MR-099 | MCP create_review kind + latex-aware wording | svc | P2 | done |
| MR-100 | Docs sweep: README, gate refs, runbook | docs | P1 | ready |

## Preferred execution order

1. MR-092 then MR-093 (core seam + kind; oracle green before anything else lands).
2. MR-094 then MR-095 (module, then compiler).
3. MR-096 (image; unlocks end-to-end compile + render smokes).
4. MR-097, MR-098, MR-099 (independent surfaces, any order).
5. MR-100 last (sweep; not carry-over eligible).

## Notes / retro

- Epic: latex-paper-review (G1 passed 2026-07-21, 2 critic rounds on hosted review 9215476104).
- Owner decisions baked in: dev consolidated first (ff to 94671c1) and branch cut from dev;
  bare-filename figures; hosted rollout only after local owner testing; compile security accepted
  in hardened form (scrubbed env + unprivileged uid).

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where); MR-100 is NOT
      carry-over eligible;
- [ ] a **staff-critic sprint-close review** exists at
      `docs/process/reviews/sprint-29-close-review-YYYY-MM-DD.md`, verifying shipped work against
      each ticket's acceptance criteria, including the rebuilt-container smoke (`/healthz` +
      `/api/reviews`), per-page DOM assertions + screenshots for `latex-viewer.html` and
      `dashboard.html` under `docs/process/reviews/sprint-29-render-evidence-*`, and the
      golden-transcript flag-off proof;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
