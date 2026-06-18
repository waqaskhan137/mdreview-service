---
epic: landing-page
status: done           # shipped: merged to main (PR #4), live at https://mdreview.waqasrana.space/ (MR-021 GIF demo remains backlog)
created: 2026-06-09
source: requirements/landing-page.md
gate: passed 2026-06-09   # G1 (Plan Gate): staff-critic r2 PASS
review: reviews/landing-page-plan-review-2026-06-09.md   # r1 PASS-WITH-FIXES (resolved); r2 -r2.md PASS
related_sprints: [sprint-05]
related_tickets: [MR-019, MR-020, MR-021]   # MR-021 backlog, not committed to sprint-05
---

# Landing page on GitHub Pages Plan

mdreview-service is a working, documented micro-service with no public face. This epic ships a
single hand-written static HTML/CSS page — zero build step, matching the repo's stdlib-only
spirit — published on GitHub Pages at the fixed canonical URL **`mdreview.waqasrana.space`**. The
page exists to *sell* the tool to a human discovering it (HN, MCP server directories, search): a
tagline, a visual demo of the review loop (its reason to exist), the agent curl flow at a glance,
"run it" with docker compose, a first-class MCP mention, and a prominent repo link. It documents
nothing the README already documents — it links there — so it never becomes a drift surface.

**Source requirement:** [`requirements/landing-page.md`](../requirements/landing-page.md) — the
original ask, kept verbatim (two mdreview feedback rounds already applied; the custom domain is
fixed in its Amendments).

## Product goal

A person who hears about mdreview can open one canonical URL and, within a screen or two,
understand what it is, *see* the human-in-the-loop review loop happen, copy the curl flow that
drives it, know how to run it (`docker compose up -d --build`), learn it speaks MCP, and click
through to the GitHub repo. The page is live at `https://mdreview.waqasrana.space` over HTTPS, is
buildless and self-contained, and the README records the canonical URL. The service, its API, and
the MCP wrapper are **byte-for-byte unchanged** — this epic adds one static artifact and the
publishing wiring around it, nothing more.

## Core design principle

**It sells; the README documents. Zero build; zero drift.** The page is one self-contained
hand-written `.html` file (inline `<style>`, vanilla JS only if genuinely needed) with no
framework, bundler, or generator — the same "no installs, it just runs" posture as the service.
Every fact that *changes* (the API table, config table, MCP tool list) is **linked**, never
copied, so the page cannot rot out of sync with the README. Anything more than one page, or any
edit to the service, is out of scope by construction.

## Recommended approach

This epic touches no running code. There is no `app.py` change and no service behavior change —
the page is hosted by GitHub Pages, not by the container. The work is a static asset plus its
publishing pipeline.

### Service (`app.py`)
- **No change.** `python3 -m py_compile app.py` remains green trivially; this epic adds no route,
  no field, no served file to the container. The Dockerfile `COPY` (`Dockerfile:8`) is **not**
  touched — the landing page is *not* served by the service, so the sprint-01 "served file needs
  a Dockerfile COPY" footgun does **not** apply here. (Called out so a reviewer can confirm the
  asset deliberately lives outside the image.)

