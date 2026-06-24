---
id: MR-069
title: "Promote the watcher launch prototype into `watcher/` (+ .env.example, gitignore .env)"
status: ready          # backlog | ready | in-progress | review | done | blocked
layer: infra           # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-25
epic: watcher-container
depends_on: []
created: 2026-06-24
updated: 2026-06-24
---

## Goal

The host-side prototype that drives a Claude agent for a Sent review (verified this session — actions
a comment end-to-end in ~24s) lives in `.scratch/` and must become a real, versioned repo artifact
before it can be baked into an image. This ticket promotes it into a `watcher/` dir, adds a
`.env.example` for the subscription-token wiring, and gitignores `.env` so a real token is never
committed. Independently shippable — host operators benefit immediately.

## Acceptance criteria

- [ ] `watcher/launch.sh` — the launch wrapper: interpolates `$REVIEW_ID`/`$MDREVIEW_BASE`/
      `$MDREVIEW_OWNER` into the agent prompt and runs `claude --mcp-config watcher/agent-mcp.json
      --strict-mcp-config --permission-mode dontAsk --allowedTools "mcp__mdreview__*" -p "<prompt>"`,
      with **`-p "<prompt>"` as the FINAL argv token** (MR-063 gotcha: the variadic `--allowedTools`
      swallows a trailing bare prompt). Executable (`chmod +x`).
- [ ] `watcher/agent-mcp.json` — the agent's MCP config, pointing the mdreview server at
      `http://mdreview:8080` (the compose service name), **not** `localhost:8139`.
- [ ] `.env.example` ships with an **empty** `CLAUDE_CODE_OAUTH_TOKEN=` (template only, no value).
- [ ] `.gitignore` gains `.env` (it currently has only `.scratch/`); confirm no `.env` is tracked.
- [ ] Local validation passes (below).

## Notes / context

- Epic plan: `epics/watcher-container-plan.md` (Watcher section + MR-069 verification). Prototype
  source: `.scratch/agent-launch.sh` + `.scratch/agent-mcp.json` (read both; do not ship from
  `.scratch/`). `--strict-mcp-config` (pinned per G1) makes the agent's tool surface deterministic.
- The `claude` CLI is NOT invoked by this ticket (no image yet) — this is the in-repo asset promotion.

## Validation

_How this was verified._

- `python3 -m py_compile app.py watch.py mcp_server.py` (untouched, sanity).
- `test -x watcher/launch.sh`; structural assert the `-p` prompt is the **last** argv token
  (`grep -nE '(-p|--print)[[:space:]]+"[^"]*"[[:space:]]*$' watcher/launch.sh`) and the negative guard
  that **no flag trails it** (`! grep -nE '(-p|--print)[[:space:]]+"[^"]*"[[:space:]]+--?[A-Za-z]'`).
- `grep -q 'http://mdreview:8080' watcher/agent-mcp.json`.
- Secrets hygiene: `grep -qxF '.env' .gitignore`; `.env.example` ships empty
  (`! grep -qE '=.+' .env.example`); no `.env` tracked.
- Host dry-run: `REVIEW_ID=test1234 MDREVIEW_BASE=http://x:8080 MDREVIEW_OWNER=w bash -n watcher/launch.sh`.

## Follow-ups

- MR-070 bakes these into `Dockerfile.watcher` and proves headless subscription auth.
