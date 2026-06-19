---
epic: dashboard-redesign
status: done           # draft | active | done  (stays draft until G1 passes)
created: 2026-06-19
source: requirements/dashboard-redesign.md
gate: passed 2026-06-19  # G1 (Plan Gate): passed (round 2, staff-critic PASS) — tickets unblocked
review: reviews/dashboard-redesign-plan-review-2026-06-19.md, reviews/dashboard-redesign-plan-review-2026-06-19-r2.md
related_sprints: [sprint-09]
related_tickets: [MR-031]
---

# Dashboard Redesign Plan

The reviews dashboard at `GET /` (served from `dashboard.html`) renders every review as a tall
card in a narrow centered column that fits only ~2 columns on a wide screen, wraps file paths to
three lines, and stacks a full-row Open and Delete button under every card. The result is endless
scrolling past wasted space. This epic rewrites `dashboard.html` (and only that file) into a
dense, full-width, searchable grid of collapsed click-to-expand cards with collapsible project
groups — without touching the service, the API, the MCP wrapper, or `viewer.html`. The exact same
`GET /api/reviews` payload feeds it.

**Source requirement:** [`requirements/dashboard-redesign.md`](../requirements/dashboard-redesign.md)
— the original brief, kept verbatim.

## Current-state map (what exists today, verified)

Read in full from `dashboard.html` (139 lines) and the serving path in `app.py`.

**How it is served.** `app.py` route `route()` handles `path in ("/", "/api")` for GET
(`app.py:293`); for the HTML branch it returns `_read(.../dashboard.html)` as `text/html`
(`app.py:303-304`). The page is served **inline from the repo root file** — it is *not* under
`/static/`. `dashboard.html` is already named in the `Dockerfile` COPY (`Dockerfile:8`,
`COPY app.py viewer.html dashboard.html ./`), so **no Dockerfile or route change is needed**
(footgun 9 satisfied by inspection).

**Data it consumes.** It fetches `GET /api/reviews` (`dashboard.html:96`), which returns
`{"reviews": list_reviews()}` (`app.py:306-307`). `list_reviews()` (`app.py:138-141`) maps
`summary()` (`app.py:120-135`) over every review and sorts by `created` descending. Each review
object carries: `id`, `title`, `created`, `source_updated`, `feedback_updated`, `project`,
`source_path`, `session` (all from `meta.json` via `create_review`, `app.py:177-182`), plus
`notes_total`, `notes_addressed`, `revision`, and a derived `status` of
`awaiting | feedback | resolved` (`app.py:126-134`). **The redesign uses this same payload and
adds no field.**

**Grouping.** Today it groups **Project › Session › files**: `groupBy(reviews,"project")`
(`dashboard.html:108`) then `groupBy(items,"session")` (`dashboard.html:117`). Ungrouped projects
(`project===""`) sort last; undated sessions (`session===""`) render with no sub-header first.
The brief's "blog 2" example is a **project** name; the brief asks to make **project** groups
collapsible. The redesign keeps project as the collapsible group and keeps the session sub-group
*within* each project (see fork 4).

**Status pills.** `.pill.awaiting | .pill.feedback | .pill.resolved` (`dashboard.html:30-33`),
driven by `r.status`. The `.pill.feedback` color has a dark-pane override (`dashboard.html:32`).

**Open.** `<a class="btn open" href="/review/${id}">Open</a>` (`dashboard.html:84`) — a plain
link to the viewer route (`app.py:453`, `re.fullmatch(r"/review/" + RID, ...)`). Preserve as a
link.

**Delete.** `<button class="btn del" data-id data-title>` (`dashboard.html:85`) + a delegated
document click handler (`dashboard.html:130-135`) that `confirm()`s, calls
`DELETE /api/reviews/{id}`, then `load()`s. This is the one action that **mutates server state**
— the close review's delete test must run against a throwaway review (see Risks + Verification).

**Version badge.** `r.revision>0` renders `<span class="badge rev">v${revision}</span>`
(`dashboard.html:73`). Preserve.

**Notes display.** `noteLabel(r)` (`dashboard.html:66-70`) renders "N notes · M done" / "no notes"
from `notes_total`/`notes_addressed` into a `.badge`. The dashboard shows note *counts*, not note
*bodies* — there is no per-note quote/body on this page today (note bodies live in `viewer.html`).
"Preserve notes" therefore means **preserve the notes-count display**; "full notes" in the brief's
expanded view means the same count badge (and the note label) shown in the expanded card. This is
called out as an assumption (A3) — there is no richer note data in the `/api/reviews` payload to
show, so the plan does not invent one.

**Theme — the load-bearing finding.** The dashboard is **NOT dark-only. It is pane-adaptive**,
exactly like `viewer.html`: a light `:root` default plus a `@media (prefers-color-scheme: dark)`
override (`dashboard.html:8-9`), with token names matching `viewer.html:10-11`
(`--bg/--text/--muted/--accent/--rule/--card`). It therefore renders a **light** pane in a
light-OS-theme browser and a **dark** pane in a dark one. Consequently:
- "Keep the dark theme" = keep the existing pane-adaptive tokens with a polished dark pane; do
  **not** collapse to dark-only (that would regress light-theme users).
