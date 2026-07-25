#!/usr/bin/env bash
# auto-update.sh (issue #88) — health-gated auto-update of the hosted mdreview service.
#
# Run by mdreview-autoupdate.timer every 30 min. Pulls the service image; if its digest changed,
# recreates the container from the single canonical deploy dir and HEALTH-GATES the result — rolling
# back to the previous image (and refusing to re-deploy that same bad digest) if the gate fails.
# No-churn: an unchanged digest exits without touching the container. Depends on #86 (one deploy dir).
#
# Env overrides (defaults are the Kapture prod values — so the staging stack reuses this same script):
#   MDR_DEPLOY_DIR  MDR_IMAGE  MDR_SERVICE  MDR_HEALTH  MDR_AUTHPROBE  MDR_LOG
#   MDR_COMPOSE_FILE  MDR_ENV_FILE   (added for the isolated staging stack; default to prod's files)
set -uo pipefail

DEPLOY_DIR="${MDR_DEPLOY_DIR:-$HOME/mdreview-deploy}"
SERVICE="${MDR_SERVICE:-mdreview}"
# Which compose file + env file the recreate uses. Default = prod, so prod behaviour is byte-identical;
# staging points these at docker-compose.staging.yml + .env.staging in its OWN deploy dir.
COMPOSE_FILE="${MDR_COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${MDR_ENV_FILE:-.env}"
# Watch exactly the image the running container uses (self-aligning with the compose, slim OR -latex) —
# hardcoding a tag risks watching a different image than `compose up` recreates, so the updater would
# forever "see a new digest" it can never apply. Fall back to the -latex prod default if not running.
IMAGE="${MDR_IMAGE:-$(docker inspect --format '{{.Config.Image}}' "$SERVICE" 2>/dev/null)}"
IMAGE="${IMAGE:-ghcr.io/ranawaqas-ai/mdreview-service-latex:latest}"
HEALTH="${MDR_HEALTH:-http://127.0.0.1:8140/healthz}"
AUTHPROBE="${MDR_AUTHPROBE:-http://127.0.0.1:8140/api/reviews}"   # MUST be 401 when auth is enforced
LOG="${MDR_LOG:-$DEPLOY_DIR/auto-update.log}"
HELD="$DEPLOY_DIR/.autoupdate-bad-digest"       # a digest we rolled back FROM; do not re-deploy it
MARKER="$DEPLOY_DIR/.deployed-digest"           # #163: the manifest digest we last health-gated OK
LOCK="$DEPLOY_DIR/.autoupdate.lock"

