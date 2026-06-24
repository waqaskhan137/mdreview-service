---
id: MR-077
title: "Service Dockerfile: COPY src/+web/, ENV MDREVIEW_WEB_DIR/PYTHONPATH, CMD python src/app.py"
status: ready
layer: infra
priority: P1
sprint: sprint-27
epic: oop-refactor-src-layout
depends_on: [MR-076]
branch:
created: 2026-06-25
updated: 2026-06-25
---

## Goal

Make the service container build and serve the relocated monolith from the new layout. The image must
serve a fully rendered viewer/dashboard from `web/` and run the app from `src/`, with the web path
pinned by an explicit env var so prod never depends on path arithmetic.

## Acceptance criteria

- [ ] `Dockerfile`: replace `COPY app.py viewer.html dashboard.html ./` + `COPY static/ ./static/`
      with `COPY src/ ./src/` and `COPY web/ ./web/`; add `ENV MDREVIEW_WEB_DIR=/app/web` and
      `ENV PYTHONPATH=/app/src`; `CMD ["python", "src/app.py"]` (the entrypoint flips to
      `python -m mdreview` only in MR-086). `HEALTHCHECK` unchanged (`127.0.0.1:8080/healthz`).
- [ ] `docker build .` succeeds. Run a **throwaway container on a scratch port** (e.g. `-p
      8155:8080`) with a throwaway `MDREVIEW_DATA` volume — never `docker compose up` (binds :8137),
      never the live `:8139` / `mdreview-data`.
- [ ] **Render-smoke from the rebuilt container** (a 200 is not a render): create a review, then
      `scripts/render-smoke.sh "<url>/review/<id>" '#article' 'h1'` and
      `scripts/render-smoke.sh "<url>/" '#list' '.card'` pass. (render-smoke.sh is still at `scripts/`
      at this point; it relocates to `tests/` in MR-078.)
- [ ] `curl <url>/healthz` → `{"ok": true}`; header dump confirms `text/html; charset=utf-8` for the
      viewer and `text/javascript` for `/static/marked.min.js`.
- [ ] Local validation: `docker build .` (the infra gate) + the render-smoke above.

## Notes / context

- `Dockerfile` current: `WORKDIR /app`, `COPY app.py viewer.html dashboard.html ./`, `COPY static/
  ./static/`, `CMD ["python", "app.py"]`.
- Epic: "Infra (stays at root)" — the service-Dockerfile bullet, and the two-step `CMD` (Phase 0
  `src/app.py`, MR-086 `-m mdreview`).
- `.card` requires at least one review to exist (create the golden review first); `#article`/`h1`
  require the viewer to have rendered the markdown.

## Work log

_Filled in during implementation._

## Validation

_How this was verified._

## Follow-ups

Anything deliberately deferred.
