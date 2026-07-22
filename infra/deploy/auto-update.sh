#!/usr/bin/env bash
# auto-update.sh (issue #88) — health-gated auto-update of the hosted mdreview service.
#
# Run by mdreview-autoupdate.timer every 30 min. Pulls the service image; if its digest changed,
# recreates the container from the single canonical deploy dir and HEALTH-GATES the result — rolling
# back to the previous image (and refusing to re-deploy that same bad digest) if the gate fails.
# No-churn: an unchanged digest exits without touching the container. Depends on #86 (one deploy dir).
#
# Env overrides (defaults are the Kapture prod values):
#   MDR_DEPLOY_DIR  MDR_IMAGE  MDR_SERVICE  MDR_HEALTH  MDR_AUTHPROBE  MDR_LOG
set -uo pipefail

DEPLOY_DIR="${MDR_DEPLOY_DIR:-$HOME/mdreview-deploy}"
SERVICE="${MDR_SERVICE:-mdreview}"
# Watch exactly the image the running container uses (self-aligning with the compose, slim OR -latex) —
# hardcoding a tag risks watching a different image than `compose up` recreates, so the updater would
# forever "see a new digest" it can never apply. Fall back to the -latex prod default if not running.
IMAGE="${MDR_IMAGE:-$(docker inspect --format '{{.Config.Image}}' "$SERVICE" 2>/dev/null)}"
IMAGE="${IMAGE:-ghcr.io/waqaskhan137/mdreview-service-latex:latest}"
HEALTH="${MDR_HEALTH:-http://127.0.0.1:8140/healthz}"
AUTHPROBE="${MDR_AUTHPROBE:-http://127.0.0.1:8140/api/reviews}"   # MUST be 401 when auth is enforced
LOG="${MDR_LOG:-$DEPLOY_DIR/auto-update.log}"
HELD="$DEPLOY_DIR/.autoupdate-bad-digest"       # a digest we rolled back FROM; do not re-deploy it
LOCK="$DEPLOY_DIR/.autoupdate.lock"

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG"; }
compose(){ (cd "$DEPLOY_DIR" && docker compose --env-file .env -f docker-compose.prod.yml "$@"); }
img_id(){ docker inspect --format '{{.Id}}' "$1" 2>/dev/null; }               # image ID by ref (tag)
running_img(){ docker inspect --format '{{.Image}}' "$SERVICE" 2>/dev/null; } # the container's image ID
probe(){ curl -s -o /dev/null -w '%{http_code}' -m 3 "$1" 2>/dev/null; }

# single-flight: a slow update (pull + recreate + 60s health wait) must not overlap the next tick.
exec 9>"$LOCK" || { log "cannot open lock $LOCK"; exit 1; }
flock -n 9 || { log "another run holds the lock; skipping this tick"; exit 0; }

if ! docker pull -q "$IMAGE" >/dev/null 2>&1; then log "docker pull failed (registry/network); skip"; exit 0; fi
new=$(img_id "$IMAGE"); cur=$(running_img)
[ -z "$new" ] && { log "cannot inspect $IMAGE after pull; skip"; exit 0; }
[ "$new" = "$cur" ] && exit 0                                  # no-churn: image unchanged
if [ "$new" = "$(cat "$HELD" 2>/dev/null)" ]; then
  log "new digest ${new#sha256:} is the HELD bad one; staying on current until a newer image ships"; exit 0
fi

prev="$cur"                                                    # rollback point = the currently-running image ID
log "update available: ${cur#sha256:} -> ${new#sha256:}; recreating $SERVICE"
compose up -d "$SERVICE" >>"$LOG" 2>&1

# guard: if the recreate did not actually adopt the new image (compose error, missing secret, etc.),
# the OLD container is still up — do NOT health-gate that (it would falsely pass). Retry next tick.
if [ "$(running_img)" != "$new" ]; then
  log "recreate did not adopt ${new#sha256:} (still on ${cur#sha256:}); compose up failed — old container left running, retry next tick"
  exit 0
fi

# health gate: /healthz 200 AND the auth-probe 401 (proves it booted with auth ENFORCED — not wide
# open and not crashed). WALL-CLOCK deadline (not iterations x curl-timeout, which balloons to ~360s
# if the new image HANGS and every probe eats its full timeout), so the rollback block below ALWAYS
# runs well under the unit's TimeoutStartSec — a hanging bad image must not escape rollback + latch.
h=""; a=""; ok=""; deadline=$((SECONDS + 90))
while [ "$SECONDS" -lt "$deadline" ]; do
  h=$(probe "$HEALTH"); a=$(probe "$AUTHPROBE")
  [ "$h" = "200" ] && [ "$a" = "401" ] && { ok=1; break; }
  sleep 3
done

if [ -n "$ok" ]; then
  rm -f "$HELD"
  log "update OK: $SERVICE healthy on ${new#sha256:} (healthz=200, auth-probe=401)"
elif [ -z "$prev" ]; then
  log "HEALTH GATE FAILED (healthz=$h auth-probe=$a) on ${new#sha256:} and NO previous image to roll back to — leaving as-is, investigate NOW"
  echo "$new" >"$HELD"
else
  log "HEALTH GATE FAILED (healthz=$h auth-probe=$a) on ${new#sha256:} — ROLLING BACK to ${prev#sha256:}"
  docker tag "$prev" "$IMAGE" >>"$LOG" 2>&1               # re-point :latest at the previous image
  compose up -d --force-recreate "$SERVICE" >>"$LOG" 2>&1
  echo "$new" >"$HELD"                                    # don't re-deploy this digest until a newer one ships
  log "rollback done (post-rollback healthz=$(probe "$HEALTH")). HELD ${new#sha256:}; auto-update paused for it — investigate."
fi
