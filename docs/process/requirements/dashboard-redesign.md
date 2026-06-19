---
slug: dashboard-redesign
captured: 2026-06-19
source: user request 2026-06-19 (waqas) — pasted brief; "Show me the result when done." User chose the full feature-cycle over a direct build.
related_epic: epics/dashboard-redesign-plan.md
---

# Redesign the reviews dashboard — dense, compact, visually refined

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> Redesign the reviews dashboard to be dense, compact, and visually refined.
> Current problem: cards are far too tall, the grid only fits ~2 columns on a wide screen, file
> paths wrap to 3 lines, and Open/Delete buttons each take a full row — causing endless scrolling
> past wasted space.
>
> **LAYOUT & DENSITY**
> - Replace the narrow centered container with a full-width responsive grid:
>   `repeat(auto-fill, minmax(280px, 1fr))`. Aim for 3–5 columns on desktop.
> - Halve card padding; tighten line-height and inter-card/section gaps.
> - A collapsed card must be ~5–6 lines tall, no more.
> - File path: single line, ellipsis truncation (no wrapping).
>
> **COLLAPSED VS EXPANDED (click to expand)**
> - Collapsed card shows ONLY: title + one metadata row (feedback badge · notes/done · version · date).
> - Whole card is clickable; clicking expands it in place to reveal: full file path, full notes, and
>   the action buttons.
> - Remove the always-visible stacked Open/Delete rows. Show actions only on hover or when expanded,
>   as small inline text/icon buttons.
>
> **SEARCH / FILTER BAR**
> - Add a sticky search bar at the top of the page.
> - Live-filter cards as the user types, matching title, project name, and file path. Hide
>   non-matching cards and any project group left with no matches.
> - Optional but nice: a filter chip/toggle for feedback status (e.g. has-notes / done) next to the
>   search input.
>
> **COLLAPSIBLE PROJECT GROUPS**
> - Make each project section header (e.g. "blog 2") a clickable row that collapses/expands all cards
>   in that group.
> - Show a chevron indicator and keep the count badge visible.
> - Add "Expand all / Collapse all" controls near the search bar.
> - Remember collapsed/expanded state in memory during the session.
>
> **POLISH**
> - Keep the dark theme. Add subtle hover states (background lift / border highlight), consistent
>   small-radius corners, and a tighter type scale so it reads intentional, not cramped.
>
> **CONSTRAINTS**
> - Preserve all existing functionality and data (open, delete, version, notes).
> - Change only layout, density, search/filter, and collapse/expand behavior.
> - Show me the result when done.

## Scope notes (for grooming, not changes to the ask)

- `ui`-only: the file is `dashboard.html` (served at `GET /`). No service/API/MCP change — the same
  `GET /api/reviews` payload (`list_reviews()`) feeds it.
- "Keep the dark theme" — the `viewer.html` `:root` + `@media (prefers-color-scheme: dark)` tokens
  are the reference. (Note the dashboard may currently be dark-only; the plan should confirm whether
  it must also support a light pane, or is intentionally dark.)
- Preserve-functionality is load-bearing and explicitly verifiable: open, delete, the revision/
  version badge, and notes must all still work after the redesign.

## Out of scope

- Any change to the service, its API, the MCP wrapper, or `viewer.html`.
- New data/fields, pagination/virtualization, persistent (cross-session) collapse state (the brief
  says **in memory during the session** only).

## Amendments

_None yet._
