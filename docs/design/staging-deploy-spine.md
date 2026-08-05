# Plan: dev → staging deployment (rev 3, G1 CLEAR after round 3)

> Status: PLAN — critic-cleared round 3 (spine approved 2026-07-24; revised through rounds 1-2, verified
> clean round 3). Awaiting owner approval. URL:
> **`https://staging.mdreview.space`**. Decisions: Kapture isolated stack · auto-update pull
> (reuse #88) · activate the new hosted plane (`python -m mdreview.hosted`).

## Goal
Every `dev` image auto-deploys to an isolated staging stack on Kapture running the new hosted
plane (native magic-link + sharing + admin) at `https://staging.mdreview.space`, validating the
overnight cluster end-to-end before prod. Prod (`app.mdreview.space`, `~/mdreview-deploy`) untouched.

## Part A — repo (one PR into `dev`, reversible, zero host change)

1. **`.github/workflows/staging-image.yml`** — on `push: branches: [dev]`, build+push
   **`ghcr.io/${{ github.repository_owner }}/mdreview-service-latex:dev`** (= `ranawaqas-ai`, matching
   `release.yml` — MF1). Reuse `release.yml`'s build/login steps. Add
   `concurrency: { group: staging-image, cancel-in-progress: true }` (a dev-push burst builds once).
2. **`infra/deploy/docker-compose.staging.yml`** — project `mdreview-staging`; **compose service KEY
   AND `container_name` both `mdreview-staging`** (MF2 + R2/worth: auto-update.sh uses `MDR_SERVICE`
   as both the `compose up -d <svc>` arg and the `docker inspect` name — the service key, not just the
   container_name, must match); image `ghcr.io/ranawaqas-ai/mdreview-service-latex:dev`; **entrypoint
   `python -m mdreview.hosted`**; own volume `mdreview-staging-data`; own docker network (compose
   default per-project, kept distinct); app loopback `127.0.0.1:8141` (prod 8140); env-file
   `.env.staging` (host-only): `MDREVIEW_PUBLIC_BASE=https://staging.mdreview.space`,
   `MDREVIEW_REQUIRE_AUTH=1`, `MDREVIEW_OWNER_EMAIL=<owner>`, `MDREVIEW_ALLOW_STUB_EMAIL=1`,
   `MDREVIEW_SESSION_SECRET`, `MDREVIEW_TOKEN_PEPPER`, **`MDREVIEW_ALLOW_PROXY_PLANE=0`** (MF3 — native
   plane only; nginx sets no proxy header and identity.py never builds the proxy plane), plus a **fresh
   inert `MDREVIEW_PROXY_SECRET`** (R2-NEW: `config.py:47`'s guard hard-requires it at IMPORT time
   whenever `REQUIRE_AUTH=1`, and that guard is NOT `ALLOW_PROXY_PLANE`-aware — it protects the
   non-hosted path, so we satisfy it rather than weaken it; the value is never consumed because the
   proxy plane isn't built), `ENABLE_LATEX` unset/off. No oauth2-proxy service.
3. **`.github/`/`infra/deploy/auto-update.sh` — add two backward-compatible params (MF2).** New
   `MDR_COMPOSE_FILE` (default `docker-compose.prod.yml`) and `MDR_ENV_FILE` (default `.env`); the
   `compose()` helper uses them. Prod's defaults are byte-unchanged (re-test prod's updater after the
   edit — this is prod's live script; the repo edit reaches prod only on a deliberate repo-sync).
   Staging's autoupdate config sets `MDR_DEPLOY_DIR=~/mdreview-staging`,
   `MDR_COMPOSE_FILE=docker-compose.staging.yml`, `MDR_ENV_FILE=.env.staging`,
   `MDR_SERVICE=mdreview-staging`, `MDR_IMAGE=ghcr.io/ranawaqas-ai/mdreview-service-latex:dev`,
   **`MDR_HEALTH=http://127.0.0.1:8141/healthz`**, **`MDR_AUTHPROBE=http://127.0.0.1:8141/api/reviews`**
   (R2-MF2: both default to prod's `:8140` — without overriding them staging's health gate probes PROD
   and false-greens a broken `:dev`), distinct `MDR_LOG`. A **distinct systemd unit**
   `mdreview-staging-autoupdate.{service,timer}` (`OnUnitActiveSec=15min`, reconciled — MF/worth) so it
   never shares state with prod's timer.
4. **`infra/deploy/nginx/staging.mdreview.space.conf` — authored FRESH for native auth (MF3), NOT a
   mirror.** `server_name staging.mdreview.space`; own cert path; `proxy_pass http://127.0.0.1:8141`.
   **No `/oauth2/*`, no `auth_request`, no `mdreview-proxy-secret` snippet/header** (the native plane
   needs none, and this removes the spoofable-header surface at the root). Public reads + `/auth/`
   serve unauthenticated (the app enforces custody); include a **staging-specific limits** file, not
   prod's.
5. **`infra/deploy/nginx/mdreview-staging-limits.conf` (MF4)** — its OWN
   `limit_req_zone …=mdreview_staging_req` / `limit_conn_zone …=mdreview_staging_conn` (distinct zone
   names, http-context conf.d, so no duplicate-zone `nginx -t` failure that would wedge prod's reload).
6. **`check-drift.sh` — a SEPARATE staging code path (worth-considering).** Staging has no
   oauth2-proxy and a different `PUBLIC_BASE`; assert staging's dir/volume/port/`REQUIRE_AUTH`/
   `PUBLIC_BASE=staging.mdreview.space`/`ALLOW_PROXY_PLANE=0`, that it shares nothing with prod, AND a
   **staleness signal** (staging image age / last-successful-update, so a latched-bad `:dev` doesn't
   give false "dev is green").
7. **`infra/deploy/.env.staging.example`** + `RUNBOOK-staging.md` (incl. the certbot renew
   deploy-hook that reloads nginx — else staging TLS dies in 90 days).

## Part B — host (infra-manager on Kapture; SECOND explicit go — touches the prod box)
1. **DNS:** `staging.mdreview.space` A → Kapture IP (owner confirms the IP; likely `72.62.4.70`).
2. **Cert:** `certbot certonly --webroot` for `staging.mdreview.space`; confirm `certbot renew`'s
   nginx-reload deploy-hook covers it.
3. **Host secrets** (`~/mdreview-staging/.env.staging`, 600): fresh `SESSION_SECRET` + `TOKEN_PEPPER`
   + a fresh **inert** `PROXY_SECRET` (all `openssl rand`; the proxy secret is required only to pass
   `config.py:47`'s import-time guard, never used at runtime with the plane off),
   `MDREVIEW_OWNER_EMAIL`=owner, `MDREVIEW_ALLOW_STUB_EMAIL=1`. All distinct from prod's.
4. **Deploy dir:** `~/mdreview-staging` (the ONLY staging dir — #86 one-source rule).
5. **First boot + verify:** `docker compose -p mdreview-staging -f docker-compose.staging.yml
   --env-file .env.staging up -d`; `/healthz` 200; loopback `:8141 /api/reviews` → 401;
   `staging.mdreview.space` → native login; end-to-end smoke: stub-link login (from logs), create a
   doc, make it public (anon views), share to a 2nd account, an admin action + its audit row.
6. **Isolation proof:** `docker inspect` shows staging mounts only `mdreview-staging-data`; prod's
   volume/`:8140`/`~/mdreview-deploy`/container `mdreview` untouched; **prod's own auto-update re-tested
   green**; `check-drift.sh` CLEAN for BOTH stacks.

## Isolation contract (non-negotiable)
| Axis | prod | staging |
|---|---|---|
| dir | `~/mdreview-deploy` | `~/mdreview-staging` |
| compose project | `mdreview-deploy` | `mdreview-staging` |
| container name | `mdreview` | `mdreview-staging` |
| data volume | `mdreview-deploy_mdreview-prod` | `mdreview-staging-data` |
| docker network | prod default | staging default (distinct) |
| app port | 8140 | 8141 |
| domain | app.mdreview.space | staging.mdreview.space |
| image tag | `:latest` | `:dev` |
| **nginx rate-limit zones** | `mdreview_req/conn` | `mdreview_staging_req/conn` |
| auth | oauth2-proxy (Google) @ :4181 | native plane, `ALLOW_PROXY_PLANE=0`, NO oauth2-proxy |
| autoupdate unit | `mdreview-autoupdate.*` | `mdreview-staging-autoupdate.*` |
| health/authprobe target | `:8140` | `:8141` (overridden — never prod) |
| secrets / owner-email | prod set | fresh staging set (PROXY_SECRET inert) |
Staging touches NO prod data, volume, port, network, secret, oauth client, nginx zone, or timer.

## Accepted staging risks (stub-email on a shared, open box)
- Anyone with Docker/log access on Kapture can complete a login as any email (stub logs the link).
  Acceptable for bring-up; external testers would need a real `MDREVIEW_SMTP_HOST`.
- The 500/day global magic-link budget is a lock-out lever. Low severity for staging.

## Verify / rollback / out of scope
- **Verify:** a **boot smoke with the exact staging env** (`REQUIRE_AUTH=1`, `ALLOW_PROXY_PLANE=0`,
  inert `PROXY_SECRET`, `SESSION_SECRET`, `TOKEN_PEPPER`, `OWNER_EMAIL`, https `PUBLIC_BASE`, stub
  email) — asserts the container reaches `/healthz` 200 and does NOT `SystemExit` at import (locks
  R2-NEW against regression, since the fail-closed tests don't run with `REQUIRE_AUTH=1`). **Land it as
  an automated test on the dev PR, not a manual host step** (R3/worth) so a future `config.py` guard
  change can't silently reintroduce the crash-loop. **Standing gate assumption (R3/worth): on the
  hosted build an anonymous loopback `GET /api/reviews` returns exactly `401`** — the auto-update
  health gate requires `health=200 AND authprobe=401`, and staging is the first hosted-plane consumer
  of that gate; a hosted anonymous principal that ever yields `200` would false-green every deploy (the
  class R2-MF2 targeted). Then health-gate each auto-deploy; `check-drift.sh` clean for both; staleness
  signal green; the hosted-plane smoke passes.
- **Rollback:** auto-update rolls back a bad `:dev` digest; whole stack = `docker compose -p
  mdreview-staging down` + `rm -rf ~/mdreview-staging` — prod unaffected.
- **Out of scope:** touching prod; auto-promote dev→main→prod (G8 stays manual); real email;
  `ENABLE_LATEX` on staging until the latex module's custody is separately verified; who-gets-paged
  on a latched rollback (staging is silent-until-checked for now). **Deferred (not this plan): making
  `config.py:47` hosted-aware so the hosted plane needn't carry an inert `PROXY_SECRET`.** It touches a
  guard that is the non-hosted path's ONLY defense against empty-header impersonation (`server.py:97`
  → `ProxyBearerIdentity`, `access.py:113`); a naive shared gate on `ALLOW_PROXY_PLANE` would open a
  `REQUIRE_AUTH=1 + ALLOW_PROXY_PLANE=0` non-hosted instance to spoofed identity headers. Own PR, own
  security review.
