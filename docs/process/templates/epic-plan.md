---
epic: <epic-slug>
status: draft          # draft | active | done  (stays draft until G1 passes)
created: YYYY-MM-DD
source:                # requirements/<slug>.md — the verbatim brief this groomed from
gate: G1 not passed    # G1 (Plan Gate): not passed | passed YYYY-MM-DD — tickets blocked until passed
review:                # reviews/<slug>-plan-review-YYYY-MM-DD.md once reviewed
related_sprints: []    # [sprint-01]
related_tickets: []    # [MR-001, MR-002] — empty until G1 passes and tickets are created
---

# <Epic Name> Plan

One paragraph: what this epic is and why it matters now.

**Source requirement:** [`requirements/<slug>.md`](../requirements/<slug>.md) — the original
brief, kept verbatim.

## Product goal

The user/product outcome. The "done" state at the epic level.

## Core design principle

The one idea that keeps the design coherent — the constraint everything else serves.

## Recommended approach

The shape of the solution, split by area where useful.

### Service (`app.py`)
- …

### UI (`viewer.html` / `dashboard.html` / `static/`)
- …

## Rollout phases

Deliver in phases so each is shippable and the next builds on it.

### Phase 1 — <foundation>
- …

## Non-goals

Explicit scope boundaries — what this epic is deliberately **not** doing.

- …

## Key constraints

Hard rules the implementation must not violate.

- …

## Preferred execution order

1. …

## Ticket breakdown

How this epic decomposes into tickets (create them in `tickets/` after G1, then link here).

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-000 | … | svc | 1 |
