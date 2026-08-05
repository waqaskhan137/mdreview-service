#!/usr/bin/env bash
# mint_spinner_selfcheck.sh — #286 AC5 (mint pending spinner, disabled + "Minting…") + AC6
# (regression guard: success/error copy and the #281 copy-to-clipboard control, which already
# ships) + AC10 (reduced-motion). Needs a real hosted+login session — account.html 404s
# /auth/session and never renders on the plain local tier (#224) — so this boots
# mdreview.hosted with a stub email, same login() flow tests/account_page_selfcheck.sh uses.
#
#   bash tests/mint_spinner_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/mint_spinner_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=0 \
  MDREVIEW_PROXY_SECRET=inert-not-consumed-with-plane-off \
  MDREVIEW_SESSION_SECRET=mint-spinner-session MDREVIEW_TOKEN_PEPPER=mint-spinner-pepper \
  MDREVIEW_OWNER_EMAIL=owner@example.com MDREVIEW_ALLOW_STUB_EMAIL=1 \
  MDREVIEW_PUBLIC_BASE=https://mint-spinner-selfcheck.invalid \
  python3 -m mdreview.hosted >"$scratch/s.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up on :$port"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

export PATH="/Users/apple/.nvm/versions/node/v22.22.0/bin:$PATH"
node "$here/scripts/mint-spinner-check.mjs" "http://127.0.0.1:$port" "$scratch/s.log"
