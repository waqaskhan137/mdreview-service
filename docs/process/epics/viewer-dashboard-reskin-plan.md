---
epic: viewer-dashboard-reskin
status: draft          # draft | active | done  (stays draft until G1 passes)
created: 2026-06-25
source: requirements/viewer-dashboard-reskin.md
gate: G1 not passed    # G1 (Plan Gate): not passed | passed YYYY-MM-DD — tickets blocked until passed
review:                # reviews/viewer-dashboard-reskin-plan-review-YYYY-MM-DD.md once reviewed
related_sprints: []    # [sprint-28]
related_tickets: []    # empty until G1 passes and tickets are created
---

# Viewer & Dashboard Re-skin Plan

Re-skin `viewer.html` and `dashboard.html` **in place** to match the new mockup
(`.scratch/mockup-viewer-dashboard.html`), the same way the landing page was swapped (commit
`0e83ec8`) — except the landing page is a static page and these two are **live app screens** wired
to the API. The look and the supported information architecture change; the wiring (markdown +
KaTeX + mermaid render, comments CRUD, turn baton, live-reload, the staleness timer) does **not**.
This matters now because the landing page already moved to the new visual language and the two app
screens are the visible inconsistency left behind.

**Source requirement:** [`requirements/viewer-dashboard-reskin.md`](../requirements/viewer-dashboard-reskin.md) — the original brief, kept verbatim.

## Assumptions & open questions

Surfaced first, per process. I proceed on the stated assumption for each; none is a
BLOCKER-FOR-HUMAN (the one genuine product fork, IA replacement, has a safe default the user's
"Re-skin + supported IA" decision already points at). Tag: **load-bearing** changes the design,
**minor** does not.

1. **(load-bearing) The dashboard fully replaces the chip filter model with the sidebar inbox, and
   carries forward every durable affordance the chips/toolbar do today.** The mockup has no
   `All / Has notes / Done` chip row and no `Group by project` toggle; it has a left sidebar with an
   **Inbox** (All reviews / Needs you / Agent working / Resolved) + a **Projects** list. The user
   chose "Re-skin + supported IA", so I match the mockup: the inbox *replaces* the chips, and the
   sidebar Projects list *replaces* the grouped/flat toggle (clicking a project scopes the grid to
   it; "All reviews" is the flat default). **Durable behaviors that must survive the swap or the
   re-skin regresses live functionality:** search (mockup keeps a search box, top-right), delete-on-
   card-hover (the trash button), the empty state, and the live `load()` refresh. The grouped
   *collapsible* Project › Session tree is the one current affordance with no mockup equivalent; the
   sidebar Projects list is its functional replacement (filter-to-project), and Session grouping is
   recorded as a **non-goal** for this epic (no API data is lost; provenance still renders on the
   card). See decision **D1**.
2. **(load-bearing) Dark mode is preserved, not dropped.** The mockup is light-only (zero
   `prefers-color-scheme` — verified by grep). Both current files ship a dark theme via
   `@media (prefers-color-scheme: dark)`. Dropping it is a visible regression for every dark-OS
   reviewer. I keep both files theme-adaptive: implement the mockup's light palette as the light
   theme and derive a dark palette as today's files already do (the existing `--bg/--text/--accent/
   --rule` token swap). See decision **D4**. This is the asymmetric-fix footgun: a palette tuned only
   for the light pane must be verified on **both** panes (verification fixtures below capture each).
3. **(minor) The mockup's "agent watcher · connected" sidebar indicator is dropped, not stubbed.**
   The brief puts it out of scope (no backend backing). A stubbed always-"connected" dot is a lie the
   first time the watcher is not running. I omit the element entirely. See non-goals.
4. **(minor) The viewer keeps its serif body type for the rendered article.** The mockup's article
   body reads as a serif column (matching today's `Charter, Georgia` body); the chrome (top bar,
   breadcrumb, baton, comments, bottom bar) is sans. I keep the existing font split: serif `#article`,
   sans chrome. No new web font is vendored (stdlib/no-pip footgun — a font would need a `static/`
   COPY and a `font/woff2` GET-header check).