- **Render evidence needs BOTH panes** (a light-pane and a dark-pane screenshot), and any new
  token color introduced must read on **both** panes — verified with a `getComputedStyle` /
  screenshot check on the **dark** pane specifically (the harder pane), per the close-and-ship
  reference.

## Product goal

A reviews dashboard that fits 3–5 review cards per row on a desktop screen, where each review is a
~3-line collapsed card (title + one metadata row) that expands in place to reveal its full path,
note state, and actions; with a sticky search bar that live-filters by title/project/path and a
set of collapsible project groups whose collapsed/expanded state is remembered for the session.
All current behavior — Open, Delete, the version badge, the notes-count display, the
Project › Session grouping, and pane-adaptive theming — survives the rewrite.

## Core design principle

**Density without losing anything: collapse by default, reveal on demand, never re-fetch, never
touch the server.** Every interaction (search, group collapse, card expand, the status chip)
operates on the **already-loaded DOM** built from one `GET /api/reviews`; the only network call
that mutates anything remains the existing `DELETE`. This keeps the epic a pure `ui` change with a
single data dependency it already has, and makes the whole feature verifiable by rendering one
page and asserting/clicking its nodes.

## Recommended approach

### Service (`app.py`)

**No change.** This epic touches `app.py` zero lines. The payload (`list_reviews()`/`summary()`),
the `/` route, the `/review/{id}` link target, and the `DELETE /api/reviews/{id}` endpoint all
already exist and are reused as-is. The plan asserts this so the implementer does not "improve"
the API mid-flight; any API need that surfaces is an out-of-epic follow-up (see Non-goals).

### UI (`dashboard.html`)

A single cohesive rewrite of the `<style>` and `<script>` in `dashboard.html`, structured as five
mechanisms layered on the existing fetch+group skeleton (so `load()`, `groupBy`, `esc`, `rel`,
`noteLabel` are reused, not reinvented):

1. **Full-width dense grid.** Replace `.wrap{max-width:920px}` (`dashboard.html:12`) with a
   full-width container (small side padding, e.g. `padding: 24px 24px 96px`, no `max-width` on the
   container). Each session's `.grid` becomes
   `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` (the brief's value, verbatim;
   today it is `minmax(260px,1fr)`, `dashboard.html:22`). **Density numbers (measured, see fork
   2):** card padding `8px 10px` (halved from today's `13px 14px`), `gap: 5px` inside the card,
   grid `gap: 10px`, body `font-size: 14px`, `line-height: 1.45`, card `border-radius: 8px`.

2. **Collapsed/expanded cards.** Default render is **collapsed**: title (single-line ellipsis) +
   one metadata row (status pill · notes-count badge · version badge · relative date). Clicking
   the card toggles an `.expanded` class that reveals an extra block (full `source_path` on its own
   line, the notes-count label restated in full, and the Open/Delete actions as small inline
   buttons). Actions are hidden when collapsed and shown on hover **or** when expanded. See fork 1
   for the click-vs-button-vs-selection handling.

3. **Sticky search bar.** A `<header>`-level sticky bar (`position: sticky; top: 0`) containing a
   single `<input id="search">`, the **Expand all / Collapse all** controls, and an optional
   **status chip toggle** (All / Has notes / Done). Typing live-filters the already-rendered cards
   (case-insensitive substring over title + project + source_path); cards that do not match get a
   `hidden` attribute / `.is-hidden` class; any project group **and** session sub-group left with
   zero visible cards is hidden too. No re-fetch (fork 3).

4. **Collapsible project groups.** Each project `<section>` gets a clickable `.group-header` row
   (chevron + project name + count badge). Clicking toggles `.collapsed` on the section, which
   hides its body. **Expand all / Collapse all** toggle every group. State is held in a
   **session-lifetime JS `Set`** of collapsed project names (NOT localStorage) so it survives a
   `load()` re-render within the same page session but not a reload (fork 4).

5. **Polish.** Hover lift (`transform: translateY(-1px)` + border-highlight to `--accent` on
   `.card:hover`, building on the existing `.card:hover{border-color:var(--accent)}` at
   `dashboard.html:24`), consistent small radii (8px cards / 6px buttons / 20px pills), tighter
   type scale. Pane-adaptive tokens are preserved; any new token reads on both panes (fork 5).

## Design forks — resolved (measured where render-observable)

### Fork 1 — collapse/expand mechanism: click handler that ignores buttons, links, and selections

**Decision: a delegated card click handler, NOT `<details>`.** `<details>`/`<summary>` cannot
express "the whole card is the summary but the Open link and Delete button inside it must not
toggle it," and its default marker/`open` styling fights the dense card. Instead: one delegated
listener on the card grid that, on click, ignores the event if (a) `e.target.closest('a, button')`
is truthy (so Open and Delete fire their own behavior and never toggle), or (b) a non-empty text
selection exists (`window.getSelection().toString()` — so selecting the path/title to copy does
not toggle); otherwise it toggles `.expanded` on the clicked `.card`.

**Accessibility:** the card carries `role="button"`, `tabindex="0"`, and `aria-expanded`
(toggled with the class), and a keydown handler toggles on Enter/Space. The Open link and Delete
button remain independently focusable and are excluded from the toggle by the `closest('a,button')`
guard. **The Enter/Space keydown handler MUST apply the same guard as the click handler** — the
identical `e.target.closest('a, button')` check (and the non-empty-selection check) — so that
activating a focused inner Open link or Delete button with the keyboard fires only that control and
does **not** also toggle the card. (Without this parity, pressing Enter on a focused Open link would
both navigate and toggle.) State this in the ticket AC.

**Collapsed vs expanded — concrete (measured, see fork 2):**
- **Collapsed (default):** line 1 = title (ellipsis). line 2 = metadata row (pill · notes badge ·
  version · date). Actions hidden. Path hidden. Measured height ~57–60px ≈ ~3 text lines — within
  the brief's "~5–6 lines, no more" budget (the brief's "5–6 lines" is an upper bound on the
  current too-tall cards; the natural collapsed height is below it — do **not** pad the card to
  hit 5–6 lines).
