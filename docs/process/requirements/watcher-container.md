---
slug: watcher-container
captured: 2026-06-24
source: this session — product-owner request after discovering the watcher is not part of the deployment (Send-to-agent on a fresh deploy goes nowhere because no watcher runs). GitHub issue #30. The owner pushed back (correctly) that the public/no-auth "blast radius" rationale for keeping the watcher separate does NOT apply to a local single-user tool, and that subscription auth (not API keys) is the only affordable path for most users.
related_epic: epics/watcher-container-plan.md
---

# Opt-in containerized watcher with Claude subscription auth

GH #30. Make the watcher (`watch.py`) an **opt-in** part of the docker deployment, authenticated by
the user's **Claude subscription** (not an API key), so `docker compose --profile watcher up` brings
up the service AND an agent runner that auto-actions reviewer comments.

## Why

The watcher — the process that picks up "Send to agent" and spawns a Claude to action comments — is
not part of the deployment today. After a fresh `docker run`/`compose up`, a human Sends a comment
and nothing picks it up (the #26 cue correctly says "no agent has picked this up — is a watcher
running?"). For a **local, single-user tool**, the public-instance "fail-closed, separate process,
don't auto-run agents on attacker input" rationale does not apply — there are no untrusted commenters.
The watcher should be a first-class, opt-in service. **API billing is a non-starter for most users**,
so subscription OAuth (the `claude` CLI's login) is the required auth path.

## Key findings (planner must verify; grounding for the plan)

1. **Subscription auth across the container boundary is the load-bearing question.** On macOS the
   `claude` CLI stores its OAuth token in the **Keychain**, NOT a mountable file (`~/.claude/` holds
   only settings/history/stats; `~/.claude.json` is config, not the token). So mounting `~/.claude`
   does not carry auth on macOS — a Linux container can't read the Keychain. The portable path is
   **`claude setup-token`** → a **long-lived subscription OAuth token** passed into the container via
   an env var (believed `CLAUDE_CODE_OAUTH_TOKEN`) and/or, on Linux hosts, mounting
   `~/.claude/.credentials.json`. PIN: the exact env-var name `claude` reads for a headless OAuth
   token, that `setup-token` bills against the SUBSCRIPTION (not the API), and the one-time operator
   step to mint it. If it can't be made to work headless, that is a BLOCKER-FOR-HUMAN to surface.
2. **A working host-side prototype already exists** (built + verified this session — actions a comment
   end-to-end in ~24s): a wrapper that interpolates `$REVIEW_ID`/`$MDREVIEW_BASE`/`$MDREVIEW_OWNER`
   into a prompt and runs `claude --mcp-config <cfg> --permission-mode dontAsk --allowedTools
   "mcp__mdreview__*" -p "<prompt>"`, plus an MCP config pointing the agent's mdreview tools at the
   service. Reuse this shape, moved into the repo proper (e.g. a `watcher/` dir, not `.scratch/`).
   Recipe gotcha (MR-063): keep `-p "<prompt>"` LAST so the variadic `--allowedTools` doesn't swallow it.

## Design (planner resolves details + ticket split)

- **Opt-in, off by default:** a separate `docker-compose.yml` service behind a compose `profile` so a
  plain `docker compose up` starts ONLY the service; `--profile watcher up` adds the agent runner.
  Bundling into the DEFAULT deploy is explicitly out of scope.
- **`Dockerfile.watcher`:** Python (for `watch.py` + `mcp_server.py`) PLUS Node + the `claude` CLI;
  copies `watch.py`, `mcp_server.py`, the launch wrapper, and the agent MCP config. The main service
  image stays stdlib-only Python — do NOT add Node to it.
- **Networking:** the watcher reaches the service at `MDREVIEW_BASE=http://mdreview:8080` (compose
  service name = non-loopback), so `WATCH_TRUSTED_BASE` must vouch for that exact base (the fail-closed
  trusted-base check stays). The agent MCP config also points at `http://mdreview:8080`.
- **Auth wiring:** the long-lived subscription token via env (operator-provided `.env` /
  `CLAUDE_CODE_OAUTH_TOKEN`), documented with the one-time `claude setup-token` step. Never commit a
  token; `.env` stays gitignored; document rotation.
- **Keep the launch posture:** `WATCH_LAUNCH_CMD` → the wrapper → `claude --permission-mode dontAsk
  --allowedTools "mcp__mdreview__*" -p "<prompt with $REVIEW_ID>"`.

## Constraints

The service stays stdlib-only Python (Node/claude live ONLY in the watcher image); never break the
existing host-watcher path or the `docker compose up` default (the watcher must be profile-gated OFF);
`py_compile app.py`/`watch.py` gates apply; Europe/London dates; keep the Claude commit trailer.
**NEVER commit credentials/tokens.** The live instance is the `mdreview` container on :8139 (volume
`mdreview-data`) — do not disturb it; build/test on throwaway names/ports, `.scratch/` for temp.

## Validation (infra — the headline gates)

`docker build -f Dockerfile.watcher` succeeds and the image has a working `claude` CLI; **`docker
compose up` (no profile) starts ONLY the service, NOT the watcher** (the opt-in gate); `docker compose
--profile watcher up` starts both and, with a test subscription token, the watcher container picks up
a "Send to agent" and an agent **actions a comment end-to-end** (the host loop, now in-container) —
assert doc changed + comment resolved + turn returned, bounded ~2min. All on throwaway compose project
names/ports, never the live `mdreview`/`mdreview-data`/:8139/:8137. The subscription-token + setup-token
flow is verified or surfaced as a BLOCKER.

## Out of scope

- Bundling the watcher into the DEFAULT deploy (it stays opt-in).
- Public/multi-tenant hardening (the existing fail-closed host watcher remains the public-instance answer).
