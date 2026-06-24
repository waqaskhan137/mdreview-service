---
epic: watcher-container
status: active
created: 2026-06-24
source: docs/process/requirements/watcher-container.md
gate: passed 2026-06-24
review: reviews/watcher-container-plan-review-2026-06-24.md
related_sprints: [sprint-25]
related_tickets: [MR-069, MR-070, MR-071, MR-072]
---

# Opt-in Containerized Watcher (Claude Subscription Auth) Plan

Today the watcher (`watch.py`) — the process that picks up "Send to agent" and spawns a Claude to
action reviewer comments — is **not part of the deployment**. After a fresh `docker run` /
`compose up`, a human Sends a comment and nothing picks it up (the #26 cue says "no agent has picked
this up — is a watcher running?"). This epic makes the watcher a **first-class, opt-in** compose
service, gated behind a `watcher` profile so the default `docker compose up` is unchanged, and
authenticated by the user's **Claude subscription** (a long-lived OAuth token from
`claude setup-token`), because per-token API billing is a non-starter for most users. For a
**local, single-user** tool there are no untrusted commenters, so the public-instance fail-closed
"don't auto-run agents on attacker input" rationale does not apply here (product owner established
this); the existing host-side fail-closed watcher remains the answer for a public instance.

**Source requirement:** [`requirements/watcher-container.md`](../requirements/watcher-container.md) —
the original brief, kept verbatim.

## Assumptions & open questions

Surface these first. Each is tagged **load-bearing** (changes the design) or **minor**, with the
assumption I am planning against.

### The load-bearing auth question — RESOLVED (verified this session, not assumed)

The brief's central risk: *can the `claude` CLI authenticate via the user's **subscription** inside
a Linux container, headless?* I verified the falsifiable parts against the installed CLI on this
machine (existence/structure only — **no token value was ever printed or stored**):

| Claim to verify | Method | Result |
|---|---|---|
| macOS keychain, not a mountable file | `ls ~/.claude/` ; stat the creds paths | `~/.claude/.credentials.json` **absent**; `~/.claude.json` exists (237 KB) but is **config, not the token**. `claude --help` says: *"strictly `ANTHROPIC_API_KEY` or apiKeyHelper … OAuth and **keychain are never read**"* by the headless path. **Confirmed: mounting `~/.claude` does NOT carry auth on macOS.** |
| `claude setup-token` exists and bills against the **subscription** | `claude setup-token --help` | Output: *"Set up a long-lived authentication token **(requires Claude subscription)**"* — **confirmed subscription-billed, not API.** |
| The env var the CLI reads for a headless OAuth token | `strings` the native bin (2.1.190) + `grep` the npm `cli.js` (1.0.102) for env names (names only) | **`CLAUDE_CODE_OAUTH_TOKEN`** present in **both** independent installs (110 and 11 occurrences). This is the pinned env var. (`ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` also present — those are the API path we are NOT using.) |
| Linux-host alternative (mountable creds) | brief + CLI docs | On Linux hosts the CLI writes `~/.claude/.credentials.json` (no keychain), which **is** mountable — documented as the alternative for Linux operators, but the **env-var token is the portable, OS-agnostic path** we build against. |

**What is verified vs. what remains a build-time test.** Verified: the env var name, that
`setup-token` is subscription-billed, and the macOS keychain reality. **NOT yet executed end-to-end
here** (cannot run a containerized `claude` from this planning session): that a token minted by
`claude setup-token` and passed as `CLAUDE_CODE_OAUTH_TOKEN` into a **Linux container with no
keychain and no interactive login** actually authenticates a headless `-p` run. This is the
**single biggest residual risk** and is the headline acceptance gate of the infra ticket (see
Verification). The host-side prototype works on macOS where the keychain is present; the unproven
delta is the no-keychain Linux container relying purely on the env-var token.

**This is NOT a BLOCKER-FOR-HUMAN.** Everything I can falsify without running a container is
confirmed and points to a working path; the env var exists, `setup-token` is subscription-billed,
and the brief reports a working ~24s host prototype. The remaining unknown is a normal build-time
verification (run the container, watch it action a comment), not a product fork with no safe
default. If that build-time test fails, the implementer escalates from the ticket — the plan names
exactly what to test and what failure looks like.

