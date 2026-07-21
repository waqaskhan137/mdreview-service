---
epic: latex-template-catalog
status: active
created: 2026-07-21
source: requirements/latex-template-catalog.md
gate: G1 passed 2026-07-21
review: docs/process/reviews/latex-template-catalog-plan-review-2026-07-21.md
related_sprints: [sprint-30]
related_tickets: [MR-101, MR-102, MR-103, MR-104, MR-105, MR-106, MR-107]
---

# LaTeX Template Catalog Plan

Let an author start a `kind=latex` review from a named template instead of a blank `.tex`. We ship
a small bundled set of the famous templates; if the human wants one we do not ship, we download it
once and keep it in the runtime `/data` volume (never in the repo/image/build). Selection is a
CLI/agent action (`create_review(kind="latex", template="<id>")`), not a web UI. Planned and
critic-gated on hosted mdreview review `a4b479b1ac` (2 rounds, "proceed with named risks accepted");
this file is the committed record (review revision 7). Extends the `latex_review` module and follows
its IoC pattern.

**Source requirement:** [`requirements/latex-template-catalog.md`](../requirements/latex-template-catalog.md), verbatim.

## Product goal

An agent creates a paper from a template the human names ("make a NeurIPS paper"); the service seeds
the right skeleton, supplies the document class/style, compiles, and the human reviews the PDF. The
famous classes work offline; an uncommon conference style is fetched on first use and cached.

## Core design principle

**Two storage tiers, one hard rule.** Our starter `.tex` skeletons + the registry manifest of
pointers are source-controlled config (they ship). A *downloaded* conference style file
(`.sty`/`.bst`/`.cls`) lives only in the `/data` volume, **never** in the repo/image/build. (Owner
exception, decision 3: the one or two most-popular non-CTAN styles are bundled as files for offline
use.) Adding or fetching a template never needs a rebuild.

## Recommended approach

### The sharpening insight (recon)

The compile is not `--only-cached`, so Tectonic already fetches CTAN document classes at compile
time. `IEEEtran`, `acmart`, `elsarticle`, `revtex4`, `llncs`, `amsart` are all on CTAN, so for those
a "template" is only our starter `.tex`. **Only the non-CTAN conference styles** (`NeurIPS`, `ICLR`,
`ICML`, `CVPR/ICCV`, `ACL/EMNLP`, `AAAI`) need a download, and they are a small enumerable set,
each a pinned **file-set** (a `.sty` plus its `.bst`; older CVPR needs `cvpr.sty` + `cvpr_eso.sty`),
not a single file.

### IoC wiring: a `TemplateService` assembled by config at `build()`

`build(store, reviews, comments, assets)` (`src/latex_review/__init__.py:16-21`) is the module's
composition root; core calls it only under the flag (`server.py:65-69`). Templates add one injected
dependency, assembled from a resolver chain and injected into the units that need it:

```python
def build(store, reviews, comments, assets):
    resolvers = [BundledCatalog(), DataCache(store)]            # always present
    if config.LATEX_TEMPLATE_REGISTRY_ENABLED:                  # puller only when enabled
        resolvers.append(RegistryPuller(config.LATEX_TEMPLATE_REGISTRY, store))
    templates = TemplateService(resolvers)
    worker = CompileWorker(store, reviews, assets, templates)   # materializes companion files
    worker.start()
    wrapped = LatexAwareReviews(reviews, worker, templates)     # seeds source, validates id
    module  = LatexModule(store, wrapped, comments, worker, templates)  # lists the catalog
    return module, wrapped
```

The decorator, worker, and module depend only on the abstraction (`templates.starter(id)` /
`companion_files(id)` / `available()`); the composition root decides which concrete resolvers exist.
**The puller is absent when the registry is disabled** (air-gapped ⇒ bundled-only, test-double
provable). Core imports nothing template-related.

### Files (all under `src/latex_review/`)

```
src/latex_review/
  templates.py     TemplateService + BundledCatalog + DataCache + RegistryPuller + UnknownTemplate
  templates/       our starters:  <id>/manifest.json + starter.tex (+ bundled companion bytes for the top styles)
  registry.json    pinned pointers for non-CTAN styles: {id: {starter, files:[{url,filename,sha256,bytes}]}}
```

### Resolution model

Companion files resolve at COMPILE time (bundled bytes → `/data` cache → download), never blocking
create: bundled catalog has the files → use; else all files cached and sha256-valid → use; else id in
the pinned manifest → download each pinned url (bounded timeout, verify sha256 + byte size, no
archives) → persist under `/data` → use; else the compile fails with "unknown template". The `/data`
download cache is **shared/global** (`<data>/.templates/<id>/`), not per-review/per-tenant.

### Where templates enter the compile (IoC-correct placement)

