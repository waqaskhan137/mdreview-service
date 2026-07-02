# Phase 0 runbook: private preview (TLS + OAuth gate, owner-only, zero app code)

Goal: get the existing mdreview app online at `https://app.mdreview.waqasrana.space`, behind
Google OAuth, reachable only by the owner. This proves DNS, TLS, the OAuth registration, and the
oauth2-proxy + nginx `auth_request` wiring, which are exactly the moving parts Phase 1 depends on.
No application code changes in this phase.

Phase 0 gates **every** path (including `/api`) behind oauth2-proxy with **no bearer exception**,
because per-user token auth does not exist yet. Agents stay local (pointed at your local instance).

## Prerequisites (owner actions, not scriptable here)

1. **DNS.** Add an `A` record `app.mdreview.waqasrana.space` -> the Kapture public IP (and `AAAA`
   if Kapture has a routable IPv6). If DNS is on Cloudflare, set the record to **DNS-only (grey
   cloud)** so certbot http-01 and the app work without Cloudflare in the path. The apex
   `mdreview.waqasrana.space` is unchanged (it stays GitHub Pages).
2. **Google OAuth client.** Google Cloud Console -> APIs & Services -> Credentials -> Create OAuth
   client ID -> **Web application**. Authorized redirect URI (exact):
   `https://app.mdreview.waqasrana.space/oauth2/callback`. Copy the client id + secret.
3. **Kapture host** has Docker + the existing nginx + certbot, and a webroot for http-01 challenges
   at `/var/www/certbot` (create it: `sudo mkdir -p /var/www/certbot`).

## Deploy

```bash
# On Kapture, in a checkout of this repo:
cp infra/deploy/.env.example infra/deploy/.env
# Fill OAUTH2_PROXY_CLIENT_ID / _SECRET, and generate the cookie secret:
python3 -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
#   -> paste into OAUTH2_PROXY_COOKIE_SECRET in infra/deploy/.env

# Confirm the invite list is owner-only:
cat infra/deploy/oauth2-proxy/invited-emails.txt      # waqaskhan137@gmail.com

# TLS cert (webroot; does NOT touch the hand-authored vhost):
sudo certbot certonly --webroot -w /var/www/certbot -d app.mdreview.waqasrana.space

# nginx vhost + the identity-blank snippet:
sudo cp infra/deploy/nginx/mdreview-blank-identity.conf /etc/nginx/snippets/
sudo cp infra/deploy/nginx/app.mdreview.conf /etc/nginx/sites-available/app.mdreview.waqasrana.space
sudo ln -sf /etc/nginx/sites-available/app.mdreview.waqasrana.space /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# App + oauth2-proxy (loopback-only publish):
docker compose -f infra/deploy/docker-compose.prod.yml --env-file infra/deploy/.env up -d
```

## Verify (do all of these before calling it done)

```bash
# 1. Unauthenticated browser is redirected to Google (not the dashboard):
curl -sS -o /dev/null -w "%{http_code} %{redirect_url}\n" https://app.mdreview.waqasrana.space/
#    -> 302 to /oauth2/start (or accounts.google.com), NEVER 200 with the dashboard.

# 2. The API is gated too (this is the whole point of "no bearer exception" in Phase 0):
curl -sS -o /dev/null -w "%{http_code}\n" https://app.mdreview.waqasrana.space/api/reviews
#    -> 302/401, NEVER a JSON list.

# 3. The app port is NOT publicly reachable (loopback-only publish + firewall):
curl -sS -m 5 http://<KAPTURE_PUBLIC_IP>:8140/healthz ; echo "exit=$?"
#    -> connection refused / timeout, NOT {"ok": true}.

# 4. Sign in as the owner in a browser -> the dashboard loads.
# 5. A non-allowlisted Google account -> 403 after authenticating (not admitted).
```

Firewall: only 22, 80, 443 should be open to the world. `8140` and `4180` are loopback-only.

## Rollback (instant, zero data impact)

```bash
sudo rm /etc/nginx/sites-enabled/app.mdreview.waqasrana.space && sudo systemctl reload nginx
docker compose -f infra/deploy/docker-compose.prod.yml down     # keeps the mdreview-prod volume
```

The app image and the `mdreview-prod` volume are untouched by enable/disable, so rollback is just
removing the vhost and stopping the containers.

## What Phase 1 adds on top (not in this phase)

Per-user isolation (`owner` field + 404-on-mismatch), the `X-Mdreview-Proxy` shared-secret gate,
per-user API bearer tokens (so agents create scoped reviews), the `X-Auth-Request-*` capture +
`X-Mdreview-Provider` tag in the nginx location, and the cookie-or-bearer routing. Ship the nginx
bearer routing and the app token check in the **same** deploy, or there is a window where the edge
lets a bearer through but the app cannot validate it (an open API). See the main plan.