5. **(minor) The viewer's right-hand COMMENTS panel is the existing `#gutter`/Resolved machinery
   re-styled into a fixed right rail, not a new component.** The mockup's comments column is exactly
   what `layoutComments()` already produces in "wide" mode (a right gutter of thread cards), plus the
   Resolved panel. I re-skin those, I do not rebuild the comment store/anchoring. See decision **D3**.
6. **(minor) No new served file is introduced.** The re-skin is entirely inside the two existing
   HTML files (inline `<style>`/`<script>`), so the Dockerfile `COPY` (`Dockerfile:8`) is unchanged
   and footgun #9 (new served file needs a COPY) does **not** apply. If, during implementation, an
   asset is extracted to `static/`, the introducing `ui` ticket must carry the `Dockerfile` COPY edit
   — called out in Key constraints as a tripwire, even though the plan does not introduce one.

## Product goal

A reviewer opening the dashboard or a review sees the new mockup's look and information
architecture — sidebar inbox driven by the turn baton, restyled cards with baton status badges, a
restyled viewer with breadcrumb chrome, the "Your turn" baton banner, numbered markdown lines, the
right-hand threaded COMMENTS panel, and the bottom open/resolved/history bar — while **every existing
behavior still works**: comments author/reply/resolve/reopen/delete, the turn baton (Send / reclaim /
working timeline / staleness), live-reload of source and comments, KaTeX/mermaid/highlight render,
asset image rewriting, history, and lightbox. "Done" = both screens render to the new design from the
rebuilt container (proven by DOM-asserting render-smoke against the new selectors) with no functional
regression.

## Core design principle

**Re-skin the DOM, never the wiring.** Every behavioral JS path (`numberBlocks`, `renderAll`,
`layoutComments`, `highlightComment`, `renderBanner`, `poll`, `load`, the comment CRUD calls, the
`/handoff` baton calls, `STALE_S`) keeps its contract; the change is the markup it targets and the
CSS that styles it. When a JS function reads or writes a DOM id/class, that id/class either survives
the re-skin or every reference to it is updated **in the same ticket**. A re-skin that returns a 200
but breaks `layoutComments` because `#gutter` was renamed is the failure mode this principle exists to
prevent — which is why each `ui` ticket's gate is a DOM-asserting render-smoke, not a status code.

## Design decisions (the real forks)

### D1 — Dashboard IA: replace the chip model with the sidebar inbox (carry durable behaviors forward)

**Decision:** Replace. The left sidebar becomes the primary navigation: an **Inbox** section (All
reviews / Needs you / Agent working / Resolved) and a **Projects** list. The chip row and the
grouped/flat toggle are removed. Search, card-hover delete, the empty state, and live refresh are
carried forward into the new layout.

**Why:** the user explicitly chose "Re-skin + supported IA"; the inbox is the mockup's IA and is
**fully backable by existing data** — every field the filters need is already on each
`GET /api/reviews` row (verified: `summary()` at `app.py:147` returns `turn`, `status`
[`awaiting`/`feedback`/`resolved`], `notes_total`, `notes_addressed`, `revision`, `project`,
`session`, `source_path`; and because `summary()` does `dict(meta(rid))` first, `agent_status` and
`turn_updated` from `meta.json` ride along on each row too). No new endpoint, no cross-review
aggregation beyond what `/api/reviews` already does.

**Inbox filter semantics** (client-side over the existing `/api/reviews` rows — same place the chip
filter runs today, `applyFilter()` at `dashboard.html:224`):

| Inbox item | Predicate over a review row | Backed by |
|---|---|---|
| All reviews | (no filter) | — |
| Needs you | `turn === "reviewer" && status !== "resolved"` | `turn`, `status` |
| Agent working | `turn === "agent"` (parked or leased) | `turn` |
| Resolved | `status === "resolved"` | `status` |

