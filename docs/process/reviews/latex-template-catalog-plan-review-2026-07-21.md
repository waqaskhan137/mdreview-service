---
review_of: docs/process/epics/latex-template-catalog-plan.md
gate: G1
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-07-21
verdict: proceed with named risks accepted (round 2; round 1 was needs-revision)
status: resolved
---

# G1 review: latex-template-catalog epic plan

Authored and critic-gated on hosted mdreview review `a4b479b1ac`
(https://app.mdreview.space/review/a4b479b1ac); this file is the committed gate record. Reviewer was
the `staff-critic` agent, independent of the plan's author; it verified the plan's load-bearing
claims against the as-built `latex_review` module and the process docs (all code citations and the
branch topology confirmed accurate: `build()` `__init__.py:16-21`, `decorator.py:24-28`,
`_prepare_job` `compiler.py:134-152`, `reviews.py:108-109/127-128`, `server.py:65-69`,
`Dockerfile.latex:87`, `client.py:56`).

## Round 1 (verdict: needs revision), 8 findings, all applied in plan revision 6

1. **MUST-FIX. Single-file-only guts the download tier.** Non-CTAN conference styles are largely
   multi-file (the conference `.bst`; CVPR needs `cvpr.sty` + `cvpr_eso.sty`). Fix: a registry entry
   is a pinned FILE-SET; archives banned; MR-104 budgets per-conference file-list verification.
2. **MUST-FIX (IoC). Template validation placed on the wrong side of the seam.** Core cannot produce
   "the available list" without importing the `TemplateService` it must not import. Fix: the decorator
   raises a typed `UnknownTemplate(available=[...])`; core catches and renders the 400.
3. **MUST-FIX (IoC). The create seam could not attach companion files** (assets are per-rid; a
   synchronous download would block the POST handler). Fix: materialize companion files in the
   worker's `_prepare_job`; the decorator only seeds source + records the id; precedence defined.
4. Worth-considering: sha256 verified only on download, not on cache hit → verify on hit + atomic
   write + streamed size cap.
5. Worth-considering: egress/registry-host gap → name the registry hosts; puller fails loudly if
   egress is locked to Tectonic-only.
6. Worth-considering: SSRF guard hostname-only → validate the resolved IP + pin the connection.
7. Worth-considering: `GET /api/latex/templates` `cached` list leaked cross-tenant usage → the cache
   is shared/global, so the list is availability, not tenant data.
8. Owner-decisions note (not a defect): base branch, year-churn, and open questions carried to the
   owner; the manifest-of-pointers-in-source distinction was confirmed NOT a violation of the hard rule.

## Round 2 (verdict: PROCEED WITH NAMED RISKS ACCEPTED)

All 8 round-1 findings verified fixed. Two new worth-considering items, applied in revision 7:
- The download on the single worker thread was not time-bounded (a hung host could wedge the shared
  queue) → bounded connect+read timeout + total fetch budget, fails that compile like `TimeoutExpired`.
- `UnknownTemplate` ownership under-specified → it subclasses a **core-defined** `ReviewCreateRejected`
  base so core catches without importing the module (flag-off oracle safe).

No must-fix remains.

## Owner decisions (2026-07-21, on review a4b479b1ac) — all G1 blocker questions answered

1. Default registry shipped-populated. 2. Merge `feat/latex-review` to `dev` first (done, PR #62),
then cut this epic from `dev`. 3. Bundle the top non-CTAN styles as files (verify redistribution
license per style). 4. Registry origin = each conference's own official source (no mirror v1).

## Resolution log

- [x] Round-1 must-fixes 1-3 (file-set; validation-via-typed-exception; worker-materializes-companions):
      applied in revision 6, verified in round 2.
- [x] Round-1 worth-considering 4-7: applied in revision 6, verified in round 2.
- [x] Round-2 worth-considering (fetch timeout; core-owned base exception): applied in revision 7.
- [x] All four owner open questions answered (2026-07-21).
- [x] G1 closed: independent staff-critic PASS + all blocker questions answered + owner "merge it and go".
