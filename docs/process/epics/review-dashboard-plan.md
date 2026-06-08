---
epic: review-dashboard
status: active
created: 2026-06-08
source: requirements/review-dashboard.md
gate: passed 2026-06-08
review: reviews/review-dashboard-plan-review-2026-06-08.md
related_sprints: [sprint-01]
related_tickets: [MR-001, MR-002, MR-003, MR-004, MR-005, MR-006, MR-007]
---

# Review dashboard, provenance, history, sessions, and Google-Docs comments

mdreview-service already persists everything per review (`source.md`, `feedback.md`,
`notes.json`, `meta.json` under `DATA_DIR/{id}`), but there is no way to see what exists, no
record of where a review came from, and no history of past drafts/feedback. This epic adds a
human dashboard at `/`, provenance tagging, lightweight history, session grouping, and
Google-Docs style inline comments in the viewer.

**Source requirement:** [`requirements/review-dashboard.md`](../requirements/review-dashboard.md)
— the original asks, kept verbatim.

## Product goal

A person (or the agent's operator) opens `http://localhost:8137/` and sees every review grouped by
project and session, which file each came from, whether feedback is waiting, and can jump into any
of them. Agents can revisit the full history (past drafts + the feedback each received). Humans
leave feedback as Google-Docs style margin comments anchored to the exact text.

## Core design principle

**Additive and default-safe.** Everything new is optional metadata or an append-only snapshot, so
existing reviews on disk keep working unchanged and a missing file/key preserves today's behavior.
The service stays stdlib-only with zero new dependencies.

## Recommended approach

### Service (`app.py`)
- **Provenance:** `create_review(markdown, title, project="", source_path="", session="")` writes
  the new optional fields into `meta.json`; the `POST /api/reviews` handler reads them from the
  body.
- **List + summary:** a `summary(rid)` helper augments `meta` with `notes_total`,
  `notes_addressed`, `revision`, and a derived `status` (`awaiting` | `feedback` | `resolved`);
  `list_reviews()` scans `DATA_DIR` and sorts by `created` desc; `GET /api/reviews` returns
  `{reviews:[...]}`.
- **Dashboard route:** `/` serves `dashboard.html` for browsers, or the JSON descriptor when the
  request sends `Accept: application/json`; a new `/api` route serves that descriptor too.
- **History:** on `PUT /source`, snapshot the outgoing `source.md` + current
  `notes.json`/`feedback.md` into `{id}/history/round-{N}/` with a `round.json`, bump a `revision`
  counter in `meta.json`; `GET /api/reviews/{id}/history` and `/history/{n}` expose it read-only.

### UI (`dashboard.html`, `viewer.html`)
- **`dashboard.html`** (new): self-contained, matching `viewer.html`'s aesthetic; groups
  Project > Session > files; each card shows title, source path, relative created time, note-count
  badge, status pill, revision badge; actions Open + Delete.
- **`viewer.html`:** replace the collapsible dock/panel with always-visible right-gutter comment
  cards anchored to their text; wrap the exact quoted span in a highlight; click syncs highlight
  <-> card; below ~820px collapse back to the current panel/dock. Add a minimal read-only history
  view.

## Rollout phases

### Phase 1 — service foundation
Provenance fields, list/summary endpoint, dashboard route + `/api` descriptor, history snapshots.
Each independently smoke-testable with curl.

### Phase 2 — UI
The dashboard page, then the viewer's gutter comments + history view, consuming Phase 1 endpoints.

### Phase 3 — docs
Document the new fields, list/history endpoints, and the dashboard; sketch the deferred MCP wrapper.

## Non-goals

- **MCP wrapper.** Out of scope; the HTTP contract is MCP-ready and a thin wrapper is a clean
  separate deliverable. Documented as a follow-up in `docs/future-mcp.md` and `backlog.md`.
- **Full history timeline / diffing UI.** History is lightweight snapshots + a read-only view, not
  a diff timeline.
- **Auth.** Unchanged; the service stays trust-the-network, id-only tenancy.

## Key constraints

- **Stdlib-only, zero pip.** No new runtime dependency. `dashboard.html` uses no external assets.
- **Back-compat.** Existing reviews lack the new `meta.json` keys; all readers default missing
  keys. New POST fields are optional; untagged reviews group under "Ungrouped".
- **No route shadowing.** New routes slot into `route()` without shadowing existing ones; ids stay
  within `[A-Za-z0-9]{4,40}`.
- **JS-rendered pages.** `ui` validation must open the page in a browser, not just curl a 200.
- **Exposure note.** `GET /api/reviews` and the dashboard list across all reviews; acceptable for
  the trusted-network posture, but call it out in docs.

## Preferred execution order

1. MR-001 (provenance) -> 2. MR-002 (list/summary) -> 3. MR-003 (dashboard route) ->
4. MR-005 (history) -> 5. MR-004 (dashboard UI) -> 6. MR-006 (viewer comments + history view) ->
7. MR-007 (docs). Service endpoints precede the UI that consumes them; history (MR-005) lands
before the dashboard so the revision badge has data.

## Ticket breakdown

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-001 | Persist provenance (`project`/`source_path`/`session`) on POST + meta | svc | 1 |
| MR-002 | `summary()` + `list_reviews()` + `GET /api/reviews` | svc | 1 |
| MR-003 | Serve dashboard at `/`; move JSON descriptor to `/api` | svc | 1 |
| MR-005 | History snapshots on PUT + `/history` routes | svc | 1 |
| MR-004 | `dashboard.html`: Project>Session grouping, status pills, open/delete, revision badge | ui | 2 |
| MR-006 | `viewer.html`: Google-Docs gutter comments + minimal history view | ui | 2 |
| MR-007 | Docs: provenance/list/history fields + `docs/future-mcp.md` | docs | 3 |

## Risks and mitigations

- **Route ordering / shadowing** when inserting `/`, `/api`, `/history`. Mitigation: match
  `/api` and `/history/{n}` before broader patterns; smoke every existing endpoint after.
- **Exact-span highlight across inline tags** (MR-006) is the fiddliest piece. Mitigation: walk
  the block's text nodes and wrap the matching range; whole-block notes keep the block highlight;
  fall back to block highlight if the span is not found.
- **History write volume.** Snapshotting on every `POST /feedback` would explode (auto-save per
  keystroke); snapshot only on `PUT /source` (one round per agent revision).

## Verification

Per the process G7 render-smoke. Highlights:
- `POST /api/reviews` with `project`/`session`/`source_path` -> `GET /api/reviews` shows them
  plus `notes_total`/`status`.
- `/` renders the dashboard in a browser, grouped Project > Session; pre-existing reviews appear
  under "Ungrouped".
- `PUT /source` then `GET /history` lists a round; the viewer shows gutter comments with
  exact-span highlights and stacks overlapping cards; below ~820px the panel returns.
- Back-compat: `curl -H 'Accept: application/json' /` and `/api` both return the descriptor JSON.
