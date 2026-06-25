# mdreview-service

A containerized markdown review microservice. An agent POSTs markdown, gets back a review URL
for a human, and polls feedback over HTTP. One service handles many reviews, isolated by id.
No per-process spawning, no shared filesystem with the agent.

**Landing page:** [mdreview.waqasrana.space](https://mdreview.waqasrana.space/) (served from the
`gh-pages` branch; source in `site/`).

Stdlib Python only (tiny image, no pip installs). Self-contained: the marked, Mermaid, KaTeX,
highlight.js, and footnote renderers are vendored and served from `/static`, so the browser needs no
CDN. The viewer renders Markdown the way a Jekyll/MathJax site does: **LaTeX math** (inline `$…$` /
`\(…\)`, display `$$…$$` / `\[…\]`; prose/currency `$` left literal), **Mermaid** diagrams, **GFM
footnotes** (`[^id]` refs → an ordered back-ref section), and **syntax-highlighted** fenced code (a
dual-scheme theme that reads on light and dark panes).

## Run

```bash
docker compose up -d --build        # serves on http://localhost:8137
# or:
docker build -t mdreview-service .
docker run -d -p 8137:8080 -v mdreview-data:/data mdreview-service
```

Health check: `curl localhost:8137/healthz` -> `{"ok":true}`.

Feedback and source persist in the `/data` volume across restarts.

## The flow

