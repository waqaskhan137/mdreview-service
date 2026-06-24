---
slug: watcher-ux-fixes
captured: 2026-06-24
source: this session — two fixes surfaced while the product owner tested the watcher live. MR-062 supersedes MR-061 (product-owner feedback); MR-063 fixes GH #25.
related_epic: epics/watcher-ux-fixes-plan.md
related_issues: ["#25", "#27"]
---

# Watcher UX fixes (batch)

A small two-ticket batch of fixes found while testing the watcher end-to-end. Both are low-risk and already validated.

## MR-062 (ui) — replace the working-banner animation with a visible loading SPINNER, broadened to both agent-turn waiting states

**Why.** MR-061 (sprint-21, shipped) added a subtle opacity-pulsing ellipsis scoped ONLY to the narrow `working` state. The product owner tested it and it failed the goal: (a) too subtle to read as "loading", and (b) it missed the most common waiting moment — the **"Sent — waiting for an agent to pick this up"** state (seen right after pressing Send, before any agent claims the lease) was static. This supersedes MR-061's pulse.

**The change (already implemented + product-owner-eyeballed + deployed to :8139; lives in a git stash).** `viewer.html` only:
- Remove MR-061's `#turnbanner.working #turntext::after` opacity-pulse + the `turnworking` keyframes.
- Add a CSS rotating spinner `#turnbanner.loading #turntext::before` — an 11px ring, `border:2px solid var(--muted)` with `border-top-color:transparent`, `animation:turnspin .8s linear infinite`, `@keyframes turnspin{to{transform:rotate(360deg)}}`.
- `renderBanner` removes a `loading` class at the top and ADDS it in BOTH agent-turn waiting arms — the `if(!as)` "waiting for pickup" arm AND the genuine "Agent is working…" arm — but NOT the stale "may have stopped" arm.
- `@media (prefers-reduced-motion:reduce)` shows a static ring (no spin). Theme-coloured via `--muted` (reads both panes).

**Validation (ui → render-smoke from a rebuilt throwaway image, scratch port, never 8139/8137):** `.loading` present in the "waiting for pickup" AND "working" states; ABSENT in the stale state and on a reviewer turn; reduced-motion probe `getComputedStyle($("#turntext"),'::before').animationName` = `none` under reduce, `turnspin` without; both-pane screenshots. Evidence under `reviews/sprint-22-render-evidence-2026-06-24/`.

## MR-063 (docs) — fix the watcher runbook recipe arg order (GH #25)

**The bug.** MR-060's runbook recipe `["claude","-p","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","<prompt>"]` is wrong: `--allowedTools` is **variadic** (a space-separated tool list), so it swallows the trailing `<prompt>` as another tool name → `claude` errors "Input must be provided … when using --print", the agent dies, the review strands.

**The fix (verified `exit 0`).** Reorder so the prompt is LAST, after the variadic flag: `["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]`. Fix BOTH the scoped recipe in `README.md` and `CLAUDE.md` "Watcher" runbook spots; add a one-line note: "`--allowedTools` is variadic — keep `-p \"<prompt>\"` last so the prompt isn't consumed as a tool name." Verify the full-autonomy recipe (`["claude","--dangerously-skip-permissions","-p","…"]` — prompt already last, likely fine). docs-only, no code/render change.

**Validation.** `python3 -m py_compile app.py` (sanity, unchanged) + grep the recipes to confirm the corrected order. The corrected recipe was runtime-verified (a stub `claude … -p "Reply with exactly: OK"` returned `exit 0, stdout OK`). GH #25 is closed after the PR is updated.

## Out of scope

- The rest of #27 (behind-the-scenes progress steps, streamed/diff-animated document updates) stays in #27.
- Watcher observability / resilience (the watcher exiting on a server restart instead of backing off) stays in #26.