This mirrors the card status badge (D2) so the sidebar count and the badge agree. "Agent working" is
turn-based (`turn === "agent"`) so a parked handoff still shows; the per-card badge (D2) refines the
*display* into "Agent working" vs "Waiting for agent" using `agent_status`, but the **inbox bucket** is
the coarser turn test so its count is stable and cheap.

**Behaviors carried forward (regression guard):**

| Today (dashboard.html) | After re-skin |
|---|---|
| Search box (`#search`, line 81) filtering title/project/path | kept, restyled to the mockup's top-right search |
| Card-hover trash delete (`.del`, `confirm()`, `DELETE /api/reviews/{id}`, line 246) | kept on the restyled card |
| Empty state (`No reviews yet … POST /api/reviews`) | kept, restyled |
| `load()` fetch of `/api/reviews` + `render()` | unchanged |
| Status pill (awaiting/feedback/resolved) | replaced by baton status badge (D2) |
| Chips All/Has notes/Done | **removed** — replaced by Inbox |
| Group-by-project collapsible tree (`renderGrouped`, line 186) | **removed** — replaced by sidebar Projects filter (D1); Session grouping is a non-goal |

**What is lost and acknowledged:** the collapsible Project › Session *tree* with per-session
subheadings. No data is lost (project + session + path still render on each card); the
filter-to-project capability is preserved via the sidebar. Recorded as a non-goal.

### D2 — Card status badge: derive the four baton labels from `turn` + `agent_status`

The mockup's cards show one of four badges: **Your turn**, **Agent working**, **Waiting for agent**,
**Resolved**. These are derivable per row with no new data:

| Badge | Predicate (`r` = review row) |
|---|---|
| Resolved | `r.status === "resolved"` |
| Agent working | `r.turn === "agent" && r.agent_status && r.agent_status.state === "working" && (now − agent_status.at) <= STALE_S` |
| Waiting for agent | `r.turn === "agent"` and not the above (parked, or stale lease) |
| Your turn | `r.turn === "reviewer"` and not resolved |

`STALE_S` here is the **same 180s** the viewer uses (footgun: it mirrors `app.py:57`
`LEASE_TTL_S=180`). The dashboard does not currently know about `STALE_S`; introducing the constant on
the dashboard widens the mirror obligation to a **second** file. See Risk R1 — the mitigation is to
add the same `STALE_S` source-of-truth comment to `dashboard.html` pointing at `app.py:57`, identical
to the viewer's.

### D3 — Viewer COMMENTS panel reuses the existing gutter, re-styled as a fixed right rail

The mockup's right COMMENTS column is what `layoutComments()` already builds in "wide" mode: a column
of thread cards (`.gcard`) anchored to blocks, plus the Resolved panel and the bottom dock. The
re-skin **re-styles** `#gutter` / `.gcard` / `#dock` / `#resolved` and **keeps**:
- `highlightComment()` (text-anchor + `mark.cmt` highlight by `quoted_text`/`block_num`) — unchanged.
- `layoutComments()`'s **fit-based** wide/narrow decision (`window.innerWidth >= rect.right + 320`,
  line 693). This is the post-sprint-01 fix: it is a *fit* test, not a pixel breakpoint, and the
  re-skin **must keep it a fit test** (footgun #6: behavior, not a hard-coded `<=NNNpx`). The new
  right-rail width and the article column width feed that geometry, so if the rail width changes the
  number `320` and the doc `max-width` must be re-derived together, not guessed.
- `renderAll()`'s card construction, reply/resolve/reopen/delete wiring, focus-pair, counts.
- The narrow-screen docked fallback (`#gutter.docked`) — the mockup is a wide layout, but the viewer
  must still degrade on a phone, so the docked fallback stays.

The mockup's per-card **Resolve** action (visible in the screenshot) maps to the existing
`POST /comments/{cid}/resolve` — but note: today the viewer does **not** expose a reviewer-side
Resolve button (agents resolve; the reviewer reopens). Adding a reviewer Resolve button is a
**behavior change, not a re-skin** (it lets a human resolve their own thread). Recorded as a non-goal
for this epic: the comment card keeps today's actions (Reply, and Delete only on an un-engaged
reviewer thread per `deletable` at line 645). The bottom bar's "Resolved N" / "History vN" buttons
already exist (`#resbtn`, `#histbtn`) and are re-styled in place. See non-goals.

