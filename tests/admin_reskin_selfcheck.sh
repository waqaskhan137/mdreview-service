#!/usr/bin/env bash
# admin_reskin_selfcheck.sh — #282's runnable regression check, asserted as RENDERED OUTCOMES
# (computed style, measured geometry, DOM/AX state) in headless Chrome, never CSS text.
#
# admin.html is hosted-only (its shell is served unauthenticated; the DATA endpoints
# /admin/users, /admin/blocklist, /admin/audit, and every POST action are admin-gated). This
# boots a real hosted instance the same way tests/theme_toggle_selfcheck.sh does, then hands the
# real page to scripts/admin-reskin-check.mjs, which stubs window.fetch (installed BEFORE any
# page script runs, via Page.addScriptToEvaluateOnNewDocument) so the check drives admin.html's
# OWN rendering logic — the only file this ticket owns — against a known fixture, without
# depending on the magic-link login flow or CSRF plumbing that adminroutes.py/authroutes.py
# already own and the groom verified separately. Real navigation to the real hosted /admin route
# still proves the shell serves unauthenticated and every static asset (theme.css, basecoat,
# account.js, session.js) loads for real — window.fetch stubbing has no effect on <link>/<script
# src> resource loading, only on the page's own fetch() calls.
#
#   bash tests/admin_reskin_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/admin_reskin_data"
rm -rf "$scratch"; mkdir -p "$scratch"

freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/hosted" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_PROXY_SECRET=inert-not-a-plane \
  MDREVIEW_SESSION_SECRET=s MDREVIEW_TOKEN_PEPPER=p MDREVIEW_OWNER_EMAIL=o@e.com \
  MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_PUBLIC_BASE=https://l.test \
  PYTHONPATH="$here/src" python3 -m mdreview.hosted >"$scratch/hosted.log" 2>&1 &
srv=$!

up=0; for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - hosted server never came up"; sed -n '1,8p' "$scratch/hosted.log"; exit 1; }

node "$here/scripts/admin-reskin-check.mjs" "http://127.0.0.1:$port"
rc=$?
rm -rf "$scratch"
exit "$rc"
