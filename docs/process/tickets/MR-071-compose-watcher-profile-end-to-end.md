---
id: MR-071
title: "`docker-compose.yml` `watcher` profile (off by default, health-gated) + end-to-end Send→action"
status: done           # backlog | ready | in-progress | review | done | blocked
layer: infra           # svc | ui | infra | docs
priority: P1           # P0 | P1 | P2 | P3
sprint: sprint-25
epic: watcher-container
depends_on: [MR-070]
branch: dev
created: 2026-06-24
updated: 2026-06-24
---

## Goal

Wire the watcher image into `docker-compose.yml` as an **opt-in** service behind a compose `profile`,
so a plain `docker compose up` starts ONLY the service and `docker compose --profile watcher up` adds
the agent runner. Prove the opt-in gate and the full end-to-end loop (Send → agent actions a comment →
resolves → hands back) in-container. **Closes GH #30** (the working, verifiably-deployable profile).
Depends on MR-070's auth + MCP proofs passing.

## Acceptance criteria

- [ ] A `watcher` service in `docker-compose.yml` under `profiles: [watcher]` (off by default), built
      from `Dockerfile.watcher`, with `MDREVIEW_BASE=http://mdreview:8080`, `WATCH_TRUSTED_BASE`
      vouching that **exact** base (fail-closed check stays satisfied), `WATCH_LAUNCH_CMD` →
      `watcher/launch.sh`, and `CLAUDE_CODE_OAUTH_TOKEN` from the gitignored `.env`.
- [ ] **Readiness, not just start-order:** `depends_on: { mdreview: { condition: service_healthy } }`
      (against the main image's existing `HEALTHCHECK`, `Dockerfile:15`), so the watcher's first poll
      never races the listener.
- [ ] **Opt-in proven:** `docker compose config --services` (no profile) lists **only** `mdreview`;
      `--profile watcher config --services` lists `mdreview` + `watcher`; a default `up` starts only
      the service. The existing default `up` behavior is otherwise unchanged.
- [ ] **End-to-end (bounded ~2 min):** with a test token in `.env`, `--profile watcher up`, then
      create a review on the compose port, add an open comment, flip `turn=agent` → assert the **doc
      changed**, the **comment is resolved**, and the **turn returns to reviewer**.
- [ ] **Closes GH #30** (the merge landing this profile, not the docs PR).
- [ ] No live instance touched: throwaway compose project name + unused host port + `down -v` teardown;
      never `mdreview`/`mdreview-data`/:8139/:8137.

## Notes / context

- Epic plan: `epics/watcher-container-plan.md` (MR-071 verification — the opt-in gate asserts + the
  e2e). The watcher attaches to the **compose** `mdreview` service, NOT the live :8139 container.
- Human dependency: a `setup-token` in `.env` (same as MR-070), gitignored, never committed.

## Work log

- `2026-06-24` — added the `watcher` service to `docker-compose.yml` under `profiles: ["watcher"]`
  (off by default), built from `Dockerfile.watcher`, `depends_on: { mdreview: { condition:
  service_healthy } }`, env `MDREVIEW_BASE`/`WATCH_TRUSTED_BASE`=`http://mdreview:8080`,
  `WATCH_LAUNCH_CMD`=`["bash","/app/watcher/launch.sh"]`, `CLAUDE_CODE_OAUTH_TOKEN: ${…:-}` (from a
  gitignored `.env`; empty-allowed so `config`/`up` work without it). Committed on dev.

## Validation

_Verified 2026-06-24 (G4). Opt-in proven on the real compose file; end-to-end on a throwaway project
(`mdreview-wtest`, port 8141, container_name overridden so it never collides with the live standalone
`mdreview`/:8139); `down -v` teardown; live :8139 confirmed untouched. **PASS.**_

- **Opt-in gate:** `docker compose config --services` (no profile) → **`mdreview` only**;
  `--profile watcher config --services` → **`mdreview` + `watcher`**; `service_healthy` declared in
  `depends_on`; `compose config -q` valid.
- **End-to-end (in-container agent, ~27s):** `--profile watcher up --build` → both services up,
  service healthy on :8141. Created a review with a typo + a comment ("fix teh→the"), flipped
  `turn=agent`; the **in-container watcher** picked it up, spawned a subscription-authed `claude`
  agent, and it fixed the typo, resolved the comment, handed back. FINAL: `turn=reviewer`,
  `state=done`, `open_comments=0`, source = "The colour of **the** sky is blue." PASS.
- No live instance touched; no token committed/printed (token from the gitignored `.scratch/.test-token`).

### Owed at G7 (re-drive against a fresh build)

- `docker compose -p mdreview-wtest config --services` → `mdreview` only; `--profile watcher config
  --services` → `mdreview, watcher`.
- `docker compose -p mdreview-wtest up -d` (no profile) → `ps --services` = `mdreview` only.
- `--profile watcher config | grep -A2 depends_on | grep service_healthy` (readiness declared).
- `--profile watcher up -d` → both up, watcher not Exited; end-to-end: create review → comment → Send →
  `/status` turn back to `reviewer` + comment absent from `?status=open` + draft reflects the edit.
- `docker compose -p mdreview-wtest --profile watcher down -v` (throwaway teardown).

## Follow-ups

- MR-072 writes the operator runbook (references #30, does not re-close it).