### UI (the static page — a new artifact, not `viewer.html`/`dashboard.html`)
- **One file: `site/index.html`** (a new top-level `site/` directory on `dev`; see Phase 1 for why
  `site/` and not `docs/`). Hand-written HTML + inline `<style>`. Sections, in order:
  1. **Hero** — product name, one-line tagline, one-paragraph what-it-is, primary CTA buttons
     (GitHub repo, "run it").
  2. **Visual demo of the review loop** — the page's reason to exist. A static screen capture
     (Phase 1) of the viewer mid-review (a human's note, a struck-through addressed note),
     upgradeable to an animated GIF (Phase 2) with **no layout change** — the GIF drops into the
     same `<img>` slot. Caption names the loop: human annotates -> agent revises -> notes strike
     through.
  3. **Curl flow at a glance** — a short, copy-pasteable `POST -> hand off -> poll -> PUT`
     sequence in a `<pre>`. This is an *at-a-glance* teaser, deliberately shorter than the README
     contract; it links to the README for the full API table rather than reproducing it.
  4. **Run it** — `docker compose up -d --build` (serves `http://localhost:8137`), one line, with
     a link to the README "Run" section for variants.
  5. **MCP, first-class** — one short paragraph that it speaks MCP (stdio, JSON-RPC) with a link to
     the README "MCP server" section; **no tool list copied inline** (drift surface).
  6. **Footer** — prominent repo link, canonical URL, license/author.
- **Design direction (Decision 5): reuse the viewer/dashboard visual tokens, own the layout.**
  Adopt the existing palette + type system verbatim from `dashboard.html:8-9` — the **full** `:root`
  custom-property set (`--bg:#fafaf9; --text:#1a1a1a; --muted:#6b6b6b; --accent:#0f766e;
  --rule:#e6e4e0; --noteline:#d4a017; --card:#fff;`, including `--noteline` — the strike-through /
  annotation accent the demo screenshot shows, so the page chrome and the screenshot share a
  palette) and the dark-mode `@media (prefers-color-scheme: dark)` block (`dashboard.html:9`) —
  and the system font stack (`-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif`,
  `dashboard.html:11`) and the `ui-monospace,SFMono-Regular,Menlo,monospace` stack used throughout
  `dashboard.html`.
  This makes the landing page look like the same product as the screenshot it shows, at zero cost.
  The page copies these values into its own inline `<style>` (it is a separate artifact on a
  separate host; it cannot and should not import the dashboard's CSS).
- **Responsive behavior as behavior, not a pixel breakpoint** (sprint-01 lesson). The page is a
  single readable column with a `max-width` (the dashboard uses `920px`,
  `dashboard.html:12`); the demo image is `max-width:100%` and scales to fit its container; the
  curl/run `<pre>` blocks scroll horizontally rather than forcing a min-width. No hard-coded
  `<=NNNpx` media query is required for the core layout — a single fluid column "fits any viewport
  that is at least one column wide" by construction. If any element (e.g. side-by-side CTAs) needs
  to stack on narrow screens, specify it as "stack when the row no longer fits its content," not a
  guessed pixel value.

## Rollout phases

Each phase is independently shippable. Phase 1 puts a real, live, branded page on the canonical
URL with a static demo. Phase 2 swaps the static demo for an animated GIF with no other change.

### Phase 1 — Buildless page, live at the canonical URL (static demo)
- Author `site/index.html` with all six sections, reusing the dashboard tokens.
- Capture a **static screenshot** of the viewer mid-review as the demo asset and place it in
  `site/` (e.g. `site/demo.png`). **`scripts/render-smoke.sh` does not and cannot produce this —
  it only `--dump-dom`s the rendered page and counts DOM nodes; it never writes an image.** The
  screenshot is produced by one of the two procedures below (chosen in MR-019), against a running
  viewer that has a human note and an addressed (struck-through) note (see Verification). The page
  references it with a descriptive `alt`.
  - **(a) Manual browser capture (matches the repo's actual practice, default).** Open the local
    viewer mid-review in a browser and capture the screenshot to `site/demo.png` — the same manual
    procedure that produced `reviews/sprint-01-render-evidence/*.png` (per the feature-cycle skill's
    `references/04-close-and-ship.md`: "open it in a browser, screenshotting to
    `reviews/...-render-evidence`"). Cheapest, honest about what the repo does, no new tooling.
  - **(b) Direct headless-Chrome screenshot (only if a repeatable command is wanted).** Invoke
    Chrome's own `--screenshot` flag **directly** — *not* via render-smoke — reusing the same Chrome
    binary render-smoke locates (the `RENDER_SMOKE_CHROME` env var or the `CANDIDATES` list in
    `scripts/render-smoke.sh:32-41`, e.g. `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
    on macOS, `google-chrome`/`chromium` on Linux):
    ```bash
    "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --screenshot=site/demo.png --window-size=1280,800 \
      --virtual-time-budget=2500 "http://localhost:8137/r/<id>"
    ```
    This adds no pip/npm dependency and no build step, but it is a new ad-hoc command (not existing
    tooling); MR-019 picks (a) or (b) explicitly. Default is (a).
- Add the `site/CNAME` file containing `mdreview.waqasrana.space` (GitHub Pages reads this from the
  publish source to set the custom domain).
- Establish the **publishing pipeline**: publish the contents of `site/` to a dedicated
  `gh-pages` branch root (see Decision 1). This is a documented, repeatable manual/scriptable
  step, decoupled from the `dev`/`main` integration flow.
- **One-time human steps** (documented in the publishing ticket, akin to the G8 merge): enable
  Pages on the repo pointing at the publish source, confirm/add the DNS record for the subdomain,
  verify the domain in repo settings, and enforce HTTPS.
- **Then** record the canonical URL in the README (a small docs edit; the README already exists and
  is the source of truth for "where it lives"). **This edit is sequenced last and gated on the
  publish-verification block passing** (`dig` resolves to `<owner>.github.io`, `curl -sI … 200`
  over HTTPS, live render-smoke green) — the README must not assert a live URL that 404s. MR-020's
  ACs order this as "record the URL in README *after* publish-verification is green," not in
  parallel with the publish step.

### Phase 2 — Animated GIF demo (drop-in upgrade)
- Produce an animated GIF (or compressed `.mp4`/`.webm` with a poster fallback) of the live review
  loop: a human typing a note, the agent's `PUT /source` live-reloading the viewer, the addressed
  note striking through. Replace `site/demo.png` in the same `<img>` slot — no layout change, no
  HTML structure change beyond the asset reference (and a `<video>` swap only if the team chooses
  video over GIF). Re-publish.
- This phase is deliberately separable so Phase 1 is not blocked on capture tooling; the page is
  fully functional and on-brand with the static screenshot until the GIF exists.
- **MR-021 is NOT committed to this sprint.** It is **backlog / next cycle.** The GIF asset does not
  exist and the capture approach (GIF vs. `<video>`) is an open question (see Assumptions), so
  MR-021 cannot be `ready` and committing it would fail G6 (every committed ticket must be `ready`).
  **The epic's sprint commits MR-019 + MR-020 only**; MR-021 is groomed and committed in a later
  sprint once the GIF decision and tooling are settled.

## Non-goals

Explicit scope boundaries — what this epic is deliberately **not** doing.

- **No second page, docs site, blog, or analytics.** One `index.html`. (Brief "Out of scope".)
- **No change to the service, its API, or the MCP wrapper.** No `app.py`, no route, no `meta.json`
  field, no `Dockerfile` `COPY`, no `static/` served asset. The page is hosted by Pages, not the
  container.
- **No duplication of the README's API/config tables or the MCP tool list.** The page links; it
  never copies content that changes. (Brief "No drift surface".)
- **No submission to HN, MCP directories, or registries.** The page *enables* that; doing it is the
  user's later call. (Brief "Out of scope".)
- **No build tooling of any kind** — no npm, no static-site generator, no CSS preprocessor, no
  asset pipeline. Hand-written HTML/CSS only.
- **No `MDREVIEW_PUBLIC_BASE` / live-instance wiring as part of this epic.** The page is marketing,
  not an integration; if it wants to link to a live demo instance that is a copy-link, not config.

## Key constraints

Hard rules the implementation must not violate (the repo footguns, made specific to this epic).

- **Zero build, stdlib spirit.** No framework/bundler/generator/preprocessor and **no pip / npm
  dependency**. If a feature tempts a tool (e.g. a CSS framework), it does not ship — hand-write it.
- **No drift surface.** Never copy the README's API table, config table, or MCP tool list into the
  page. Link to the relevant README section instead. Any inline command (the curl teaser, the
  docker line) must be the *minimal* at-a-glance form, with a link to the canonical README block.
- **The page is NOT served by the container.** It is not a sibling of `viewer.html`/`dashboard.html`
  inside the image; it lives in `site/` and is published to GitHub Pages. Therefore the
  "new served file needs a `Dockerfile COPY`" footgun (sprint-01, commit `1326462`) does **not**
  apply — and the plan asserts the `Dockerfile` (`Dockerfile:8`) is deliberately left untouched, so
  a reviewer can confirm the asset is intentionally outside the image.
- **A 200 is not a render** (sprint-01 lesson). The deliverable is a JS/HTML-rendered surface, so
  verification renders the page from its served location and asserts the expected DOM nodes via
  `scripts/render-smoke.sh`, not a curl 200 or a screenshot alone (a screenshot proves first-paint
  only). Because the page is static HTML with inline CSS, render-smoke against the **published
  URL** (or a `python3 -m http.server` of `site/`) is the gate, not a container rebuild.
- **Responsive = behavior, not pixels.** Single fluid column with a `max-width`; demo image fits
  its container; code blocks scroll. No hard-coded `<=NNNpx` breakpoint asserted without measuring
  the element it gates (the sprint-01 820px/284px gutter reconciliation).
- **`dev`/`main` branching is untouched** (Decision 1). All authoring work integrates into `dev`
  per the Branching rule; `main` advances only at G8. GitHub Pages publishes from a **separate
  `gh-pages` branch**, so publishing is decoupled from the `dev`->`main` promotion and does not
  force `main` to advance just to ship the page.
- **Do not disturb `docs/process/`.** The committed process tree owns `docs/`. The page does not go
  under `docs/` (see Decision 1).
- **Dates `Europe/London`; commits carry the `Co-Authored-By: Claude` trailer and the ticket ID.**

## Decisions (resolved here, per the brief)

These are the five decisions the brief explicitly delegated to the plan.

**Decision 1 — Pages source layout: a dedicated `gh-pages` branch, published from its root.**
GitHub Pages on a *branch* can serve only `/` (root) or `/docs`. `/docs` is taken by the committed
process tree and must not be disturbed; serving from the **root of `dev`/`main`** would force a
top-level `index.html` to sit beside `app.py` and the process docs, and couple publishing to the
`dev`->`main` G8 promotion. **Resolution:** author the page under a top-level `site/` directory on
`dev` (the editable source of record), and **publish it to a dedicated `gh-pages` branch whose
root is the `site/` contents.** Pages is configured to serve from `gh-pages` root. This keeps the
authored source on `dev` (normal flow, normal review), keeps `docs/process/` untouched, and
decouples publishing from `main`. *(Alternative considered: a GitHub Actions workflow to auto-build
`gh-pages` from `site/` on push. Rejected for this epic — it adds a moving part and a hidden build
step, against the "zero build" principle. The publish step stays an explicit, documented action; a
later follow-up could automate it if desired.)*

**Decision 2 — The demo asset: static screenshot first (Phase 1), GIF as a drop-in upgrade
(Phase 2).** A real animated capture of the loop is the ideal, but capture tooling/quality should
not block shipping a live, branded page. **Resolution:** Phase 1 ships a **static screenshot**
(`site/demo.png`) of the viewer mid-review, captured by the procedure in *Rollout phases -> Phase 1*
— **(a) a documented manual browser capture (default, matching how `sprint-01-render-evidence/*.png`
were made), or (b) a direct `chrome --headless=new --screenshot=…` command** invoked against a
running viewer with a human note + an addressed/struck note. **`scripts/render-smoke.sh` is not a
screenshot tool — it `--dump-dom`s and asserts DOM nodes only, never writing an image — so it is
*not* used to produce the demo asset.** Phase 2 replaces the screenshot with an animated GIF/video
in the same slot, no layout change. The page is fully on-brand with the screenshot until the GIF
exists. The capture is taken against a **local** docker-compose viewer on `localhost:8137`
(deterministic, no dependence on the live instance).

**Decision 3 — Publishing mechanics: one-time human steps, explicitly documented (akin to G8).**
**Resolution:** enabling Pages, pointing it at `gh-pages` root, verifying the custom domain, and
enforcing HTTPS are **one-time manual human steps** — acceptable, the same posture as the G8 merge
being a human go-ahead. They are written as an explicit runbook in the publishing ticket's
acceptance criteria so they are repeatable and auditable. The per-cycle act of *updating* the page
is: edit `site/` on `dev`, then publish the **contents of `site/`** to the **root** of `gh-pages`
(a documented git command sequence in the ticket, not a build).

**The one pinned publish sequence (MR-020 inherits this verbatim) — a dedicated `git worktree` on
an orphan `gh-pages` branch.** Chosen over `git subtree split` (accumulates history bloat / is
awkward to re-run) and a throwaway in-place `git checkout` of `gh-pages` (collides with the working
tree, easy to commit `site/` source by mistake). A worktree keeps `dev` clean, places `site/`
*contents at the branch root* (not under `site/`), and is idempotent on re-publish:

```bash
# one-time: create the orphan gh-pages branch in a separate worktree dir (outside the repo tree)
git worktree add --orphan -b gh-pages ../mdreview-gh-pages   # empty orphan branch, own working tree
# (if gh-pages already exists remotely: `git worktree add ../mdreview-gh-pages gh-pages` instead)

# each publish: mirror site/ CONTENTS into the worktree root, commit, push
rsync -a --delete --exclude '.git' site/ ../mdreview-gh-pages/   # site/* -> gh-pages root; CNAME carried
git -C ../mdreview-gh-pages add -A
git -C ../mdreview-gh-pages commit -m "publish: site -> gh-pages (MR-020)

Co-Authored-By: Claude <noreply@anthropic.com>"
git -C ../mdreview-gh-pages push origin gh-pages
```
`rsync --delete` makes re-publishes idempotent (removed files disappear); `site/CNAME` lands at the
branch root so Pages picks up the custom domain. `dev` is never checked out into the worktree, so
the authored source and the published artifact never cross-contaminate. The canonical URL is
recorded in the README by a small docs edit **after** the publish-verification block is green (see
*Rollout phases -> Phase 1* sequencing), so the README never asserts a URL that 404s.

**Decision 4 — CNAME mechanics for `mdreview.waqasrana.space`.** **Resolution:** add a `CNAME` file
containing exactly `mdreview.waqasrana.space` to the publish source (`site/CNAME`, carried to
`gh-pages` root) — GitHub Pages reads it to set the custom domain. The DNS side is a **DNS `CNAME`
record** for `mdreview` -> `<owner>.github.io` (an `A`/`AAAA` apex set is not needed for a
subdomain). The user's wildcard `*.waqasrana.space` **may already resolve** the subdomain to a
parking/host target, so the plan flags **verifying the DNS record actually points at GitHub Pages**
(wildcard coverage is not the same as the correct CNAME target) as a human step in the publishing
ticket. See the BLOCKER-FOR-HUMAN below on the repo-owner / domain-owner mismatch.

**Decision 5 — Design direction: reuse the viewer/dashboard tokens, own the layout.** Resolved in
*Recommended approach -> UI*: adopt the dashboard's full `:root` palette (including `--noteline`,
`dashboard.html:8`), dark-mode block (`dashboard.html:9`), and font stacks (the system stack at
`dashboard.html:11`, and the `ui-monospace,SFMono-Regular,Menlo,monospace` stack used throughout
`dashboard.html`) so the page matches the product it shows, with a bespoke single-column marketing
layout. Zero new design system, zero dependency.

## Assumptions & open questions

Surfaced first, per process. Each is the default this plan proceeds against (autonomous run).

- **BLOCKER-FOR-HUMAN — repo owner vs. domain owner.** The repo is
  `github.com/waqaskhan137/mdreview-service`; the domain is `waqasrana.space`. For GitHub Pages
  custom-domain verification, the GitHub account that owns the repo must be the one that verifies
  the domain, and the DNS `CNAME` target is `<repo-owner>.github.io` (i.e. `waqaskhan137.github.io`)
  — **not** a `waqasrana`-named target. If these are the **same person's** two identities this is
  just a fact to encode in the runbook; if the domain is administered by a **different** GitHub
  org/account than `waqaskhan137`, the verification and DNS steps differ and could stall publishing.
  **This needs a one-line human confirmation** of which GitHub account owns the repo at publish
  time and that it controls (or is delegated) the `waqasrana.space` DNS. *(Default if unanswered:
  assume same owner; CNAME target `waqaskhan137.github.io`; encode it as a verify step. Flagged
  because a wrong assumption here wastes a publish attempt, not a sprint — hence BLOCKER-FOR-HUMAN,
  not a silent default.)* **load-bearing.**

- **Q (minor): GIF vs. video for the Phase 2 demo.** Assumption: produce an **animated GIF** for
  maximum portability (no JS, no codec concerns, works in every directory/embed); accept the larger
  file size for a short loop. If size is a problem, fall back to a `<video autoplay muted loop
  playsinline>` with the Phase-1 PNG as `poster`. Either way it drops into the same slot. Resolved
  in Phase 2; no design impact.

- **Q (minor): exact tagline / marketing copy.** Assumption: derive the tagline and what-it-is
  paragraph from the README's opening ("A containerized markdown review microservice. An agent
  POSTs markdown, gets back a review URL for a human, and polls feedback over HTTP.") so the page
  and README agree in voice. The user can tweak copy at authoring review; copy is not load-bearing
  to the structure.

- **Q (minor): does the page link to a live demo instance?** Assumption: **no live-instance link in
  Phase 1** — the demo screenshot/GIF carries the "see it work" job, and a public unauthenticated
  live instance widens exposure (no auth; id-only tenancy). If the user wants a "try it" link to
  their live instance later, that is a one-line copy change, not a structural one. Noted so the
  no-auth posture is respected by default.

- **Q (minor): where in `site/` the demo asset lives.** Assumption: alongside `index.html`
  (`site/demo.png`, `site/CNAME`) so the publish step is a flat copy of `site/` -> `gh-pages` root
  with no path rewriting. Resolved in Phase 1.

## Preferred execution order

Author the page and capture the asset first (the shippable artifact), then wire publishing, then
record the URL. Publishing's one-time human steps are last and explicitly human-gated.

1. **MR-019** — author `site/index.html` (all six sections, dashboard tokens, fluid column) +
   `site/demo.png` static screenshot + `site/CNAME`. Local render-smoke is the gate.
2. **MR-020** — publishing runbook + `gh-pages` pipeline + one-time Pages/DNS/HTTPS human steps;
   record the canonical URL in the README. (Depends on MR-019; the human steps gate going live.)
3. **MR-021** *(Phase 2 — backlog / next cycle, NOT in this sprint)* — animated GIF demo, drop-in
   replacement in the same slot, re-publish. Depends on MR-019/MR-020; independently shippable
   later, not required to declare Phase 1 live. Parked because it is not `ready` (no asset; GIF-vs-
   video open) — committing it would fail G6.

**This epic's sprint commitment is MR-019 + MR-020 only** (both Phase 1, both reach `ready`).
MR-021 is backlog.

A docs-sweep is not separately needed: the only durable doc change is recording the canonical URL,
folded into MR-020 (not deferred), satisfying the Definition of Done in the same change.

## Ticket breakdown

Create these in `tickets/` only after G1 passes, then link them here. IDs are placeholders; the
orchestrator allocates real IDs (next free is MR-019).

| ID | Title | Layer | Phase | Sprint |
|----|-------|-------|-------|--------|
| MR-019 | Author buildless landing page (`site/index.html`) with dashboard tokens, static demo screenshot, and `CNAME` | ui | 1 | **committed** |
| MR-020 | Publish to GitHub Pages: `gh-pages` pipeline, one-time Pages/DNS/HTTPS runbook, record canonical URL in README | infra | 1 | **committed** |
| MR-021 | Replace static demo with animated GIF of the review loop (drop-in) and re-publish | ui | 2 | **backlog / next cycle** |

Layer notes: MR-019 is `ui` (a human-facing rendered surface, even though served by Pages, not the
container — its gate is render-smoke against a local `python3 -m http.server` of `site/`). MR-020 is
`infra` (deploy/host wiring + the README URL edit folded in as the DoD docs change). MR-021 is `ui`
(asset swap on the rendered page).

**Sprint commitment: MR-019 + MR-020 only.** MR-021 is **not** committed to this sprint — it is
backlog (next cycle), because its GIF asset does not exist and the GIF-vs-`<video>` decision is open,
so it cannot reach `ready` and committing it would fail G6. It is groomed and committed in a later
sprint.

## Risks & mitigations

- **Risk: custom-domain verification stalls** (repo-owner vs. domain-owner mismatch, wrong CNAME
  target, wildcard masking the real record). *Mitigation:* the BLOCKER-FOR-HUMAN above forces a
  one-line owner/DNS confirmation before MR-020's go-live steps; the runbook includes an explicit
  "verify `dig CNAME mdreview.waqasrana.space` resolves to `<owner>.github.io`" check rather than
  trusting wildcard coverage.
- **Risk: the page silently becomes a drift surface** (someone pastes the API table in later).
  *Mitigation:* the Core design principle and a Key constraint forbid copying changeable content;
  MR-019's acceptance criteria require every API/config/MCP detail to be a *link*, not inline text.
- **Risk: a "small" build step creeps in** (a CSS framework, a generator). *Mitigation:* zero-build
  is a Key constraint and a Non-goal; MR-019 AC require a single hand-written `.html` with inline
  CSS and no dependency manifest of any kind.
- **Risk: Phase 1 blocked waiting on a perfect GIF.** *Mitigation:* Decision 2 ships a static
  screenshot first; the GIF is a separable Phase 2 drop-in, so the page goes live on time.
- **Risk: publishing couples to `main`/G8.** *Mitigation:* Decision 1 publishes from a dedicated
  `gh-pages` branch, decoupled from the `dev`->`main` promotion.
- **Risk: render-smoke has no container to hit** (the page is not served by the image), and
  README's G4 says render-smoke runs "from the rebuilt image" — which is impossible for an artifact
  never in any image. *Mitigation:* this is resolved **inside MR-019's acceptance criteria** (not
  left as a risk): MR-019's named G4 render-smoke target is a local `python3 -m http.server
  --directory site`, and MR-019 states as a ticket-level fact that the absent container rebuild is
  compliant for this artifact. See *Verification -> Page render-smoke (MR-019)*.

## Verification

No test framework; the gates are `py_compile` (trivially green — no `app.py` change) plus
render-smoke DOM assertions for the page, run against the page's served location.

**Service gate (sanity, unchanged):**
```bash
python3 -m py_compile app.py    # still green; this epic does not touch app.py
```

**Page render-smoke (MR-019 — the real gate for the new artifact).**

**MR-019's named G4 validation target is a local `python3 -m http.server` of `site/`, NOT a rebuilt
container image.** README's G4 pass-condition says a `ui` ticket's render-smoke runs "from the
rebuilt image" — but MR-019's artifact (`site/index.html`) is **never in any image** (it is hosted
by Pages, not the container; the Dockerfile is untouched). So MR-019 carries this as an explicit
ticket-level fact: its G4 render-smoke target is **`python3 -m http.server --directory site`**, and
a missing container rebuild is **compliant** for this artifact, not a gate miss. The script's own
contract ("target a SERVED url, never `file://`") is satisfied — an `http.server` URL *is* a served
URL, just not a container's published port.

**MR-019's acceptance criteria carry the render obligation (owed at G4, independent of the G7
trigger):**
1. `python3 -m http.server 8200 --directory site` serves the page; `scripts/render-smoke.sh
   http://localhost:8200/ <selectors>` exits 0 against the served page (DOM nodes asserted, not a
   200 or substring grep).
2. A **captured screenshot** of the rendered page is committed as G4 evidence under
   `reviews/sprint-NN-render-evidence/…` (the repo's existing manual-capture practice — the same
   way `viewer.html`/`dashboard.html` evidence is produced; `scripts/render-smoke.sh` does **not**
   produce it).
3. `site/demo.png` exists and the `<img class="demo-img">` references it with a descriptive `alt`
   (the `img.demo-img` selector in the render-smoke proves the element rendered).
4. No-drift grep passes (no README table/tool-list text copied inline; see below).

```bash
# from repo root, serve the static site (the named G4 target — no container)
python3 -m http.server 8200 --directory site &   # serves http://localhost:8200/

# assert the page rendered its key sections (give each landmark a stable class/id in the HTML)
scripts/render-smoke.sh http://localhost:8200/ \
  .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link
# expect: every selector matches >=1 node -> exit 0
```
(Selectors here are illustrative landmarks; MR-019 must add matching stable hooks — e.g.
`class="hero"`, `class="demo"`, `<img class="demo-img">`, `class="curl-flow"`, `class="run-it"`,
`class="mcp"`, `class="repo-link"` — and the ticket asserts exactly the ones it ships. The
render-smoke matcher supports `tag`, `.class`, `tag.class`, `#id`.)

**Demo asset present and referenced.** Confirm `site/demo.png` exists and the page's `<img>` points
at it with a descriptive `alt`; the `img.demo-img` selector above proves the element rendered.

**No-drift check (manual, in MR-019 review).** Grep the page for the README's table headers /
tool names to confirm none were copied inline; every API/config/MCP reference is an `href` to the
README, not reproduced text.

**Publish verification (MR-020, after the one-time human steps):**
```bash
# DNS points at GitHub Pages (not just covered by the wildcard)
dig +short CNAME mdreview.waqasrana.space      # expect <owner>.github.io

# the live page serves over HTTPS and rendered its DOM
curl -sI https://mdreview.waqasrana.space/ | head -1        # expect HTTP/2 200
scripts/render-smoke.sh https://mdreview.waqasrana.space/ \
  .hero .demo img.demo-img .curl-flow .run-it .mcp .repo-link

# CNAME file is in the publish source
curl -s https://mdreview.waqasrana.space/CNAME              # expect: mdreview.waqasrana.space
```
The README records the canonical URL (grep the README for `mdreview.waqasrana.space` after MR-020).

**Phase 2 (MR-021):** after swapping the asset, re-run the live render-smoke (`img.demo-img` still
matches; if switched to `<video>`, assert `video.demo-vid` instead) and confirm the loop animates.

## Process / gate enforcement note

This epic proposes **no new rule the delivery process must enforce** — it adds a static artifact and
a publishing runbook, all within existing gates (G1 plan review, G4 render-smoke for the `ui`
ticket, G5 DoD with the README URL folded in, G7 sprint-close review). **It also does not rely on
the G7 per-page render-evidence trigger to cover this page**, and deliberately so:

- The G7 pass-condition row fires the per-page DOM-assertion + screenshot obligation **only if a
  product page (`viewer.html` / `dashboard.html` / `static/**`) was touched this sprint.**
  `site/index.html` is, by this epic's design, **none** of those three and lives **outside**
  `static/**`. By the row's literal text this sprint touches no product page, so G7 would owe only
  the unconditional rebuild + `curl /healthz` + `/api/reviews` smoke — which is trivially green
  (`app.py` is unchanged) and proves nothing about the landing page. **We do not assert the G7
  trigger covers `site/**`** — that would be claiming a gate row says something it does not (the
  MR-012 / mcp-wrapper-B1 defect class).
- **Instead, the render verification lives in MR-019's own acceptance criteria** (see *Verification
  -> Page render-smoke (MR-019)* and the MR-019 AC list there): a render-smoke DOM assertion against
  the **served `site/`** plus a captured screenshot is **owed at G4 as MR-019's own evidence**,
  independent of how the G7 trigger reads. The gate enforcement lives in a real ticket AC (per the
  MR-012 rule that teeth must live in the enforcing artifact, not in prose), so the page is
  render-verified whether or not G7's trigger set ever names it.

Because the enforcement is carried entirely by MR-019's existing-gate ACs (G4), **no gate
pass-condition row needs amending and no new process rule is introduced.** (Flagged here so the G1
reviewer can confirm the render obligation has real teeth in MR-019, not in this prose note.)

## Review resolutions

Revisions applied by the plan's author after the G1 staff-critic review
(`reviews/landing-page-plan-review-2026-06-09.md`, PASS-WITH-FIXES). The epic stays `status: draft`
/ `gate: G1 not passed`; the orchestrator flips it after the critic confirms.

- **2026-06-09 — F1 (BLOCKER): render-smoke screenshot path was fictional.** Removed every claim
  that `scripts/render-smoke.sh` produces `site/demo.png`. *Rollout phases -> Phase 1* and
  *Decision 2* now state render-smoke only `--dump-dom`s/asserts DOM nodes and is **not** used for
  the demo asset; the capture is one of two real procedures — (a) documented manual browser capture
  (default), or (b) a direct `chrome --headless=new --screenshot=…` command reusing the binary at
  `scripts/render-smoke.sh:32-41`. Wired into MR-019's ACs.
- **2026-06-09 — F2 (MAJOR): G7 trigger does not name `site/index.html`.** *Process / gate
  enforcement note* no longer asserts the G7 per-page trigger covers the page; the render-smoke +
  screenshot obligation now lives in **MR-019's own G4 acceptance criteria** (*Verification -> Page
  render-smoke (MR-019)*), owed regardless of the G7 trigger wording.
- **2026-06-09 — F3 (MAJOR): README G4 "rebuilt image" is impossible here.** Promoted
  `python3 -m http.server --directory site` from a Risk bullet into **MR-019's named G4 validation
  target**, with a ticket-level statement that the absent container rebuild is compliant for a
  Pages-hosted artifact.
- **2026-06-09 — F4 (MINOR): token set + cite.** Added `--noteline:#d4a017` to the copied `:root`
  set (*Recommended approach -> UI*, *Decision 5*); replaced the imprecise `dashboard.html:20` mono
  cite with "the `ui-monospace,SFMono-Regular,Menlo,monospace` stack used throughout
  `dashboard.html`"; kept precise palette/dark/font-stack cites (`:8`, `:9`, `:11`).
- **2026-06-09 — F5 (MINOR): README URL ordering.** Re-sequenced *Phase 1* so the README
  canonical-URL edit is last and gated on the publish-verification block passing.
- **2026-06-09 — F6 (MINOR): MR-021 not `ready`.** Declared MR-021 **backlog / next cycle, not
  committed** (Phase 2, execution order, and a new "Sprint" column in the ticket breakdown); sprint
  commits **MR-019 + MR-020 only**.
- **2026-06-09 — F7 (NIT): publish sequence shape.** Pinned a single `git worktree` + `rsync
  --delete` orphan-`gh-pages` sequence with exact commands in *Decision 3* for MR-020 to inherit;
  rejected `git subtree split` and in-place throwaway checkout.
