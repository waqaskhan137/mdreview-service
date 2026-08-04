# Watcher

> **Shelved (2026-07-03).** The watcher is **disabled**: the `make watcher` target and the compose
> `watcher` service were removed, so there is no wired way to run it. The code below stays under
> `src/watcher/` (+ `src/watch.py`, `infra/Dockerfile.watcher`, `infra/watcher/`), and this runbook
> still describes it. To revive: restore the compose `watcher` service and the `make watcher` target
> (see git history), then follow the steps below.

The **`watcher` package** (`src/watcher/`, thin entry point `src/watch.py`, canonical `python -m watcher`) is a stdlib-only sibling of the `mcp` package that closes the handoff loop without a human
in the relay: it long-polls the service for reviews the reviewer flipped to `turn==agent` ("Send to
agent"), claims each review's cooperative lease, and spawns the operator's **required**
`WATCH_LAUNCH_CMD`; with it **unset the watcher refuses to start** (exit `2` with guidance) — there is no runnable default. It runs **where the operator's agent runs** (like
`src/mcp_server.py`). It runs **two ways**: on the host (`python3 src/watch.py`, below — the answer for a
public/shared instance), or as an **opt-in container** (`make watcher` — the
local-use path, see **"Containerized watcher"** below). A plain `make up` does **not** start
it; it is off unless you ask for the profile.

```bash
# trusted-base mode: a loopback service. WATCH_LAUNCH_CMD is REQUIRED (no default); the
# scoped/recommended recipe (mdreview-tools-only, robustly headless) is:
MDREVIEW_BASE=http://localhost:8137 \
  WATCH_LAUNCH_CMD='["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]' \
  python3 src/watch.py

# with a non-loopback base, you MUST vouch for it explicitly (exact match):
MDREVIEW_BASE=http://10.0.0.5:8137 WATCH_TRUSTED_BASE=http://10.0.0.5:8137 \
  WATCH_LAUNCH_CMD='["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]' \
  python3 src/watch.py
```

**Configuring the launch command (the recipes).** `WATCH_LAUNCH_CMD` must carry **both** the agent
command **and its permission stance**; an unconfigured watcher exits `2` rather than spawn a command
that silently no-ops headless. The agent runs with **no TTY**, so any tool whose use would otherwise
raise an interactive approval prompt stalls the run.

- **Scoped / recommended (headless, mdreview-tools-only):**
  `WATCH_LAUNCH_CMD='["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]'`.
  **Argument order matters:** `--allowedTools` is **variadic** (a space-separated tool list), so keep
  `-p "<prompt>"` **last** — a prompt placed right after `--allowedTools` is swallowed as another tool
  name, and `claude` then errors `Input must be provided … when using --print` (the agent dies and the
  review strands).
  `--allowedTools` **alone is not robustly headless**: an unlisted tool the agent reaches for
  (`Read`/`Bash`/`TodoWrite`/a web fetch) falls through to the no-TTY permission prompt and stalls (a
  narrowed reprise of the original no-op defect). **`--permission-mode dontAsk` converts that
  fall-through into a clean deny** — listed tools are approved, everything else is denied outright
  with no prompt. **Anchoring rule:** the MCP server segment must be **glob-free** —
  `mcp__mdreview__*` is valid (server `mdreview`, any tool); `mcp__*` and `*` are ignored with a
  startup warning, so they grant nothing.
- **Full-autonomy (only if you accept it, trusted/localhost only):**
  `WATCH_LAUNCH_CMD='["claude","--dangerously-skip-permissions","-p","<prompt>"]'`. Every tool is
  permitted with no prompt. Use this **only** on a base whose reviewer comments you fully trust.

**Prompt-injection caveat (load-bearing).** On a public or armed base the launched agent **executes
instructions embedded in reviewer comments** — the open comments are its instruction, and a reviewer
is anyone with the URL on the no-auth service. The `WATCH_LAUNCH_CMD` permission posture is what
**bounds the blast radius**: a comment that says "shell out and exfiltrate via Bash" is a clean deny
under the scoped `dontAsk` + `mcp__mdreview__*` recipe, but is executed under
`--dangerously-skip-permissions`. **Use the scoped posture, not `--dangerously-skip-permissions`, on
any base where comments aren't fully trusted.**