### D4 — Dark mode preserved on both files

Implement the mockup's light palette as the `:root` light theme, and keep the
`@media (prefers-color-scheme: dark)` block deriving a dark palette via the existing token swap. The
mockup's accents (violet baton, blue Send button) become tokens so the dark theme can re-map them.
**Asymmetric-fix discipline (footgun):** the baton banner and the comment cards are the most palette-
sensitive surfaces; verification captures **both** panes (light via `preferredColorScheme=1`, dark via
`preferredColorScheme=0`, never `--force-dark-mode`) for each screen.

### D5 — Numbered markdown lines interact with mermaid/KaTeX exactly as today

The mockup shows a number per block in the left margin — that is `numberBlocks()` (line 513), already
shipped. It wraps each top-level `#article` child in a `.blk` with a `.num`. Mermaid and KaTeX are
already handled: `renderMermaid()` runs **before** `numberBlocks()`? — verified order in `load()`
(line 508): `numberBlocks()` then `renderMermaid()`. The re-skin must **not** reorder these (mermaid
replaces a `code.language-mermaid` with a `.mermaid` div; numbering wraps whatever children exist).
The re-skin only restyles `.blk` / `.num` (the mockup's number is lighter-weight, left-margin); the
`.blk.has-comment` margin-bar + dot stays. The left-margin geometry uses the existing
`@media (max-width:820px)` narrowing of `.num` left offset (line 67) — that is a *number position*
breakpoint, not a layout-fit decision, so it is acceptable as a pixel media query (it is cosmetic
nudging of a margin number, not a "does the gutter fit" test); keep or re-tune it but do not convert
the comment-rail fit test (D3) into a pixel query.

## Recommended approach

### Service (`app.py`)

**No service change.** Every datum the new IA needs is already served:
- `GET /api/reviews` (`app.py:503`) returns rows with `turn`, `agent_status`, `status`,
  `notes_total/addressed`, `revision`, provenance — verified in `summary()` (`app.py:147`).
- `GET /status` (`app.py:583`) returns `turn`/`agent_status`/`turn_updated` for the viewer banner.
- `dashboard.html` is served at `/` via `_read` (`app.py:500`); `viewer.html` at `/review/{id}` via
  `_read` (`app.py:812`). Both are plain `_read` of a root-level file — the re-skin edits the file
  content only; the route is untouched.

If review during implementation finds a filter the mockup implies but the data cannot back, that is a
**stop-and-blocked** event (process Blocking rule), not a silent backend addition — but the table in
D1/D2 shows every needed field already exists, so none is expected.

### UI (`viewer.html` / `dashboard.html`)

**Dashboard (`dashboard.html`):**
- New layout shell: left sidebar (brand, Inbox section, Projects section) + main column (heading
  "All reviews" / active filter name, sub-count, top-right search, card grid). The sidebar
  "agent watcher · connected" element is **omitted** (assumption 3).
- Sidebar Inbox items are buttons with live counts; clicking sets the active filter (replaces
  `statusFilter`). Projects items are derived from the distinct `project` values already in
  `allReviews` (the data `render()` already groups by). Active item highlighted as in the mockup.
- Cards restyled to the mockup (project/session/path breadcrumb line, title, baton status badge,
  open/resolved count line, version `vN`, relative time). Keep `.del` hover-trash and the whole-card
  `<a href="/review/{id}">` link.
- Rewire `applyFilter()` to the inbox predicates (D1 table) + search; remove chip and group code.
- Preserve `rel()` relative-time and the `toLocaleDateString()` fallback (Europe/London / locale
  date handling, line 109) unchanged.

**Viewer (`viewer.html`):**
- New chrome: top bar with `← Reviews` home link + `source_path` filename (left) and `vN · <turn
  state>` (right); a breadcrumb line `project / session / source_path` above the title; title +
  `N words · ~M min read · vN` meta. Wire the breadcrumb from `META.project/session/source_path`
  (already fetched in `boot()`), defaulting missing keys (back-compat footgun: legacy reviews lack
  provenance — render only the segments present).
- Re-skin the baton banner (`#turnbanner`, the violet "Your turn" treatment + "Send to agent" button)
  **without touching `renderBanner()`'s class logic** (`loading`/`warn`/`steps`/`show`, the
  `#turnsteps` timeline, `#turntimer`). The CSS changes; the class names and ids the JS toggles do
  **not**. `STALE_S` (line 249) stays `180` and keeps its mirror comment.
