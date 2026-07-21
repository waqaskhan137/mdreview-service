---
id: MR-104
title: RegistryPuller (pinned file-set, sha256, timeout, size cap, SSRF guard, /data cache) + smoke
status: done
layer: svc
priority: P1
sprint: sprint-30
epic: latex-template-catalog
depends_on: [MR-102, MR-103]
branch: feat/latex-templates
created: 2026-07-21
updated: 2026-07-21
---

## Goal

Download-on-miss: fetch a non-CTAN style's pinned file-set from its conference source, verify, and
cache under /data, contained per the security posture.

## Acceptance criteria

- [x] `RegistryPuller` reads a pinned `registry.json` shipped pre-populated (owner decision 1) with
      real, verified non-CTAN file-sets pointing at each conference's OWN source (owner decision 4):
      `acl` (acl.sty + acl_natbib.bst @ acl-org/acl-style-files), `iclr2026`
      (iclr2026_conference.sty + .bst @ ICLR/Master-Template). The manifest IS the allowlist (only
      the exact pinned URLs are ever fetched).
- [x] Per-file: HTTPS-only (test may relax); sha256 verified on download AND on every cache hit;
      atomic write (temp + os.replace); streamed size cap (aborts mid-download); per-IO timeout +
      total wall-clock fetch budget (a hung host fails the compile, not the queue); archives rejected.
- [x] SSRF guard: only manifest URLs fetched; resolved-IP validated public (private/loopback/
      link-local/reserved/multicast rejected); connection pinned to the validated IP (SNI+cert vs the
      hostname, closes DNS-rebind/TOCTOU); redirects rejected (manifest gives final URLs).
- [x] Cache under `<data>/.templates/<id>/` (shared/global, root-only); files copied into the job dir
      by basename (MR-103's `_prepare_job`); 0700 /data barrier preserved.
- [x] Puller injected in `build()` only when `MDREVIEW_LATEX_TEMPLATE_DOWNLOAD` (default on; =0 for
      air-gapped -> no puller). `MDREVIEW_LATEX_TEMPLATE_REGISTRY` overrides the manifest path.
- [x] Per-conference file-list verified: ACL and ICLR-2026 each compile with their listed files +
      CTAN-resident natbib/fancyhdr (compiled both).
- [x] `tests/template_smoke.py` (hermetic, local HTTP server): download -> sha256 -> atomic cache ->
      cache-hit re-verify (corrupt -> re-fetch); guards: non-HTTPS refused, private-IP refused, wrong
      sha256 rejected, oversize aborted, archive rejected. Live end-to-end (real ACL fetch -> compile
      -> cached under /data, NOT in repo) proven manually.
- [x] Local validation passes: `python3 -m py_compile ...`
- [~] **Bundle the top non-CTAN style as a file (owner decision 3): DEFERRED.** Neither ACL nor
      ICLR repo carries a detected redistribution license (GitHub spdx = None), so bundling their
      bytes into the image is not license-safe. The download path (decision 4) already makes them
      work; bundling stays a follow-up pending a style with a confirmed permissive license. Flagged
      to the owner.

## Notes / context

Epic plan "Security posture" + Risks. Year-churn is accepted (fails closed). Verify redistribution
license for any style whose bytes we cache/serve.

## Work log

- `2026-07-21` — `src/latex_review/puller.py` (RegistryPuller: HTTPS + IP-validate + pin + sha256 +
  streamed size cap + timeout/budget + no-redirect + no-archive + atomic /data cache). `templates.py`
  companion_files delegates registry ids to `puller.materialize`. `config.py`
  LATEX_TEMPLATE_DOWNLOAD + LATEX_TEMPLATE_REGISTRY. `build()` injects the puller when enabled.
  `registry.json` (acl, iclr2026, real pinned+verified). Starter dirs templates/acl + templates/iclr2026.
  `tests/template_smoke.py` (hermetic).

## Validation

- `2026-07-21` — py_compile green; flag-off oracle 23/23. Hermetic smoke: 9/9 (download+sha256+cache+
  re-verify + all 5 guards). Live: `template=acl` -> downloaded acl.sty+acl_natbib.bst from acl-org
  repo, sha256-verified, cached under <data>/.templates/acl/ (NOT in repo), compiled to a 9KB ACL PDF;
  2nd create served from cache. IoC: DOWNLOAD=0 -> no puller; default -> puller with registry ids
  [acl, iclr2026]. Per-conference compile check: ACL + ICLR-2026 both compile with their file-sets.

## Follow-ups

- Bundle-the-top-style (decision 3) pending a permissive-license style; the download path covers the
  need meanwhile. Year-stamped churn: registry.json is data (add iclr2027 etc. without a rebuild).

## Follow-ups
