#!/usr/bin/env bash
# check-drift-staging.sh — drift + isolation check for the STAGING stack on Kapture. Separate from
# check-drift.sh (prod) on purpose: staging has NO oauth2-proxy, a different domain, and its own
# dir/volume/port — so it asserts a different invariant set, and prod's incident-hardened checker stays
# untouched. Also carries a STALENESS signal: staging must actually be tracking dev, not latched on a
# bad :dev digest that would make "dev is green" a lie. Exit 0 = clean, 1 = drift.
#
#   ./infra/deploy/check-drift-staging.sh          # from a machine with `ssh kapture`
#   HOST= ./infra/deploy/check-drift-staging.sh    # on the host itself (no ssh hop)
set -uo pipefail
HOST="${HOST-kapture}"
DIR="${MDR_DEPLOY_DIR:-\$HOME/mdreview-staging}"   # \$HOME expands on the remote shell
STALE_DAYS="${STALE_DAYS:-3}"
run(){ if [ -n "$HOST" ]; then ssh -o ConnectTimeout=15 "$HOST" "$@"; else bash -c "$@"; fi; }
fail=0; drift(){ echo "  DRIFT: $*"; fail=1; }; ok(){ echo "  ok   : $*"; }

echo "== mdreview STAGING drift check (host=${HOST:-local}) =="

# 1. the staging deploy dir exists and is its OWN dir (never prod's ~/mdreview-deploy)
run "test -d $DIR" 2>/dev/null && ok "staging deploy dir present ($DIR)" \
  || drift "staging deploy dir $DIR missing"

# 2. the app runs the NATIVE hosted plane with auth on + proxy plane retired + the staging domain
env=$(run "docker inspect mdreview-staging --format '{{range .Config.Env}}{{println .}}{{end}}'" 2>/dev/null)
echo "$env" | grep -qx "MDREVIEW_REQUIRE_AUTH=1" && ok "REQUIRE_AUTH=1" || drift "REQUIRE_AUTH not =1"
echo "$env" | grep -qx "MDREVIEW_ALLOW_PROXY_PLANE=0" && ok "proxy plane retired (=0)" || drift "MDREVIEW_ALLOW_PROXY_PLANE not =0 (spoofable-header plane may be live)"
echo "$env" | grep -qx "MDREVIEW_PUBLIC_BASE=https://staging.mdreview.space" && ok "PUBLIC_BASE = staging" || drift "PUBLIC_BASE not staging.mdreview.space"

# 3. ISOLATION: staging shares no volume/port/oauth-sidecar with prod
mounts=$(run "docker inspect mdreview-staging --format '{{range .Mounts}}{{.Source}}{{\"\\n\"}}{{end}}'" 2>/dev/null)
echo "$mounts" | grep -qE 'mdreview-deploy|mdreview-prod' && drift "staging mounts a PROD volume: $mounts" || ok "staging mounts no prod volume"
echo "$mounts" | grep -qE 'mdreview-staging' && ok "staging mounts its own data volume" || drift "staging does not mount mdreview-staging-data"
ports=$(run "docker inspect mdreview-staging --format '{{json .HostConfig.PortBindings}}'" 2>/dev/null)
echo "$ports" | grep -q '8141' && ok "publishes loopback :8141" || drift "not on :8141 (port collision risk with prod :8140)"
echo "$ports" | grep -q '8140' && drift "staging binds prod's :8140" || ok "does not bind prod's :8140"
run "docker inspect mdreview-staging-oauth2-proxy >/dev/null 2>&1" && drift "a staging oauth2-proxy sidecar exists (native plane needs none)" || ok "no oauth2-proxy sidecar (native plane)"

# 4. IMAGE REFERENCE: the running container must be the image the compose file pins (#214).
# Everything below this line checked WHEN the image was built, never WHICH image it is — so staging
# could run mdreview-service:dev while compose pinned mdreview-service-latex:dev, stay perfectly
# fresh, and report clean. CI pushes BOTH repositories, so the mismatch is reachable, not theoretical.
# `.Config.Image` is the ref the container was CREATED from; `.Image` is the resolved digest ID,
# which is what made #163 hard to see under the containerd image store. Compare the ref.
# The expected value is READ FROM the compose file rather than hardcoded here, so the checker and
# the deployment cannot drift apart the moment someone repoints the image.
want_img=$(run "grep -oE '^[[:space:]]*image:[[:space:]]*\S+' $DIR/docker-compose.staging.yml | head -1 | sed 's/.*image:[[:space:]]*//'" 2>/dev/null)
have_img=$(run "docker inspect mdreview-staging --format '{{.Config.Image}}'" 2>/dev/null)
if [ -z "$want_img" ] || [ -z "$have_img" ]; then
  # Unreadable is not the same as matching — the #216 rule, applied here.
  drift "could not read the image ref (compose='${want_img:-<empty>}' running='${have_img:-<empty>}')"
elif [ "$want_img" = "$have_img" ]; then
  ok "image ref matches compose ($have_img)"
else
  drift "image ref MISMATCH: compose pins '$want_img' but the container runs '$have_img'"
fi

# 5. STALENESS: staging must be tracking dev, not latched on a bad :dev digest, nor running a stale image.
if run "test -s $DIR/.autoupdate-bad-digest" 2>/dev/null; then
  drift "auto-update is PAUSED on a HELD bad :dev digest — staging is NOT tracking dev; 'dev is green' would be a lie. Investigate $DIR/auto-update.log"
else ok "no held-bad digest (auto-update tracking dev)"; fi
# Image-created epoch computed ON the host (GNU `date -d` lives there, not on a BSD/mac controller);
# `date +%s` for "now" is portable, so it can run wherever this script does.
img_epoch=$(run "c=\$(docker inspect mdreview-staging --format '{{.Image}}' 2>/dev/null | xargs -r docker inspect --format '{{.Created}}' 2>/dev/null); [ -n \"\$c\" ] && date -d \"\$c\" +%s 2>/dev/null" 2>/dev/null)
if [ -n "$img_epoch" ]; then
  age_days=$(( ( $(date +%s) - img_epoch ) / 86400 ))
  [ "$age_days" -le "$STALE_DAYS" ] && ok "running :dev image is ${age_days}d old (<= ${STALE_DAYS}d)" \
    || drift "running :dev image is ${age_days}d old (> ${STALE_DAYS}d) — staging may be stuck; check auto-update"
fi

echo "== $( [ $fail -eq 0 ] && echo 'CLEAN: staging isolated + tracking dev' || echo 'DRIFT DETECTED — reconcile' ) =="
exit $fail