- Re-skin the COMMENTS rail (D3): `#gutter`/`.gcard` as the mockup's right column with a "COMMENTS · N
  open" header; Resolved panel and bottom dock (`#dock`: open count, Send, Comments, Resolved N,
  History) restyled to the bottom-right pill bar.
- Re-skin `.blk`/`.num` numbered lines (D5) and `#article` typography to the mockup; keep serif body
  (assumption 4). Keep lightbox, footnotes `.sr-only` clip, image mat (the theme-awareness `#article
  img` light mat at line 43 — do **not** widen it past `img`, the documented non-goal).

## Rollout phases

Each phase is independently shippable (the two screens are independent files) and independently
render-smoke-able.

### Phase 1 — Dashboard re-skin
Re-skin `dashboard.html`: sidebar shell, inbox filters (D1), projects list, restyled cards with baton
badges (D2), search/delete/empty carried forward. Independently shippable: the viewer is untouched and
the dashboard's `load()` contract is unchanged.

### Phase 2 — Viewer re-skin
Re-skin `viewer.html`: chrome + breadcrumb, baton banner, numbered lines, COMMENTS rail, bottom bar.
Split into two tickets if the diff is large (chrome+article vs comments-rail+dock), because the comment
rail is where the load-bearing JS (`layoutComments`, `highlightComment`, `renderAll`) is most at risk
and deserves an isolated render-smoke. Independently shippable: dashboard untouched.

