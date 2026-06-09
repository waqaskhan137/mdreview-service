---
slug: landing-page
captured: 2026-06-09
source: user request 2026-06-09 (waqas) — "single static page on github" after a should-this-have-a-website discussion; accepted the "single static page on GitHub Pages" recommendation from that discussion
related_epic: (pending — epics/landing-page-plan.md once planned)
audience: public — prospective users discovering the tool (HN, MCP server directories, search); not the agents that call the API
---

# Single static landing page on GitHub Pages

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> single static page on github. Start writing the breif get it approved and then we will do the
> feature cycle.

Context the user accepted (from the same conversation, the "option 2" recommendation):

> **Single static page on GitHub Pages** (the repo already serves static assets, and a
> stdlib-only project pairs nicely with a zero-build HTML page): tagline, the GIF, the curl flow,
> "deploy with docker compose". Worth it only if you plan to share the project publicly — on HN,
> in MCP server directories, etc. [...] MCP server directories and registries are becoming how
> people discover tools like this. A canonical URL with a clear demo helps there.

## What it must be

- **One page, zero build.** Hand-written HTML/CSS (vanilla JS only if needed), no framework, no
  bundler, no generator. Matches the project's stdlib-only / no-pip spirit.
- **Hosted on GitHub Pages** from this repo, served at **`mdreview.waqasrana.space`** (the
  repo's name on the user's `waqasrana.space` domain, which has wildcard subdomains enabled) as
  the project's canonical public URL.
- **Content:** tagline + one-paragraph what-it-is; a visual demo of the review loop (the page's
  reason to exist — a human annotating, the agent's revision live-reloading with notes struck
  through); the agent curl flow at a glance; "run it" (`docker compose up -d --build`); the MCP
  server as a first-class mention; prominent link to the GitHub repo.
- **No drift surface.** The page must not duplicate content that changes (the full API table,
  config tables, tool lists) — it links to the README for those. It sells; the README documents.

## Decisions for the plan (not pre-made here)

- **Pages source layout:** `gh-pages` branch vs. a directory on `main` (note `docs/` already
  holds process docs and is the only directory GitHub Pages can serve from `main` besides root —
  the plan must resolve this without disturbing `docs/process/`).
- **The demo asset:** a real GIF/screen capture of the review loop needs producing — how, at what
  point in the cycle, and what the page shows until it exists (screenshot fallback?).
- **Publishing mechanics:** whether enabling Pages is a manual one-time step (acceptable; akin to
  the G8 merge) and how the page's URL gets recorded in the README.
- **Custom domain wiring:** the subdomain is fixed (`mdreview.waqasrana.space`); the plan
  resolves the mechanics — the `CNAME` file in the Pages source, and which DNS steps stay manual
  (the wildcard may already cover the CNAME record; verifying + enabling HTTPS in repo settings
  is likely a one-time human step).
- **Design direction:** consistent with the viewer/dashboard's existing look, or its own identity.

## Out of scope

- Multi-page site, docs site, blog, analytics.
- Any change to the service, its API, or the MCP wrapper.
- Submitting to directories/HN (the page enables it; doing it is the user's call later).

## Amendments

- **2026-06-09 (waqas, via mdreview note on this brief):** serve the page on a custom domain —
  `waqasrana.space` has wildcard subdomains enabled, so use a subdomain (e.g.
  `mdreview.waqasrana.space`) rather than the bare `*.github.io` URL. Custom domain moved from
  out-of-scope to a plan decision (wiring details above).
- **2026-06-09 (waqas, via mdreview note, round 2):** asked which subdomain concretely. Fixed it
  as **`mdreview.waqasrana.space`** (the repo name); only the CNAME/DNS mechanics remain a plan
  decision.
