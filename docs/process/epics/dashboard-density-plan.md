---
epic: dashboard-density
status: done   # shipped 2026-06-19 within a direct, out-of-cycle flat-grid redesign (user exception); G1 passed, G7 waived — see sprint-10
created: 2026-06-19
source: requirements/dashboard-density.md
gate: passed 2026-06-19  # G1 passed (round 2, staff-critic PASS)
review: reviews/dashboard-density-plan-review-2026-06-19.md, reviews/dashboard-density-plan-review-2026-06-19-r2.md
related_sprints: [sprint-10]
related_tickets: [MR-032]
---

# Dashboard density Plan

The dashboard redesign (MR-031 / sprint-09) shipped a dense, full-width, searchable card grid, but
two pieces of wasted space remain that the user wants gone: a tall gap between the search bar and
the first project, and — the headline complaint — **sparse rows leave most of the row blank** (a
session with 1 card, e.g. "agit"'s single session, strands ~75% of the row). Note the fill/cap unit
is the **per-session grid** (`dashboard.html` renders one `.grid` per session within a project), so
"row" throughout means a session row. This epic is a small, prescriptive,
**single-file CSS refinement of `dashboard.html`** that (1) tightens the top gap, (2) switches the
grid from `auto-fill` to `auto-fit` so sparse rows fill, with a sensible cap on the lone-card case,
(3) reconsiders the MR-031 `max-width:1600px` cap toward "edge-to-edge, not floating," and (4) trims
group/card whitespace. No service, API, MCP, route, `viewer.html`, or `Dockerfile` change.

**Source requirement:** [`requirements/dashboard-density.md`](../requirements/dashboard-density.md) —
the original brief, kept verbatim.

## Product goal

Open the dashboard on a wide monitor and it reads as a full, intentional grid: the first project sits
just under the search bar (no floating gap), every session row is filled left-to-right (a 1-card
session shows one sensibly-sized card, a 2-card session splits the row evenly with no right gutter,
many-card sessions pack the row), and the whole page uses the screen edge-to-edge without feeling
cramped. Every existing behavior — search/filter, status chips, card + group collapse/expand,
expand/collapse-all, Open/Delete/version/notes, pane-adaptive theme — is preserved unchanged.

## Current state (the values being changed)

All in `dashboard.html`'s inline `<style>`; nothing else moves. The values this epic edits:

| Selector | `dashboard.html` | Current value | What it controls |
|----------|------------------|---------------|------------------|
| `.grid` | `:45` | `grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:10px` | **the headline fix** — `auto-fill` keeps phantom empty tracks on sparse rows |
| `.wrap` | `:25` | `max-width:1600px; margin:0 auto; padding:16px 24px 96px` | page width cap + top whitespace |
| `.bar-inner` | `:15` | `max-width:1600px; padding:9px 24px` | search-bar width cap (must track `.wrap` to stay aligned) |
| `.sub` | `:26` | `margin:2px 0 18px` | the "43 reviews across 14 projects" line — 18px below it is the top gap |
| `.project` | `:29` | `margin:0 0 14px` | gap between project groups |
| `.session` | `:39` | `margin:8px 0 0` | gap above each session block |
| `.session>h3` | `:41` | `margin:6px 0 6px` | session sub-label spacing |
| `.group-header` | `:31` | `padding:5px 4px` | project header padding |
| `.card` | `:48` | `padding:8px 10px; gap:5px` | per-card whitespace (already halved in MR-031) |

The card internals were already tightened in MR-031 (`padding:8px 10px`, `border-radius:8px`,
`14px/1.45`); this epic does **not** re-cram the card — it trims the *between-element* whitespace and
fixes the row-fill, which is where the remaining waste lives.

## Core design principle

**Fill the row, cap only the absurd case.** `auto-fit` collapses empty tracks so a session grid's
cards stretch to fill the row — that single change fixes the named complaint for every **session row**
with ≥2 cards. (The row-fill / cap unit is the **per-session grid**: `dashboard.html` renders one
`.grid` per session within a project — `section.project > .group-body > .session > .grid > .card[]`,
`dashboard.html:177-178` — so "fill the row" and the lone-card cap both apply per session, not per
project.) The *only* judgment call is the lone card: with `auto-fit` a single-card session grid
stretches that card to the full grid width (measured: **2152px at 2560px viewport** — absurd). So cap
**only the lone-card session grid** to a sensible column-ish width, leaving the even-fill behavior
intact for everyone else. Density numbers are halved/tightened only where they remove dead space,
never to the point of cramping a legible 14px card.

## Forks resolved (with the measurements that settled them)

I built the throwaway image, ran it on **:8138** (never compose/:8139), seeded a 1-card project
("agit"), a 2-card project ("pairproj"), and a 6-card project ("bigproj"), and measured card widths
live via CDP (`getBoundingClientRect`, Node built-in `WebSocket`). The numbers below are real, not
prose.

### Fork 2 first — the 1600px cap (raise, don't remove). DECIDED: **raise to `max-width:2000px`.**

`auto-fit` fixes the sparse-row gutter *regardless of the cap*; the cap governs only the edge-to-edge
feel and the column count on very wide monitors. Measured grid behavior (`auto-fit`,
`minmax(280px,1fr)`, 6-card project):

| Viewport | Cap 1600 (`.wrap`) | Cap 2200 | No cap |
|----------|--------------------|----------|--------|
| 1920px | wrap=1600, 6-card→302px ea | wrap=1920, 6-card→304px ea | wrap=1920, 6-card→304px ea |
| 2560px | wrap=1600, 6-card→302px ea | wrap=2200, 6-card→350px ea | wrap=2560, 6-card→410px ea |

The user explicitly overrode the MR-031 A4 decision ("edge-to-edge … wide screens actually filled"),
so 1600 is out — at 2560px it floats a 1600px column centred in a 2560px screen, exactly the
"floating in empty space" the brief names. **No cap** fills a 2560px screen but a 6-card project then
gives 410px cards on a 27" panel and the grid sprawls to the literal screen edges with no breathing
room — legible but not intentional, and on a 32"/4K panel it would pack a wall of tiny cards. **Cap
2000** (between the measured 1920 and 2200 rows) is the middle: it fills any common laptop/desktop
(≤1920) completely with no cap visible at all, gives genuine edge-to-edge use of the width up to 2000,
and only on a true ultrawide (>2000px) leaves a modest centred margin that reads as a deliberate
reading width rather than a stranded 1600 column. It honours "edge-to-edge, not floating" for the
overwhelming majority of screens while keeping cards legible on a 4K panel. I picked **2000** over
2200 because 2000 is a round, defensible reading-width ceiling and the difference at 2560 is one extra
card column either way; if the user prefers true full-bleed on 4K, removing the cap is a one-line
follow-up (noted as out-of-epic). `.wrap` **and** `.bar-inner` both move to `2000px` so the search bar
stays aligned with the content.

### Fork 1 — the lone-card "sensible max" (the one real fork). DECIDED: **option (c)** — cap only the lone-card session grid via `:has()`.

**The cap unit is the per-session grid, not the project.** `dashboard.html` emits one `.grid` per
session (`dashboard.html:177-178`: `<div class="session">…<div class="grid">${cards}</div></div>`),
and `.card` is a direct child of that grid. So `.grid:has(.card:only-child)` matches **a session grid
that holds exactly one card** — what "lone card" means here is "a session row with a single card,"
which is the correct read: a session that produced one review genuinely is a lone card and should cap,
not span the screen.

With `auto-fit`, that lone card spans the full grid track. Measured three candidate fixes (cap 2200
base so the absurd case is maximally visible):

| Candidate | 1-card session @2560 | 2-card session @2560 (each) | 6-card session @2560 | Verdict |
|-----------|----------------------|-----------------------------|----------------------|---------|
| **(a)** accept full-span (base `auto-fit`) | **2152px** | 1071px, fills row | 350px | lone card absurdly wide on any wide screen |
| **(b)** `.card{max-width:560px}` | 560px | **560px + right gutter** | 350px | caps lone card BUT 2-card session no longer fills the row — **reintroduces the exact gutter the user complained about** |
| **(c)** `.grid:has(.card:only-child){grid-template-columns:minmax(280px,560px)}` | **560px** | **1071px, fills row** | 350px | lone card sensible (~2 columns), 2+ card sessions still split evenly and fill the row |

(The @2560 numbers above are the **cap-2200/gap-10 exploration** numbers, kept verbatim as the
relative comparison that settled the fork — the candidate-elimination logic is unchanged by the cap.
The **shipped** cap-2000/gap-8 widths a verifier asserts are computed in the Verification section:
2-card ≈972, 6-card ≈319, lone card 560.)

**(c) is the only candidate that fixes the lone card without regressing the headline 2-card fix.**
(b) is rejected for exactly that reason — it solves fork 1 by re-creating the brief's primary
complaint. The mechanism is a single added rule:

```css
.grid:has(.card:only-child){grid-template-columns:minmax(280px,560px);}
```

`:has()` is verified supported in the smoke Chrome (`CSS.supports('selector(:has(*))')` → true) and has
shipped in all major browsers since late 2023 — safe for a 2026 internal dashboard. `560px` ≈ two
280px columns, so a lone card reads as a comfortably-sized single card, not a banner. No JS, no payload
change — it keys purely on DOM shape (`only-child`). The brief said "full width (or a sensible max)";
this is the sensible max, and it's the one that keeps every other row filled.

> **Multi-session consequence (per-session keying):** a project whose cards are spread one-per-session
> (e.g. six sessions, one card each) renders as **six separate single-card session grids, each capped
> to 560px** — six narrow capped rows, not one filled row. This is the intended behavior: each of
> those rows genuinely is a lone card. It is *not* "a 6-card project packed into a row" — that only
> happens when the six cards share one session. The Verification seed includes a two-session
> single-card project ("multisess") and screenshots it so this read is signed off, not discovered at
> close.
>
> **Filter interaction (`:only-child` ignores `.is-hidden`):** `applyFilter()`
> (`dashboard.html:196-202`) hides non-matching cards with `.is-hidden` (`display:none`), it does not
> remove them. So a session grid filtered down to one *visible* card still has >1 element child →
> `:only-child` is **false** → no 560 cap. And because a `display:none` grid item generates no track,
> that single visible card then sizes to the **full** available width (wider, not narrower). This is a
> transient filter-only state and is acceptable — the cap is for genuinely single-card session grids,
> not filtered-down ones — but it is named here so it is not mistaken for a defect at the close review.

> **Note on `:has()` as the load-bearing mechanism (state for the critic):** the entire fork-1 fix is
> this one selector. If a reviewer wants a JS-free fallback for a hypothetical non-`:has()` browser,
> the graceful degradation is benign — without `:has()` support the rule is ignored and a lone card
> falls back to full-span (candidate (a)), which is ugly but not broken. No functionality depends on
> it. Given the verified support, no fallback is built.

### Fork 3 — concrete density numbers (current → new)

Each trimmed only where it removes dead space; the card interior is left at its MR-031 values.

| Selector | Current | New | Rationale |
|----------|---------|-----|-----------|
| `.sub` margin | `2px 0 18px` | `2px 0 8px` | the 18px below the count line is the top gap the user names; 8px keeps the line distinct without floating the first header |
| `.wrap` padding | `16px 24px 96px` | `10px 24px 64px` | top 16→10 pulls content up under the bar; keep 24px side gutters (edge legibility); 96→64 trims excess bottom scroll-room |
| `.wrap` / `.bar-inner` max-width | `1600px` | `2000px` | fork 2 |
| `.project` margin | `0 0 14px` | `0 0 10px` | tighten inter-group gap |
| `.session` margin | `8px 0 0` | `6px 0 0` | tighten gap above a session block |
| `.session>h3` margin | `6px 0 6px` | `4px 0 5px` | tighten session sub-label |
| `.group-header` padding | `5px 4px` | `4px 4px` | shave header vertical padding |
| `.grid` gap | `10px` | `8px` | tighter card gutters; cards then fill the reclaimed width |
| `.card` padding / gap | `8px 10px` / `5px` | **unchanged** | already halved in MR-031; trimming further risks cramping the 14px card |

These shave ~10px off the top stack and a few px between every group/card while leaving the card itself
readable. None is a hard responsive breakpoint — they are static density values, so footgun 6's
"behavior not pixel-breakpoint" caveat does not bite here (the one viewport-dependent behavior, the
grid column count, is handled by `auto-fit` + the cap, both fluid).

## Recommended approach

### Service (`app.py`)

None. No `app.py`, route, API, MCP, or `Dockerfile` change. `dashboard.html` is already served at
`GET /` and already in the `Dockerfile` `COPY` (footgun 9 satisfied — no new served file is
introduced, so no `COPY` edit is needed). `python3 -m py_compile app.py` still passes trivially
(file untouched).

### UI (`dashboard.html` only)

A single ticket making the CSS edits in the Fork-3 table, plus:
- `.grid` `:45` → `grid-template-columns:repeat(auto-fit,minmax(280px,1fr))` (auto-fill → **auto-fit**)
  and `gap:8px`.
- Add one rule: `.grid:has(.card:only-child){grid-template-columns:minmax(280px,560px);}` (fork 1).
- `.wrap` `:25` and `.bar-inner` `:15` max-width `1600px → 2000px` (fork 2).
- The MR-031 comment block at `:44` ("capped so columns top out at 5…") is now stale — update it to
  describe `auto-fit` + the **per-session** lone-card cap (`:has(.card:only-child)`) + the 2000px
  reading-width ceiling so the next reader isn't misled.
- **No JS change.** `load()`, `card()`, `applyFilter()`, `setGroup()`, the delegated click/keydown
  handlers, and all helpers (`esc`/`rel`/`noteLabel`/`groupBy`) are untouched — this is CSS-only, so
  every interaction behavior is preserved by construction.

## Rollout phases

One phase — this is a single-file CSS refinement, not a multi-slice feature.

### Phase 1 — density + row-fill (MR-032)
The complete change: `auto-fit`, the lone-card `:has()` cap, the 2000px cap, and the Fork-3 density
values, shipped together in one `ui` ticket. They are interdependent (the cap and the lone-card rule
only make sense together) and individually trivial, so splitting them would add ceremony without
adding shippability.

## Non-goals

- **No service/API/MCP/route/`viewer.html`/`Dockerfile` change** — `dashboard.html` only.
- **No new feature** — density/layout only (no new filters, sort, persisted collapse, per-note bodies).
- **No removal of the width cap entirely** — true full-bleed on 4K is deliberately *not* done; the cap
  is raised to 2000, not removed. (Out-of-epic one-line follow-up if the user wants full-bleed.)
- **No re-cramming the card interior** — card `padding`/`gap`/type scale stay at MR-031 values.
- **No JS-side responsive logic** — column behavior stays pure CSS (`auto-fit` + cap).

## Key constraints

- **`ui` change ⇒ render-smoke + screenshots are the binding proof, not a 200.** G4/G7 evidence is
  `scripts/render-smoke.sh` from the rebuilt container asserting DOM nodes, plus the before/after
  screenshot set below. A 200 is not a render (footgun 6).
- **render-smoke selectors are flat** (footgun 11): use `'.grid' '.card' '#search' '.group-header'` —
  never a descendant selector like `'.grid .card'` (exits 2, not a miss).
- **Dark pane via scheme emulation, never `--force-dark-mode`** (footgun 6). Use
  `--blink-settings=preferredColorScheme=0` (dark) / `=1` (light) for screenshots, or CDP
  `Emulation.setEmulatedMedia` for measurement. `--force-dark-mode` is auto-invert (it never sets
  `prefers-color-scheme`), so it would test the wrong path against the `@media (prefers-color-scheme:
  dark)` rules at `dashboard.html:9,56`. **Re-verify the enum direction live in the close review** —
  the `0=dark / 1=light` ordering is non-obvious and has bitten people: assert the dark-pane shot's
  computed `body` bg is the dark token (expected `rgb(17,17,17)`) rather than trusting this comment.
  (Bare headless also resolves dark by default, so a no-flag "light" shot would be wrong — both panes
  must be emulated explicitly.)
- **Live instance is :8139** — never `docker compose up` (compose maps 8137; the live publish is on
  8139). Build a throwaway image and run it on a free port (e.g. **:8138**) for all smokes/captures.
- **Delete test only on a throwaway review on the throwaway container** — never touch a real review.
- **Header dumps use GET, not `curl -sI`** (footgun 10) — there's no `do_HEAD`; a `-sI` hits the 501
  page. (Not needed here — no header assertions — but stated so a verifier doesn't reach for `-sI`.)
- **`:has()` is the load-bearing mechanism for fork 1** — verified supported; degrades benignly to
  full-span if ever absent.
- **No new served file** ⇒ no `Dockerfile COPY` edit (footgun 9) — confirmed `dashboard.html` is
  already copied.

## Preferred execution order

1. MR-032 — make the CSS edits in `dashboard.html` (auto-fit + lone-card `:has()` cap + 2000px cap +
   density values + stale-comment fix). Validate with `py_compile`, the render-smoke, the before/after
   screenshot set, and the full preserve-functionality re-check. One ticket, sprint-10.

## Ticket breakdown

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-032 | Dashboard density: auto-fit row-fill + lone-card `:has()` cap + raise width cap to 2000px + trim top/group/card whitespace (`dashboard.html` only) | ui | 1 |

(Single ticket, proposed for **sprint-10**. ID is a placeholder — the orchestrator allocates the real
ID; `032` is the next sequential after `031`.)

## Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| **`:has()` not supported on the reviewer's browser** ⇒ lone card falls back to full-span. | Verified supported in the smoke Chrome (`CSS.supports('selector(:has(*))')` → true) and in all major browsers since late 2023. Degradation is benign (ugly lone card, nothing broken). Stated in the plan for the critic. |
| **Raising the cap to 2000 makes cards too small / the grid sprawl on 4K.** | Measured: at 2560px a 6-card session under the shipped cap-2000/gap-8 is ≈319px cards (legible) and the cap holds a 2000px reading width with a modest centred margin, not a screen-edge sprawl. Both panes captured in the wide-viewport screenshot. |
| **A density value cramps the card / breaks legibility.** | Card interior left at MR-031 values; only between-element whitespace trimmed. The `collapsed`/`expanded`/dark/light screenshots are the legibility check. |
| **Stale `.grid` comment at `:44` misleads the next reader** ("top out at 5"). | The ticket explicitly updates that comment to describe auto-fit + lone-card cap + 2000px ceiling. |
| **A CSS edit silently breaks an interaction** (search, collapse, delete). | The change is CSS-only — no JS touched — and the preserve-functionality re-check (below) re-exercises Open/Delete/version/notes/search/chips/collapse end-to-end via CDP, as MR-031/sprint-09 did. |
| **`.bar-inner` cap not moved in lockstep with `.wrap`** ⇒ search bar misaligned from content. | Both cited in the ticket as a paired edit (`1600 → 2000` on both `:15` and `:25`); the wide-viewport screenshot shows the bar aligned to the content edge. |

## Verification

All against a **throwaway** rebuilt image on **:8138** (never compose/:8139). Seed a 1-card project
("agit"), a 2-card project, a ≥6-card project, **and a multi-session single-card project
("multisess") with two sessions of one card each** — so the row-fill is observable AND the
per-session-grid capping (Fork 1) is exercised; create one extra **throwaway** review for the delete
test.

### Build + seed
```bash
docker build -t mdreview-density .
docker rm -f mdr-dens 2>/dev/null; docker run -d --name mdr-dens -p 8138:8080 mdreview-density
BASE=http://localhost:8138
curl -s "$BASE/healthz"                      # {"ok": true}
mk(){ curl -s -X POST "$BASE/api/reviews" -H 'Content-Type: application/json' -d "$1" >/dev/null; }
mk '{"title":"agit lone","markdown":"# x","project":"agit","session":"run-1","source_path":"docs/a.md"}'
mk '{"title":"pair one","markdown":"# x","project":"pairproj","session":"run-1","source_path":"docs/p1.md"}'
mk '{"title":"pair two","markdown":"# x","project":"pairproj","session":"run-1","source_path":"docs/p2.md"}'
for i in 1 2 3 4 5 6; do mk "{\"title\":\"big $i\",\"markdown\":\"# x\",\"project\":\"bigproj\",\"session\":\"run-1\",\"source_path\":\"docs/b$i.md\"}"; done
# multi-session single-card project: two sessions, ONE card each → two separate :only-child grids
mk '{"title":"ms one","markdown":"# x","project":"multisess","session":"run-1","source_path":"docs/m1.md"}'
mk '{"title":"ms two","markdown":"# x","project":"multisess","session":"run-2","source_path":"docs/m2.md"}'
```

### Service gate (unchanged file)
```bash
python3 -m py_compile app.py        # exit 0 (app.py untouched)
git diff --stat                      # only dashboard.html (+ process files)
```

### Render-smoke (flat selectors — footgun 11)
```bash
scripts/render-smoke.sh "$BASE/" '.grid' '.card' '#search' '.group-header'
# expect: all ok (.grid >=5 — agit/pairproj/bigproj + two multisess session grids,
#         .card >=11, #search 1, .group-header >=4), exit 0
```

### Row-fill + lone-card measurement (CDP — the binding numbers)
Drive headless Chrome over CDP (Node built-in `WebSocket`; `Emulation.setDeviceMetricsOverride` for
viewport; `getBoundingClientRect` for widths).

**The numbers are computed against the SHIPPED config** (cap `2000`, `.wrap` side padding `24px`
each side = 48px, gap `8px`), NOT the cap-2200/gap-10 exploration table. At 2560px the grid is
capped at 2000, so the content width inside `.grid` is `2000 − 48 = 1952px`, and an N-card session
grid gives each card `(1952 − (N−1)×8) / N`:

| Session grid | Formula | Each-card width |
|--------------|---------|-----------------|
| 2-card (pairproj) | `(1952 − 1×8)/2 = 1944/2` | **≈972px** |
| 6-card (bigproj)  | `(1952 − 5×8)/6 = 1912/6` | **≈319px** |

Assert, at **2560px**:
- **agit lone session (1 card):** card width **≈560px** (the `:has(.card:only-child)` cap — NOT
  ~2152px full-span).
- **pairproj single session (2 cards):** two cards **each ≈972px**, together filling the row (no
  right gutter).
- **bigproj single session (6 cards):** six cards **each ≈319px**, filling the row.
- **multi-session single-card project (`run-1`, `run-2`, one card each):** **each** session row is a
  separate `:only-child` grid, so **each** lone card caps at **≈560px** — two narrow capped rows, the
  intended behavior (see Fork 1).
- `.wrap` box width **= 2000px** (the raised cap holds; not 1600, not 2560).

And at **1440px** (common laptop): `.wrap` box = 1440 (cap not yet reached → genuinely edge-to-edge,
content width `1440 − 48 = 1392`, so 2-card ≈ `(1392−8)/2 ≈ 692px` each), agit lone card ≈560px,
pairproj fills the row evenly.

### Before/after screenshot set (the user asked "show me the result")
Capture from the throwaway. **Dark pane = `--blink-settings=preferredColorScheme=0`; light pane = `=1`;
never `--force-dark-mode`.** Save under `reviews/sprint-10-render-evidence-2026-06-19/`:
- `top-gap.png` — viewport ~1440px, first project header sitting **just under the search bar** (the
  tightened `.sub`/`.wrap` top stack). The headline "gap above content" fix.
- `sparse-fill.png` — the **1-card "agit" row showing the capped ~560px card** and the **2-card
  "pairproj" row filling the width evenly** in the same shot. The headline "empty right side" fix.
- `multisession.png` — the **"multisess" project with two single-card session rows (`run-1`,
  `run-2`)**, each lone card capped at ~560px. Confirms the cap unit is the **session grid** (Fork 1):
  a multi-session project of single cards reads as several capped rows, the intended behavior — not a
  filled row. Captured at ~1440px so both session rows are visible together.
- `wide-edge.png` — viewport **2560px**, edge-to-edge fill at the 2000px cap (bigproj packs the row;
  the centred reading margin reads as deliberate, not a stranded 1600 column).
- `dark-pane.png` (`preferredColorScheme=0`) + `light-pane.png` (`=1`) — both legible, pane-adaptive
  theme intact.

### Preserve-functionality re-check (CDP-clicked, as MR-031/sprint-09 did)
Re-exercise every behavior the brief says to preserve — CSS-only change, but proven, not assumed:
- **Search** — type a project name in `#search`; only matching cards visible; empty sessions/projects
  hidden; clearing restores all.
- **Status chips** — All / Has notes / Done filter correctly (ANDed with search); "Done" with no
  resolved review shows `#noresults`.
- **Card collapse/expand** — click a card → `.expanded`, path + Open/Delete revealed; click again
  collapses. Enter/Space on a focused card toggles `aria-expanded`.
- **Group collapse/expand + Expand-all/Collapse-all** — `.group-header` click toggles `.collapsed`
  (chevron rotates, count badge stays); the bulk buttons toggle every group.
- **Open** — `<a href="/review/{id}">` navigates (sample the href).
- **Delete** (throwaway review only) — click → `confirm()` → `DELETE /api/reviews/{id}` → card gone
  from the DOM **and** from `GET /api/reviews`.
- **Version / notes** — `v{n}` badge for `revision>0`; `noteLabel` renders "N notes · M done".
- **Pane-adaptive theme** — both panes legible (covered by the dark/light screenshots).

### Teardown
```bash
docker rm -f mdr-dens; docker rmi mdreview-density   # leave :8139 live instance untouched
```

## Assumptions & open questions

No **BLOCKER-FOR-HUMAN**. The brief explicitly authorises both the cap reconsideration and "full width
(or a sensible max)" for the lone card, so both forks have a safe, brief-sanctioned default and I
proceed on them.

- **[load-bearing] The lone-card max is `560px` (~2 columns), via `:has()`.** Justification: measured
  — option (c) is the only one that caps the lone card without regressing the 2-card row-fill the user
  complained about (option (b) reintroduces the gutter). 560px ≈ two 280px columns reads as a normal
  single card, not a banner. The brief sanctions "a sensible max," so this is within the ask. If the
  user genuinely prefers a full-span lone card, deleting the one `:has()` rule reverts to option (a).
- **[load-bearing] The width cap is raised to `2000px`, not removed.** Justification: measured — 2000
  fills every common screen (≤1920) with no visible cap and gives true edge-to-edge use up to 2000,
  while keeping cards legible on a 4K panel; removing the cap entirely sprawls a wall of small cards on
  ultrawide. The brief overrode 1600 toward edge-to-edge but also values legibility ("denser but still
  legible"); 2000 is the balance. Full-bleed (no cap) is a one-line out-of-epic follow-up if wanted.
- **[minor] Density deltas (the Fork-3 table).** Best-effort halving/trimming of dead space; the exact
  px are a judgment the screenshots confirm. If any reads as cramped at review, nudge up a few px — no
  design rework.
- **[minor] Keep 24px side gutters** rather than trimming them too. Justification: the brief says
  "trim outer page padding" but card legibility at the screen edge wants a small gutter; 24px is modest
  and the edge-to-edge feel comes from the raised cap + `auto-fit`, not from zero side padding.

## Review resolutions

G1 staff-critic review `reviews/dashboard-density-plan-review-2026-06-19.md` —
PASS-WITH-CONDITIONS (0 BLOCKER, 2 SHOULD, 2 NIT). Both forks ruled sound; conditions are on the
verification recipe and prose. Resolved 2026-06-19 (still one ticket, MR-032).

- **[SHOULD-1] Verification asserted cap-2200/gap-10 widths against the cap-2000/gap-8 build.**
  Resolved: rewrote the "Row-fill + lone-card measurement" block to compute the asserted each-card
  widths from the **shipped** config — added the formula (`content = 2000 − 48 = 1952`, each card
  `(1952 − (N−1)×8)/N`) and a result table, replacing the stale targets: 2-card **≈972px** (was
  1071), 6-card **≈319px** (was 350). Lone-card 560 and `.wrap`=2000 were already correct; left
  unchanged. Also corrected the 1440px line to compute against the 1392px content width. Kept the
  cap-2200 figures in the Fork-1 candidate table but labeled them explicitly as the *exploration*
  comparison (the relative ordering that settled the fork is unchanged by the cap) and pointed to the
  Verification section for the binding shipped numbers.
- **[SHOULD-2] `:has()` keys on the per-session grid, not the project; multi-session case unseeded.**
  Resolved: (1) corrected the prose — Core design principle, Fork 1 heading/table/prose, the opening
  summary, and the product goal now say the fill/cap unit is the **per-session grid** (cited
  `dashboard.html:177-178`), and Fork 1 states per-session lone-card capping is the *intended* read.
  (2) Added a multi-session consequence note to Fork 1 (a one-card-per-session project shows several
  capped 560px rows, not a filled row). (3) Added a **two-session single-card project ("multisess")**
  to the verification seed (`run-1` + `run-2`, one card each), a CDP assertion that each session row
  caps at ≈560px, a `multisession.png` screenshot, and bumped the render-smoke expected counts
  (`.grid >=5`, `.card >=11`, `.group-header >=4`).
- **[NIT — `:only-child` ignores `.is-hidden`]** Actioned (cheap, in scope): added a "Filter
  interaction" note to Fork 1 stating that `applyFilter()` hides cards via `.is-hidden`
  (`display:none`, `dashboard.html:196-202`) without removing them, so a grid filtered to one *visible*
  card keeps >1 element child → `:only-child` is false → no cap, and the lone visible card sizes to the
  full width (wider, not narrower). Named as an acceptable transient filter-only state.
- **[NIT — confirm `preferredColorScheme` enum live]** Actioned: changed the dark-pane key constraint
  from "verified (body bg rgb(17,17,17))" as an inherited claim to a **live re-check in the close
  review** — assert the dark-pane shot's computed `body` bg is the dark token rather than trusting the
  plan comment, with the `--force-dark-mode`-is-auto-invert rationale and the bare-headless-resolves-
  dark caveat spelled out.
- **[NIT — stale `.grid` comment at `:44`]** Already in scope (a named MR-032 edit and a risk-table
  row); extended the instruction to have the rewritten comment describe the **per-session**
  lone-card cap, not a generic one.
