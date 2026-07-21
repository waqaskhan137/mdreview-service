---
id: sprint-30
name: latex-template-catalog
status: active
start: 2026-07-21
end: 2026-07-28
goal: Ship the LaTeX template catalog (bundled famous-few + download-on-miss to /data) following the latex_review IoC pattern.
close_review:
---

## Goal

By sprint end, `create_review(kind="latex", template="<id>")` seeds a review from a bundled starter
and (on miss) downloads a pinned, checksummed non-CTAN style file-set to `/data`, all through an
injected `TemplateService`; the core stays byte-identical flag-off; nothing downloaded is baked into
the image. On branch `feat/latex-templates` (cut from dev after PR #62), single standing PR to `dev`.

## Committed tickets

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-101 | Capture brief + epic plan + G1 record | docs | P1 | done |
| MR-102 | TemplateService + BundledCatalog + DataCache + ReviewCreateRejected + build() injection | svc | P1 | done |
| MR-103 | template create plumbing | svc | P1 | done |
| MR-104 | RegistryPuller + template smoke | svc | P1 | ready |
| MR-105 | GET /api/latex/templates listing | svc | P2 | ready |
| MR-106 | MCP create_review template param | mcp | P2 | ready |
| MR-107 | Docs sweep | docs | P1 | ready |

## Preferred execution order

1. MR-102 (foundation + IoC injection).
2. MR-103 (create plumbing + bundled compile).
3. MR-104 (download-on-miss + smoke).
4. MR-105, MR-106 (independent surfaces).
5. MR-107 (docs sweep; not carry-over eligible).

## Notes / retro

- Epic: latex-template-catalog (G1 passed 2026-07-21, 2 critic rounds on hosted review a4b479b1ac).
- Owner decisions: registry shipped-populated; base merged to dev first (PR #62); bundle top styles;
  conference-source origin. "merge it and go".

## Close gate (G7)

- [ ] every committed ticket done or explicitly carried over (MR-107 is NOT carry-over eligible);
- [ ] independent staff-critic sprint-close review at `docs/process/reviews/sprint-30-close-review-YYYY-MM-DD.md`,
      incl. a container rebuild + `curl /healthz` + `/api/reviews` smoke under `MDREVIEW_ENABLE_LATEX`
      proving resolve/download/persist-to-/data + egress-fail-loud + style-files-not-in-image (no
      product page touched, so no per-page render-evidence);
- [ ] retro + carry-overs recorded above, `close_review:` set.