### Phase 3 — Docs sweep
Update `README.md` / `CLAUDE.md` wherever they describe the dashboard's chip filters or the viewer's
affordances that changed (the dashboard "filters" mention; any viewer UI description). Same-sprint
docs-sweep ticket (process Definition of Done allows deferral to a same-sprint sweep named in the
deferring ticket's Work log; it is **not** carry-over-eligible per G7).

## Non-goals

- **No backend change.** No new endpoint, field, or cross-review aggregation. If the mockup implies
  one, stop-and-blocked, do not add it.
- **The "agent watcher · connected" indicator is dropped** (no backing; assumption 3). Not stubbed.
- **No reviewer-side "Resolve" button** in the comment card (D3) — that is a behavior change (a human
  resolving their own thread), not a re-skin. The card keeps Reply + the existing conditional Delete.
- **No Session-level grouping tree** on the dashboard (D1). Project filtering via the sidebar replaces
  grouped mode; session still renders on the card. No data lost.
- **No new web font / no new `static/` asset.** Stdlib/no-pip; a font would need a Dockerfile COPY and
  a `font/woff2` GET-header check (out of scope).
- **No change to `numberBlocks` / comment anchoring / baton JS contracts** — re-skin restyles their
  DOM, it does not change their logic.
- **No live agent-connection telemetry** of any kind (the dropped watcher indicator's backing).

## Key constraints

Hard rules the implementation must not violate (the project footguns, made specific):

1. **Buildless, stdlib-only, zero pip.** Edits are inline `<style>`/`<script>` in the two existing
   HTML files. No bundler, no React, no build step. The React mockup is a **visual spec only** and is
   never shipped.
2. **`STALE_S` stays mirrored.** `viewer.html` `STALE_S=180` (line 249) **must** equal `app.py:57`
   `LEASE_TTL_S=180`; keep the source-of-truth comment. If D2's dashboard badge introduces `STALE_S`
   to `dashboard.html`, that file now also mirrors `app.py:57` — add the same comment there (Risk R1).
3. **Back-compat of `meta.json`.** Legacy reviews lack `project`/`session`/`source_path`/`turn`/
   `agent_status`. Every new render path defaults missing keys (render only present breadcrumb
   segments; `turn` defaults `"reviewer"` as `summary()` already does at `app.py:165`). Never assume
   a key is present.
4. **Re-skin the DOM, not the wiring (core principle).** Any renamed id/class that JS reads
   (`#gutter`, `.gcard`, `#turnbanner`, `#turntext`, `#turnsteps`, `#turntimer`, `#sendbtn`,
   `#reclaimbtn`, `#dock`, `#count`, `#resbtn`, `#histbtn`, `#article`, `.blk`, `.num`, `mark.cmt`,
   `#addbtn`, `#pop`, `#filename`, `#doctitle`, `#docmeta`, `#search`, `#list`, `.card`, `.del`) is
   updated at **every** JS reference in the **same ticket**. Prefer keeping the ids and changing only
   CSS where possible.
5. **`layoutComments()` stays a fit test, not a pixel breakpoint** (footgun #6). The comment-rail
   wide/narrow decision is `innerWidth >= rect.right + 320`; re-derive the `320`/doc-width pair
   together if the rail width changes. Do not convert it to `<=NNNpx`.
6. **Dark mode preserved on both files** (D4); verify **both** panes via `preferredColorScheme`
   emulation, **never** `--force-dark-mode` (footgun #6: bare headless Chrome resolves dark by
   default, so a no-flag "light" shot is wrong).
7. **No new served file** (assumption 6). If implementation extracts an asset to `static/`, the
   introducing `ui` ticket **must** carry the `Dockerfile:8` COPY edit (footgun #9) — tripwire only;
   the plan introduces none.
8. **`render-smoke.sh` selectors are flat** (footgun #11): only `tag`, `.class`, `tag.class`, `#id`;
   no descendant combinators/spaces. Assert a node *inside* a container with two separate selectors,
   not `#parent child`.
9. **Header checks use GET, not `curl -sI`** (footgun #10): there is no `do_HEAD`, so any
   `Content-Type` check is `curl -sD - -o /dev/null <url>`. (Not expected here — no new asset — but
   the smoke recipe uses the GET form.)
10. **Europe/London / locale date handling preserved** (dashboard `rel()` + `toLocaleDateString`,
    line 109; viewer history `toLocaleString`, line 794).

## Preferred execution order

1. **Phase 1 — Dashboard re-skin** (no dependency on the viewer; smallest blast radius; ships the
   visible sidebar IA first).
2. **Phase 2 — Viewer re-skin** (chrome+article first, then comments-rail+dock if split — the rail
   carries the highest-risk JS and gets its own render-smoke).
3. **Phase 3 — Docs sweep** (after both screens land, so it documents the shipped reality; must be
   `done` before sprint close, never carried over).

Service-before-UI ordering is moot here (no `svc` ticket). Within the sprint, dashboard and viewer are
independent and could be done in either order; dashboard first is preferred as the lower-risk warm-up.

## Ticket breakdown

Create in `tickets/` only after G1. IDs are placeholders — the orchestrator allocates real IDs
(allocate **MR-087+**; the project-wide max is MR-086 on the refactor branch, so these must not
collide). Target sprint **sprint-28** (no sprint below sprint-28).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-### | Dashboard re-skin: sidebar inbox (D1) + projects filter + restyled cards with baton badges (D2), search/delete/empty carried forward | ui | 1 |
| MR-### | Viewer re-skin: chrome (top bar + breadcrumb + title meta) + baton banner restyle + numbered-line + article typography | ui | 2 |
| MR-### | Viewer re-skin: COMMENTS right rail + Resolved panel + bottom open/resolved/history dock (re-style `#gutter`/`.gcard`/`#dock`, keep `layoutComments`/`highlightComment`/`renderAll`) | ui | 2 |
| MR-### | Docs sweep: update README.md / CLAUDE.md where they describe the dashboard chip filters / viewer affordances that changed | docs | 3 |

If the viewer diff is small enough to validate in one render-smoke, the two Phase-2 `ui` tickets may
collapse into one at grooming; keep them split if the comment-rail JS rewiring is non-trivial (it is
the highest-risk surface).

## Risks & mitigations

| # | Risk | Mitigation |
|---|------|------------|
| R1 | D2's dashboard badge needs `STALE_S=180`, creating a **second** file that must mirror `app.py:57`. Drift would mislabel "Agent working" vs "Waiting". | Add the same source-of-truth comment to `dashboard.html` pointing at `app.py:57`; both viewer and dashboard `STALE_S` move with `LEASE_TTL_S`. Call it out in the ticket AC. |
| R2 | Renaming an id/class the load-bearing JS reads silently breaks comments/baton/live-reload while still returning 200. | Core principle + render-smoke asserting the *functional* DOM nodes (comment cards, baton banner, numbered blocks) from the rebuilt container, not a status code. Prefer keeping ids, changing CSS only. |
| R3 | Re-skinning the comment rail breaks `layoutComments()` fit geometry (cards mispositioned or hidden). | Keep the fit test (`innerWidth >= rect.right + 320`); re-derive `320`/doc-width together; render-smoke asserts `.gcard` present and a manual/captured wide+narrow check confirms positioning. |
| R4 | Dark pane regresses (palette tuned for the light mockup) — the asymmetric-fix footgun. | Both-pane capture per screen via `preferredColorScheme` emulation (never `--force-dark-mode`); baton + comment cards specifically checked on both panes. |
| R5 | Legacy reviews (no provenance/turn keys) crash the new breadcrumb/badge render. | Default every missing key; render only present breadcrumb segments; verification includes a fixture review with **no** project/session/turn. |
| R6 | The mockup tempts a reviewer-side Resolve button or session tree (scope creep into behavior change). | Both explicitly non-goals; tickets re-skin existing affordances only. |
| R7 | Dropping the chip/group code orphans an event handler or leaves dead CSS, breaking search/delete. | The dashboard ticket AC requires search + hover-delete + empty-state to pass render-smoke and a manual click-through; remove chip/group code and its handlers together. |

## Verification

Run from the **rebuilt container** (never `docker compose up` on the live box; use a throwaway
container + `MDREVIEW_DATA` per the repo's run rules). A 200 is not a render; the gate is DOM
assertions + both-pane captures.

**0. Compile + build (every ticket):**
```bash
python3 -m py_compile app.py        # unchanged, but gate requires it green
docker build -t mdreview:reskin .   # serves the edited HTML; COPY (Dockerfile:8) unchanged
```

**1. Seed fixtures** (against the throwaway container, `$BASE`): create at least
- one review with full provenance + `turn=reviewer` (Your turn / Needs you),
- one flipped to `turn=agent` with a fresh `working` lease (Agent working),
- one flipped to `turn=agent` with no lease (Waiting for agent / parked),
- one fully resolved (Resolved),
- one **legacy-shaped** review with **no** project/session/turn keys (back-compat R5),
- a few comments on the viewer fixture (open + resolved) so the COMMENTS rail and Resolved panel
  render.

**2. Dashboard render-smoke (Phase 1)** — assert the new selectors (these **replace** the old
`.chip`/`.grid` assertions; selectors change with the re-skin, footgun):
```bash
scripts/render-smoke.sh "$BASE/" \
  '#sidebar' '.inbox-item' '.project-item' '#search' \
  '.card' '.badge-turn' '.del' '.grid'
# every selector >=1 node => exit 0. (final class names set at implementation; AC pins them.)
```
Plus a both-pane screenshot of `/`:
```bash
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CH" --headless=new --disable-gpu --no-sandbox --hide-scrollbars --virtual-time-budget=3000 \
  --blink-settings=preferredColorScheme=1 --screenshot=dash-light.png --window-size=1400,1000 "$BASE/"
"$CH" --headless=new --disable-gpu --no-sandbox --hide-scrollbars --virtual-time-budget=3000 \
  --blink-settings=preferredColorScheme=0 --screenshot=dash-dark.png  --window-size=1400,1000 "$BASE/"
```
Manual click-through: each inbox filter narrows the grid; clicking a project scopes it; search filters;
hover-trash deletes (confirm dialog); empty state shows when no reviews.

**3. Viewer render-smoke (Phase 2)** — assert chrome, baton, numbered lines, comments, bottom bar
(two selectors when asserting "inside", never a descendant combinator):
```bash
scripts/render-smoke.sh "$BASE/review/<id>" \
  '.topbar' '.breadcrumb' '#doctitle' \
  '#turnbanner' '#sendbtn' '#reclaimbtn' \
  '.blk' '.num' \
  '#gutter' '.gcard' '#dock' '#resbtn' '#histbtn'
```
- `#turnbanner` + `#sendbtn` prove the baton banner rendered (and `renderBanner` ran); seed the
  viewer fixture as `turn=reviewer` so the banner shows "Your turn".
- `.blk` + `.num` prove `numberBlocks()` ran on the re-skinned article.
- `.gcard` proves the comment rail rendered threads (seed open comments first).
Both-pane screenshots of `/review/<id>` via `preferredColorScheme=1` / `=0` (never
`--force-dark-mode`), specifically inspecting the baton banner + comment cards on each pane (R4).

**4. Functional regression (no behavior lost)** — beyond DOM presence:
- **Comments:** select text → "+ comment" → save (`POST /comments`); reply; the agent-side
  `resolve_comment`/`reopen` round-trip moves a card to Resolved and back. Live-reload: push
  `PUT /source` to the fixture and confirm the viewer re-renders ("Draft updated by AI" toast) without
  a manual refresh.
- **Baton:** click "Send to agent" → `turn` flips to `agent`, banner shows working state; reclaim →
  `turn` back to `reviewer`. Confirm `STALE_S=180` is still present and still equals `app.py:57`
  (grep both; R1).
- **Staleness timer:** with a `working` lease, the `#turntimer`/`#turnsteps` timeline ticks; let the
  lease age past `STALE_S` → banner flips to "may have stopped" (the existing `startTicker`/
  `renderBanner` path, unchanged).
- **History + lightbox:** `History` opens the modal and lists rounds; clicking a figure zooms.
- **Legacy fixture:** the no-provenance review renders the viewer (breadcrumb shows only present
  segments) and a dashboard card (badge defaults to "Your turn" via `turn="reviewer"`) without error
  (R5).

**5. Sprint close (G7):** because product pages (`viewer.html`, `dashboard.html`) were touched,
`scripts/render-smoke.sh` against **each** page asserting its DOM nodes + a screenshot under
`reviews/sprint-28-render-evidence-*`, plus the container rebuild + `curl /healthz` + `/api/reviews`
smoke, per the G7 pass-condition row.