**Fail-closed trusted base (the safety crux).** `src/watch.py` is a *credentialed process spawner*, so it
**refuses to start** (exit `2`, no network call) against a base it cannot vouch for. With
`WATCH_TRUSTED_BASE` unset it allows **loopback only** (`localhost`/`127.0.0.1`/`::1`); for any other
base you must set `WATCH_TRUSTED_BASE` to an **EXACT** string match of `MDREVIEW_BASE` (no wildcard,
no prefix, so `localhost.evil.com` is refused). A mismatch (http vs https, `:443` vs bare) is a
refusal by design — the fix is the correct vouch, not a looser comparand.

**Generic launch template (no shell injection).** The watcher only knows "spawn this argv with this
env." `WATCH_LAUNCH_CMD` is read as a **JSON array** (preferred, e.g. `'["claude","-p","..."]'`) or
a plain string parsed with `shlex.split`; either way it is spawned with `subprocess.Popen(argv, …)`
**without a shell** (never `shell=True`, never the review id interpolated into a command string).
Unset, the watcher **refuses to start** (exit `2`) with guidance to set `WATCH_LAUNCH_CMD` including its permission stance — there is no runnable default. The child receives the review
via **env, not argv** — the interface is `REVIEW_ID`, `MDREVIEW_BASE`, and `MDREVIEW_OWNER` (the
watcher's lease owner, so the child renews the **same** lease via `ping_working` — a same-owner `200`,
not a foreign `409`). The **child** owns the heartbeat and `hand_back`; the watcher claims once, then
only reaps + logs the child on exit.

**Arming — running against an untrusted / public instance.** Loopback (or an exact `WATCH_TRUSTED_BASE`
vouch) is the trusted-base path above. To run against a **non-loopback, un-vouched** base — a public
instance — you must **arm** the specific reviews the watcher may auto-run. Arming is a **local operator
allowlist of review ids**; with it configured the watcher **runs but gates per review** — it spawns
**only armed reviews** and **skips un-armed ones without claiming a lease**. Without arming (and without
a vouch), a non-loopback base still **EXITs `2`** — arming is the *only* way to run there.

- **`WATCH_ARMED_FILE`** — path to the allowlist file: **one review id per line**, `#` comments and
  blank lines ignored, whitespace stripped, and any token that is not a valid id (including a `*`
  wildcard) is **dropped and logged** — there is no match-all. The file is **re-read on every check**,
  so arming a review is **append a line, no restart**.
- **`WATCH_ARMED`** — an inline convenience id-list (comma/space-separated), unioned with the file and
  fixed at process start (the file is the live-editable surface).

**Local-only, and why it is the whole security boundary.** The allowlist is **operator-local config a
service request cannot influence**: there is **no endpoint to arm a review** (`src/watch.py` reads it from
disk/env; the service never sees it), so on a no-auth public instance a review **cannot arm itself**.
**Provenance is not a trust boundary** on the no-auth service — anyone with the URL can set
`project`/`session` and press "Send to agent" — so the *only* thing standing between a public Send and a
process launch on the operator's machine is the **local allowlist**. Arm deliberately; treat the armed
file as you would any credential-adjacent config.

```bash
# public-instance operation: arm specific reviews, no WATCH_TRUSTED_BASE vouch needed.
# Review ids are what /api/reviews returns (10 hex chars, e.g. secrets.token_hex(5)) — not "rev_..".
printf '%s\n' '4b09a6cbe0' 'd2abf53a16' > ~/.mdreview-armed
WATCH_ARMED_FILE=~/.mdreview-armed MDREVIEW_BASE=https://public.example python3 src/watch.py
# un-armed reviews flipped to turn==agent are skipped (no lease claim); only the two armed ids run.
```

**Caps (bound spend).** Three independent ceilings; a spawn happens only when it passes **all** of them:

- `WATCH_MAX_CONCURRENT` (default `3`) — simultaneous live children.
- `WATCH_MAX_LAUNCHES_PER_HOUR` (default `30`) — spawns over a rolling 3600s window, across **all** ids.
- `WATCH_MAX_ATTEMPTS_PER_REVIEW` (default `5`) over `WATCH_ATTEMPT_WINDOW_S` (default `3600`s) —
  spawns for a **single** review id within the window. Once one review id hits it, that review is
  skipped (no claim) until its window slides; **distinct reviews are unaffected**.

The first two are enforced **before** the claim (the watcher never claims a lease it cannot spawn). The
per-review cap bounds the **re-Send / re-surface loop** — one review repeatedly returned to `turn==agent`
(a human who keeps pressing "Send", an agent that hands back and is re-Sent, a `--backlog` re-seed), so a
single non-converging review cannot eat the global hourly budget. It bounds **only** that loop, **not** a
crash-loop: a child that exits before `hand_back` **strands** its review at `turn==agent` (the server
bumps `turn_updated` only on a real reviewer→agent flip), the edge-triggered poll never re-surfaces it,
and the watcher **never auto-relaunches** — the failure mode is a fail-safe **under**-spawn, recovered by
the human (the 180s stale "Agent may have stopped" banner) or a `--backlog`/restart re-seed.

### Containerized watcher (opt-in, Claude subscription auth)

For **local single-user** use you can run the watcher as a compose service instead of on the host —
authenticated by your Claude **subscription** (no API key, no per-token billing). It is **off by
default**: a plain `make up` starts only the service; you opt in with `make watcher`.

> ⚠️ **Local use only.** The containerized watcher runs with `WATCH_ARMED*` unset, so it
> **auto-actions every review you Send to the agent** — fine when you are the only commenter, unsafe on
> a shared/public instance (a comment is attacker-controllable input the agent will execute). For a
> public instance use the **host** watcher above with **arming** (`WATCH_ARMED_FILE`), which is also the
> per-review opt-in escape hatch here if you want it.

```bash
# 1. One-time: mint a LONG-LIVED subscription token (requires a Claude subscription; NOT an API key).
#    Run on a machine where you're logged in to Claude:
claude setup-token
# 2. Put it in a gitignored infra/.env (compose reads it automatically; never commit it):
cp infra/.env.example infra/.env
#    edit infra/.env →  CLAUDE_CODE_OAUTH_TOKEN=<the token from step 1>
# 3. Start the service + the watcher:
make watcher
# 4. Startup AUTH probe — catch an EXPIRED token at deploy time, not as a silently stranded review.
#    (This checks AUTH only — it deliberately omits --mcp-config; the in-compose network/MCP path is
#     covered by actually Sending a review once it's up.)
docker compose -f infra/docker-compose.yml --profile watcher exec watcher \
  claude --strict-mcp-config --permission-mode dontAsk -p "Reply OK."
#    exit 0 / "OK"  => auth good.   401 / non-zero => token expired or wrong → re-run setup-token.
```

Now "Send to agent" in the viewer is picked up automatically: the watcher container spawns a `claude`
agent (scoped to the mdreview MCP tools), which reads your open comments, edits the draft, resolves
them, and hands the turn back — the page live-updates as it goes.

- **Rotation.** `setup-token` mints a long-lived token, but to rotate: run `claude setup-token` again,
  replace the value in `infra/.env`, and `docker compose -f infra/docker-compose.yml --profile watcher up -d` (recreates the watcher).
  Re-run the step-4 probe after rotating. (You can revoke old tokens from your Claude account.)
- **Linux hosts — credentials-file alternative (unverified; `setup-token` is the proven path).** On
  Linux the CLI stores creds in a file under `~/.claude`, so in principle you can bind-mount your host
  creds into the watcher instead of minting a token: `-v ~/.claude:/home/watcher/.claude` (mount it
  **writable**, not `:ro` — the CLI writes session/policy state into `~/.claude` at runtime). The exact
  on-disk schema varies by CLI version, so **verify on your host** (`docker run -v ~/.claude:/home/watcher/.claude
  mdreview-watcher … claude -p "Reply OK."` → exit 0) before relying on it. **This does not work on
  macOS** at all, where the token lives in the Keychain (not a mountable file) — there, `setup-token`
  is the path. When in doubt, use `setup-token` (proven end-to-end in CI).
