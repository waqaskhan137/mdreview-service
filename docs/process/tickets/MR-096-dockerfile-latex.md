---
id: MR-096
title: Dockerfile.latex: pinned Tectonic, warmed cache, compile user, release step
status: review
layer: infra
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-095]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

A separate latex-enabled image so flag-off deployments keep today's slim image byte-identical,
following the Dockerfile.watcher second-Dockerfile precedent.

## Acceptance criteria

- [x] `infra/Dockerfile.latex`: FROM python:3.12-slim, same COPYs as infra/Dockerfile, pinned
      Tectonic musl tarball (0.16.9, sha256 60b13a08...verified), pre-warmed world-readable bundle
      cache (representative preamble: amsmath, amssymb, natbib, graphicx, hyperref, booktabs,
      xcolor), `ENV TECTONIC_UNTRUSTED_MODE=1 MDREVIEW_ENABLE_LATEX=1
      TECTONIC_CACHE_DIR=/opt/tectonic-cache MDREVIEW_LATEX_USER/WORKDIR`, `useradd tectonic`
      (server stays root), `chmod 700 /data`, `/opt/latex-jobs` owned by tectonic.
- [x] Build is amd64-only (watcher precedent); no QEMU-emulated warm-up.
- [x] `release.yml`: mirrored build-push step publishing
      `ghcr.io/<owner>/mdreview-service-latex:{VERSION,latest}`; slim + watcher steps untouched.
- [ ] **OWED (Docker daemon down locally):** `docker build -f infra/Dockerfile.latex .` succeeds
      and a container compiles the sample paper offline. Runs at G7 (container rebuild) with
      `latex_smoke.py --require-hardened --secret <pepper>`.
- [x] Slim path untouched: infra/Dockerfile, compose, Makefile unchanged (git-verified).
- [x] Local validation passes: `python3 -m py_compile ...` (green); `docker build` OWED (daemon
      down; see above).

## Notes / context

Epic plan "Infra". Runbook item (MR-100): one-time `chmod 700 /data` on pre-existing volumes.
Validate against throwaway containers on scratch ports only; never :8139/:8137 or the
`mdreview-data` volume. The Tectonic sha256 was verified by downloading the 0.16.9 x86_64 musl
tarball and hashing it (60b13a0826ae7ad9ce34b4a2df06bff2cfcfa6dda8a915477c0cbb84e1a4a902).

## Work log

- `2026-07-21` — `infra/Dockerfile.latex` (pinned+checksummed Tectonic, unprivileged `tectonic`
  user, warmed world-readable cache, 0700 /data, /opt/latex-jobs). `.github/workflows/release.yml`
  third build-push step for `mdreview-service-latex` (amd64). Slim/watcher steps unchanged.

## Validation

- `2026-07-21` — py_compile green. Slim `infra/Dockerfile`, compose, and Makefile git-verified
  UNCHANGED. `release.yml` parses as valid YAML (pyyaml) with exactly 3 build-push steps and the
  latex tag present. Tectonic tarball sha256 verified by download+hash. **Not yet built:** the
  Docker daemon is down in this environment, so the image build + offline compile + hardened smoke
  are owed at G7.

## Follow-ups

- G7 / owner local test: `docker build -f infra/Dockerfile.latex -t mdreview-service-latex .`,
  run a throwaway container on a scratch port with throwaway MDREVIEW_DATA, then
  `python3 tests/latex_smoke.py http://localhost:<scratch> --require-hardened --secret <pepper>`
  to bind the uid-drop + 0700 + env-scrub assertions.

## Follow-ups

