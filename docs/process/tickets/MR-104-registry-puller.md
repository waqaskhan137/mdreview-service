---
id: MR-104
title: RegistryPuller (pinned file-set, sha256, timeout, size cap, SSRF guard, /data cache) + smoke
status: ready
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

- [ ] `RegistryPuller` reads a pinned `registry.json` (`{id:{starter, files:[{url,filename,sha256,bytes}]}}`)
      shipped pre-populated (owner decision 1) with the known non-CTAN conference file-sets pointing
      at each conference's own source (owner decision 4).
- [ ] Per-file: HTTPS-only; sha256 verified on download AND on every cache hit; atomic write
      (temp + os.replace); streamed size cap (abort mid-download); bounded connect+read timeout +
      total fetch budget (a hung host fails the compile, not the queue); archives/zips rejected.
- [ ] SSRF guard: host allowlist + resolved-IP validation (reject private/link-local/loopback) +
      connection pinned to that IP; no off-allowlist redirects.
- [ ] Cache under `<data>/.templates/<id>/` (shared/global, root-only); files copied into the job dir
      (never referenced in place); 0700 /data barrier preserved.
- [ ] Puller injected in `build()` only when `LATEX_TEMPLATE_REGISTRY_ENABLED`; config envs added.
- [ ] Per-conference file-list verification: compile each named target (NeurIPS/ICLR/ACL/CVPR) to
      confirm the listed files + CTAN deps are sufficient.
- [ ] `tests/template_smoke.py`: bundled resolve; download-on-miss file-set (assert sha256 + persisted
      under /data + NOT in image/repo); cache-hit re-verify (corrupt -> re-fetch); tamper/SSRF refusal;
      unknown id -> 400; egress-locked -> fail loud; fetch-timeout -> compile fails within budget.
- [ ] Local validation passes: `python3 -m py_compile ...`

## Notes / context

Epic plan "Security posture" + Risks. Year-churn is accepted (fails closed). Verify redistribution
license for any style whose bytes we cache/serve.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups
