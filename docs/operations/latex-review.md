# LaTeX paper review

An opt-in mode for reviewing research papers Overleaf-style: LaTeX source (line-numbered,
highlighted) on the left, a **live server-compiled PDF** on the right, with the same comment system
as markdown reviews (comments anchor to source lines) and a Download-PDF button. There is no turn
baton in this mode — comment freely in the browser, then ask the coding agent in your CLI to collect
feedback.

- **Enable it:** run the separate LaTeX image with the flag set. The default slim image is
  unchanged and never carries the toolchain.
  ```sh
  docker run -d -p 8137:8080 -v mdreview-data:/data \
    ghcr.io/<owner>/mdreview-service-latex:latest      # ENABLE_LATEX + Tectonic baked in
  ```
- **Create one** (agent, over MCP): `create_review(markdown=<raw .tex>, kind="latex")`; push
  revisions with `update_source` (the server recompiles on each push). Or over HTTP:
  `POST /api/reviews {"markdown": "<raw .tex>", "kind": "latex"}`.
- **Start from a template** (agent, over MCP): `create_review(kind="latex", template="<id>")`. The
  template seeds the source (unless you also pass `markdown`) and supplies the document class/style.
  Bundled ids — `ieee`, `acm`, `arxiv`, `lncs`, `elsevier` (CTAN classes, fetched by Tectonic).
  Download-on-miss ids — `acl`, `iclr2026` (and more): the conference's `.sty`/`.bst` are fetched
  once from its own repo (pinned + sha256-checked) and cached under `/data`, **never** added to the
  image/repo. `GET /api/latex/templates` lists the current ids; an unknown id returns 400 with the
  list. Selection is a CLI/agent action — there is no web template picker.
- **What compiles:** a single `.tex` document. Figures attach as assets referenced by **bare
  filename** (`\includegraphics{fig.png}`); subdirectory paths and multi-file `\input` are not
  supported in v1. Bibliographies use bibtex/natbib (biblatex/biber is not supported — Tectonic).
  The engine is XeTeX-based, so it differs from pdflatex in minor ways.
- **Compile failures** show a banner + the TeX log in the PDF pane; the last good PDF stays visible.
- **Networking:** the compile is not `--only-cached`. The image pre-warms a common resource cache
  (fast, offline for typical papers), but a paper using something unwarmed will fetch it from
  Tectonic's bundle CDN at compile time — the compile's only network egress (the document cannot
  redirect it). Lock egress to the Tectonic bundle host at the container/network level if you want
  zero-trust egress.
- **Security:** the compile runs `--untrusted` (no shell-escape) as an unprivileged user with a
  scrubbed environment, and `/data` is `0700` so a malicious `\input` cannot read other reviews'
  sources. Template downloads are contained: only the exact pinned URLs in the shipped
  `registry.json` are fetched (never an agent-supplied URL), HTTPS-only, the resolved IP is
  validated public with the connection pinned to it, each file is sha256-verified on download and on
  every cache hit, with a streamed size cap and a bounded fetch timeout. Full posture:
  `docs/process/epics/latex-paper-review-plan.md` and `docs/process/epics/latex-template-catalog-plan.md`.

### Templates — operator notes

- **Registry:** the download-on-miss catalog lives in `src/latex_review/registry.json` (id →
  pinned file-set of `{url, filename, sha256, bytes}`, pointing at each conference's own repo).
  Add a conference (or bump a year-stamped style, e.g. `iclr2027`) by editing that data file and
  pinning the new sha256 — **no rebuild needed for the manifest** (it ships with the image, but the
  fetched bytes only ever land in `/data`). A moved/renamed upstream file fails **closed** with a
  clear compile error (the sha256 won't match), never a silent wrong file.
- **Air-gapped / zero-download:** set `MDREVIEW_LATEX_TEMPLATE_DOWNLOAD=0`. The service then
  registers no downloader at all — only the bundled CTAN starters and anything already cached under
  `/data` resolve; an id that would need a download 400s.
- **Egress:** download-on-miss needs the image's egress to reach the registry hosts (e.g.
  `raw.githubusercontent.com`) in addition to Tectonic's bundle host. If egress is locked to the
  Tectonic host only, a non-cached template fails **loudly** (a compile-status error), never silently.
- **Custom registry:** point `MDREVIEW_LATEX_TEMPLATE_REGISTRY` at your own `registry.json` path to
  curate the set.
- **Licensing:** bundled *starters* are our own skeletons. Conference style files are **downloaded
  from each conference's own repo**, not re-hosted by us. Bundling a style's bytes into the image is
  intentionally avoided unless it carries a confirmed redistribution-OK license.

> The default `mdreview-service` image and the Python runtime stay stdlib-only (zero pip). The
> opt-in latex image adds one system binary (Tectonic), invoked via `subprocess`; it changes
> nothing about the default image.

### LaTeX image — operator runbook

```sh
# Build (amd64; the warm-up runs Tectonic, so build on amd64, not under arm64 emulation):
docker build -f infra/Dockerfile.latex -t mdreview-service-latex .

# Smoke it on a THROWAWAY container + scratch port + throwaway volume (never :8137/:8139 or the
# live mdreview-data volume):
docker run -d --name mdr-latex-smoke -p 18999:8080 -v mdr-latex-scratch:/data mdreview-service-latex
python3 tests/latex_smoke.py http://localhost:18999 --require-hardened   # binds the uid/0700/env checks
#   add --secret <your MDREVIEW_TOKEN_PEPPER> to also assert env scrubbing
docker rm -f mdr-latex-smoke && docker volume rm mdr-latex-scratch

# Pre-existing /data volume (created before this image): tighten it ONCE so the compile user cannot
# read other reviews' sources (fresh volumes are 0700 by the image already):
docker exec <container> chmod 700 /data
```

- **MCP reconnect:** enabling latex changed the MCP tool schema (`create_review` gained `kind`), so
  `tools_hash` bumped. Any connected stdio MCP client must reconnect to see it (`python3
  src/mcp_server.py --print-version` reports the current hash).
- **Egress:** if the deployment must not reach the internet, either accept that unwarmed papers
  fail (broaden the warm-up preamble in `infra/Dockerfile.latex`) or allowlist only the Tectonic
  bundle host at the network layer.

---

Moved out of `README.md` by #257. Commands, ports, paths and env vars are
byte-identical to what shipped there; nothing was corrected in the move.
