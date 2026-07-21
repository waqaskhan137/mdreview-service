---
review_of: docs/process/sprints/sprint-30.md
gate: G7
reviewer: staff-critic (agent)
independent: true
timestamp: 2026-07-22
verdict: CLOSE-WITH-NOTES
status: resolved
---

# G7 sprint-close review: sprint-30 (latex-template-catalog)

Independent reviewer (did not implement the sprint), verifying shipped work against each committed
ticket's acceptance criteria on `feat/latex-templates @ 4a592c3`.

## Verdict: CLOSE-WITH-NOTES

All 7 tickets (MR-101..MR-107) are `done`; every AC is met; the G7 container smoke is satisfied. No
blockers. Two non-blocking notes carried to the owner (below).

## Independently reproduced (not just read)

- `python3 -m py_compile` over the full glob: PASS.
- `tests/template_smoke.py` (hermetic puller): re-ran, 9/9 PASS (download, atomic cache, cache-hit
  re-verify with corrupt→refetch, non-HTTPS refused, private-IP refused, wrong-sha256 rejected,
  oversize aborted, archive rejected).
- `tests/golden_transcript.sh` flag-off vs flag-on markdown sequence: "transcripts identical (23
  steps)", exit 0 — the additive `template` plumbing is inert for markdown flows.
- Live local endpoints (flag-on stdlib boot): `/healthz` 200, `/api/reviews` 200,
  `/api/latex/templates` → `{bundled:[acl,acm,arxiv,elsevier,iclr2026,ieee,lncs], registry:[acl,
  iclr2026], cached:[]}`; unknown-template create → 400 with the available list, no review created.
- Core-isolation grep: core imports `latex_review` only inside the `ENABLE_LATEX` branch
  (`server.py:67`); `errors.py` is core-owned.
- `src/latex_review/puller.py` line-by-line: every named MR-104 security control present — HTTPS-only,
  resolved-IP validation (private/loopback/link-local/reserved/multicast/unspecified rejected),
  connection pinned to the validated IP (SNI+cert vs hostname, DNS-rebind/TOCTOU), per-file sha256 on
  download and on every cache hit, atomic temp+rename write, streamed size cap, per-IO timeout + total
  budget, redirects rejected, archives rejected. The manifest is the allowlist.
- `--print-version` tools_hash = 7c3de6863ce4 (matches MR-106).
- sprint-30 diff touches no `web/**` or `static/**` — the "no product page" claim holds, so no
  per-page render-evidence is owed.

## Container smoke (evidence)

`docs/process/reviews/sprint-30-close-evidence-2026-07-21/container-smoke.txt`: fresh throwaway
container, `/healthz` 200, `/api/reviews` 200, hermetic puller PASS, hardened latex smoke
(`--require-hardened --secret`) PASS (compile → application/pdf; cross-review `/data` `\input`
blocked; env scrubbed), download-on-miss `acl` fetched + cached at `/data/.templates/acl/` and
**not** present in `/app` (image source), unknown id → 400. The reviewer did not rebuild the
multi-GB Tectonic image; the container lines rest on this evidence corroborated by the hermetic
smoke + code read + local boot.

## Per-ticket AC

MR-101 docs · MR-102 svc · MR-103 svc · MR-104 svc · MR-105 svc · MR-106 mcp · MR-107 docs — **all
AC met.**

## Notes (non-blocking, owner)

1. **MR-104 deferred AC (owner decision).** "Bundle the top non-CTAN style as a file" is recorded
   `DEFERRED`: neither the ACL nor ICLR upstream repo carries a detected redistribution license, so
   bundling their bytes is not license-safe. Honestly recorded; the download-on-miss path covers the
   need. Owner to either accept download-only permanently or track re-bundling once a
   permissively-licensed style exists.
2. **Registry pinned mutable `master` refs** (raised here). **RESOLVED after the review:** the
   registry URLs were re-pinned to immutable commit SHAs (content-verified identical to the recorded
   sha256), so downloads are reproducible and won't break on unrelated upstream pushes.

## Resolution log

- [x] All 7 tickets verified `done` with AC met.
- [x] G7 container smoke satisfied (health + api + hardened + download-to-/data + not-in-image).
- [x] Note 2 (mutable refs) resolved: commit-SHA pins applied post-review.
- [~] Note 1 (bundle-a-style) carried to the owner as a standing decision; not a close blocker.