- **Expanded:** the two collapsed lines **plus** the full `source_path` on its own line and a row
  of small inline Open/Delete buttons. (Notes count is already in the metadata row; the expanded
  view restates the full notes label.)

### Fork 2 — grid + density numbers (measured)

Halved from current. Today: card `padding:13px 14px`, card `gap:7px`, grid `gap:12px`,
body `15px/1.5`, radius `10px`, grid floor `260px` (`dashboard.html:11,22,23`). Redesign:

| Property | Current | Redesign |
|---|---|---|
| card padding | 13px 14px | **8px 10px** |
| card inner gap | 7px | **5px** |
| grid gap | 12px | **10px** |
| body font-size / line-height | 15px / 1.5 | **14px / 1.45** |
| card radius | 10px | **8px** |
| grid floor | minmax(260px,1fr) | **minmax(280px,1fr)** (brief) |
| container | max-width:920px centered | **full-width, padding 24px** |

**Measured column count for `minmax(280px,1fr)` (24-card probe, side padding 48px, gap 10px):**

| Viewport width | Columns | Each ~ |
|---|---|---|
| 1280px | 4 | 308px |
| 1440px | 4 | 348px |
| 1680px | 5 | 326px |
| 1920px | **6** | 312px |
| 2560px | **8** | 314px |

So `minmax(280px,1fr)` lands **3–5 columns through ~1680px** but **overshoots to 6 at 1920px (a
common 1080p monitor) and 8 on ultrawides.** The brief prescribes `minmax(280px,1fr)` *and* "3–5
columns on desktop." These conflict on wide monitors. **Decision: honor the brief's `minmax(280px,1fr)`
verbatim, and cap the grid container at `max-width: 1600px` centered (`margin-inline:auto`)** so
the column count tops out at 5 on any monitor while still being "full-width" on the ≤1600px screens
the brief is describing. This is the smallest change that satisfies both the literal value and the
"3–5 columns" intent. **The `1600px` number is the 5-column ceiling, not a guess: 5 columns need at
least 5×280 (cards) + 4×10 (inner gaps) + 2×24 (container padding) ≈ 1488px of content box; a 6th
column needs another 280+10 ≈ 1778px. A `max-width:1600px` container therefore admits exactly 5
columns (fits 1488, short of 1778) and never a 6th — tie this math to the number in the ticket AC so
a later reader sees it as the 5-column ceiling.** The cap is recorded so the reviewer can object if "truly edge-to-edge on a
4K monitor, columns be damned" is actually wanted — see assumption A4. **A wide-viewport screenshot
must confirm the realized column count** (verification).

**Collapsed-card height (measured):** title (14px/1.25) + meta row (11px/1.45) + 5px gap + 8px×2
padding + 1px×2 border ≈ **57px**; rendered DOM `getBoundingClientRect().height` = **60px**.
Screenshot confirmed: one ellipsis title line + one metadata row, nothing more.

### Fork 3 — search/filter: client-side, over rendered DOM, hides empty groups

**Decision: live client-side filter over already-rendered cards; no re-fetch.** On each `input`
event, lowercase the query and, for every `.card`, test
`title.includes(q) || project.includes(q) || path.includes(q)` (case-insensitive substring;
title/project/path stored on the card as `data-` attributes at render time so filtering reads
data, not DOM text). Non-matching cards get a `.is-hidden` class. After filtering, each session
sub-group and each project group with zero visible cards gets `.is-hidden` too (so empty groups
disappear, per the brief). An empty query clears all `.is-hidden` filter classes (group
collapse state, fork 4, is independent and preserved). **Optional status chip:** a small segmented
toggle (All / Has notes / Done) that ANDs a status predicate with the text query
(`status==="feedback"||status==="resolved"` for "has notes"; `status==="resolved"` for "done").
The chip is in scope as the brief's "optional but nice"; if cut for time it becomes the one
splittable slice (see ticket decision).

### Fork 4 — collapsible groups + expand/collapse-all + session memory; grouping stays project-level

