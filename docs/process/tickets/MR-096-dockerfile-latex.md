---
id: MR-096
title: Dockerfile.latex: pinned Tectonic, warmed cache, compile user, release step
status: ready
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

- [ ] `infra/Dockerfile.latex`: FROM python:3.12-slim, same COPYs as infra/Dockerfile, pinned
      Tectonic musl tarball (version + sha256), pre-warmed world-readable bundle cache
      (representative preamble: amsmath, amssymb, natbib, graphicx, hyperref, booktabs, xcolor),
      `ENV TECTONIC_UNTRUSTED_MODE=1 MDREVIEW_ENABLE_LATEX=1 TECTONIC_CACHE_DIR=/opt/tectonic-cache`,
      `useradd tectonic` (server stays root), `chmod 700 /data`.
- [ ] Build is amd64-only (watcher precedent, release.yml:59); no QEMU-emulated warm-up.
- [ ] `release.yml`: mirrored build-push step publishing
      `ghcr.io/<owner>/mdreview-service-latex:{VERSION,latest}`; slim service step untouched.
- [ ] `docker build -f infra/Dockerfile.latex .` succeeds; a container from it compiles the
      sample paper offline (`--only-cached` proven: no network at compile time).
- [ ] Slim path untouched: infra/Dockerfile, compose, Makefile, README build commands unchanged.
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py` and `docker build -f infra/Dockerfile .` (infra layer gate).

## Notes / context

Epic plan "Infra". Runbook item (MR-100): one-time `chmod 700 /data` on pre-existing volumes.
Validate against throwaway containers on scratch ports only; never :8139/:8137 or the
`mdreview-data` volume.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

