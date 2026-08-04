#!/usr/bin/env bash
# account_page_selfcheck.sh — #281's runnable regression check, asserted as RENDERED OUTCOMES
# (computed style, measured geometry, DOM/network state) in headless Chrome against a REAL hosted
# server (real magic-link logins, real cookies, real CSRF, real mint/revoke/end-session/sign-out
# calls) — never CSS text, never a fetch stub for the mutating endpoints.
#
# Boots a real hosted instance the same way tests/admin_reskin_selfcheck.sh does, then hands its
# origin AND its log file (where the stub-email path writes magic-link redeem URLs) to
# scripts/account-page-check.mjs, which drives the login flow itself over plain HTTP.
#
#   bash tests/account_page_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/account_page_data"
rm -rf "$scratch"; mkdir -p "$scratch"

freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

# MDREVIEW_OWNER_EMAIL matches the check script's EMAIL constant on purpose: the mock's persona
# (a.kerr@example.com) is Admin, and AC10's Role-row assertion tests the Admin branch.
MDREVIEW_DATA="$scratch/hosted" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=0 MDREVIEW_PROXY_SECRET=inert-not-a-plane \
  MDREVIEW_SESSION_SECRET=s MDREVIEW_TOKEN_PEPPER=p MDREVIEW_OWNER_EMAIL=a.kerr@example.com \
  MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_PUBLIC_BASE=https://l.test \
  PYTHONPATH="$here/src" python3 -m mdreview.hosted >"$scratch/hosted.log" 2>&1 &
srv=$!

up=0; for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - hosted server never came up"; sed -n '1,8p' "$scratch/hosted.log"; exit 1; }

node "$here/scripts/account-page-check.mjs" "http://127.0.0.1:$port" "$scratch/hosted.log"
rc=$?
rm -rf "$scratch"
exit "$rc"
