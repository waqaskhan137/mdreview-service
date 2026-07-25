#!/usr/bin/env bash
# autoupdate_digest_smoke.sh (#163) — the executable check auto-update.sh never had.
#
# Reproduces the containerd image store's digest behaviour with a stubbed `docker`, then asserts
# auto-update.sh does the right thing. The bug this guards against shipped silently and sat in
# staging for weeks: the script compared a multi-arch tag's MANIFEST digest against the running
# container's CONFIG id, which under containerd can never be equal, so every tick logged
# "recreate did not adopt ... retry next tick" and nothing ever deployed.
#
# The stub deliberately models the containerd quirk that caused it:
#   docker inspect --format '{{.Id}}' <multi-arch tag>  -> MANIFEST digest (changes every push)
#   docker inspect --format '{{.Image}}' <container>    -> CONFIG id       (different value)
# A script that compares those two fails case 1 below. The fixed script compares RepoDigests
# against the .deployed-digest marker and passes.
#
# Run: bash tests/autoupdate_digest_smoke.sh          (no docker, no network, no host)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$HERE/infra/deploy/auto-update.sh"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
fails=0

MANIFEST="ghcr.io/x/mdreview-service@sha256:1111111111111111111111111111111111111111111111111111111111111111"
CONFIG="sha256:2222222222222222222222222222222222222222222222222222222222222222"

mkstubs(){                                    # $1 = bin dir, $2 = health code, $3 = authprobe code
  mkdir -p "$1"
  cat > "$1/docker" <<STUB
#!/usr/bin/env bash
# containerd-flavoured docker stub. Records what it was asked to do in \$STUBLOG.
echo "\$*" >> "\$STUBLOG"
case "\$1" in
  pull) exit 0 ;;
  tag)  exit 0 ;;
  compose)
    # only the recreate matters: simulate it by bumping the container id
    if printf '%s' "\$*" | grep -q 'up -d'; then echo "\$RANDOM\$RANDOM" > "\$CIDFILE"; fi
    exit 0 ;;
  inspect)
    fmt="\$3"; ref="\$4"
    case "\$fmt" in
      *RepoDigests*)   printf '%s' "$MANIFEST" ;;
      *'{{.Id}}'*)
        # THE QUIRK: for the image tag containerd returns the manifest digest; for the container
        # name it returns the container id.
        if [ "\$ref" = "mdreview-staging" ]; then cat "\$CIDFILE"; else printf '%s' "$MANIFEST"; fi ;;
      *'{{.Image}}'*)  printf '%s' "$CONFIG" ;;
      *'{{.Config.Image}}'*) printf '%s' "ghcr.io/x/mdreview-service:dev" ;;
    esac
    exit 0 ;;
esac
exit 0
STUB
  cat > "$1/curl" <<STUB
#!/usr/bin/env bash
# health probe stub: last arg is the URL
for a in "\$@"; do url="\$a"; done
case "\$url" in
  *healthz*)      printf '%s' "$2" ;;
  *api/reviews*)  printf '%s' "$3" ;;
esac
STUB
  # flock is Linux-only; the script's single-flight guard is not what we are testing.
  printf '#!/usr/bin/env bash\nexit 0\n' > "$1/flock"
  chmod +x "$1"/*
}

run(){                                        # $1 = case name, sets $LOGOUT
  local dir="$WORK/$1"; mkdir -p "$dir/deploy"
  export STUBLOG="$dir/stub.log"; export CIDFILE="$dir/cid"; : > "$STUBLOG"; echo "container-aaa" > "$CIDFILE"
  mkstubs "$dir/bin" "${HEALTH_CODE:-200}" "${AUTH_CODE:-401}"
  PATH="$dir/bin:$PATH" \
  MDR_DEPLOY_DIR="$dir/deploy" MDR_SERVICE=mdreview-staging \
  MDR_IMAGE="ghcr.io/x/mdreview-service:dev" MDR_LOG="$dir/auto-update.log" MDR_GATE_TIMEOUT=1 \
  bash "$SCRIPT" >/dev/null 2>&1
  LOGOUT="$(cat "$dir/auto-update.log" 2>/dev/null)"; STUBOUT="$(cat "$STUBLOG")"
  MARKEROUT="$(cat "$dir/deploy/.deployed-digest" 2>/dev/null)"
}

check(){ if [ "$2" = "$3" ]; then echo "  ok   $1"; else echo "  FAIL $1"; echo "        want: $3"; echo "        got:  $2"; fails=$((fails+1)); fi; }
has(){   if printf '%s' "$2" | grep -q "$3"; then echo "  ok   $1"; else echo "  FAIL $1 (missing: $3)"; fails=$((fails+1)); fi; }
hasnt(){ if printf '%s' "$2" | grep -q "$3"; then echo "  FAIL $1 (unexpected: $3)"; fails=$((fails+1)); else echo "  ok   $1"; fi; }

echo "1. fresh digest, healthy -> deploys, force-recreates, writes the marker"
HEALTH_CODE=200 AUTH_CODE=401 run deploy
has   "recreated the service"            "$STUBOUT"  "up -d --force-recreate"
has   "logged the update"                "$LOGOUT"   "update available"
has   "health gate passed"               "$LOGOUT"   "update OK"
check "marker records the manifest digest" "$MARKEROUT" "$MANIFEST"
hasnt "no phantom adoption failure"      "$LOGOUT"   "did not"

echo "2. THE REGRESSION: marker already at this digest -> no-churn, no recreate"
d="$WORK/nochurn"; mkdir -p "$d/deploy"; echo "$MANIFEST" > "$d/deploy/.deployed-digest"
export STUBLOG="$d/stub.log"; export CIDFILE="$d/cid"; : > "$STUBLOG"; echo "container-aaa" > "$CIDFILE"
mkstubs "$d/bin" 200 401
PATH="$d/bin:$PATH" MDR_DEPLOY_DIR="$d/deploy" MDR_SERVICE=mdreview-staging \
  MDR_IMAGE="ghcr.io/x/mdreview-service:dev" MDR_LOG="$d/auto-update.log" MDR_GATE_TIMEOUT=1 bash "$SCRIPT" >/dev/null 2>&1
hasnt "did not recreate an unchanged image" "$(cat "$d/stub.log")" "force-recreate"
check "log stayed empty"                    "$(cat "$d/auto-update.log" 2>/dev/null)" ""

echo "3. health gate fails -> rolls back, HOLDs the digest, marker NOT advanced"
HEALTH_CODE=500 AUTH_CODE=500 run gatefail
has   "rolled back"                      "$LOGOUT"   "ROLLING BACK"
has   "gate failure logged"              "$LOGOUT"   "HEALTH GATE FAILED"
check "marker not advanced to a bad digest" "$MARKEROUT" ""

echo "4. auth-probe 200 (booted UNAUTHENTICATED) is treated as a gate failure"
HEALTH_CODE=200 AUTH_CODE=200 run wideopen
has   "wide-open boot rejected"          "$LOGOUT"   "HEALTH GATE FAILED"
check "marker not advanced"              "$MARKEROUT" ""

echo
if [ "$fails" -eq 0 ]; then echo "autoupdate_digest_smoke: PASS"; else echo "autoupdate_digest_smoke: $fails FAILURE(S)"; fi
exit $((fails > 0))