1. **At create (decorator `LatexAwareReviews.create`, `decorator.py:24-28`):** reads the `template`
   kwarg; validates the id and raises `UnknownTemplate(available=[...])` on miss. `UnknownTemplate`
   **subclasses a core-defined `ReviewCreateRejected` base** (defined in `mdreview`, imported by the
   module, never the reverse), so the core POST arm catches the core base type and never imports
   `latex_review` — flag-off byte-identity preserved. Seeds the review source from the shipped
   starter `.tex` only when the caller supplied no source (explicit `markdown` wins; the template
   still contributes its companion files); records the `template` id in meta (persisted only when
   set, mirroring `kind` at `reviews.py:127-128`). No network, no assets here.
2. **At compile (`CompileWorker._prepare_job`, `compiler.py:134-152`):** reads `meta.template`,
   materializes the file-set via `templates.companion_files(id)` (bundled / `/data` cache /
   download-on-miss), and copies each file into the job dir by basename — the traversal-safe path
   assets already use (`compiler.py:147-152`). The download runs on the worker thread with a bounded
   connect+read timeout and total fetch budget, so a slow/hung host fails that one compile (the
   `TimeoutExpired`-style path) instead of wedging the single-thread queue. The root worker reads the
   `/data` cache and copies out; the `tectonic` uid never touches `/data` (0700 barrier preserved).

Companion files are compile-time inputs owned by the worker, **not** per-review assets.

### Create + MCP + listing surface

- `ReviewService.create` gains optional `template=""` (`reviews.py:108-109`), persisted only when set.
- `GET /api/latex/templates` via `LatexModule.handle` (`module.py:29-63`), no core route; returns
  `{bundled, registry, cached}` where `cached` is the shared/global set (no tenant data, no authz
  needed).
- MCP: optional `template` **free string** on `create_review` (schema + `client.py:56` whitelist),
  validated server-side (not a schema enum, so `tools_hash` stays stable as the catalog grows). No
  `list_templates` tool (YAGNI). Flips `tools_hash` ⇒ one reconnect.

### Security posture (download-on-miss)

The compile is already the real boundary (`--untrusted`, uid-dropped, no `/data` reads, shell-escape
off). The download adds: pinned registry only (never agent-supplied URLs), HTTPS-only; per-file
sha256 verified on download **and every cache hit**; atomic write; streamed size cap; bounded fetch
timeout + total budget; file-set of individually-pinned files, archives/zips rejected; SSRF guard
(host allowlist + resolved-IP validation against private/link-local/loopback + connection pin for
DNS-rebind/TOCTOU + no off-allowlist redirects); egress must permit the registry hosts (else the
puller fails loudly, never silently); fetched bytes land only in the root-only `/data` cache and the
ephemeral per-compile dir.

## Rollout phases

Each phase independently shippable; flag-off core stays byte-identical throughout.

1. **Foundation (MR-102):** `TemplateService` + `BundledCatalog` + `DataCache`, the core
   `ReviewCreateRejected` base exception, `build()` injection, CTAN-class starters.
2. **Create plumbing (MR-103):** `template` kwarg + POST arm catch → 400; decorator seeds/validates;
   `_prepare_job` copies bundled file-sets.
3. **Download (MR-104):** `RegistryPuller` (pinned file-set, sha256, timeout, size cap, atomic
   write, SSRF guard, `/data` cache); `tests/template_smoke.py`.
4. **Surfaces (MR-105, MR-106):** `GET /api/latex/templates`; MCP `template` param.
5. **Docs (MR-107).**

## Non-goals

- Web UI / template picker (selection is CLI/agent-only).
- Arbitrary-URL fetch; v1 fetches only the pinned registry (v2 candidate, still sha256-pinned).
- Archives/zips or unbounded multi-file kits; a template is an explicit individually-pinned file-set
  (typically 1-3 files) plus CTAN-resident deps.
- Bundling *downloaded* style files into the repo/image (the hard rule; the owner-chosen top-styles
  exception and our own starter skeletons are the only source-resident LaTeX).
- A `list_templates` MCP tool.
- Re-implementing CTAN classes (Tectonic fetches them).

## Key constraints (hard rules)

1. **IoC:** the `TemplateService`/resolver chain is constructed only in `build()` and injected; core
   imports nothing template-related; template validation + catalog listing are produced by the
   module (a `UnknownTemplate` subclassing the core-defined `ReviewCreateRejected`, plus the module
   route), never by core knowing the catalog; the puller exists only when the registry is enabled.
2. **No downloaded files in source/build** (pointer manifest + starter skeletons + the owner-chosen
   top-styles bundling are the only source-resident LaTeX; conference bytes fetched on miss live only
   in `/data`).
3. **Flag-off byte-identical core** (base oracle still passes; `template` persisted only when set;
   core catches only its own base exception, never imports the module).
