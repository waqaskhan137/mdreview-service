# RUNBOOK — staging.mdreview.space (Kapture)

The isolated staging stack: every `dev` push builds `ghcr.io/ranawaqas-ai/mdreview-service:dev`
(`.github/workflows/staging-image.yml`, boot-smoke-gated), and this host's 15-min auto-update timer
pulls + health-gates it. Runs the NATIVE hosted plane (magic-link + sharing + admin), stub email.
Shares NOTHING with prod (`app.mdreview.space` / `~/mdreview-deploy` / `:8140`). Do this via the
infra-manager skill; it touches the prod box, so it needs the owner's explicit second go.

## Isolation contract (verify at the end)
| Axis | prod | staging |
|---|---|---|
| dir | `~/mdreview-deploy` | `~/mdreview-staging` |
| compose project | `mdreview-deploy` | `mdreview-staging` |
| container | `mdreview` | `mdreview-staging` |
| data volume | `..._mdreview-prod` | `mdreview-staging-data` |
| loopback port | 8140 | 8141 |
| domain | app.mdreview.space | staging.mdreview.space |
| image | `mdreview-service-latex:latest` | `mdreview-service:dev` (slim, latex off) |
| nginx zones | `mdreview_req/conn` | `mdreview_staging_req/conn` |
| auth | oauth2-proxy @ :4181 | native plane, `ALLOW_PROXY_PLANE=0`, no sidecar |
| autoupdate | `mdreview-autoupdate.*` (30m) | `mdreview-staging-autoupdate.*` (15m) |

## 1. DNS
`staging.mdreview.space` A → `72.62.4.70` (Kapture). Wait for propagation before certbot.

## 2. Deploy dir + files
```
mkdir -p ~/mdreview-staging/nginx ~/mdreview-staging/systemd
# from the repo checkout on the host (or scp): copy the staging files in
cp infra/deploy/docker-compose.staging.yml infra/deploy/auto-update.sh ~/mdreview-staging/
cp infra/deploy/nginx/staging.mdreview.space.conf infra/deploy/nginx/mdreview-staging-limits.conf ~/mdreview-staging/nginx/
chmod +x ~/mdreview-staging/auto-update.sh
```

## 3. Secrets (host-only, 600)
```
cp infra/deploy/.env.staging.example ~/mdreview-staging/.env.staging && chmod 600 ~/mdreview-staging/.env.staging
# fill in: SESSION_SECRET, TOKEN_PEPPER, PROXY_SECRET (all `openssl rand -hex 32`; PROXY_SECRET is
# inert), OWNER_EMAIL = the owner's verified email. All DISTINCT from prod's.
```

## 4. TLS (do NOT use `certbot --nginx` — it rewrites the vhost)
```
sudo certbot certonly --webroot -w /var/www/certbot -d staging.mdreview.space
# confirm the renew deploy-hook reloads nginx (else staging TLS dies in ~90d):
sudo ls /etc/letsencrypt/renewal-hooks/deploy/   # a hook doing `systemctl reload nginx` must exist
sudo certbot renew --dry-run
```

## 5. nginx
```
sudo cp ~/mdreview-staging/nginx/mdreview-staging-limits.conf /etc/nginx/conf.d/
sudo cp ~/mdreview-staging/nginx/staging.mdreview.space.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/staging.mdreview.space.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx      # nginx -t must pass for BOTH stacks (distinct zones)
```

## 6. First boot + verify
```
cd ~/mdreview-staging
docker compose -p mdreview-staging -f docker-compose.staging.yml --env-file .env.staging up -d
docker logs --tail 30 mdreview-staging          # expect "mdreview-service HOSTED ... listening on :8080"
curl -fsS http://127.0.0.1:8141/healthz && echo  # 200
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8141/api/reviews   # 401 (auth enforced)
```
End-to-end hosted-plane smoke (the staging URL): magic-link login (grab the link from
`docker logs mdreview-staging` — stub email), create a doc, make it public (anon view in a logged-out
browser), share to a second account, do an admin action and confirm its audit row.

## 7. Auto-update timer
```
sudo cp infra/deploy/systemd/mdreview-staging-autoupdate.service /etc/systemd/system/
sudo cp infra/deploy/systemd/mdreview-staging-autoupdate.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mdreview-staging-autoupdate.timer
sudo systemctl start mdreview-staging-autoupdate.service   # one manual run; tail the log
tail -f ~/mdreview-staging/auto-update.log
```

## 8. Isolation proof (must pass before calling this done)
```
./infra/deploy/check-drift-staging.sh          # CLEAN
./infra/deploy/check-drift.sh                  # prod STILL CLEAN (staging touched nothing)
sudo systemctl start mdreview-autoupdate.service && tail ~/mdreview-deploy/auto-update.log  # prod updater still green
```
`docker inspect mdreview-staging` mounts only `mdreview-staging-data`; prod's `mdreview` container,
`:8140`, volume, network, oauth2-proxy, secrets, and timer are all untouched.

## Rollback
Bad `:dev` digest → auto-update rolls back + latches it (`check-drift-staging.sh` flags the pause).
Whole stack → `docker compose -p mdreview-staging down && rm -rf ~/mdreview-staging` + remove the two
systemd units and the nginx vhost/limits. Prod is unaffected.
