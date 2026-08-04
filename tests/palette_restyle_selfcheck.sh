#!/usr/bin/env bash
# palette_restyle_selfcheck.sh — #283, the ⌘K palette restyle asserted as RENDERED OUTCOMES.
#
# Boots a throwaway local instance, seeds the fixture scripts/palette-restyle-check.mjs expects
# (8 reviews across 5 projects, with "auth-service" holding exactly 4 — see that file's header for
# why this exact shape), then drives real headless Chrome against it in both themes.
#
#   bash tests/palette_restyle_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/palette_restyle_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/s.log" 2>&1 &
srv=$!
up=0; for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

seed() {  # title project
  curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
    -d "{\"title\":\"$1\",\"project\":\"$2\",\"markdown\":\"# $1\\n\\nbody.\\n\"}" -o /dev/null
}
# Exactly 4 in auth-service (the "4 reviews" hint AC), plus 4 more spread across 4 other projects
# — 8 reviews / 5 projects total, which is cmdBuild's slice(0,8)/slice(0,5) ceiling: the largest
# DOM the palette can ever render, needed to force real overflow at the narrow probe size.
seed "Palette fixture auth 1" "auth-service"
seed "Palette fixture auth 2" "auth-service"
seed "Palette fixture auth 3" "auth-service"
seed "Palette fixture auth 4" "auth-service"
seed "Palette fixture bridge" "agent-bridge"
seed "Palette fixture billing" "billing-service"
seed "Palette fixture docs" "docs-site"
seed "Palette fixture infra" "infra-tools"

node "$here/scripts/palette-restyle-check.mjs" "http://127.0.0.1:$port/"