**Decision: collapsible at the PROJECT level (the brief's "blog 2" is a project), session
sub-groups preserved inside.** Each project `<section>` gets a `.group-header` (chevron + name +
count badge) whose click toggles `.collapsed`. The session sub-header (`.session>h3`,
`dashboard.html:20`) stays as a non-collapsible sub-label within the project. **Session memory =
a module-level `const collapsed = new Set()` of collapsed project names** (NOT localStorage —
the brief says "in memory during the session" explicitly, and although `viewer.html` uses
localStorage for notes, this brief is deliberate about *session-only*). `load()` re-renders from
this Set so collapse survives a delete-triggered `load()` within the page session but resets on
reload. **Expand all / Collapse all** clear / fill the Set and re-apply. The chevron rotates via a
`.collapsed` CSS transform; the count badge stays visible in both states.

### Fork 5 — theme: pane-adaptive, both panes verified

**Decision: keep the existing pane-adaptive `:root` + `@media (prefers-color-scheme: dark)` token
model** (the current-state finding above — the dashboard is not dark-only). New surfaces (search
bar background, chip toggle, group-header hover, card hover-lift, expanded panel) use existing
tokens (`--card/--bg/--rule/--accent/--muted`) so they adapt for free. If any **new literal color**
is introduced (e.g. a chip "active" fill), it must be given a light value and a dark override and
**verified on the dark pane** by screenshot + a `getComputedStyle` legibility check (text vs
background), per footgun and the close-and-ship reference. **The dark pane is emulated with
`--blink-settings=preferredColorScheme=0` (and the light pane with `=1`) — NOT `--force-dark-mode`,
which is Chrome's auto-invert, a different mechanism; bare headless Chrome resolves dark by default,
so both the screenshot and the `getComputedStyle` check must pass the explicit flag (see Verification
step 4d and `theme-awareness-plan-review-2026-06-18.md`).** No hand-derived/stripped asset is
involved (all CSS is hand-written inline, no vendored file is edited), so there is no separate
"verify the transform" surface here — but the dark-pane computed-style check still applies to any
new token.

## Rollout phases

This is one `dashboard.html` rewrite; the phases below are the **internal build order within the
single ticket**, each independently demonstrable, not separately shippable files (they all edit
the same file and therefore serialize — see ticket decision).

### Phase 1 — Dense full-width grid + collapsed/expanded cards (foundation)
Full-width container + `minmax(280px,1fr)` grid (capped at 1600px) + halved density + single-line
ellipsis path + collapsed-by-default cards with click-to-expand (fork 1) and hover/expanded
actions. Preserves Open, Delete, version badge, notes-count, Project›Session grouping. Demonstrable:
wide screenshot shows 3–5 columns, collapsed screenshot shows ~3-line cards, expanded screenshot
shows path + actions; Open/Delete still work.

### Phase 2 — Sticky search + collapsible groups + session memory
Sticky search bar (fork 3), Expand/Collapse-all + per-project collapse with session Set (fork 4),
empty-group hiding, optional status chip. Builds directly on Phase 1's rendered cards.

### Phase 3 — Polish + both-pane verification
Hover lift, radii, type-scale tightening, and the explicit **both-pane** (light + dark) render
evidence + dark-pane computed-style legibility check.

## Non-goals

- **Any change to `app.py`, the API, the MCP wrapper, `viewer.html`, the `Dockerfile`, or routing.**
  The payload and routes are reused unchanged.
- **No new served file** — `dashboard.html` already exists and is already in the Dockerfile COPY.
- **No new `/api/reviews` field**, no pagination, no virtualization, no server-side search/sort.
- **No cross-session (persistent) collapse state** — the brief says in-memory/session only; no
  localStorage for collapse.
- **No new note data** — the dashboard shows note *counts* (the only note data in the payload);
  it does not gain per-note bodies (those live in `viewer.html`).
- **No multi-tenant / auth change** — the dashboard already lists across all reviews; this
  redesign does not change exposure (the search bar only filters data already returned by
  `GET /api/reviews`). See Key constraints.

## Key constraints (footguns, made specific)

- **JS-rendered page — a 200 is not a render (footgun 6).** Every dashboard claim is proven by
  `scripts/render-smoke.sh` against the **rebuilt throwaway container**, asserting the new DOM
  nodes, **plus screenshots**. Because the brief is visual/dense, the binding proof is the
  screenshot set (wide / collapsed / expanded / both-pane), not the smoke alone.
- **render-smoke is a flat matcher (footgun 11).** Assert each node as a **standalone** selector
  (`.grid`, `.card`, `#search`, `.group-header`) — **never** a descendant selector with a space.
  To assert "a card inside the grid," pass `.grid` and `.card` as two separate selectors.
- **HEAD → 501 (footgun 10).** The dashboard is served **inline** by `app.py` (not a `/static/`
  asset), so there is **no MIME/header check needed** here. If any header is ever inspected, use a
  GET header-dump (`curl -sD - -o /dev/null <url>`), never `curl -sI`.
- **No new served file (footgun 9).** `dashboard.html` is already served (`app.py:303`) and
  already in `Dockerfile:8`. Confirmed by inspection — **no `Dockerfile`/route change**, and the
  ticket carries no infra change.
- **Live instance is on :8139 — never `docker compose` (compose says 8137).** All smokes use a
  **throwaway container published on :8138** built from the working tree, then removed.
- **Delete mutates server state.** The delete-functionality test (preserve-functionality
  verification) must create and target a **throwaway review in the throwaway container**, never a
  real review on the live :8139 instance.
- **id-only tenancy / no auth (footgun 5).** The dashboard already aggregates across all reviews;
  the search bar filters only data already in the response, so the redesign **does not widen
  exposure**. Called out for completeness; no new exposure introduced.
- **Pane-adaptive theme.** Render evidence covers **both** panes, emulated with
  `--blink-settings=preferredColorScheme=0` (dark) / `=1` (light) — **never `--force-dark-mode`**
  (auto-invert, wrong mechanism) and never a no-flag shot (bare headless resolves dark by default).
  New token colors verified on the **dark** pane via screenshot + `getComputedStyle`.

## Preferred execution order

1. Author plan → independent G1 review → resolve blockers → epic `active`.
2. Create the single `ui` ticket (MR-031) in sprint-09 (or, if the reviewer prefers the split,
   the 2-ticket variant below).
3. Implement Phase 1 → Phase 2 → Phase 3 inside `dashboard.html` on a ticket branch.
4. G4: `python3 -m py_compile app.py` (unchanged file still compiles the server) + rebuild
   throwaway container on :8138 + `scripts/render-smoke.sh` asserting the new nodes + the four
   screenshot classes + the preserve-functionality clicks (Open/Delete/expand) + both-pane shots.
5. G5/G7 per process; the G7 close review re-runs the render smoke (product page touched) and the
   delete test against a throwaway review.

## Ticket breakdown

**Recommendation: ONE `ui` ticket (MR-031).** Justification: the brief is a single cohesive
rewrite of one file (`dashboard.html`'s `<style>` + `<script>`). Any split (layout/density |
search/filter | collapsible groups) produces tickets that **all edit the same file and therefore
serialize** — they cannot be worked in parallel (single-flight process anyway), share no
independently shippable artifact, and a half-applied split would leave the file in an awkward
intermediate state. The internal Phase 1/2/3 order gives the build its structure without the
overhead of three tickets that must merge sequentially into the same file. The ticket is a
big-ish but bounded single slice, validated by one render-smoke + screenshot pass.

**If the reviewer prefers a split** (e.g. to de-risk the search/group JS separately from the
layout CSS), the only defensible cut is **two** serialized tickets — (a) layout/density +
collapse/expand cards, (b) search + collapsible groups + chip — sharing the file. Listed below as
the fallback; the recommendation remains one ticket. (IDs are placeholders; the orchestrator
allocates real IDs.)

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-031 | Redesign `dashboard.html`: dense full-width grid, collapsible cards, sticky search, collapsible project groups (preserve open/delete/version/notes) | ui | 1–3 |
| MR-031a *(fallback split only)* | Dashboard layout/density + collapse-expand cards | ui | 1 |
| MR-031b *(fallback split only)* | Dashboard sticky search + collapsible project groups + status chip | ui | 2 |

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| **Card click swallows the Open link / Delete button** (whole-card click eats the action). | Toggle handler guards with `e.target.closest('a, button')` and returns early; verification explicitly clicks Open (navigates to `/review/{id}`) and Delete (removes a throwaway review) and asserts the toggle did NOT fire. |
| **Keyboard activation double-fires** (Enter/Space on a focused Open link both navigates and toggles the card). | The Enter/Space keydown handler applies the **same** `closest('a, button')` + non-empty-selection guard as the click handler, so keyboard activation of an inner control does not also toggle; ticket AC requires the keydown guard parity (Fork 1). |
| **Card click swallows text selection** (selecting a path to copy expands/collapses instead). | Handler returns early if `window.getSelection().toString()` is non-empty; manual check during render evidence. |
| **Search hides a group's header too aggressively / leaves an empty group visible.** | Empty-group hiding is computed AFTER per-card filtering by counting visible cards per group; verified by a screenshot of a filtered query showing only matching groups and no empty headers. |
| **"5–6 line" target misread as a floor** (implementer pads the card to 5–6 lines). | Plan states it is an **upper bound**; measured natural collapsed height is ~3 lines / ~60px; collapsed-card screenshot is the AC. |
| **Column count overshoots "3–5" on 1080p/ultrawide** (measured: 6 at 1920px, 8 at 2560px). | Grid container capped at `max-width:1600px` (the 5-column ceiling: 5×280 + 4×10 + 2×24 ≈ 1488px fits 5, a 6th needs ≈1778px) so columns top out at 5; wide screenshot confirms realized count. Recorded as a decision (assumption A4) for the reviewer to override if true edge-to-edge is wanted. |
| **Dark-pane legibility regression** from a new token color. | Pane-adaptive tokens reused; any new literal color gets a dark override and is verified on the dark pane by screenshot + `getComputedStyle` text/background contrast check. |
| **Delete test nukes real data.** | All delete testing is against a **throwaway review** created in the **throwaway :8138 container**; the live :8139 instance is never touched. |
| **Sticky search bar overlaps cards / breaks on scroll.** | `position:sticky;top:0` with a solid `--bg` background and z-index; screenshot mid-scroll confirms it stays pinned and opaque. |
| **Group collapse state lost on the delete-triggered `load()` re-render.** | Collapse state is the session `Set`, read by `load()` on every render, so it survives `load()`; verified by collapsing a group, deleting a throwaway card in another group, and asserting the first group stays collapsed. |

## Assumptions & open questions

Proceeding on these (no `--ask`); none is a true BLOCKER-FOR-HUMAN.

- **A1 (load-bearing, assumed): pane-adaptive theme is kept, not collapsed to dark-only.** The
  brief says "keep the dark theme," but the dashboard is **pane-adaptive today** (verified,
  `dashboard.html:8-9`). Collapsing to dark-only would regress light-theme users, which the brief's
  "preserve all existing functionality" forbids. Assumption: keep pane-adaptive, polish the dark
  pane, verify both panes. *Justification:* preserving existing behavior is explicitly load-bearing
  in the brief; dark-only is a behavior loss, not a polish.
- **A2 (minor): grouping stays project-level, sessions remain non-collapsible sub-groups.** The
  brief's collapsible example ("blog 2") is a project name; it does not mention session collapse.
  Assumption: only project groups collapse. *Justification:* matches the brief's example and the
  existing Project›Session hierarchy.
- **A3 (load-bearing, assumed): "preserve notes" = preserve the notes-COUNT display.** The
  `/api/reviews` payload carries only `notes_total`/`notes_addressed`, not note bodies; the
  dashboard never showed note bodies. Assumption: expanded card shows the full notes-count label,
  not per-note text. *Justification:* there is no note-body data in the payload, and adding one is
  an out-of-scope API change. If the reviewer reads "full notes" as per-note bodies, that is a
  service change and a separate epic — flagged, not silently dropped.
- **A4 (minor): grid capped at `max-width:1600px` to honor "3–5 columns."** Measured overshoot to
  6/8 columns on 1920/2560px. Assumption: cap at 1600px (≤5 columns) while keeping full-width on
  ≤1600px screens. *Justification:* the brief gives both `minmax(280px,1fr)` and "3–5 columns";
  the cap reconciles them with the smallest change. **`1600px` is the 5-column ceiling from the
  layout math — 5×280 + 4×10 + 2×24 ≈ 1488px fits 5, and a 6th column needs ≈1778px, so 1600 admits
  exactly 5 and no more.** Reviewer may prefer true edge-to-edge.
- **A5 (minor): status chip is in scope** as the brief's "optional but nice." Assumption: include
  it; it is the natural cut line if the single ticket runs long (becomes MR-031b in the fallback
  split). *Justification:* brief tags it optional; low-risk to include.

No BLOCKER-FOR-HUMAN: every fork has a safe, brief-aligned default and a recorded escape hatch for
the reviewer.

## Verification

All commands run against a **throwaway container on :8138** built from the working tree; the live
:8139 instance and `docker compose` (8137) are never touched. Dates `Europe/London`.

### 0. Build + run a throwaway container (clean data)
```bash
docker build -t mdreview-dash-smoke /Users/apple/Dev/personal/tools-utilities/mdreview-service
docker rm -f mdreview-dash-smoke 2>/dev/null
docker run -d --name mdreview-dash-smoke -p 8138:8080 mdreview-dash-smoke
BASE=http://localhost:8138
# wait for health
until curl -fsS "$BASE/healthz" >/dev/null 2>&1; do sleep 0.3; done
```

### 1. Server still compiles (file unchanged by this epic, but the gate is mandatory)
```bash
python3 -m py_compile /Users/apple/Dev/personal/tools-utilities/mdreview-service/app.py   # exit 0
```

### 2. Seed reviews so the grid, groups, and notes have something to render
```bash
# two projects so collapsible groups + group-hiding-on-search are exercisable
curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"Intro post","markdown":"# Intro\n\nhello\n","project":"blog 2","session":"run-1","source_path":"content/posts/intro.md"}'
curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"Pricing page copy","markdown":"# Pricing\n\ndraft\n","project":"marketing-site","session":"","source_path":"src/pages/pricing/index.mdx"}'
# capture one id we will use for the DELETE test (throwaway)
DEL_ID=$(curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"Delete me","markdown":"# tmp\n","project":"blog 2","source_path":"tmp/del.md"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
echo "throwaway delete id = $DEL_ID"
# sanity: payload shape is unchanged (same fields the cards read)
curl -s "$BASE/api/reviews" | python3 -m json.tool | head -30
```

### 3. Render-smoke: assert the NEW DOM nodes (flat selectors, each standalone)
```bash
scripts/render-smoke.sh "$BASE/" \
  '.grid' '.card' '#search' '.group-header'
# expected: every selector matches >=1 rendered node -> exit 0
# NEVER pass a descendant selector like '.grid .card' (footgun 11 -> exit 2).
```
(Selector names are the proposed class/id hooks; the implementer must use exactly these so the
smoke matches: grid container `.grid`, a card `.card`, the search input `#search`, a project
header `.group-header`. If a name changes during build, the ticket's AC carries the final names.)

### 4. The visual proof (the binding evidence for a dense/visual brief) — screenshots
```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EV=/Users/apple/Dev/personal/tools-utilities/mdreview-service/docs/process/reviews/sprint-09-render-evidence-2026-06-19
mkdir -p "$EV"
# a) WIDE viewport -> must show 3-5 columns (cap proves <=5)
"$CHROME" --headless=new --disable-gpu --no-sandbox --window-size=1680,1000 \
  --virtual-time-budget=2500 --screenshot="$EV/wide-5col.png" "$BASE/"
"$CHROME" --headless=new --disable-gpu --no-sandbox --window-size=2560,1000 \
  --virtual-time-budget=2500 --screenshot="$EV/ultrawide-capped.png" "$BASE/"   # still <=5 cols
# b) COLLAPSED card -> proves ~3-line / <=5-6-line cards (default render is collapsed)
"$CHROME" --headless=new --disable-gpu --no-sandbox --window-size=1280,900 \
  --virtual-time-budget=2500 --screenshot="$EV/collapsed.png" "$BASE/"
# c) EXPANDED card + filtered search + collapsed group: drive via an injected script page
#    (use Chrome to load, then a small click-script; or capture manually in a real browser and
#     save expanded.png / search-filtered.png / group-collapsed.png into $EV)
# d) BOTH PANES (pane-adaptive theme): emulate prefers-color-scheme via --blink-settings.
#    NOTE: --force-dark-mode is Chrome's auto-invert filter, NOT prefers-color-scheme emulation,
#    and bare headless Chrome resolves DARK by default — so a no-flag "light" shot comes out dark
#    and the both-pane proof is vacuous. Use preferredColorScheme=0 (dark) / =1 (light), the
#    mechanism this repo already settled (theme-awareness-plan-review-2026-06-18.md, "What's sound").
"$CHROME" --headless=new --disable-gpu --no-sandbox --window-size=1680,1000 \
  --blink-settings=preferredColorScheme=0 --virtual-time-budget=2500 --screenshot="$EV/dark-pane.png" "$BASE/"
"$CHROME" --headless=new --disable-gpu --no-sandbox --window-size=1680,1000 \
  --blink-settings=preferredColorScheme=1 --virtual-time-budget=2500 --screenshot="$EV/light-pane.png" "$BASE/"
```
Required screenshots in evidence: `wide-5col.png` (3–5 cols), `ultrawide-capped.png` (≤5 cols),
`collapsed.png` (~3-line cards), `expanded.png` (path + actions + notes label visible),
`search-filtered.png` (only matching cards/groups, no empty headers), `group-collapsed.png`
(a collapsed project group with chevron + count badge still visible), `dark-pane.png` +
`light-pane.png` (both panes legible). The expanded / filtered / group-collapsed shots require an
interaction, so they are captured in a real browser (or a click-driver) and saved into `$EV`.

**Required-artifact list (the ticket AC enumerates these as deliverables).** `render-smoke.sh`
proves the static DOM nodes but **cannot** verify the three interaction-driven states
(`expanded.png`, `search-filtered.png`, `group-collapsed.png`) — those rest on the implementer
capturing them by hand. To stop "trusted but never taken" from slipping through, the ticket AC
lists **all eight** screenshots above as **required evidence artifacts**, and **G7 checks each file
exists** under `$EV` (`reviews/sprint-09-render-evidence-2026-06-19/`) before the close review
passes. A missing required artifact fails G7; the AC must name them so the gate has a concrete
checklist, not a judgement call.

### 5. Preserve-functionality — exercise Open / Delete / version / notes (load-bearing)
- **Open:** the card's Open control is an `<a href="/review/{id}">`; assert the link target is
  present and resolves:
  ```bash
  curl -s "$BASE/review/$DEL_ID" -o /dev/null -w '%{http_code}\n'   # 200 (viewer renders)
  ```
  and in the browser, click Open on a card and confirm it navigates to the viewer (manual /
  click-driver step in the evidence).
- **Delete (throwaway only):** click Delete on the `Delete me` card, confirm the `confirm()` and
  the `DELETE /api/reviews/{id}` fire, and the card disappears after `load()`:
  ```bash
  curl -s -X DELETE "$BASE/api/reviews/$DEL_ID" -o /dev/null -w '%{http_code}\n'   # 200
  curl -s "$BASE/api/reviews" | grep -c "$DEL_ID"   # 0 -> gone
  ```
  (Browser path: the click handler must still call DELETE then `load()`; verified by the card
  vanishing in the UI. This is run ONLY against the throwaway :8138 container.)
- **Version badge:** bump a review's revision via `PUT /source`, reload the dashboard, assert the
  `v{n}` badge renders:
  ```bash
  curl -s -X PUT "$BASE/api/reviews/$(curl -s "$BASE/api/reviews" | python3 -c 'import sys,json;print(json.load(sys.stdin)["reviews"][0]["id"])')/source" \
    -H 'Content-Type: application/json' -d '{"markdown":"# Intro\n\nv2 body\n"}' -o /dev/null -w '%{http_code}\n'  # 200
  ```
  then a screenshot of that card showing `v1` in collapsed metadata.
- **Notes count:** the seeded reviews start at "no notes"; the notes-count badge renders the
  `noteLabel()` output (preserved helper). Confirm "no notes" / "N notes · M done" appears in the
  collapsed metadata row (screenshot) — proving the notes-count display survives.

### 6. Tear down the throwaway container
```bash
docker rm -f mdreview-dash-smoke
```

### G4 / G7 gate mapping
- **G4** (this ticket): step 1 (py_compile) + step 0/3 (rebuilt-container render-smoke asserting
  `.grid` `.card` `#search` `.group-header`) + the screenshot set + the preserve-functionality
  checks. A 200 is not a render — the smoke + screenshots are the proof.
- **G7** (sprint-09 close, independent `staff-critic`): rebuild the container, `curl /healthz` +
  `/api/reviews`, re-run `scripts/render-smoke.sh` against `/` (a product page was touched), and
  save the screenshot set under `reviews/sprint-09-render-evidence-2026-06-19/`. **G7 confirms all
  eight required screenshot artifacts exist** in that directory (the three interaction-driven shots
  — `expanded.png`, `search-filtered.png`, `group-collapsed.png` — are not smoke-verifiable, so
  their presence is checked as files); a missing required artifact fails the close review. The
  delete test runs against a throwaway review in the throwaway container, never live data.

## Resolution log

Findings from the G1 review (`reviews/dashboard-redesign-plan-review-2026-06-19.md`,
PASS-WITH-CONDITIONS: 0 BLOCKER + 1 SHOULD + 6 NIT). Author resolutions, 2026-06-19:

- **SHOULD-1 — Verification 4d used `--force-dark-mode` (invalid both-pane proof).** Fixed. The
  dark/light pane capture in **Verification step 4d** now uses
  `--blink-settings=preferredColorScheme=0` (dark) and `=1` (light), with `--force-dark-mode`
  removed entirely and a code comment explaining why (auto-invert ≠ scheme emulation, and bare
  headless resolves dark by default so a no-flag "light" shot is vacuous). The same flag is now
  named in **Fork 5** (the dark-pane `getComputedStyle` legibility check passes
  `preferredColorScheme=0`) and in the **Key constraints "Pane-adaptive theme"** bullet. Precedent
  cited: `theme-awareness-plan-review-2026-06-18.md`. This was a verification-recipe defect, not a
  design defect; the both-pane requirement was already correct.
- **NIT — A3 (notes-count) ruling.** Accepted as ruled CORRECT by the critic; no design change.
  Per the critic's one concrete ask, no edit is needed because the plan already treats the
  expanded-card notes label as the same `noteLabel()` string (Fork 1, "Notes count is already in
  the metadata row; the expanded view restates the full notes label") and the Non-goals already bar
  per-note bodies. The ticket AC will not treat the redundant restatement as a hard must-have — it
  is satisfied by the existing `noteLabel()` output, which Fork 1 already states.
- **NIT — A4 (1600px cap) ruling.** Accepted as ruled CORRECT; cap stays the default with A4
  flagged. Actioned the critic's refinement: tied `1600px` to the 5-column math
  (5×280 + 4×10 + 2×24 ≈ 1488px fits 5; a 6th needs ≈1778px) in **Fork 2**, **assumption A4**, and
  the **column-overshoot risk row**, so a later reader sees it as the 5-column ceiling, not a guess.
- **NIT — keyboard a11y guard parity.** Actioned. The **Fork 1 Accessibility** paragraph now
  requires the Enter/Space keydown handler to apply the **same** `closest('a, button')` +
  non-empty-selection guard as the click handler (so keyboard activation of a focused inner Open
  link / Delete button fires only that control and does not also toggle the card), and a matching
  **risk row** was added. The ticket AC carries the keydown-guard parity.
- **NIT — Open `<a>` navigation actually clicked, not just asserted.** Accepted; no change needed.
  The critic confirmed **Verification step 5** already clicks Open in the browser/click-driver
  (navigating to `/review/{id}`) in addition to asserting the href, which is the requested behavior.
- **NIT — manually-captured screenshots are unverifiable by the smoke.** Actioned. **Verification
  step 4** now enumerates all eight screenshots as **required evidence artifacts** the ticket AC
  lists as deliverables, and the **G7 gate-mapping** row now checks each file exists under `$EV`
  (the three interaction-driven shots — `expanded.png`, `search-filtered.png`, `group-collapsed.png`
  — are not smoke-verifiable, so their presence is a file-existence check, and a missing required
  artifact fails the close review).
- **NIT — one-ticket default + "5–6 lines = upper bound" reading.** Accepted; no change. The critic
  confirmed the single-ticket recommendation, the flat/standalone render-smoke selectors, and the
  upper-bound reading are all correct as written; the plan already records the 2-ticket fallback as
  the escape hatch and guards the "5–6 lines as a floor" misread explicitly (Fork 1 + risk row).

Ticket count unchanged: **one `ui` ticket, MR-031** (2-ticket split remains the recorded fallback
only). Epic frontmatter stays `gate: G1 not passed` / `status: draft` pending re-review.
