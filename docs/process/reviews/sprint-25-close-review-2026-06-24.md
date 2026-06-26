---
review_of: sprint-25
gate: G7
reviewer: staff-critic
independent: true
verdict: PASS
date: 2026-06-24
epic: watcher-container
github: "#30"
---

# Sprint-25 close review (G7) — watcher-container

Independent G7 close review. Each ticket re-driven from a fresh build against its acceptance
criteria; the two gating proofs (headless subscription auth, MCP round-trip) and the compose
end-to-end were re-run, not taken on report. All container work on throwaway
names/networks/ports; the live `mdreview`/:8139/`mdreview-data` were never touched and are intact.
No token value was printed or stored; outputs scrubbed of `sk-ant-…`.

**Verdict: G7 PASS (ships).** All four tickets meet their ACs. One worth-fixing doc defect
(the Linux credentials-mount alternative is unverified and its `:ro` flag is suspect) and a few
nits — none blocking.

---

## Per-ticket results

### MR-069 — promote watcher assets into `watcher/` — PASS

| AC | Result | Evidence |
| --- | --- | --- |
| `watcher/launch.sh`, `-p` final argv, executable | PASS | `test -x` ok; `-p "$PROMPT"` is the last token; negative-guard grep finds no flag after it |
| `watcher/agent-mcp.json` → `http://mdreview:8080` | PASS | `grep 'http://mdreview:8080'` matches; not `localhost:8139` |
| `.env.example` empty `CLAUDE_CODE_OAUTH_TOKEN=` | PASS | no `=value` line |
| `.env` gitignored, none tracked | PASS | `.env` in `.gitignore`; `git ls-files` shows no `.env` |

Scope is clean: the four sprint-25 commits touch only `.env.example`, `.gitignore`,
`Dockerfile.watcher`, `README.md`, `docker-compose.yml`, `watcher/agent-mcp.json`,
`watcher/launch.sh`. `app.py` and the main `Dockerfile` are untouched (`git diff --name-only
32f716f..8af6f74 -- app.py Dockerfile` is empty).

### MR-070 — `Dockerfile.watcher` + headless subscription-auth proof (the gate) — PASS

| AC | Result | Evidence |
| --- | --- | --- |
| `docker build -f Dockerfile.watcher` succeeds | PASS | built `mdreview-watcher:g7` clean |
| python3 + Node + pinned claude in image | PASS | `claude --version` = `2.1.190` (pinned in Dockerfile); `python3 --version` = 3.11.2 |
| Non-root, writable `$HOME` | PASS | `id` = `uid=10001(watcher)`; `$HOME=/home/watcher` writable; baked `~/.claude.json` present |
| Main `Dockerfile` stays stdlib-only Python, no Node | PASS | unchanged: `FROM python:3.12-slim`, no Node |
| **Auth proof (gate)** | PASS | real flag shape, token from gitignored file, no keychain → **exit 0, "OK"** |
| **MCP round-trip (gate)** | PASS | throwaway service aliased `mdreview` on a private net; agent called `list_reviews` → **exit 0, reported `0`** |
| No token committed/printed | PASS | commit + tree scan finds no `sk-ant-`; all runs piped the token from `.scratch/.test-token`, scrubbed |

Failure mode is cleanly distinguishable from a trust hang, as the ticket claims: an **invalid**
token gives a fast `exit 1 / 401 Invalid bearer token` (not a timeout). The unresolvable MCP host
in the pure-auth run did not hang — `--strict-mcp-config` + `dontAsk` degrade cleanly.

### MR-071 — compose `watcher` profile (opt-in, health-gated) + end-to-end — PASS

| AC | Result | Evidence |
| --- | --- | --- |
| `watcher` under `profiles:[watcher]`, off by default | PASS | `config --services` (no profile) → `mdreview` only; `--profile watcher` → `mdreview` + `watcher` |
| **Behavioral** default `up` excludes watcher | PASS | default `up -d` running services = `mdreview` only; `watcher` not even created (`ps -a --services` count 0) |
| `depends_on: service_healthy` | PASS | declared against the main image `HEALTHCHECK` |
| `MDREVIEW_BASE`/`WATCH_TRUSTED_BASE` exact-match vouch | PASS | both `http://mdreview:8080`; fail-closed check in `watch.py` (exact-match, non-loopback) is satisfied |
| **End-to-end Send→action** | PASS | throwaway project `mdreview-wtest`, container override, port 8141: created review with `teh` typo + comment, flipped `turn=agent`; in-container watcher spawned a subscription-authed agent that fixed `teh`→`the`, resolved the comment (`open_comments=0`), handed back (`turn=reviewer`, `state=done`) in ~27s |
| No live instance touched; `down -v` teardown | PASS | live :8139 healthy throughout; no `wtest` containers/volumes left after teardown |

Collision risk noted and handled: the committed compose pins `container_name: mdreview` and
`8137:8080`, both of which collide with the live standalone container and the live compose port.
The e2e override (`container_name: mdreview-wtest`, `8141:8080`, project `mdreview-wtest`) avoids
the collision. This is a test-harness concern, not a product defect — an operator running the
documented `docker compose --profile watcher up` against their own single instance has no
collision.

### MR-072 — operator runbook — PASS