### Other questions

- **(load-bearing) Does the vouched-base path mean arming is bypassed (so EVERY `turn==agent`
  review is auto-actioned)?** Verified in `watch.py:227` (`require_trusted_base_or_exit`): with
  `WATCH_TRUSTED_BASE` **exact-matching** `MDREVIEW_BASE=http://mdreview:8080`, the non-loopback
  base is vouched and the watcher runs **without** requiring arming — so every review flipped to
  `turn==agent` is picked up. **Assumption: this is the intended local-use posture** (no untrusted
  commenters; the owner explicitly waived the blast-radius rationale). The plan vouches the base and
  does **not** set `WATCH_ARMED*`. Justification: the brief says "the watcher should be a first-class
  opt-in service" for a single-user tool, and arming exists only to gate untrusted multi-tenant
  public instances, which are an explicit non-goal. (An operator who still wants per-review arming
  can set `WATCH_ARMED_FILE` against a mounted file — documented as optional, not default.)
- **(minor) Pin the `claude` CLI version or float `@latest`?** Assumption: **pin** an exact
  `@anthropic-ai/claude-code` version in `Dockerfile.watcher` for reproducible builds, with a
  comment on how to bump. Justification: a floating CLI can change auth/flag behavior under us and
  break a rebuilt watcher silently; pinning matches this repo's "pin upstream, don't float" instinct.
  The token format is owned by Anthropic, not the pin, so a pinned CLI still honors a freshly minted
  token.
- **(minor) Base image for `Dockerfile.watcher`?** Assumption: `node:22-bookworm-slim` (Node already
  present for the npm-installed CLI; add `python3` via apt for `watch.py`/`mcp_server.py`).
  Justification: the CLI is a Node package, so Node is the harder dependency to satisfy; Debian's
  `python3` is stdlib-complete for our two scripts. Alternative (`python:3.12-slim` + nodejs apt) is
  equivalent; either is fine, the AC just requires a working `claude` + `python3` in one image.
- **(minor) MCP transport inside the watcher container.** The agent MCP config spawns
  `python3 mcp_server.py` as a child of the `claude` process, with `MDREVIEW_BASE=http://mdreview:8080`.
  Assumption: both `watch.py` and the spawned `mcp_server.py` live in the watcher image and reach the
  service over the compose network. Verified `mcp_server.py:35` reads `MDREVIEW_BASE`.

## Product goal

`docker compose --profile watcher up` brings up the review service **and** an agent runner that, on
a human "Send to agent", picks up the review and actions the open comments end-to-end (edits the
draft, resolves the comments, hands the turn back) — with **no host-side process and no API key**,
authenticated by the operator's Claude subscription. A plain `docker compose up` is **byte-for-byte
unchanged**: service only, no watcher, no Node, still stdlib-only.

## Core design principle

**Opt-in and isolated: the watcher is a second compose service behind a profile, in its own image;
the main service image and the default `up` never change.** Node and the `claude` CLI live only in
`Dockerfile.watcher`; `app.py` stays stdlib-only Python. Everything the watcher needs already exists
(`watch.py`'s `WATCH_LAUNCH_CMD` generic launch interface, the fail-closed trusted-base check, the
working host prototype) — this epic **packages** that shape into the repo and the compose file; it
writes **no new `app.py` code and no new `watch.py` policy**.

## Recommended approach

### Service (`app.py`)

**No change.** The service is already correct and stdlib-only; the watcher is purely additive
deployment plumbing. `app.py` is named only to assert the `py_compile` gate still passes (it is
untouched).

### Watcher (new `watcher/` dir, `Dockerfile.watcher`, compose profile)

Move the verified host prototype (`.scratch/agent-launch.sh`, `.scratch/agent-mcp.json`) into the
repo proper and wire it through `watch.py`'s existing launch interface:

- **`watcher/launch.sh`** — the wrapper, promoted from `.scratch/agent-launch.sh` unchanged in
  shape. It interpolates `$REVIEW_ID` / `$MDREVIEW_BASE` / `$MDREVIEW_OWNER` (the contract
  `watch.py` sets in the child env) into the prompt and `exec`s:
  `claude --mcp-config <cfg> --strict-mcp-config --permission-mode dontAsk --allowedTools
  "mcp__mdreview__*" -p "<prompt>"`.
  **Recipe gotcha (MR-063): keep `-p "<prompt>"` LAST** — the variadic `--allowedTools` swallows a
  trailing bare prompt. Carry this as an inline comment in the wrapper so it is not re-broken.
  **Pin `--strict-mcp-config`** (verified flag: "Only use MCP servers from --mcp-config") so the
  agent's tool surface is exactly the one mdreview server — no ambient/inherited MCP merge — making
  the agent deterministic and narrowing any failure to compose wiring.
- **`watcher/agent-mcp.json`** — the agent's MCP config, promoted from `.scratch/agent-mcp.json` but
  with `MDREVIEW_BASE` set to **`http://mdreview:8080`** (compose service name) and the
  `mcp_server.py` path set to the in-image location. Points the agent's mdreview tools at the
  service over the compose network.
- **`Dockerfile.watcher`** — `node:22-bookworm-slim` base; `apt-get install python3` (for
  `watch.py` + `mcp_server.py`); `npm install -g @anthropic-ai/claude-code@<pinned>`; `COPY watch.py
  mcp_server.py watcher/launch.sh watcher/agent-mcp.json`; `chmod +x` the wrapper. **CMD runs
  `watch.py`.** The main `Dockerfile` is untouched (stays stdlib-only).
- **`docker-compose.yml`** — add a `watcher` service under `profiles: [watcher]` (so plain `up`
  excludes it), `build: { dockerfile: Dockerfile.watcher }`, and a **readiness-gated** dependency
  `depends_on: { mdreview: { condition: service_healthy } }` (NOT the bare `depends_on: [mdreview]`,
  which only orders start and lets the watcher poll `http://mdreview:8080` before the listener is up).
  The main image already defines a `HEALTHCHECK` (`Dockerfile:15`), so `service_healthy` is available
  and makes the e2e deterministic — no flaky first-poll race in the ~2 min MR-071 gate. Env:
  - `MDREVIEW_BASE: http://mdreview:8080`
  - `WATCH_TRUSTED_BASE: http://mdreview:8080` (EXACT match → vouches the non-loopback base; the
    fail-closed check at `watch.py:227` stays in force)
  - `WATCH_LAUNCH_CMD`: JSON-array argv invoking `watcher/launch.sh` (the must-configure gate at
    `watch.py:258`)
  - `WATCH_OWNER`: a stable owner id for the lease
  - `CLAUDE_CODE_OAUTH_TOKEN: ${CLAUDE_CODE_OAUTH_TOKEN}` — interpolated from an operator `.env`
    (gitignored), **never committed**.
- **`.env.example`** + **`.gitignore` add `.env`** — a committed template documenting the one
  variable (`CLAUDE_CODE_OAUTH_TOKEN=`), and a gitignore entry so the real `.env` never lands in
  git. (`.gitignore` currently has `.scratch/` but **not** `.env` — verified; this must be added.)

### UI

**No change.** No `viewer.html` / `dashboard.html` / `static/` work; no render-smoke applies. The
existing #26 "no watcher running" cue is what made this gap visible and stays as-is (it simply stops
firing once the watcher is up).

## Rollout phases

Each phase is independently shippable.

### Phase 1 — In-repo watcher assets (no deploy change yet)

Promote the prototype into `watcher/` (wrapper + agent MCP config) and add `.env.example` +
`.gitignore` `.env`. Shippable on its own: a host operator can already point `WATCH_LAUNCH_CMD` at
`watcher/launch.sh`. No image, no compose change yet — pure de-risking of the launch shape into the
repo, validated by `py_compile` (unchanged scripts) + a host dry-run of the wrapper.

### Phase 2 — `Dockerfile.watcher` + auth-verified image