1. Agent: `POST /api/reviews {markdown, title}` -> `{id, review_url, feedback_url, ...}`
2. Agent hands `review_url` to a human.
3. Human opens it, selects text or clicks a paragraph number, types notes (auto-saved).
4. Agent polls `GET /api/reviews/{id}/status` then `GET /api/reviews/{id}/feedback`.
5. Agent applies edits and `PUT /api/reviews/{id}/source {markdown}` -> the human's page
   live-reloads and addressed notes are struck through. Repeat as needed.

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/` | | **dashboard** HTML (or the descriptor JSON on `Accept: application/json`) |
| GET | `/api` | | service descriptor JSON |
| POST | `/api/reviews` | `{markdown, title?, project?, source_path?, session?}` | `{id, review_url, feedback_url, source_url, status_url}` |
| GET | `/api/reviews` | `?turn=agent` (optional, exact-match on the turn baton; empty/absent ⇒ all) | `{reviews[]}` — every review's meta + `notes_total`, `notes_addressed`, `revision`, `status`, `turn` |
| GET | `/api/reviews/wait` | `?since=<turn_updated>` **required** (edge cursor; missing ⇒ `now`, `0` ⇒ backlog) · `?turn=agent` · `?timeout=<s>` (capped to server max ≈25s, `MDREVIEW_WAIT_TIMEOUT_S`) | `{reviews[]}` — **long-poll**: blocks until a baton flips *newer* than `since` (each row carries its `turn_updated`), or `{reviews:[], timeout:true}` on expiry |
| GET | `/api/reviews/{id}` | | meta |
| DELETE | `/api/reviews/{id}` | | `{deleted}` |
| GET | `/api/reviews/{id}/source` | | raw markdown |
| PUT | `/api/reviews/{id}/source` | `{markdown}` | meta (snapshots a history round, then live-reloads) |
| GET | `/api/reviews/{id}/feedback` | | `{markdown, notes[], ...meta}` — `notes[]` is legacy notes **plus a projection of the comments** (so this read path stays live) |
| GET | `/api/reviews/{id}/status` | | `{source_updated, feedback_updated, comments_updated, turn, turn_updated, handoff, agent_status}` |
| POST | `/api/reviews/{id}/handoff` | `{to:"agent"}` · `{to:"reviewer", state, message}` · `{state:"working", owner, message?}` · `{to:"reviewer", by:"reviewer"}` | meta — the **turn baton**: flip to the agent, hand back (done/blocked), claim/renew the lease (`409` on a *fresh* foreign owner; a **stale** foreign lease — older than `LEASE_TTL_S`, 180s — is taken over unless already reclaimed), or reviewer reclaim; `400` on an unrecognized body |
| GET | `/api/reviews/{id}/history` | | `{rounds[]}` — `{round, ts}`, newest first |
| GET | `/api/reviews/{id}/history/{n}` | | one round: `{source, feedback, notes[], ...round meta}` |
| GET | `/api/reviews/{id}/comments` | `?status=open\|resolved\|reopened\|all` (default `all`) | `{comments[]}` — the threaded comments |
| POST | `/api/reviews/{id}/comments` | `{anchor{quoted_text, block_num?, start?, end?}, text, role?}` | `{comment}` (201; reviewer authors) |
| GET | `/api/reviews/{id}/comments/{cid}` | | `{comment}` — full `thread[]` + `status_history[]` |
| DELETE | `/api/reviews/{id}/comments/{cid}` | | `{deleted}` — hard-remove a junk comment (`404` if missing); distinct from resolve |
| POST | `/api/reviews/{id}/comments/{cid}/reply` | `{text, role?}` | `{comment}` — append a reply; status unchanged |
| POST | `/api/reviews/{id}/comments/{cid}/resolve` | `{justification?}` | `{comment}` — agent resolves (`409` if not open/reopened) |
| POST | `/api/reviews/{id}/comments/{cid}/reopen` | `{text?}` | `{comment}` — reviewer reopens (`409` if not resolved) |
| POST | `/api/reviews/{id}/assets` | `{name, content_b64}` | `{name, stored, url, bytes, ctype}` — attach an image (base64) the viewer serves at `url` |
| GET | `/api/reviews/{id}/assets` | | `{assets[]}` — `{name, stored, url, bytes, ctype, ts}` per attached asset |
| GET | `/api/reviews/{id}/asset/{stored}` | | the asset bytes (binary, with its stored content-type) |
| GET | `/review/{id}` | | viewer HTML (human opens) |
| GET | `/healthz` | | `{ok}` |

**Provenance (optional, on POST):** `project` and `session` organize a review on the dashboard —
the left sidebar lists **Projects** you can filter the grid by, and each card shows a
`project / session / source_path` crumb; `source_path` records the file it came from. Untagged
reviews still appear under **All reviews** (just not under a project). The fields are stored in
`meta.json`; existing reviews without them are unaffected.

The dashboard sidebar also has a turn-baton **Inbox** — *All reviews*, *Needs you* (your turn),
*Agent working*, *Resolved* — and each card carries the matching status badge, derived from the
same `turn`/`status` already on `GET /api/reviews` (no extra call).

**Status** (in the list/dashboard) is derived per review: `awaiting` (no feedback yet),
`feedback` (notes/comments outstanding), `resolved` (all notes addressed **and** all comments
resolved). Counts (`notes_total`/`notes_addressed`) are comment-aware — an open comment counts
toward the total, a resolved one toward addressed — so a review with live comments never reads as
"0 / awaiting".

**History:** each `PUT /source` archives the outgoing draft plus the feedback it accumulated as a
numbered round under `{id}/history/round-{N}/`, and bumps `revision`. Past rounds are read-only
via the history routes; the viewer exposes them behind its **History** button.

**Assets (images):** attach a draft's images to a review once with `POST /assets` — base64 body,
keyed by the exact `src` the draft uses (e.g. `/assets/x.png` or `fig/y.svg`). The bytes are stored
under the review by a content-hash name and **survive every `PUT /source` revision** (attach once,
never resend blobs). The viewer rewrites local/relative/site-root `<img src>` to the served `url`,
so a math- and image-heavy draft renders in review the way it does on the published site. base64 is
the only transport; the served `url` keys on the hash name (no encoded slashes), so it survives a
reverse proxy. Assets are review-scoped (not history-snapshotted) and removed with the review.
Like the rest of the service, asset serving inherits the **no-auth, id-only** posture: bytes are
served with the content-type inferred from the attached `name`, so treat an attached asset like the
draft's own HTML — don't attach bytes you wouldn't trust in `source.md`. (Responses carry
`X-Content-Type-Options: nosniff`; keep auth in front if you expose the service.)

Feedback `notes[]` entries look like:
`{"num": "3", "quote": "...", "note": "tighten this", "addressed": false}`,
and `markdown` is the same feedback rendered as a readable block per note. Each entry is either a
legacy note or a **projected comment** (`note` = the thread, `addressed` = the comment is resolved).

**Comments (threaded resolution).** A reviewer highlights text and starts a comment; it opens as a
**thread** in the viewer margin. The agent (over HTTP or MCP) lists open comments, replies to discuss,
or **resolves** one — optionally with a justification appended to the thread (`resolved_by`/`resolved_at`
are recorded). A resolved comment leaves the active document and moves to a **Resolved** panel; the
reviewer can **reopen** it (status back to `reopened`), after which the agent can resolve again. The
`open → resolved → reopened` machine is enforced server-side, so the viewer and MCP share one state.
`thread[]` and `status_history[]` are append-only (full history, never overwritten). A comment is
`{comment_id, status, anchor{quoted_text, block_num, start, end}, thread[{author, role, text, ts}],
created_by, created_at, resolved_by, resolved_at, status_history[]}`. Roles `reviewer`/`agent` are
**attribution, not auth**; "reviewer-only reopen" and "no MCP reopen tool" are conventions on the
no-auth service. Poll `comments_updated` (on `GET /status`) to live-reload threads.

## Config (env)

| Var | Default | Meaning |
|---|---|---|
| `PORT` | `8080` | in-container listen port |
| `MDREVIEW_DATA` | `/data` | storage dir (mount a volume) |
| `MDREVIEW_PUBLIC_BASE` | empty | if set (e.g. `https://review.example.com`), `review_url`/`feedback_url` use it; otherwise the request Host header is used |

