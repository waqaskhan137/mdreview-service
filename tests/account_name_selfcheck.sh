#!/usr/bin/env bash
# account_name_selfcheck.sh — #309 slice 1's runnable regression check, asserted as RENDERED
# OUTCOMES (real DOM state, real network calls) in headless Chrome against a REAL hosted server.
# Same boot shape as tests/account_page_selfcheck.sh; the assertions live in
# scripts/account-name-check.mjs (Display name row, XSS on the rendered DOM, retroactive
# comment attribution end to end).
#
#   bash tests/account_name_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/account_name_data"
rm -rf "$scratch"; mkdir -p "$scratch"

freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/hosted" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=0 MDREVIEW_PROXY_SECRET=inert-not-a-plane \
  MDREVIEW_SESSION_SECRET=s MDREVIEW_TOKEN_PEPPER=p MDREVIEW_OWNER_EMAIL=name-primary@example.com \
  MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_PUBLIC_BASE=https://l.test \
  PYTHONPATH="$here/src" python3 -m mdreview.hosted >"$scratch/hosted.log" 2>&1 &
srv=$!

up=0; for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - hosted server never came up"; sed -n '1,8p' "$scratch/hosted.log"; exit 1; }

node "$here/scripts/account-name-check.mjs" "http://127.0.0.1:$port" "$scratch/hosted.log"
rc=$?
rm -rf "$scratch"
exit "$rc"
