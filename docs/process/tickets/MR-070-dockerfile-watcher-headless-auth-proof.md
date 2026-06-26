---
id: MR-070
title: "`Dockerfile.watcher` (Node + python3 + claude CLI) + headless subscription-auth proof (the gate)"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: infra           # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-25
epic: watcher-container
depends_on: [MR-069]
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Build the watcher image and **prove the one make-or-break unknown**: that a `claude setup-token`
subscription token (`CLAUDE_CODE_OAUTH_TOKEN`) actually authenticates a **headless `claude` inside a
no-keychain Linux container** — using the REAL launch flag shape, with the fresh-container
workspace-trust dialog settled, run as the image's actual runtime user. This gate retires the auth +
trust + first-MCP-round-trip risks **before** MR-071 builds compose on top, so MR-071's failure
surface is compose wiring alone. If the in-container auth cannot be made to work headless, escalate
with the exact `claude` error — do not paper over it.

## Acceptance criteria

- [ ] `Dockerfile.watcher`: base with **python3** (for `watch.py`/`mcp_server.py`) **plus Node + the
      `claude` CLI** (`@anthropic-ai/claude-code`, pinned version); copies `watch.py`, `mcp_server.py`,
      `watcher/launch.sh`, `watcher/agent-mcp.json`. **The main service `Dockerfile` stays
      stdlib-only Python — Node/claude live ONLY here.**
- [ ] The image **pre-trusts the working dir** (a baked `--settings`/settings file marking the CWD
      trusted, or the CLI's documented headless-trust mechanism) so a fresh-container run does not hang
      on the workspace-trust/onboarding dialog.
- [ ] The image runs as a **non-root runtime user with a writable `$HOME`** (`claude` may need
      `~/.claude` scratch even with an env token).
- [ ] `docker build -f Dockerfile.watcher` succeeds; `claude --version` and `python3 --version` run in
      the image.
- [ ] **Auth proof (the gate):** with `CLAUDE_CODE_OAUTH_TOKEN` from operator env (no keychain, no
      interactive login), the REAL flag shape (`--mcp-config --strict-mcp-config --permission-mode
      dontAsk -p` last) returns a subscription-billed reply, **`timeout`-boxed** so a trust hang
      (exit 124) is distinguishable from a fast auth error.
- [ ] **MCP round-trip proof (the gate):** against a throwaway service container on a private network,
      the agent calls **one** read-only mdreview tool (`list_reviews`) and reports a count — proving the
      in-image `mcp_server.py` spawns under `claude` and reaches the service headless.
- [ ] No token committed or printed at any step.

## Notes / context

- Epic plan: `epics/watcher-container-plan.md` (MR-070 verification — the two gating proofs + the
  trust-dialog reasoning; Risks rows for the auth/trust/MCP unknowns).
- **Human dependency:** the auth proof needs a real `setup-token` (`TEST_TOKEN`). The operator runs
  `claude setup-token` once and supplies it at test time via env/gitignored file — never committed,
  never echoed. If unavailable, the ticket parks pending the token.
- Verified pre-build (G1): `setup-token --help` = "requires Claude subscription"; `CLAUDE_CODE_OAUTH_TOKEN`
  is the headless env var; `--strict-mcp-config`/`--permission-mode dontAsk` exist.

## Work log

- `2026-06-24` — `Dockerfile.watcher`: `node:20-bookworm-slim` base + `apt` python3 + `npm i -g
  @anthropic-ai/claude-code@2.1.190`; copies `watch.py`/`mcp_server.py`/`watcher/`; non-root user
  `watcher` (uid 10001) with writable `$HOME=/home/watcher`; bakes `~/.claude.json` pre-accepting
  workspace-trust + onboarding for `/app` so a headless `claude -p` doesn't hang on the trust dialog.
  The main `Dockerfile` is untouched (stays stdlib-only Python, no Node). Committed on dev.

## Validation

_Verified 2026-06-24 (G4) — all on throwaway names/networks, never the live `mdreview`/:8139/:8137.
**Both gating proofs PASS.** (Subscription token supplied by the operator via `claude setup-token` →
gitignored `.scratch/.test-token`, never committed/printed.)_

- `docker build -f Dockerfile.watcher -t mdreview-watcher:test .` → success. `claude --version` →
  `2.1.190`; `python3 --version` → 3.11.2; `id` → `uid=10001(watcher)` (non-root); `$HOME` writable +
  `~/.claude.json` present.
- **Auth proof (the gate):** `docker run -e CLAUDE_CODE_OAUTH_TOKEN=… claude --mcp-config … --strict-mcp-config
  --permission-mode dontAsk -p "Reply … OK."` → **exit 0, "OK"**. (An earlier expired short-lived
  keychain token gave a fast `exit 1 / 401` — proving the failure mode is cleanly distinguishable from
  a trust hang, and that the durable `setup-token` is the right artifact.)
- **MCP round-trip proof (the gate):** throwaway `mdreview` service on a private docker network
  (alias `mdreview`, not the live container); agent `--mcp-config watcher/agent-mcp.json` called
  `list_reviews` → **exit 0, reported `0`** (fresh container). The in-image `mcp_server.py` spawns
  under `claude` and reaches the service headless. Clean teardown (no leftover container/network).

### Owed at G7 (re-drive against a fresh build)

- `python3 -m py_compile app.py watch.py mcp_server.py`.
- `docker build -f Dockerfile.watcher -t mdreview-watcher:test .`; `docker run --rm … claude --version`
  / `python3 --version` / `id` (runtime user).
- Auth proof: `timeout 60 docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN=$TEST_TOKEN mdreview-watcher:test
  claude --mcp-config /app/watcher/agent-mcp.json --strict-mcp-config --permission-mode dontAsk -p
  "Reply with the single word OK."` → reply contains OK, exit 0. (exit 124 = trust hang to fix; fast
  non-zero = auth path broken → escalate.)
- MCP round-trip: throwaway `mdreview-service` container on a private network; agent calls
  `list_reviews` and reports a count.

## Follow-ups

- On PASS: MR-071 adds the compose profile + end-to-end. On FAIL: escalate the exact `claude` error;
  the documented fallback is mounting `~/.claude/.credentials.json` on Linux hosts (MR-072 docs it).
