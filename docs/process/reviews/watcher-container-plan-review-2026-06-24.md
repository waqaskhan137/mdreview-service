---
review_of: epics/watcher-container-plan.md
gate: G1
reviewer: staff-critic
independent: true
verdict: GO-WITH-NITS
status: resolved
date: 2026-06-24
---

# G1 review — watcher-container plan

Independent staff-critic review of the `watcher-container` epic plan (GH #30). Reviewer is not the
author (the `mdreview-planner` authored and revised; the orchestrator implements). One round.

## Verdict: GO-WITH-NITS — no blocking findings.

The load-bearing unknown (in-container subscription auth) is correctly isolated and gated at MR-070.
Every structural claim verified against the repo + installed CLI holds:

- **Auth path confirmed real, not asserted.** `~/.claude/.credentials.json` absent on this Mac
  (Keychain storage); `~/.claude.json` is config. `claude setup-token --help` says *"requires Claude
  subscription"* (subscription-billed, not API). `CLAUDE_CODE_OAUTH_TOKEN` appears 110× in the native
  binary alongside `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`. `--permission-mode dontAsk`,
  `--mcp-config`, `--strict-mcp-config`, `-p/--print` all exist.
- **`watch.py` cites accurate:** trusted-base exact-match (`:227`), launch gate (`:258`),
  arming hinge (`:144`/`:199`), child-env contract `REVIEW_ID`/`MDREVIEW_BASE`/`MDREVIEW_OWNER`
  (`:495-498`). Arming-off + vouched-base auto-actions every `turn==agent` review — the C2 baseline,
  the right local-use default (product owner waived blast-radius for local single-user use).
- **Scope/hygiene:** main `Dockerfile` is `python:3.12-slim` (no Node — stays untouched);
  `.gitignore` lacks `.env` (adding it a hard AC); last ticket MR-068 → MR-069+ correct.

## Findings + resolution

| # | Sev | Finding | Resolution (planner revision, 2026-06-24) |
|---|-----|---------|-------------------------------------------|
| 1 | worth-fixing | **MR-070 first-run-trust gap.** A fresh container's CWD + empty `~/.claude` isn't pre-trusted, so a bare `claude -p … dontAsk` may hang on the workspace-trust dialog and look like an auth failure (or `dontAsk` papers it over un-generalizably). | **Folded.** MR-070 now runs the REAL launch flag shape (`--mcp-config --strict-mcp-config --permission-mode dontAsk -p` last) as the runtime non-root user with a writable `$HOME`, bakes a trusted-CWD settings file to settle the dialog headlessly, and `timeout`-boxes the run so a trust hang (exit 124) is distinguishable from an auth error. |
| 2 | worth-fixing | MR-070 proved only a plain prompt, not the `--mcp-config` MCP round-trip — a second unproven delta folded silently into MR-071. | **Folded.** MR-070 adds a first MCP round-trip proof (agent calls one mdreview tool against a throwaway service); `--strict-mcp-config` pinned in the wrapper for a deterministic tool surface. |
| 3 | worth-fixing | `depends_on: [mdreview]` orders start, not readiness → watcher polls before the listener is up. | **Folded.** MR-071 uses `depends_on: { mdreview: { condition: service_healthy } }` (main image's `Dockerfile:15` HEALTHCHECK), with an AC asserting it. |
| 4 | worth-fixing | Proof should run as the image's real runtime user (writable `$HOME`), not root. | **Folded** into MR-070's check. |
| 5 | nit | Runbook should startup-probe an expired token (surface at `up`, not as a stranded review); #30 should close on the working profile merge. | **Folded.** MR-072 runbook gains a startup auth-probe; **MR-071** (the working profile) now owns the GH #30 close. |
| 6 | nit | MR-069 grep coupled to the `$PROMPT` var name. | **Folded.** Replaced with a structural "`-p` prompt is the final argv token (MR-063)" assertion. |

All findings resolved in the plan revision. G1 cleared. The make-or-break (in-container headless
subscription auth) remains correctly gated at MR-070 before any compose work depends on it.
