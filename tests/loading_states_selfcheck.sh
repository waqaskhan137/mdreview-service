#!/usr/bin/env bash
# loading_states_selfcheck.sh — #286's runnable regression check for dashboard.html, viewer.html
# and latex-viewer.html (AC1-4, AC7-11). Boots a real throwaway local instance and hands off to
# scripts/loading-states-check.mjs, which seeds its own fixtures over the REAL API (in the order
# each AC needs — AC2's empty-dashboard check runs before any review exists) and drives everything
# through CDP in a real headless Chrome: held-open fetches via the Fetch domain, never a fixed
# sleep standing in for a network race; computed style for colour; getAnimations()/emulated media
# for motion.
#
# account.html's mint spinner (AC5/AC6) needs a real hosted+login session (the account page 404s
# /auth/session and never renders on the plain local tier) and lives in
# mint_spinner_selfcheck.sh + scripts/mint-spinner-check.mjs instead.
#
#   bash tests/loading_states_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/loading_states_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" MDREVIEW_ENABLE_LATEX=1 \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/s.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up on :$port"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

export PATH="/Users/apple/.nvm/versions/node/v22.22.0/bin:$PATH"
node "$here/scripts/loading-states-check.mjs" "http://127.0.0.1:$port"
