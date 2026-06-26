---
id: MR-072
title: "Operator runbook: `claude setup-token`, `.env`, rotation, startup auth-probe (watcher container)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: docs            # svc | ui | infra | docs
priority: P2           # P0 | P1 | P2 | P3
sprint: sprint-25
epic: watcher-container
depends_on: [MR-071]
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Document the operator setup for the opt-in containerized watcher so a user can stand it up with their
Claude subscription. References GH #30 but does **not** close it (MR-071's working profile already did).

## Acceptance criteria

- [ ] The README "Watcher" runbook documents: (a) the one-time `claude setup-token` mint (subscription,
      not API); (b) `.env` wiring with `CLAUDE_CODE_OAUTH_TOKEN`; (c) token **rotation**; (d) the Linux
      `~/.claude/.credentials.json` **mount alternative** (since macOS stores the token in the Keychain,
      not a mountable file); (e) the explicit warning: the containerized watcher **auto-actions every
      Sent review — local single-user use only** (`WATCH_ARMED_FILE` is the per-review opt-in escape
      hatch); (f) the `docker compose --profile watcher up` command; (g) a **cheap startup auth-probe**
      the operator runs after `up` so an **expired `setup-token` surfaces at deploy time** with a clear
      auth error rather than silently stranding the first Sent review.
- [ ] Never commits or prints a token; the `.env` is gitignored (MR-069).
- [ ] Cross-checks: the README watcher runbook references resolve; no stale "watcher is host-only" claim
      left uncorrected.

## Notes / context

- Epic plan: `epics/watcher-container-plan.md` (MR-072 verification; Phase 4). Docs-only — depends on
  MR-070/MR-071 being real so the recipes match what actually ships.

## Work log

- `2026-06-24` — README "Watcher" runbook: corrected the stale "NOT containerized" claim (it now runs
  host OR opt-in container); added a **"Containerized watcher (opt-in, Claude subscription auth)"**
  subsection covering `claude setup-token`, `.env` wiring, the `--profile watcher up` command, rotation,
  the Linux `~/.claude/.credentials.json` mount alternative + the macOS-Keychain caveat, the
  auto-actions-every-review/local-only warning (with `WATCH_ARMED_FILE` escape), and a startup
  auth-probe for an expired token. References #30 (MR-071 already closed it). Committed on dev.

## Validation

_Verified 2026-06-24 — prose-only; coverage grep + py_compile sanity. PASS._

- Grep the runbook covers (a)–(g) above; the `setup-token`/`.env`/rotation/Linux-mount/auth-probe
  prose reads correctly and the `--profile watcher up` command matches MR-071's compose.
- `python3 -m py_compile app.py watch.py mcp_server.py` (sanity; untouched).

## Follow-ups

- None planned. Closes the operator-facing surface for #30.