Add `Dockerfile.watcher` (Node + python3 + pinned `claude` CLI + COPYs + a baked trusted-CWD
settings file so the workspace-trust dialog is skipped headlessly). Headline gate: build succeeds
**and** a container started with a real `CLAUDE_CODE_OAUTH_TOKEN`, run as the image's **actual runtime
user with a writable `$HOME`**, runs `claude` with the **real launch flag shape** (`--mcp-config
--strict-mcp-config --permission-mode dontAsk -p` last) and gets a **subscription response, no
keychain, no interactive login** — and separately completes a **first MCP round-trip** (the agent
calls one mdreview tool against a throwaway service). The auth/trust failure mode is made
distinguishable (auth error vs. trust-dialog timeout). This is the make-or-break test isolated to its
own ticket, retired before compose depends on it.

### Phase 3 — Compose profile (the opt-in deploy) + end-to-end

Add the `watcher` service under `profiles: [watcher]` to `docker-compose.yml`, readiness-gated on
the service (`condition: service_healthy`). Gates: plain `docker compose config` / `up` lists
**only** `mdreview` (no watcher); `--profile watcher up` brings up both; with a test token, a "Send to
agent" is picked up and an agent **actions a comment end-to-end** (doc changed + comment resolved +
turn returned, ~2 min cap) — on a throwaway compose project name/port, never the live `mdreview` /
`mdreview-data` / :8139 / :8137. **This is the merge that closes GH #30** (the working profile, not
the docs PR).

### Phase 4 — Operator runbook + docs

Document the one-time `claude setup-token` mint, the `.env` wiring, rotation, the Linux-host
`~/.claude/.credentials.json` mount alternative, a **cheap startup auth-probe** (so an expired token
surfaces at `up` time, not as a stranded review), and the explicit "this auto-actions every Sent
review; it is the **local single-user** path, not for a public instance" warning. Cross-link the
README watcher runbook. (GH #30 is already closed by MR-071's working-profile merge; this phase
references it, does not close it.)

## Non-goals

- **Bundling the watcher into the default deploy.** It stays profile-gated OFF; `docker compose up`
  is unchanged.
- **Public / multi-tenant hardening.** The existing host-side fail-closed watcher (arming allowlist,
  un-vouched-base refusal) remains the public-instance answer. This epic deliberately runs the
  watcher in the **vouched-base, arming-off** posture for local single-user use — auto-actioning
  every Sent review is **intended**, not a gap.
- **Adding Node or the `claude` CLI to the main service image.** The service stays stdlib-only
  Python; Node/claude live only in `Dockerfile.watcher`.
- **Any `app.py` / `watch.py` policy change.** No new endpoints, no new env semantics; this epic
  only packages and wires the existing generic launch interface.
- **API-key auth.** Subscription OAuth only (the affordability requirement).
- **UI changes.** No viewer/dashboard work.

## Key constraints

Hard rules, made specific to this repo (the footguns the implementer must respect):

- **Service image stays stdlib-only Python.** `Dockerfile` (the main image) is **not** edited; Node
  and `claude` exist only in `Dockerfile.watcher`. Verified the main image is `python:3.12-slim` with
  `COPY app.py viewer.html dashboard.html` + `static/` (`Dockerfile:8-9`).
- **Default `docker compose up` must NOT start the watcher.** The watcher service carries
  `profiles: [watcher]`; prove it with `docker compose config --services` (no profile) listing only
  `mdreview`. This is the opt-in gate and a hard AC.
- **The fail-closed trusted-base check STAYS and must be satisfied, not bypassed.**
  `MDREVIEW_BASE=http://mdreview:8080` is non-loopback (`watch.py:218`), so `WATCH_TRUSTED_BASE` must
  **exact-match** it (`watch.py:227-233`) — no wildcard, no prefix. An unset or mismatched
  `WATCH_TRUSTED_BASE` makes the watcher `sys.exit(2)` at startup; that is the intended fail-closed
  behavior and the compose env must set it correctly.
- **`WATCH_LAUNCH_CMD` is the must-configure gate** (`watch.py:258` `require_launch_configured_or_exit`):
  unset ⇒ the watcher refuses to start. The compose service must set it (JSON-array argv → the wrapper).
- **Never commit credentials.** `CLAUDE_CODE_OAUTH_TOKEN` comes only from a gitignored `.env`;
  `.env.example` ships with an **empty** value. Add `.env` to `.gitignore` (currently absent —
  verified). A ticket AC: `git status` after wiring shows no `.env`.
