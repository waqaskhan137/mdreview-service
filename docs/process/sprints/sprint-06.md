---
id: sprint-06
name: rich-rendering
status: active
start: 2026-06-18
end: 2026-06-25
goal: Render math (KaTeX) and serve attached local/relative images in the viewer, over both HTTP and MCP.
close_review:          # reviews/sprint-06-close-review-YYYY-MM-DD.md — required by G7 before status: closed
---

## Goal

By the end of the sprint, a reviewer opening `/review/{id}` for a math- and image-heavy draft sees
the LaTeX **rendered** (inline `$...$`/`\(...\)`, display `$$...$$`/`\[...\]`, no false positives on
prose `$`) and the draft's local/relative/site-root images **resolve** — because the agent attached
them to the review once (a base64 call over HTTP or MCP, not a blob through `update_source`) and the
service serves them at a stable per-review URL the viewer rewrites `<img src>` to. No CDN, no pip, no
second static server. A draft with neither math nor assets renders exactly as today. The two P0s from
`requirements/rich-rendering.md`; P1/P2 items stay backlog.

## Committed tickets

A ticket counts as committed only when its `sprint:` field points here.

| ID | Title | Layer | Pri | Status |
|----|-------|-------|-----|--------|
| MR-022 | Binary `_read_bytes` + static-route swap; vendor KaTeX; widen `/static/` content-types; render math | ui | P0 | done |
| MR-023 | Per-review asset storage + manifest + `POST/GET /assets`, `GET /asset/{stored}` (base64) | svc | P0 | done |
| MR-024 | MCP `attach_asset` + `list_assets` tools | svc | P0 | done |
| MR-025 | Viewer rewrites local/relative/site-root `<img src>` to served asset URLs | ui | P0 | done |
| MR-026 | Docs sweep: README API table, CLAUDE.md contract, MCP docstring | docs | P1 | done |

The former local-dir `{name,path}` asset-read form is **cut** to backlog (S5); base64 delivers both
P0s. P1 (theme awareness, SVG/animation doc line) and P2 (footnotes, syntax highlighting) are
backlog, not committed.

## Preferred execution order

Accounts for `depends_on`; unblocking + lowest-risk first.

1. **MR-022** — Math (independent, smallest). Introduces `_read_bytes` (B1) that the asset GET reuses.
2. **MR-023** — Asset storage + HTTP routes (independent of MR-022; proven by curl round-trip).
3. **MR-024** — MCP `attach_asset` + `list_assets` (depends on MR-023).
4. **MR-025** — Viewer `<img>` rewrite (depends on MR-023's `GET /assets`).
5. **MR-026** — Docs sweep (depends on all; **not** carry-over eligible per G7).

## Notes / retro

_Filled in as the sprint runs and at close._

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [ ] every committed ticket is `done` or explicitly carried over (a docs-sweep ticket — MR-026 — is
      **not** carry-over eligible; deferred docs are force-closed at close);
- [ ] **no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done`**;
- [ ] a **staff-critic sprint-close review** exists at
      `reviews/sprint-06-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      acceptance criteria; since product pages (`viewer.html`, `static/**`) are touched, it
      rebuilds the container, runs `curl /healthz` + `/api/reviews`, **and** runs
      `scripts/render-smoke.sh` against `/review/{id}` asserting both `.katex` and `#article img`
      (plus the woff2-body + asset-URL byte checks), with a screenshot under
      `reviews/sprint-06-render-evidence-*`;
- [ ] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
