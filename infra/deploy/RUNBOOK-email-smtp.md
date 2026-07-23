# Runbook: real magic-link email delivery via Azure Communication Services (ACS) SMTP

The native login plane (#67) sends a magic link by email. The send code is already built and shipped:
`src/mdreview/hosted/magiclink.py` (`SmtpEmailSender`) + `select_email_sender()` in `hosted/compose.py`.
It runs in **stub** mode (links logged, not sent) until `MDREVIEW_SMTP_HOST` is set. This runbook
provisions an ACS SMTP relay and flips it to real delivery. **No application code changes.**

## The switch (what the app reads)
`select_email_sender()` (verified): `MDREVIEW_SMTP_HOST` set -> real `SmtpEmailSender`; else
`MDREVIEW_ALLOW_STUB_EMAIL=1` -> stub (loud warning); else refuse to boot. Env it reads:

| var | meaning |
| --- | --- |
| `MDREVIEW_SMTP_HOST` | `smtp.azurecomm.net` — **presence flips stub -> real** |
| `MDREVIEW_SMTP_PORT` | `587` (STARTTLS) or `465` (implicit TLS). Default 587 |
| `MDREVIEW_SMTP_USER` | ACS: `<acs-resource-name>.<entra-app-id>.<tenant-id>` |
| `MDREVIEW_SMTP_PASSWORD` | the Entra app **client secret** |
| `MDREVIEW_SMTP_FROM` | a **verified** sender on the domain. **Set it** — it falls back to `_USER` (a composite string, not an email) |
| `MDREVIEW_SMTP_STARTTLS` | `1` (default) on 587; `0` only for implicit-TLS 465 |

## Privilege split — read this first
ACS SMTP authenticates with a **Microsoft Entra app** (app registration + client secret + a role on
the ACS resource). That splits the work across two rights levels:

- **Part A — DIRECTORY (Microsoft Entra).** Create the app + a client secret. Needs a **directory**
  role (Global Administrator, Cloud Application Administrator, or at least Application Developer) in
  the tenant. A subscription `Owner` does **not** grant this. *A guest/external member typically
  cannot — this is the step that blocks anyone without directory rights.*
- **Part B/C/D — ARM + host.** Create the ACS resources, assign the role, DNS, and the host cutover.
  Needs subscription **Owner** (or Contributor + User Access Administrator) — no directory rights.

So a subscription-Owner-but-not-directory-admin operator does Parts B–D; a directory admin must do
Part A (once) and hand back `appId`, `tenantId`, and the client secret.

Tenant/sub in use (2026-07-23): subscription `d2c647c5-827f-418a-828d-ea4b8af22ea9`
("Azure subscription 1"), tenant `b9949f2d-36ac-4756-ac98-1f968203ddf0`.

```bash
az login                                             # already logged in on the ops box
az account set --subscription d2c647c5-827f-418a-828d-ea4b8af22ea9
az extension add --name communication                # needs az >= 2.67 (installed: 2.88, ext 1.14)
RG=mdreview-email
```

## Part A — DIRECTORY: the Entra app + secret  (directory admin only)
```bash
az ad app create --display-name mdreview-smtp --sign-in-audience AzureADMyOrg
APP_ID=$(az ad app list --display-name mdreview-smtp --query "[0].appId" -o tsv)
az ad sp create --id "$APP_ID"

# Client secret -> capture to a 600 file, NEVER echo it to the terminal (it lands in shell history/logs).
umask 077
az ad app credential reset --id "$APP_ID" --years 1 --query password -o tsv > ~/.mdreview-smtp-secret
chmod 600 ~/.mdreview-smtp-secret
TENANT_ID=$(az account show --query tenantId -o tsv)
echo "Hand back to the ops operator:  APP_ID=$APP_ID  TENANT_ID=$TENANT_ID  (secret is in ~/.mdreview-smtp-secret)"
```
> If Part A errors `Insufficient privileges`, you are not a directory admin — this step must be run by
> one (portal: Microsoft Entra ID -> App registrations -> New registration -> Certificates & secrets).

## Part B — ARM: the ACS resources + role  (subscription Owner)
```bash
az group create -n $RG -l westeurope                 # RG location is metadata; ACS resources are 'global'

# 1. Email Communication Service (hosts domains)
az communication email create -n mdreview-ecs -g $RG --location global --data-location Europe

# 2a. STAGING — Azure-managed domain (instant, auto SPF/DKIM, no DNS). Sender: DoNotReply@<guid>.azurecomm.net
az communication email domain create -n AzureManagedDomain --email-service-name mdreview-ecs -g $RG \
  --location global --domain-management AzureManaged
DOMAIN=AzureManagedDomain

# 2b. PROD — custom domain (skip for staging). Requires Part C (DNS) before it verifies.
# az communication email domain create -n mail.mdreview.space --email-service-name mdreview-ecs -g $RG \
#   --location global --domain-management CustomerManaged
# DOMAIN=mail.mdreview.space

# 3. Communication Services hub + link the domain
DOMAIN_ID=$(az communication email domain show -n $DOMAIN --email-service-name mdreview-ecs -g $RG --query id -o tsv)
az communication create -n mdreview-acs -g $RG --location global --data-location Europe \
  --linked-domains "$DOMAIN_ID"

# 4. Grant the Entra app (Part A) the send role on the ACS resource (needs RBAC Admin/Owner)
ACS_ID=$(az communication show -n mdreview-acs -g $RG --query id -o tsv)
az role assignment create --assignee "$APP_ID" \
  --role "Communication and Email Service Owner" --scope "$ACS_ID"
```

## Part C — DNS  (PROD custom domain only; STAGING skips this)
```bash
# Read the records ACS wants published, then add them at the mdreview.space DNS provider:
az communication email domain show -n mail.mdreview.space --email-service-name mdreview-ecs -g $RG \
  --query "verificationRecords"
#   Domain = 1 TXT | SPF = 1 TXT (an include) | DKIM = 2 CNAMEs (selector1/selector2 ..._domainkey...)
#   Also author a DMARC TXT at _dmarc.mail.mdreview.space:  "v=DMARC1; p=none; rua=mailto:dmarc@mdreview.space"
# After DNS propagates (15-30 min) ask Azure to verify each:
for T in Domain SPF DKIM DKIM2; do
  az communication email domain initiate-verification -g $RG --email-service-name mdreview-ecs \
    --domain-name mail.mdreview.space --verification-type $T
done
```

## Part D — configure the host + cut over  (STAGING first)
```bash
# On the Kapture host, in ~/mdreview-deploy (staging stack). Compose already passes MDREVIEW_SMTP_*.
# The SMTP username is <acs-name>.<app-id>.<tenant-id>. Get the sender ('MailFrom') from the domain
# (managed default: DoNotReply@<guid>.azurecomm.net) or add a friendly one:
#   az communication email domain sender-username create --sender-username no-reply --username no-reply \
#     --domain-name $DOMAIN --email-service-name mdreview-ecs -g $RG

# Append to infra/deploy/.env.staging (chmod 600). Read the secret from the 600 file, do not paste it.
cat >> infra/deploy/.env.staging <<EOF
MDREVIEW_SMTP_HOST=smtp.azurecomm.net
MDREVIEW_SMTP_PORT=587
MDREVIEW_SMTP_STARTTLS=1
MDREVIEW_SMTP_USER=mdreview-acs.$APP_ID.$TENANT_ID
MDREVIEW_SMTP_PASSWORD=$(cat ~/.mdreview-smtp-secret)
MDREVIEW_SMTP_FROM=<the verified sender, e.g. DoNotReply@<guid>.azurecomm.net>
EOF
chmod 600 infra/deploy/.env.staging
# remove the stub flag so a misconfig fails loudly instead of silently logging tokens:
sed -i '/MDREVIEW_ALLOW_STUB_EMAIL/d' infra/deploy/docker-compose.staging.yml   # or edit by hand

docker compose -f infra/deploy/docker-compose.staging.yml --env-file infra/deploy/.env.staging up -d
docker logs --tail 15 <staging-container>     # must NOT show the "STUB email backend" warning
```

### Smoke (the ticket's done-criterion)
```bash
curl -sS -X POST https://staging.mdreview.space/auth/magic-link \
  -H 'Content-Type: application/json' -d '{"email":"you@a-real-inbox.example"}'
#  -> 200 (enumeration-safe). Check the inbox: the link arrives, SPF+DKIM PASS in the headers,
#     clicking it hits /auth/redeem and establishes a session (GET /auth/session -> your identity).
```
Confirm SPF/DKIM/DMARC pass (message headers or mail-tester.com). Abuse limits are built-in (3/addr/15m,
10/IP/hr, 500/day global) — override via `MDREVIEW_MAGICLINK_MAX_PER_ADDRESS|MAX_PER_IP|DAILY_BUDGET`
if the ACS quota differs.

## Rollback
Restore the stub: put `MDREVIEW_ALLOW_STUB_EMAIL: "1"` back (or blank `MDREVIEW_SMTP_HOST`) and redeploy.
The Azure resources are inert when unreferenced (ACS Email is pay-per-send); to fully remove: delete the
role assignment, the RG (`az group delete -n mdreview-email`), and the `mdreview-smtp` app registration.

## Notes / gotchas
- **`--data-location`** is required on `email create` and `communication create` (Europe | UnitedStates | ...).
- **Never `echo` the client secret** — capture to a 600 file (Part A) and read it into `.env` (Part D).
- **`MDREVIEW_SMTP_FROM`** must be a verified sender on the domain; unset -> falls back to `_USER` (a
  composite Entra string, not an email) -> broken From header.
- Deliverability for a young custom domain is the long pole; keep DMARC at `p=none` initially and use
  Google-secondary as the escape hatch if links spam-folder.
