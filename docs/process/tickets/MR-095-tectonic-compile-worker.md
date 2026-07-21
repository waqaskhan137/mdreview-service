---
id: MR-095
title: Compiler: hardened Tectonic worker, decorator trigger, latex smoke
status: ready
layer: svc
priority: P1
sprint: sprint-29
epic: latex-paper-review
depends_on: [MR-094]
branch: feat/latex-review
created: 2026-07-21
updated: 2026-07-21
---

## Goal

The compile pipeline: a single worker thread that turns the current `.tex` source (plus attached
figure assets) into `<data>/<rid>/latex/{paper.pdf, compile.log, status.json}`, triggered by
create/put_source via a ReviewService decorator, hardened per the owner-accepted security posture.

## Acceptance criteria

- [ ] `CompileWorker`: queue.Queue + per-rid coalescing; compiles never run under `store.lock`.
- [ ] Job dir per compile: fresh, empty, chowned to the dedicated compile uid; `paper.tex` from
      source; assets copied as `basename(manifest name)` with separator/`..`/leading-`/`
      flattening (write-side traversal closed); basename collisions documented.
- [ ] Tectonic subprocess: `-X compile --untrusted --only-cached --keep-logs`, `timeout=60`,
      `user="tectonic"` (unprivileged), scrubbed env (TECTONIC_* + PATH + HOME=jobdir only);
      never root, never the server's environment. Skips user-drop gracefully outside the latex
      image (local dev without the uid runs unhardened with a loud log line).
- [ ] Success: atomic move of pdf+log+status into `<rid>/latex/`, skipped if the review dir
      vanished (delete race). Failure/timeout: previous PDF kept, status(failed) + log written.
- [ ] Output size cap (~50 MB) enforced; `_disk_low()` respected at enqueue.
- [ ] `decorator.py` (`LatexAwareReviews`) wired in the composition root when flag on; enqueues
      iff kind=="latex" after delegating.
- [ ] `tests/latex_smoke.py` (stdlib, MDREVIEW_BASE convention): POST .tex -> poll /compile ->
      GET /pdf -> assert 200 + body startswith %PDF + application/pdf; plus the hardening probe
      (\input{/proc/self/environ} -> no MDREVIEW_* in PDF; \input{/data/...} -> permission denied
      in log) and the traversal probe (asset named "../evil.png" writes nothing outside job dir).
- [ ] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "compiler.py" + "Security posture". Tectonic 0.16.9 facts in the epic. Full end-to-end
smoke needs the MR-096 image; the smoke must fail loud (render-smoke exit-3 style) when tectonic
is absent.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

