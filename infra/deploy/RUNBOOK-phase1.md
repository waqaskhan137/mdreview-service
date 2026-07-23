# Phase 1 runbook: invite-only multi-user (per-user tokens + owner isolation)

Turns the Phase 0 preview into the real multi-user service: agents create docs via a per-user token,
each human sees only their own reviews. Auth becomes MANDATORY. This MUST be a single atomic cutover:
the app (REQUIRE_AUTH on) and the cookie-or-bearer nginx vhost go live together, or there is a
window where nginx forwards a Bearer to an auth-off app = unauthenticated read/delete of every
review. The prod compose forces `MDREVIEW_REQUIRE_AUTH=1` and the app refuses to boot without the
secrets, so the app cannot come up open; still, do the steps in order.

Prereqs: Phase 0 is already deployed (this repo at ~/mdreview-deploy on Kapture, oauth2-proxy on
:4181, the app on 127.0.0.1:8140). The app image must contain the Phase 1 code (build it below).

```bash
# On Kapture, in ~/mdreview-deploy (or a fresh checkout of branch feat/hosted-phase1):

# 1. Secrets: add the three Phase 1 secrets to infra/deploy/.env (600). Generate:
python3 -c "import secrets; print('MDREVIEW_PROXY_SECRET=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('MDREVIEW_TOKEN_PEPPER=' + secrets.token_urlsafe(32))"
# MDREVIEW_SESSION_SECRET signs the app-owned session cookie + magic-link tokens (#67); it joined
# the boot guard, so REQUIRE_AUTH now refuses to start without it. Keep it STABLE once set (rotating
# it logs everyone out).
python3 -c "import secrets; print('MDREVIEW_SESSION_SECRET=' + secrets.token_urlsafe(32))"
#   -> append all three to infra/deploy/.env

# 2. nginx host-only proxy-secret snippet: MUST equal MDREVIEW_PROXY_SECRET from .env.
sudo cp infra/deploy/nginx/mdreview-proxy-secret.conf.example /etc/nginx/snippets/mdreview-proxy-secret.conf
sudo sed -i "s#REPLACE_WITH_MDREVIEW_PROXY_SECRET#$(grep '^MDREVIEW_PROXY_SECRET=' infra/deploy/.env | cut -d= -f2-)#" /etc/nginx/snippets/mdreview-proxy-secret.conf
sudo chmod 600 /etc/nginx/snippets/mdreview-proxy-secret.conf

# 3. Build the Phase 1 app image locally on the host (experiment box; no main-merge/release yet).
docker build -f infra/Dockerfile -t mdreview-service:phase1 .
#   -> then point the compose at it: set `image: mdreview-service:phase1` on the mdreview service in
#      infra/deploy/docker-compose.prod.yml (or override with a compose.override), so it does not
#      pull the auth-less ghcr :latest.

# 4. Bring the app up WITH auth (compose ${VAR:?} + the app boot-guard fail closed if a secret is missing).
docker compose -f infra/deploy/docker-compose.prod.yml --env-file infra/deploy/.env up -d
docker logs --tail 5 mdreview        # must show it started (not a SystemExit about secrets)

# 5. Backfill owner on any pre-auth reviews (else they 404 for everyone). owner id = provider:sub of
#    the owner's Google account (google:<sub>; find it at https://app.waqasrana.space/oauth2/userinfo).
docker compose -f infra/deploy/docker-compose.prod.yml exec mdreview python -m mdreview.migrate google:100706495352040931339

# 6. nginx: install the limit zones + swap in the cookie-or-bearer vhost (blank snippet already present).
sudo cp infra/deploy/nginx/mdreview-limits.conf /etc/nginx/conf.d/
sudo cp infra/deploy/nginx/app.waqasrana.space.conf /etc/nginx/sites-available/app.waqasrana.space
sudo nginx -t && sudo systemctl reload nginx
```

## Verify (all before calling it done)

```bash
# Owner still gets in (browser, existing Google session) -> dashboard.
# Agent path works:
curl -sS -o /dev/null -w "%{http_code}\n" https://app.waqasrana.space/api/reviews            # no cred -> 302/401
curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer totally-fake" https://app.waqasrana.space/api/reviews
#   -> 401 (NOT 200, NOT a review list). This is the P0 regression check: a bogus bearer must be rejected.
# Mint a real token in the browser at /account, then:
curl -sS -H "Authorization: Bearer mdr_..." https://app.waqasrana.space/api/reviews             # -> the owner's reviews
# app port still not public:
curl -sS -m 5 http://72.62.4.70:8140/healthz ; echo "exit=$?"                                    # -> refused/timeout
```

The critical check is the bogus-bearer one: it MUST be 401. If it returns data, the app is running
auth-off, stop and fix `MDREVIEW_REQUIRE_AUTH` before leaving it exposed.

## Rollback

Revert nginx to the Phase 0 vhost (gates everything through oauth2-proxy, no bearer) and reload;
optionally `docker compose ... up -d` the previous image. The `owner` field and users.json are
additive and inert to older code. Keep a pre-cutover volume tar for a hard rollback.
