---
id: MR-095
title: Compiler: hardened Tectonic worker, decorator trigger, latex smoke
status: done
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

- [x] `CompileWorker`: queue.Queue + per-rid coalescing (redo-on-running); compiles never run
      under `store.lock` (enqueue is O(1)).
- [x] Job dir per compile: fresh, empty, OUTSIDE /data (WORKDIR) so the compile uid can use it,
      chowned to the compile uid on the drop path; `paper.tex` from source; assets copied as
      `basename(manifest name)` with `\`/separator/leading-`/`/`..`-segment flattening (write-side
      traversal closed, unit-proven); basename collisions documented as v1 scope.
- [x] Tectonic subprocess: `-X compile --untrusted --keep-logs --outdir .` (NOT --only-cached, owner decision),
      `timeout=60`, `user=/group=` drop to the `tectonic` uid, scrubbed env (PATH + HOME=jobdir +
      TECTONIC_UNTRUSTED_MODE + passed-through TECTONIC_CACHE_DIR only); never the server's env.
      Off the image (not root / uid absent) runs unhardened-as-self with a `latex_compile_unhardened`
      audit line; `tectonic` binary absent -> failed status "not the latex image".
- [x] Success: cross-fs copy of the PDF into `<rid>/latex/paper.pdf.tmp` then rename within /data
      (no half-file to a concurrent reader); skipped if the review dir vanished (delete race).
      Failure/timeout: previous PDF kept, status(failed) + log_tail written.
- [x] Output size cap (50 MB, env-tunable) enforced; `_disk_low()` respected before the self-heal
      enqueue (module) and creates.
- [x] `decorator.py` (`LatexAwareReviews`) wired in the composition root when flag on; enqueues
      iff kind=="latex" after delegating (create + put_source).
- [x] `tests/latex_smoke.py` (stdlib, BASE-url convention): POST .tex -> poll /compile -> GET /pdf
      -> assert 200 + %PDF + application/pdf; cross-review `/data` \input isolation probe and an
      optional `--secret` environ-scrub probe (both hard-fail only under `--require-hardened`, the
      G7 container flag; WARN in unhardened dev). Exit 3 when tectonic is absent.
- [x] Local validation passes: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py`

## Notes / context

Epic plan "compiler.py" + "Security posture". The full hardening (uid drop + 0700 /data blocking
cross-reads + env scrub asserted) is exercised on the MR-096 image at G7 with
`latex_smoke.py --require-hardened --secret <pepper>`; local dev proves the compile + traversal
safety only.

## Work log

- `2026-07-21` — `src/latex_review/compiler.py`: real `_produce_pdf` (hardened Tectonic
  subprocess, uid drop via subprocess `user=`, scrubbed env, timeout + 50 MB cap), `_prepare_job`
  asset copy-in (basename flattening), job dir moved to WORKDIR (outside /data) with cross-fs
  copy+rename into /data, `_compile_identity`/`_chown_tree`/`_audit_unhardened`. `__init__.build`
  + the server seam now pass `AssetService` to the worker. New `tests/latex_smoke.py`.

## Validation

- `2026-07-21` — py_compile green. Flag-off oracle 23/23 (API + markdown viewer byte-identical; dashboard excluded per MR-098). Local
  real compile (tectonic 0.15.0, unhardened-as-self, scratch port 18271, warmed cache via
  TECTONIC_CACHE_DIR): `latex_smoke.py` PASS - baseline paper -> 6331-byte application/pdf; cross-
  review /data probe reported blocked BUT locally that is a FALSE positive: MDREVIEW_DATA was a
  .scratch path, so `\input{/data/<rid>/...}` failed by absence, not by the uid/0700 barrier. The
  isolation (uid drop + 0700 /data + env scrub) is NOT verified here; it only binds on the built
  image via `latex_smoke.py --require-hardened`. env probe skipped (no --secret). Asset copy-in unit test: names
  `../../evil.png`, `/etc/passwd`, `sub/dir/plot.pdf` all flatten to basenames in the job dir,
  nothing escapes. Audit line `latex_compile_unhardened` emitted once per compile as expected off
  the image.

## Amendment (2026-07-21)

- Owner decision: dropped `--only-cached`. Tectonic may fetch missing packages from its bundle CDN
  at compile (its only egress; no document-directed SSRF). Verified a paper with unwarmed packages
  (12pt + geometry + enumitem) compiles to a 200 application/pdf. The uid-drop / scrubbed-env /
  /data-0700 protections are unaffected.

## Follow-ups

- **Security hardening VERIFIED (2026-07-21, MR-096 image built).** `latex_smoke.py
  --require-hardened --secret <pepper>` PASSED against the container; direct proof: 0
  `latex_compile_unhardened` lines and `docker exec -u tectonic cat /data/*/source.md` ->
  Permission denied. The uid drop, 0700 /data barrier, and env scrub all bind. (Supersedes the
  earlier "unverified"/false-positive-probe note above.)