## MCP server (optional)

`mcp_server.py` is a thin, stdlib-only **MCP** server (stdio, JSON-RPC 2.0, spec rev `2025-06-18`)
that exposes the review API as first-class tools, so an MCP-speaking agent can call it without
hand-rolling HTTP. It wraps the running HTTP service and adds no state — the service is unchanged.

```bash
# point it at a running mdreview-service and run it over stdio
MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py
# smoke it (stdlib only, no deps):
MDREVIEW_BASE=http://localhost:8137 python3 mcp_smoke.py
```

Example MCP client config (stdio):

```json
{
  "mcpServers": {
    "mdreview": {
      "command": "python3",
      "args": ["/path/to/mdreview-service/mcp_server.py"],
      "env": { "MDREVIEW_BASE": "http://localhost:8137" }
    }
  }
}
```

**Tools (20):** `create_review` (markdown, title?, project?, session?,
source_path?), `list_reviews`, `get_review` (id), `get_source` (id), `get_feedback` (id), `get_status` (id),
`update_source` (id, markdown), `get_history` (id, round?), `attach_asset` (id, name, path|content_b64),
`list_assets` (id), `delete_review` (id), `server_info`, `create_comment` (author a comment), the **comment** tools `list_comments` (document_id, status?=open), `get_comment` (document_id,
comment_id), `reply_to_comment` (document_id, comment_id, text), `resolve_comment` (document_id,
comment_id, justification?), `delete_comment` (document_id, comment_id — hard-remove a junk comment),
and the **turn-baton** tools `hand_back` (document_id, message, state?=done) and `ping_working` (document_id, owner, message?) — both map onto `POST /handoff`.
`document_id` is the review id.
There is **no `reopen` tool** — reopen is the reviewer's UI action (a convention on the no-auth
service, not an enforced boundary); after a reopen the agent sees the comment again via
`list_comments`. The agent workflow (`list_comments(status="open")` first; reply to discuss, resolve
when addressed; justification optional but recommended) is encoded in the tool descriptions. A failed
call (bad/expired id, service down) returns an `isError: true` result; an unknown tool name is a
JSON-RPC `-32602` error.

