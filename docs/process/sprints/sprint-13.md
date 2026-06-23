---
id: sprint-13
name: legacy-feedback-retire
status: closed
start: 2026-06-19
end: 2026-06-22
goal: Retire the frozen POST /feedback write surface (→ 410 Gone) and the feedback_updated write, landing app.py + the agent docs together, while leaving every reader and all live data untouched.
close_review: reviews/sprint-13-close-review-2026-06-19.md   # G7 PASS (staff-critic, independent rebuild + smoke)
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

**Closed 2026-06-19 — G7 PASS** (`reviews/sprint-13-close-review-2026-06-19.md`, staff-critic,
independent: rebuilt the image + re-ran the full behavioural smoke, byte-compared every reader
region against `e091509^`). Both committed tickets `done`; **no carry-overs.**

- **Shipped:** MR-046 (svc — `POST /feedback` → `410 Gone` with no write/`bump`; dropped the
  `feedback_updated` initialiser; every reader byte-unchanged) + MR-047 (docs — "human is done" →
  `comments_updated` in CLAUDE.md/AGENTS.md, dropped the README POST row, fixed `future-mcp.md:61`).
  No `mcp_server.py` change (its `get_status` already leads with `comments_updated`) → no MCP
  reconnect owed; the planned third ticket was dropped at G1.
- **What went well:** the live-volume check (memory `legacy-notes-feedback-load-bearing`) kept the
  read path intact — 31 empty reviews stay `awaiting`, 61 notes/feedback files untouched. G1 caught a
  factually-wrong design-fork table (the guard protects Pop B / new-empty reviews, not the 12 `fu>0`
  ones) before it became a wrong AC; the corrected AC tests a fresh review derives `awaiting`.
- **G7 evidence owed was reduced** (recorded pre-review so the critic didn't flag it): no product
  page touched (`viewer.html`/`dashboard.html`/`static/**` unchanged — `dashboard.html` is *read* by
  the design, not edited), so the close owed the **container rebuild + `curl /healthz` +
  `/api/reviews`** smoke, not a per-page render-smoke/screenshot. Evidence:
  `reviews/sprint-13-close-smoke-2026-06-19.txt`.
- **"Land together"** (the brief's atomicity constraint) was satisfied at **sprint** granularity
  (both tickets here, svc-before-docs), not commit granularity — single-deploy/no-CD, so the
  inter-ticket window was internal-only.
- **G7 NITs (both discharged at close):** sprint `status`/`close_review`/retro were the actions the
  PASS authorized (now set); the smoke-evidence `.txt` lives at repo-root `reviews/` per existing
  convention (audit files too), cross-linked in the close review — no action.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (note where) — MR-046 + MR-047
      both `done`; no carry-overs (MR-047 docs-sweep closed in-sprint as required);
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-13-close-review-2026-06-19.md`, verifying shipped work against each ticket's
      acceptance criteria, **including the container-rebuild + `curl /healthz` + `/api/reviews`
      smoke** (no per-page render-smoke owed — no product page touched) — **G7 PASS**, NITs discharged;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