- **The token never enters git.** `infra/.env` is gitignored; `infra/.env.example` ships empty. Don't paste the
  token anywhere it would be committed or logged.

**Full env-var reference (operator config):**

| Env var | Default | Meaning |
| --- | --- | --- |
| `MDREVIEW_BASE` | `http://localhost:8137` | Service base URL the watcher polls (same as `src/mcp_server.py`). |
| `WATCH_TRUSTED_BASE` | _(unset)_ | Explicit vouch for a non-loopback base; **exact** string match of `MDREVIEW_BASE` (no wildcard/prefix). Unset ⇒ loopback only. |
| `WATCH_ARMED_FILE` | _(unset)_ | Path to the local allowlist file (one id/line, `#` comments, bad/`*` tokens dropped); re-read per check (append-a-line, no restart). |
| `WATCH_ARMED` | _(unset)_ | Inline armed id-list (comma/space-separated), unioned with the file; fixed at process start. |
| `WATCH_LAUNCH_CMD` | **required — unset exits `2` at startup** | Launch argv as a JSON array (preferred) or a `shlex` string; spawned **without** a shell. Must include the agent command **and its permission stance** (see the recipes above); there is no runnable default. |
| `WATCH_MAX_CONCURRENT` | `3` | Max simultaneous live children (enforced before the claim). |
| `WATCH_MAX_LAUNCHES_PER_HOUR` | `30` | Rolling 3600s spawn cap across all reviews (enforced before the claim). |
| `WATCH_MAX_ATTEMPTS_PER_REVIEW` | `5` | Per-review spawn cap within `WATCH_ATTEMPT_WINDOW_S`; bounds the re-Send/re-surface loop for one id. |
| `WATCH_ATTEMPT_WINDOW_S` | `3600` | Rolling window (seconds) for the per-review attempt cap. |
| `WATCH_OWNER` | pid-derived | Stable lease owner id; a set value persists across restart (a pid-derived one changes). |
| `WATCH_SINCE` | now | `0` (or `--backlog`) opts into the existing agent-turn backlog; default = act only on flips after start. |
| `WATCH_WAIT_TIMEOUT_S` | `25` | Client long-poll timeout (the server caps it to its own `WAIT_TIMEOUT_S`). |
| `WATCH_LOG_FILE` | _(unset ⇒ stderr only)_ | Operational log file. Unset keeps today's behaviour (log to stderr — redirect it where you like); **set** ⇒ also **append** structured, timestamped records to that exact path (no baked-in path — the watcher has no `/data` mount). This is where a crashed run's **exit code + captured stderr tail** land, so a failure is diagnosable instead of buried. |
| `WATCH_VERBOSE` / `--verbose` | _(unset ⇒ INFO)_ | Raise the log level to `DEBUG`. |

**Diagnosing a crashed agent run (issue #26).** When a spawned child exits non-zero (or dies before
`hand_back`), the watcher (a) writes the exit code + the child's stderr tail to the log
(`WATCH_LOG_FILE` if set, else stderr), and (b) — after a **mandatory `/status` re-check** confirming
the review is still stranded at `turn==agent` (so it never overwrites a child that *did* hand back) —
POSTs `hand_back{state:blocked, "agent process exited N without finishing"}`, which flips the review
back to the reviewer. The viewer renders that as a distinct **"agent run stopped — Take back the
turn"** banner rather than a frozen "working" spinner. This is **visibility, not retry**: the crash
model is unchanged (B1, no auto-relaunch). The viewer only ever sees the short fixed reason; the raw
stderr stays in the operator log (no-auth posture).

---

Moved out of `README.md` by #257. Commands, ports, paths and env vars are
byte-identical to what shipped there; nothing was corrected in the move.