**Staleness.** A stdio MCP server loads its code + tool list once at process start; editing
`mcp_server.py` does nothing until the client **reconnects**. `server_info` reports the *running*
wrapper's `tools_hash`/version; a **human/CI** compares it to the on-disk `python3 mcp_server.py
--print-version` and reconnects on a mismatch (the server can signal its identity but cannot reload
itself; an HTTP/render change needs no reconnect — the wrapper just proxies — a change to
`mcp_server.py` itself does).

**Reachable `review_url`.** The wrapper relays the service's `review_url`, which the service
derives from the request `Host` header unless `MDREVIEW_PUBLIC_BASE` is set. So a human handed the
link can reach it, set `MDREVIEW_PUBLIC_BASE` on the **service** (not the wrapper) to a
host-reachable URL (e.g. `https://review.example.com`); otherwise the link may be an unreachable
`localhost`.

**Exposure.** `list_reviews` (like `GET /api/reviews` and the dashboard) returns every review with
no auth — fine for the trusted-network posture, but keep auth in front if exposed.

## Watcher (optional) — operator runbook

`watch.py` is a stdlib-only sibling of `mcp_server.py` that closes the handoff loop without a human
in the relay: it long-polls the service for reviews the reviewer flipped to `turn==agent` ("Send to
agent"), claims each review's cooperative lease, and spawns the operator's **required**
`WATCH_LAUNCH_CMD`; with it **unset the watcher refuses to start** (exit `2` with guidance) — there is no runnable default. It runs **where the operator's agent runs** (like
`mcp_server.py`). It runs **two ways**: on the host (`python3 watch.py`, below — the answer for a
public/shared instance), or as an **opt-in container** (`docker compose --profile watcher up` — the
local-use path, see **"Containerized watcher"** below). A plain `docker compose up` does **not** start
it; it is off unless you ask for the profile.

```bash
# trusted-base mode: a loopback service. WATCH_LAUNCH_CMD is REQUIRED (no default); the
# scoped/recommended recipe (mdreview-tools-only, robustly headless) is:
MDREVIEW_BASE=http://localhost:8137 \
  WATCH_LAUNCH_CMD='["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]' \
  python3 watch.py

# with a non-loopback base, you MUST vouch for it explicitly (exact match):
MDREVIEW_BASE=http://10.0.0.5:8137 WATCH_TRUSTED_BASE=http://10.0.0.5:8137 \
  WATCH_LAUNCH_CMD='["claude","--permission-mode","dontAsk","--allowedTools","mcp__mdreview__*","-p","<prompt>"]' \
  python3 watch.py
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

**Fail-closed trusted base (the safety crux).** `watch.py` is a *credentialed process spawner*, so it
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
service request cannot influence**: there is **no endpoint to arm a review** (`watch.py` reads it from
disk/env; the service never sees it), so on a no-auth public instance a review **cannot arm itself**.
**Provenance is not a trust boundary** on the no-auth service — anyone with the URL can set
`project`/`session` and press "Send to agent" — so the *only* thing standing between a public Send and a
process launch on the operator's machine is the **local allowlist**. Arm deliberately; treat the armed
file as you would any credential-adjacent config.

```bash
# public-instance operation: arm specific reviews, no WATCH_TRUSTED_BASE vouch needed.
# Review ids are what /api/reviews returns (10 hex chars, e.g. secrets.token_hex(5)) — not "rev_..".
printf '%s\n' '4b09a6cbe0' 'd2abf53a16' > ~/.mdreview-armed
WATCH_ARMED_FILE=~/.mdreview-armed MDREVIEW_BASE=https://public.example python3 watch.py
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
default**: a plain `docker compose up` starts only the service; you opt in with `--profile watcher`.