log(){ printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >>"$LOG"; }
compose(){ (cd "$DEPLOY_DIR" && docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"); }
probe(){ curl -s -o /dev/null -w '%{http_code}' -m 3 "$1" 2>/dev/null; }

# --- #163: ONE digest kind on both sides of every comparison -------------------------------------
# The old code compared `{{.Id}}` of the pulled TAG against `{{.Image}}` of the running CONTAINER.
# Under the containerd image store those are different kinds: for a multi-arch tag `{{.Id}}` returns
# the MANIFEST/INDEX digest (new on every CI push) while `{{.Image}}` returns the platform CONFIG id.
# They can never be equal, so the no-churn check never fired and the adoption guard always reported
# "did not adopt" — an infinite retry loop that deployed nothing. Staging sat stale for weeks and
# prod carried the same latent bug, masked only because :latest is re-pushed rarely.
#
# Fix: compare the pulled tag's REPO DIGEST against a marker file we write only after a passing
# health gate. Both sides are then the same kind, and the marker records what is actually deployed
# rather than what some inspect field happens to return on this storage driver.
repo_digest(){                                   # `repo@sha256:...` of an image ref
  local d; d=$(docker inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' "$1" 2>/dev/null)
  # A locally-built image that was never pushed has no RepoDigests. Fall back to .Id so the script
  # still functions (it just loses cross-host digest stability, which such an image never had).
  [ -n "$d" ] || d=$(docker inspect --format '{{.Id}}' "$1" 2>/dev/null)
  printf '%s' "$d"
}
running_img(){ docker inspect --format '{{.Image}}' "$SERVICE" 2>/dev/null; } # config id — ROLLBACK point only
container_id(){ docker inspect --format '{{.Id}}' "$SERVICE" 2>/dev/null; }   # the CONTAINER's id

# single-flight: a slow update (pull + recreate + 60s health wait) must not overlap the next tick.
exec 9>"$LOCK" || { log "cannot open lock $LOCK"; exit 1; }
flock -n 9 || { log "another run holds the lock; skipping this tick"; exit 0; }

if ! docker pull -q "$IMAGE" >/dev/null 2>&1; then log "docker pull failed (registry/network); skip"; exit 0; fi
new=$(repo_digest "$IMAGE"); cur=$(cat "$MARKER" 2>/dev/null)
[ -z "$new" ] && { log "cannot inspect $IMAGE after pull; skip"; exit 0; }
[ "$new" = "$cur" ] && exit 0                                  # no-churn: same digest already deployed
if [ "$new" = "$(cat "$HELD" 2>/dev/null)" ]; then
  log "new digest ${new##*@} is the HELD bad one; staying on current until a newer image ships"; exit 0
fi

prev="$(running_img)"                                          # rollback point = running CONFIG id (docker tag needs a local image)
cid_before="$(container_id)"
log "update available: ${cur##*@} -> ${new##*@}; recreating $SERVICE"
# --force-recreate (#163): under containerd, `compose up -d` can resolve :dev to a config equal to
# the running container and silently no-op, after which the guard below would report a phantom
# failure forever. Forcing the recreate makes adoption unconditional.
compose up -d --force-recreate "$SERVICE" >>"$LOG" 2>&1

# guard: if the recreate did not actually happen (compose error, missing secret, etc.), the OLD
# container is still up — do NOT health-gate that (it would falsely pass). Retry next tick.
# Checked by CONTAINER id, not image digest: --force-recreate always yields a new container, and a
# container-id comparison is storage-driver agnostic, which is exactly what #163 was not.
cid_after="$(container_id)"
if [ -z "$cid_after" ] || [ "$cid_after" = "$cid_before" ]; then
  log "recreate did not happen for ${new##*@} (container still ${cid_before:0:12}); compose up failed — old container left running, retry next tick"
  exit 0
fi

# health gate: /healthz 200 AND the auth-probe 401 (proves it booted with auth ENFORCED — not wide
# open and not crashed). WALL-CLOCK deadline (not iterations x curl-timeout, which balloons to ~360s
# if the new image HANGS and every probe eats its full timeout), so the rollback block below ALWAYS
# runs well under the unit's TimeoutStartSec — a hanging bad image must not escape rollback + latch.
# MDR_GATE_TIMEOUT is an override for the smoke test only — production leaves it at 90s. Without it
# every gate-failure case in tests/autoupdate_digest_smoke.sh costs a real 90s wall-clock wait, which
# is enough friction that the script stayed untested, which is how #163 shipped.
h=""; a=""; ok=""; deadline=$((SECONDS + ${MDR_GATE_TIMEOUT:-90}))
while [ "$SECONDS" -lt "$deadline" ]; do
  h=$(probe "$HEALTH"); a=$(probe "$AUTHPROBE")
  [ "$h" = "200" ] && [ "$a" = "401" ] && { ok=1; break; }
  sleep 3
done

if [ -n "$ok" ]; then
  rm -f "$HELD"
  # Write the marker ONLY here (#163): it records what is deployed AND health-gated, so a failed
  # gate leaves the marker on the last good digest and the next tick retries rather than believing
  # the bad image is live.
  echo "$new" >"$MARKER"
  log "update OK: $SERVICE healthy on ${new##*@} (healthz=200, auth-probe=401)"
elif [ -z "$prev" ]; then
  log "HEALTH GATE FAILED (healthz=$h auth-probe=$a) on ${new##*@} and NO previous image to roll back to — leaving as-is, investigate NOW"
  echo "$new" >"$HELD"
else
  log "HEALTH GATE FAILED (healthz=$h auth-probe=$a) on ${new##*@} — ROLLING BACK to ${prev#sha256:}"
  docker tag "$prev" "$IMAGE" >>"$LOG" 2>&1               # re-point the tag at the previous image
  compose up -d --force-recreate "$SERVICE" >>"$LOG" 2>&1
  echo "$new" >"$HELD"                                    # don't re-deploy this digest until a newer one ships
  # MARKER deliberately NOT updated — it still names the last digest that passed, which is what the
  # rollback restored, so the next tick's no-churn comparison is correct.
  log "rollback done (post-rollback healthz=$(probe "$HEALTH")). HELD ${new##*@}; auto-update paused for it — investigate."
fi