| AC item | Result |
| --- | --- |
| (a) `claude setup-token` mint | PASS |
| (b) `.env` wiring | PASS |
| (c) rotation | PASS |
| (d) Linux `~/.claude/.credentials.json` mount alt + macOS Keychain caveat | PASS (present) — but see worth-fix W1 |
| (e) local-only / auto-actions-every-review warning + `WATCH_ARMED_FILE` escape | PASS (prominent ⚠️ callout) |
| (f) `docker compose --profile watcher up` command | PASS |
| (g) startup auth-probe | PASS — and re-driven: the documented probe command returns exit 0 / "OK." in-image |
| Stale "NOT containerized" claim corrected | PASS |

No token is echoed anywhere in `launch.sh`, `docker-compose.yml`, or `README.md`.

---

## Findings

### Worth-fixing

**W1 — The Linux credentials-mount alternative is unverified, and `:ro` is suspect.**
The README documents `-v ~/.claude:/home/watcher/.claude:ro` as the non-`setup-token` path on
Linux. Two concerns:
- A successful run writes substantially into `~/.claude` at runtime (creates `sessions/`,
  `projects/`, `policy-limits.json`, `backups/`, and rewrites `~/.claude.json`). A `:ro` mount of
  `~/.claude` blocks those writes. This alone makes `:ro` the wrong flag for a directory the CLI
  treats as writable state, even though the baked trust file (`/home/watcher/.claude.json`, a
  sibling of the dir) survives the mount.
- I could not positively confirm the path works: a synthesized `.credentials.json` produced
  "Not logged in · Please run /login" under both `:ro` and `rw`, so this CLI version's on-disk
  creds schema differs from what I constructed. The path is therefore **unverified**, not
  proven-broken. The settling check: on a real Linux host, `claude setup-token`/login once, then
  `docker run -v ~/.claude:/home/watcher/.claude mdreview-watcher … -p "Reply OK."` and confirm
  exit 0 — and decide `:ro` vs `rw` based on whether the run needs to write session state.
  Recommend re-driving this on Linux before presenting it as a tested alternative, or softening
  the prose to "documented by Anthropic, not validated in this image."

### Nits

- **N1 — Step-4 auth-probe drops `--mcp-config`.** The README probe is
  `claude --strict-mcp-config --permission-mode dontAsk -p "Reply OK."` (no `--mcp-config`). That
  is fine and intentional for a pure auth check (zero MCP servers, fast), and it runs exit 0 in
  the image — but it does **not** exercise the MCP path, so it won't catch a broken
  `agent-mcp.json`/network. Acceptable as an auth probe; just don't oversell it as a full
  readiness check.
- **N2 — Compose interpolation warning on empty token.** With no `.env`,
  `CLAUDE_CODE_OAUTH_TOKEN: "${CLAUDE_CODE_OAUTH_TOKEN:-}"` makes `config`/`up` work (empty
  allowed, by design) and the agent fails 401 only at spawn time. Correct posture; the runbook's
  step-4 probe is what surfaces it early. No change needed.

---

## Security / hygiene sign-off

- No token in any of the four commits or in the working tree (`sk-ant-` scan clean);
  `.scratch/.test-token` not tracked.
- `.env` gitignored, `.env.example` empty. No echo/log of the token in the wrapper, compose, or
  README.
- Tool surface is bounded: `--strict-mcp-config` (mdreview MCP only) + `--allowedTools
  "mcp__mdreview__*"` + `--permission-mode dontAsk`. The MCP round-trip and e2e confirm the agent
  uses only mdreview tools.
- Prompt interpolation in `launch.sh` is safe: `$REVIEW_ID`/`$MDREVIEW_OWNER` come from
  server-generated ids (`[A-Za-z0-9]{4,40}` shape), are double-quoted into a single `-p` arg
  under `set -euo pipefail`, and `watch.py` spawns argv with `shell=False` (never `shell=True`).
- Auto-action posture is accurate and prominent: the ⚠️ "Local use only — auto-actions every
  review you Send" callout names the attacker-controllable-comment risk and points public-instance
  users to the host watcher with `WATCH_ARMED_FILE` arming.
- Scope: no creep into `app.py` or the main service image; the service stays stdlib-only Python,
  no Node.

## Re-drive teardown

All throwaway containers, images (`mdreview-watcher:g7`, `mdreview-svc:g7`), networks, volumes,
and the `mdreview-wtest`/`mdreview-wtest2` projects removed. Live `mdreview` on :8139 healthy and
`mdreview-data` intact, confirmed post-teardown.

## Gate

**G7 PASS** — sprint-25 ships. W1 is a worth-fixing doc-accuracy item for a secondary path,
not a blocker; recommend re-driving the Linux creds-mount on a Linux host (or softening the
prose) as a fast follow.

## Finding resolution (post-review, orchestrator)

- **W1 (worth-fixing) — RESOLVED 2026-06-24** (commit on dev): the README Linux creds-mount
  alternative is now marked **unverified** (verify-on-host), the suspect `:ro` is **dropped** (the CLI
  writes session/policy state into `~/.claude` at runtime, so the mount must be writable), and
  `setup-token` is reaffirmed as the proven end-to-end path. The macOS-Keychain caveat stays.
- **N1 (nit) — RESOLVED:** the step-4 startup probe is now labelled an **auth-only** check (it omits
  `--mcp-config`); the in-compose MCP/network path is covered by actually Sending a review once up.
- **N2 (nit) — accepted:** empty-token compose interpolation is the correct posture (401 only at spawn;
  the probe surfaces an expired token at deploy time).
