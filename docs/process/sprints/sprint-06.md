---
id: sprint-06
name: rich-rendering
status: closed
start: 2026-06-18
end: 2026-06-18
goal: Render math (KaTeX) and serve attached local/relative images in the viewer, over both HTTP and MCP.
close_review: reviews/sprint-06-close-review-2026-06-18.md   # G7 staff-critic PASS, resolved
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

- `2026-06-18` — All 5 committed tickets shipped same-day, in order (MR-022 → MR-026), each
  validated from a **rebuilt throwaway container on :8138** (never `docker compose` / the live :8139).
- `2026-06-18` — **The sprint's defining discovery (MR-022):** the plan's KaTeX **auto-render
  post-pass** could not meet the brief. G4 validation proved two independent blockers — `marked`
  strips the backslashes off `\(…\)`/`\[…\]` before any post-pass, and auto-render pairs prose
  dollars (`$5 and $10` rendered as math). Resolved by switching the *integration* (not the engine)
  to a **marked extension** that tokenizes math during the parse: all four delimiters render, prose/
  currency/lone/`code` `$` stay literal. This is the G4 re-open the plan explicitly anticipated —
  documented in MR-022's Work log, not a silent swap. `auto-render.min.js` was vendored then dropped.
- `2026-06-18` — Two plan/AC verification commands were wrong about this server and got corrected in
  the tickets: `curl -sI` (HEAD) returns 501 here (no `do_HEAD`) → MIME checks use a GET header-dump;
  `render-smoke.sh` has no descendant combinator → `#article img` becomes the `img` tag selector.
  Both are verification-method fixes; the features are correct on the paths browsers actually use.
- `2026-06-18` — **Closed at G7: staff-critic PASS** (`reviews/sprint-06-close-review-2026-06-18.md`,
  resolved). 0 blockers, 0 shoulds, 2 NITs. NIT 1 (asset ctype from attacker-controllable `name`)
  addressed with `nosniff` + a no-auth doc note; NIT 2 (smoke selector) accepted as a pre-existing
  harness limitation. Critic reproduced every ticket's AC from the rebuilt container.
- **Carry-overs:** none. All 5 tickets `done`; the docs sweep (MR-026, not carry-over-eligible) is
  `done`. Cut/deferred (not carried, by design): the local-dir `{name,path}` asset-read form (S5),
  and the P1/P2 backlog items (theme awareness, footnotes, syntax highlighting).
- **Retro:** the planner + G1 critic loop paid off — the binary-read B1 catch (the static route
  would have 500'd on every font) and the `%2F`-stored-name decoupling (S4) both came from G1 and
  were correct. The one thing G1 couldn't catch was the math-integration mechanism (it needed a
  running browser + marked to surface), which is exactly why G4 render-validation exists; the plan's
  pre-armed MathJax-fallback clause turned out unnecessary because the fix was an integration change,
  not an engine change.

## Close gate (G7)

The sprint cannot be marked `closed` until:

- [x] every committed ticket is `done` or explicitly carried over (a docs-sweep ticket — MR-026 — is
      **not** carry-over eligible; deferred docs are force-closed at close);
- [x] **no committed ticket has docs deferred to a docs-sweep ticket that is not yet `done`**;
- [x] a **staff-critic sprint-close review** exists at
      `reviews/sprint-06-close-review-YYYY-MM-DD.md`, verifying shipped work against each ticket's
      acceptance criteria; since product pages (`viewer.html`, `static/**`) are touched, it
      rebuilds the container, runs `curl /healthz` + `/api/reviews`, **and** runs
      `scripts/render-smoke.sh` against `/review/{id}` asserting both `.katex` and `#article img`
      (plus the woff2-body + asset-URL byte checks), with a screenshot under
      `reviews/sprint-06-render-evidence-*`;
- [x] retro + carry-overs are recorded above, and `close_review:` is set in frontmatter.