- **Do not disturb the live instance.** The live service is the `mdreview` container on **:8139**
  (volume `mdreview-data`); compose binds **:8137** + a project-prefixed volume. All build/test runs
  use **throwaway compose project names/ports** (`-p mdreview-wtest`, an unused host port) and
  `.scratch/` for temp — never `docker compose up` against the live volume.
- **Pin the `claude` CLI version** in `Dockerfile.watcher` (reproducible builds), with a bump comment.
- **`py_compile` gates apply** to `app.py` (untouched) and `watch.py` (untouched) on every ticket;
  `docker build` is the infra gate. No test framework.
- **Europe/London dates; Claude commit trailer; ticket ID in every commit subject.**

## Preferred execution order

1. **Phase 1** — `watcher/launch.sh`, `watcher/agent-mcp.json`, `.env.example`, `.gitignore` `.env`
   (assets in repo; host-runnable; no image).
2. **Phase 2** — `Dockerfile.watcher` with the **headless subscription-auth proof** (the gating risk
   retired early, before compose wiring depends on it).
3. **Phase 3** — `docker-compose.yml` `watcher` profile + the end-to-end Send→action gate.
4. **Phase 4** — operator runbook / README / `.env` + setup-token docs; close GH #30.

Service-before-UI ordering is moot (no UI); the real dependency is **auth-image before compose**, so
Phase 2 precedes Phase 3.

## Ticket breakdown

Create in `tickets/` after G1. IDs continue from MR-068 → **MR-069+**. Sprint: **sprint-25**.

