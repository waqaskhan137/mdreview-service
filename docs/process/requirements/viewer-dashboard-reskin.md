---
slug: viewer-dashboard-reskin
captured: 2026-06-25
source: user request 2026-06-25 (waqas) — follow-up to the landing-page swap (commit 0e83ec8 on feat/ui-updates); "plan to do the same for the viewer and dashboard". Full feature-cycle, scope clarified via two follow-up questions (below).
related_epic: epics/viewer-dashboard-reskin-plan.md
---

# Re-skin the viewer and dashboard to the new mockup

Verbatim ask. Do not edit; append dated notes under Amendments if the requirement changes.

> Now i want you to plan to do the same for the viewer and dashboard as well and the
> mockup file is in downloads too by the name mdreview-dashboard-update.html

Preceding context (the "same" refers to this): the landing page was just swapped to its own
standalone design bundle.

> There is this file downloaded in Downloads mdreview - landing (standalone).html and i want you
> to use this design as it is for the landing page.

## Scope decided with the user (two follow-up questions, 2026-06-25)

The viewer and dashboard are **live app screens wired to the API** (markdown/KaTeX/mermaid render,
comments CRUD, turn baton, live-reload, staleness timer) — unlike the static landing page, they
**cannot** be shipped as the React bundle as-is without breaking functionality. So "the same"
means: treat the mockup as a **visual spec** and re-skin the existing files **in place**, keeping
the buildless / stdlib / static-file-served architecture and rewiring the existing JS to the new
DOM. Shipping the React bundle as the actual app is explicitly **off the table**.

**Q1 — Fidelity / net-new functionality → answer: "Re-skin + supported IA".**
Match the mockup's look AND its new information architecture, **but only where the existing API
already supports it**.
- In scope: the dashboard's left sidebar with Inbox filters (All reviews / Needs you / Agent
  working / Resolved) driven by the existing turn baton + status that already flow through
  `GET /api/reviews`; the sidebar projects list; restyled review cards with turn-baton status
  badges (Your turn / Agent working / Waiting for agent / Resolved); the viewer's restyled top
  bar/breadcrumb, "Your turn" baton banner with Send-to-agent, numbered markdown lines, and the
  right-hand threaded COMMENTS panel; the bottom-right open/resolved/history bar.
- Out of scope: any affordance needing new backend work — notably the mockup's live
  "agent watcher · connected" indicator has **no backing** and should be dropped or stubbed, not
  built.

**Q2 — How far to take it → answer: "Run the full feature-cycle"** (plan → G1 → tickets → sprint
→ implement → G7 → PR; human stop only at the G8 merge).

## Design source

Bundler-export mockup, gitignored at `.scratch/mockup-viewer-dashboard.html` (copied from
`~/Downloads/mdreview-dashboard-update.html`). It is a self-extracting React design export — a
**visual spec only**, not code to ship. Render it locally to view it: serve the file over
`python3 -m http.server` and open it; the dashboard view is the landing card grid, and clicking a
review card routes to the viewer view.

## Hard constraints to preserve (footguns)

- Buildless and stdlib-only — no pip, no bundler, no build step. `app.py` serves both files via
  `_read`.
- The viewer's ~599 lines of inline JS are **load-bearing**: markdown + KaTeX + mermaid render,
  comments CRUD, turn baton, live-reload poll, and the `STALE_S` staleness timer.
- The viewer's `STALE_S` MUST stay in sync with `app.py:57` (single source of truth comment) — the
  two move together.
- "A 200 is not a render" — verify both screens in a real browser, not by status code.
- Preserve `Europe/London` date handling.
- Keep the `Co-Authored-By: Claude` commit trailer.
- Validation gate: `python3 -m py_compile app.py` + a browser render of both screens
  (`scripts/render-smoke.sh` DOM assertions for `ui` tickets).

## Amendments

(none)