4. **Companion files are compile-time inputs materialized in the worker** (time-bounded download),
   copied into the job dir by basename; never per-review assets.
5. **0700 `/data` barrier preserved** (shared cache root-only; copy-into-job-dir).
6. **Contained download** (pinned registry, per-file sha256 on download + cache hit, atomic write,
   streamed size cap, bounded fetch timeout + budget, HTTPS, IP-validated allowlist, no archives,
   shell-escape off).
7. Validation gate: `python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py
   src/latex_review/*.py src/mcp_server.py src/watch.py`; smokes on a throwaway container/scratch
   port under `MDREVIEW_ENABLE_LATEX`, never the live instance.

## Preferred execution order

MR-101 (this scaffolding) → MR-102 → MR-103 → MR-104 → MR-105/MR-106 (independent) → MR-107 (last).

## Ticket breakdown

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-101 | Capture brief + epic plan + G1 record | docs | 0 |
| MR-102 | TemplateService + BundledCatalog + DataCache + ReviewCreateRejected + build() injection + CTAN starters | svc | 1 |
| MR-103 | `template` create plumbing (kwarg, POST-arm 400, decorator seed/validate, bundled file-set copy-in) | svc | 2 |
| MR-104 | RegistryPuller (pinned file-set, sha256, timeout, size cap, SSRF guard, /data cache) + template smoke | svc | 3 |
| MR-105 | GET /api/latex/templates listing | svc | 4 |
| MR-106 | MCP create_review `template` param + mcp_smoke | mcp | 4 |
| MR-107 | Docs sweep: README templates + registry + egress/config + year-churn cadence, gate refs, runbook | docs | 5 |

## Risks and mitigations

| Risk | L | I | Mitigation |
|------|---|---|------------|
| Misjudged file-set (kit needs more files) | M | M | Per-conference file-list verified in MR-104; a missing file surfaces as a clear compile error; manifest updated (data, no rebuild) |
| Year-stamped styles churn; pinned sha256 stale | H | L | Manifest is data; fails closed with a clear error, never a silent wrong file; MR-107 documents the cadence |
| Slow/hung registry host wedges the compile queue | M | M | Bounded connect+read timeout + total fetch budget; fails that compile; worker stays live |
| Operator egress locked to Tectonic host ⇒ no registry | M | M | Puller fails loudly; README names the hosts to allowlist; bundled-only still works |
| Malicious/oversized/tampered file | L | L | Per-file sha256 (download + cache-hit), size cap, atomic write, no archives, shell-escape off, hardened compile |
| SSRF / DNS-rebind via registry URL | L | M | Pinned registry, HTTPS, allowlist + resolved-IP validation + connection pin, no off-allowlist redirects |
| Interface-on-spec over-abstraction | M | L | Resolver seam has 2-3 real backends + optional network unit; collapses to a plain function if only "bundled" survives |

## Verification (runnable, non-gameable)

```bash
python3 -m py_compile src/mdreview/*.py src/mcp/*.py src/watcher/*.py src/latex_review/*.py src/mcp_server.py src/watch.py
# flag-off byte-identical oracle (tests/golden_transcript.sh) still empty
# IoC isolation: registry DISABLED -> build() constructs NO RegistryPuller
# bundled resolve + compile: create template=ieee -> starter seeded -> compiles
# download-on-miss FILE-SET: first compile fetches each file, verifies sha256, persists under <data>/.templates/<id>/; assert NOT in the image/repo
# cache-hit re-verify: corrupt a cached file -> mismatch detected -> re-fetch
# tamper/SSRF: wrong sha256 -> reject; non-HTTPS / non-allowlisted host / private IP -> refuse
# unknown id -> 400 with available list (module exception, not core); egress-locked -> puller fails loudly
# precedence: explicit source + template=ieee -> explicit source kept, IEEE companion files applied
# fetch timeout: hung host -> that compile fails within budget; worker keeps serving
```

## Decisions recorded (owner, 2026-07-21, on review a4b479b1ac)

1. **Default registry: shipped-populated** with the known non-CTAN conference file-sets.
2. **Base branch: merged `feat/latex-review` to `dev` first** (done, PR #62); this epic's tickets cut
   from `dev`.
3. **Bundle the top non-CTAN styles as files** (offline); download-on-miss covers the tail. Verify a
   redistribution-OK license on each bundled style.
4. **Registry origin: each conference's own official source** (no self-hosted mirror in v1).
5. Plan critic-passed (2 rounds); owner said "merge it and go".

## Assumptions and open items

- Per-conference exact file-lists are enumerated by compiling each target in MR-104 (not asserted
  here); NeurIPS/ICLR/ACL are expected to be one `.sty` + a `.bst`, CVPR the confirmed multi-file case.
- Bundled-styles licensing is verified per style before shipping (MR-102/MR-103).
