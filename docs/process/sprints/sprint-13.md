---
id: sprint-13
name: legacy-feedback-retire
status: active
start: 2026-06-19
end: 2026-06-22
goal: Retire the frozen POST /feedback write surface (→ 410 Gone) and the feedback_updated write, landing app.py + the agent docs together, while leaving every reader and all live data untouched.
close_review:          # reviews/sprint-13-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

The no-auth service no longer exposes a write endpoint that nothing writes to, and no doc tells an
agent to poll a signal the viewer stopped bumping in MR-036. By the end date: `POST /feedback`
returns `410 Gone` (no write), `create_review` no longer seeds `feedback_updated`, and the
"human is done" guidance in `CLAUDE.md`/`AGENTS.md`/`docs/future-mcp.md` watches
`comments_updated`. **Success is measured by what does NOT change:** all 45 live reviews keep their
derived status (the `summary()` guard stays, holding the 31 new/empty reviews in `awaiting`), the
dashboard keeps sorting, and `GET /feedback`/`GET /history` still return every persisted note. Zero
data lost; zero read behaviour changed.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-046 | Retire dead `POST /feedback` write (→ 410 Gone) + `feedback_updated` bump/initialiser; keep every reader | svc | P2 | done |
| MR-047 | Docs sweep: "human is done" → `comments_updated`; drop `POST /feedback` README row; fix `future-mcp.md:61` | docs | P2 | done |

## Preferred execution order

Dependencies: MR-047 `depends_on: [MR-046]` (docs must not describe a route whose behaviour hasn't
changed yet). Svc-before-docs.

1. MR-046 — svc cut (`app.py`): POST write body → 410, remove `bump` + `create_review` initialiser,
   update in-file docstring line. `py_compile` + behavioural curls.
2. MR-047 — docs sweep (`CLAUDE.md`, `AGENTS.md`, `README.md`, `docs/future-mcp.md`). The
   non-carry-over same-sprint docs obligation for MR-046's behaviour change.

## Notes / retro

_Filled in as the sprint runs and at close._

- **G7 evidence owed is reduced:** this sprint touches **no product page** (`viewer.html` /
  `dashboard.html` / `static/**` unchanged — `dashboard.html` is *read* by the design but not
  edited), so per the G7 pass-condition row the close review owes the **container rebuild +
  `curl /healthz` + `curl /api/reviews`** smoke, **not** a `scripts/render-smoke.sh` per-page DOM
  assertion or screenshot. Stated here so the G7 reviewer does not flag a missing render-smoke as
  non-compliance.
- "Land together" (the brief's atomicity constraint) is satisfied at **sprint** granularity (both
  tickets here, svc-before-docs), not commit granularity — single-deploy/no-CD, so the inter-ticket
  window is internal-only.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (note where) — **MR-047 is a
      docs-sweep, NOT carry-over eligible** (must be `done` before close);
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-13-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      acceptance criteria, **including the container-rebuild + `curl /healthz` + `/api/reviews`
      smoke** (no per-page render-smoke owed — no product page touched), and its findings are
      resolved or carried;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