| ID | Title | Layer | Phase |
|----|-------|-------|-------|
| MR-069 | Promote prototype into `watcher/` (wrapper + agent MCP config), `.env.example`, gitignore `.env` | infra | 1 |
| MR-070 | `Dockerfile.watcher` (Node + python3 + pinned `claude` CLI) + headless auth-proof (real flag shape, trust settled, runtime-user writable home) + first MCP round-trip | infra | 2 |
| MR-071 | `docker-compose.yml` `watcher` profile (off by default, `service_healthy` gated) + end-to-end Send→action gate; **closes GH #30** | infra | 3 |
| MR-072 | Operator runbook: `claude setup-token`, `.env`, rotation, Linux creds-mount alternative, startup auth-probe; README (references #30, does NOT close it) | docs | 4 |

Right-sizing notes: the auth risk is isolated to MR-070 so it is proven before MR-071's compose work
builds on it. MR-069 is a small, independently shippable promotion (host operators benefit
immediately). MR-072 is docs-only and depends on MR-070/MR-071 being real. If MR-070's image build +
auth proof proves heavy in practice, it may split into "image builds with a working `claude`" and
"env-var token authenticates headless" — but they share one Dockerfile, so they start as one ticket.

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| **`CLAUDE_CODE_OAUTH_TOKEN` does not authenticate a headless `claude` in a no-keychain Linux container** (the residual auth unknown). | Low–medium | Env var name + subscription billing verified; host prototype works. **MR-070 gates on an in-container `claude` run using the REAL flag shape (`--mcp-config --strict-mcp-config --permission-mode dontAsk -p`)** before any compose work, with the failure mode made distinguishable (auth error vs. trust-dialog timeout). If it fails: escalate from the ticket with the exact `claude` error; fallback path is mounting `~/.claude/.credentials.json` on Linux hosts (documented as the alternative). This is named as the single biggest risk. |
| **Fresh-container workspace-trust / onboarding dialog hangs the headless run** and looks like an auth failure. | Medium | Bake a trusted-CWD `--settings`/settings file into `Dockerfile.watcher`; MR-070's auth proof is `timeout`-boxed so a trust hang (exit 124) is distinguishable from a fast auth error. |
| **First `--mcp-config` MCP round-trip fails headless in the image** (silently folded into MR-071's e2e). | Medium | MR-070 proves it directly: agent calls one mdreview tool against a throwaway service over a private network, before compose. |
| **`claude` CLI image is large / npm install flaky / pinned version yanked.** | Medium | Pin a known-good version; `node:*-slim` base; build is the gate, so a bad pin fails CI not prod. Document the bump. Image size is acceptable for an opt-in local tool (not the default service image). |
| **Operator commits a real `.env`/token.** | Medium | `.gitignore` `.env` (added), `.env.example` empty, runbook says "never commit", AC asserts `git status` clean. |
| **Watcher auto-actions a review the operator did not intend** (vouched base ⇒ no arming). | Low (local, by design) | Documented as intended local-use behavior; the runbook offers optional `WATCH_ARMED_FILE` for operators who want per-review opt-in, and states plainly this is the local single-user path, not a public instance. |
| **Compose env mis-wires `WATCH_TRUSTED_BASE`** (e.g. trailing slash, `localhost` vs service name) ⇒ watcher `exit(2)`. | Low | EXACT-match documented; `watch.py` already emits a self-explaining refusal naming both values; AC checks the watcher container stays up (not exited). |
| **Watcher polls the service before its HTTP listener is up** (start-order race). | Low | `depends_on: { mdreview: { condition: service_healthy } }` against the main image's existing `HEALTHCHECK` (`Dockerfile:15`); MR-071 AC asserts the readiness condition is declared. |
| **Expired `setup-token` silently strands the first Sent review.** | Medium | MR-072 runbook adds a cheap startup auth-probe so an expired token surfaces a clear auth error at `up` time, not as a stuck review. |
| **Test run touches the live `mdreview`/:8139/`mdreview-data`.** | Low | All ACs mandate throwaway `-p` project name + unused port + scratch data; explicit "never the live volume" in every infra ticket. |

## Verification

Concrete and runnable. Infra epic ⇒ `docker build` + `docker compose` are the headline gates; no UI
⇒ no render-smoke. All container runs use a **throwaway compose project name and an unused host
port**, never the live `mdreview` / `mdreview-data` / :8139 / :8137.

**Common gate (every ticket):**
```bash
python3 -m py_compile app.py watch.py mcp_server.py     # must pass; these are untouched
```

**MR-069 (watcher assets in repo):**
```bash
# wrapper is executable and keeps the -p prompt as the FINAL argv token (MR-063 recipe gotcha:
# variadic --allowedTools swallows a trailing bare prompt, so -p "<prompt>" must come last).
# Assert structurally, NOT by matching a literal $PROMPT var name: the last `claude ...` token is `-p`
# immediately followed by exactly one final argument and nothing after it.
test -x watcher/launch.sh
# the claude invocation ends with `-p "<one arg>"` and no flags trail it:
grep -nE '(-p|--print)[[:space:]]+"[^"]*"[[:space:]]*$' watcher/launch.sh   # -p + its prompt are last
# negative guard: no flag token appears AFTER the -p prompt on the claude line
! grep -nE '(-p|--print)[[:space:]]+"[^"]*"[[:space:]]+--?[A-Za-z]' watcher/launch.sh
# agent MCP config points at the compose service, not localhost:8139
grep -q 'http://mdreview:8080' watcher/agent-mcp.json
# secrets hygiene
grep -qxF '.env' .gitignore                # .env is gitignored
test -f .env.example && ! grep -qE '=.+' .env.example   # template ships EMPTY value
git status --porcelain | grep -q '\.env$' && echo "FAIL: .env tracked" || echo "ok: no .env tracked"
# host dry-run: wrapper composes the claude argv without executing (REVIEW_ID stub)
REVIEW_ID=test1234 MDREVIEW_BASE=http://x:8080 MDREVIEW_OWNER=w bash -n watcher/launch.sh
```

**MR-070 (`Dockerfile.watcher` + headless subscription auth — the gating proof):**

This proof must exercise the **SAME flag shape the real launch uses** and settle the workspace-trust
/ onboarding dialog headlessly, or a green check here will not de-risk MR-071. `claude --help` warns
"The workspace trust dialog is skipped when Claude is run in directories you trust" (verified) — a
fresh container CWD with an empty `~/.claude` is **not** pre-trusted, so a naive run can **hang on a
trust/onboarding prompt** and masquerade as an auth failure. The Dockerfile must pre-trust the
working dir (a baked `--settings` JSON / settings file marking the CWD trusted, or the CLI's
documented headless-trust mechanism), and the proof must time-box the run so a trust hang is
**distinguishable** from an auth error (a fast non-zero auth error vs. a timeout = unresolved trust).

```bash
docker build -f Dockerfile.watcher -t mdreview-watcher:test .          # build succeeds
docker run --rm mdreview-watcher:test claude --version                 # claude CLI present + runs
docker run --rm mdreview-watcher:test python3 -c 'import sys;print(sys.version)'  # python3 present
docker run --rm mdreview-watcher:test id                               # confirm the runtime user

# (1) AUTH PROOF — token from operator env, NO keychain, NO interactive login, REAL flag shape.
#     Runs as the image's ACTUAL runtime user (NOT root) with a WRITABLE $HOME, because `claude` may
#     need ~/.claude scratch even with an env-token; a read-only/non-writable home would fail here.
#     Uses --mcp-config + --permission-mode dontAsk + --strict-mcp-config, with -p LAST — identical
#     to watcher/launch.sh — and a stub MCP config (no service needed yet) so this isolates AUTH+TRUST.
timeout 60 docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN="$TEST_TOKEN" mdreview-watcher:test \
  claude --mcp-config /app/watcher/agent-mcp.json --strict-mcp-config \
         --permission-mode dontAsk -p "Reply with the single word OK."
#   EXPECT : a subscription-billed reply containing OK, exit 0 — proves headless auth + trust settled.
#   FAIL-A : fast non-zero with an auth/login error  => token/auth path broken (the named big risk).
#   FAIL-B : `timeout` kills it (exit 124)           => trust/onboarding dialog HUNG, not auth — fix
#            the baked trust settings, do NOT mistake it for an auth failure.
# (TEST_TOKEN supplied by the operator at test time; never committed, never printed.)

# (2) MCP ROUND-TRIP PROOF — the first `--mcp-config` spawn-and-reach-service, proven HERE (not folded
#     silently into MR-071's e2e). Bring up a THROWAWAY service container on a private network, point
#     the agent's MCP at it, and have the agent call exactly ONE read-only mdreview tool.
docker network create wnet-test
docker run -d --name svc-test --network wnet-test mdreview-service:latest   # throwaway, no live volume
# agent-mcp.json here targets http://svc-test:8080 (or pass MDREVIEW_BASE via the MCP config's env)
timeout 90 docker run --rm --network wnet-test -e CLAUDE_CODE_OAUTH_TOKEN="$TEST_TOKEN" \
  mdreview-watcher:test \
  claude --mcp-config /app/watcher/agent-mcp.json --strict-mcp-config \
         --permission-mode dontAsk --allowedTools "mcp__mdreview__*" \
         -p "Call the mdreview list_reviews tool and report how many reviews exist."
#   EXPECT: the agent reaches the service and reports a count (0 on a fresh container) — proves the
#           in-image mcp_server.py spawns under `claude` and reaches the service headless.
#   --strict-mcp-config guarantees ONLY the mdreview server is loaded (no ambient merge) — deterministic
#   tool surface, so a failure here is the MCP wiring, not a stray inherited server.
docker rm -f svc-test; docker network rm wnet-test
```

Both proofs are MR-070's gate: auth+trust (1) and the first MCP round-trip (2) are retired **before**
MR-071 adds compose, so MR-071's failure surface narrows to compose wiring alone.

**MR-071 (compose profile — the opt-in gate + end-to-end):**
```bash
# 1) OPT-IN GATE: default config lists ONLY the service (no watcher)
docker compose -p mdreview-wtest config --services | sort        # EXPECT: mdreview   (NO watcher)
docker compose -p mdreview-wtest --profile watcher config --services | sort  # EXPECT: mdreview, watcher
# 2) default up starts only the service
docker compose -p mdreview-wtest up -d                           # NO --profile
docker compose -p mdreview-wtest ps --services                   # EXPECT: mdreview only
# 3) profile up starts both; the watcher waits for service HEALTH (condition: service_healthy),
#    so its first poll never races the listener; watcher stays UP (trusted-base satisfied, cmd set)
docker compose -p mdreview-wtest --profile watcher up -d
docker compose -p mdreview-wtest ps                              # both running; watcher not Exited
# confirm the readiness gate is declared (no bare list form):
docker compose -p mdreview-wtest --profile watcher config | grep -A2 'depends_on' | grep -q 'service_healthy'
# 4) END-TO-END (bounded ~2 min), against the THROWAWAY compose service, with a test token in .env:
#    a) create a review via the compose service port (NOT :8137/:8139)
#    b) add an open comment, flip turn=agent ("Send to agent")
#    c) poll: assert (doc changed) AND (comment resolved) AND (turn back to reviewer)
#    Example asserts (curl the compose host port $P):
curl -s "http://localhost:$P/api/reviews/$ID/status"   # turn -> "reviewer" after action
curl -s "http://localhost:$P/api/reviews/$ID/comments?status=open"   # the comment no longer open
# teardown — throwaway project + volume, never the live one
docker compose -p mdreview-wtest --profile watcher down -v
```
Expected JSON shape on success: `status` shows `turn":"reviewer"` and the resolved comment is absent
from the `status=open` list; the draft markdown reflects the requested edit.

**MR-072 (docs):** prose-only; verify the runbook documents (a) the one-time `claude setup-token`
mint, (b) `.env` wiring with `CLAUDE_CODE_OAUTH_TOKEN`, (c) rotation, (d) the Linux
`~/.claude/.credentials.json` mount alternative, (e) the explicit "auto-actions every Sent review;
local single-user only" warning, (f) the `--profile watcher up` command, and (g) a **cheap startup
auth-probe** the operator runs after `up` (e.g. `docker compose -p <proj> --profile watcher exec
watcher claude -p "ok" --strict-mcp-config` or equivalent) so an **EXPIRED `setup-token` surfaces at
deploy time** with a clear auth error, rather than silently stranding the first Sent review. Cross-
check the README watcher runbook reference resolves.

**GH #30 closes with the WORKING profile, not the docs PR.** The issue is closed by the merge that
lands the verified-deployable compose profile (**MR-071**), not MR-072 — do not close #30 before the
feature is provably deployable. (If MR-072 lands after MR-071, it references #30; it does not close it.)

## Review resolutions

### 2026-06-24 — staff-critic GO-WITH-NITS (no blockers)

1. **MR-070 first-run-trust gap.** Verified `claude --help` carries the trust-dialog note (and
   `--strict-mcp-config`). Rewrote MR-070's auth proof to run the **real launch flag shape**
   (`--mcp-config --strict-mcp-config --permission-mode dontAsk -p` last), require a baked
   trusted-CWD settings file in the Dockerfile to settle trust/onboarding headlessly, and `timeout`-box
   the run so a trust hang (exit 124) is distinguishable from a fast auth error. Updated Phase 2, the
   ticket-table title, and added a dedicated risk row.
2. **MR-070 MCP round-trip + `--strict-mcp-config`.** Added a second MR-070 proof: the agent calls one
   mdreview tool against a throwaway service over a private network, proving the first `--mcp-config`
   spawn-and-reach headless before MR-071. Pinned `--strict-mcp-config` in `watcher/launch.sh` (design
   section) for a deterministic tool surface. Added a risk row.
3. **MR-071 readiness.** Changed the compose dependency to `depends_on: { mdreview: { condition:
   service_healthy } }` (the main image's `HEALTHCHECK` at `Dockerfile:15` makes it available);
   removed the bare-list race. Added an AC asserting the readiness condition is declared and a risk row.
4. **MR-070 runtime user.** Baked "run as the image's actual runtime user (not root) with a writable
   `$HOME`" into the auth proof and the ticket title, since `claude` may need `~/.claude` scratch even
   with an env-token.
5. **MR-072 auth-probe + close-#30 owner.** Added a cheap startup auth-probe to the runbook (expired
   `setup-token` surfaces at `up` time). Moved the GH #30 close to **MR-071** (the working profile),
   not the docs ticket; updated Phase 3/4 and the ticket table.
6. **MR-069 nit.** Replaced the `$PROMPT`-var-name grep with a structural assertion that the `-p`
   prompt is the FINAL argv token (plus a negative guard that no flag trails it), citing the MR-063
   recipe gotcha rather than a literal variable name.