> ⚠️ **Local use only.** The containerized watcher runs with `WATCH_ARMED*` unset, so it
> **auto-actions every review you Send to the agent** — fine when you are the only commenter, unsafe on
> a shared/public instance (a comment is attacker-controllable input the agent will execute). For a
> public instance use the **host** watcher above with **arming** (`WATCH_ARMED_FILE`), which is also the
> per-review opt-in escape hatch here if you want it.

```bash
# 1. One-time: mint a LONG-LIVED subscription token (requires a Claude subscription; NOT an API key).
#    Run on a machine where you're logged in to Claude:
claude setup-token
# 2. Put it in a gitignored .env (compose reads it automatically; never commit it):
cp .env.example .env
#    edit .env →  CLAUDE_CODE_OAUTH_TOKEN=<the token from step 1>
# 3. Start the service + the watcher:
docker compose --profile watcher up -d --build
# 4. Startup AUTH probe — catch an EXPIRED token at deploy time, not as a silently stranded review.
#    (This checks AUTH only — it deliberately omits --mcp-config; the in-compose network/MCP path is
#     covered by actually Sending a review once it's up.)
docker compose --profile watcher exec watcher \
  claude --strict-mcp-config --permission-mode dontAsk -p "Reply OK."
#    exit 0 / "OK"  => auth good.   401 / non-zero => token expired or wrong → re-run setup-token.
```

Now "Send to agent" in the viewer is picked up automatically: the watcher container spawns a `claude`
agent (scoped to the mdreview MCP tools), which reads your open comments, edits the draft, resolves
them, and hands the turn back — the page live-updates as it goes.

- **Rotation.** `setup-token` mints a long-lived token, but to rotate: run `claude setup-token` again,
  replace the value in `.env`, and `docker compose --profile watcher up -d` (recreates the watcher).
  Re-run the step-4 probe after rotating. (You can revoke old tokens from your Claude account.)
- **Linux hosts — credentials-file alternative (unverified; `setup-token` is the proven path).** On
  Linux the CLI stores creds in a file under `~/.claude`, so in principle you can bind-mount your host
  creds into the watcher instead of minting a token: `-v ~/.claude:/home/watcher/.claude` (mount it
  **writable**, not `:ro` — the CLI writes session/policy state into `~/.claude` at runtime). The exact
  on-disk schema varies by CLI version, so **verify on your host** (`docker run -v ~/.claude:/home/watcher/.claude
  mdreview-watcher … claude -p "Reply OK."` → exit 0) before relying on it. **This does not work on
  macOS** at all, where the token lives in the Keychain (not a mountable file) — there, `setup-token`
  is the path. When in doubt, use `setup-token` (proven end-to-end in CI).
- **The token never enters git.** `.env` is gitignored; `.env.example` ships empty. Don't paste the
  token anywhere it would be committed or logged.

**Full env-var reference (operator config):**

| Env var | Default | Meaning |
| --- | --- | --- |
| `MDREVIEW_BASE` | `http://localhost:8137` | Service base URL the watcher polls (same as `mcp_server.py`). |
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

## Notes

- Multi-tenant by id, so concurrent reviews never collide. No auth (intended for trusted /
  local networks); put it behind a reverse proxy with auth if exposing it.
- The dashboard (`/`) and `GET /api/reviews` list **across all reviews** — fine for the
  trusted-network posture, but a reason to keep auth in front when exposed.
- The **MCP wrapper** above was designed in [docs/future-mcp.md](docs/future-mcp.md), kept as its
  design/decision record.
- For agent integration details, see [AGENTS.md](AGENTS.md).
- A non-Docker, per-file CLI version lives in `../mdreview` (writes feedback to a file next to
  the source). This service is the networked, multi-session form.
