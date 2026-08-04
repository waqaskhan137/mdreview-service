#!/usr/bin/env bash
# share_visibility_ui_selfcheck.sh — #284, RENDERED OUTCOMES only.
#
# Boots a throwaway LOCAL-tier instance (just to serve dashboard.html + theme.css + the JS files
# for real) and drives scripts/share-visibility-check.mjs against it in real headless Chrome. The
# check's own window.fetch stub supplies the /api/reviews and /api/reviews?scope=shared payloads,
# so this does NOT exercise server-side authorization — that is
# tests/share_scope_selfcheck.py's job, against a real hosted instance with real accounts and real
# grants. This script exists only to prove the two things a server-side test cannot: that the
# badges and the "Shared with you" group actually PAINT, with the right computed colour, in both
# themes (same split as tests/dashboard_reskin_selfcheck.sh / tests/admin_reskin_selfcheck.sh).
#
#   bash tests/share_visibility_ui_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/share-vis-check-$$"
mkdir -p "$scratch"
srv=""
cleanup(){ [ -n "$srv" ] && kill "$srv" 2>/dev/null; rm -rf "$scratch" 2>/dev/null; return 0; }
trap cleanup EXIT
pickport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
waitup(){ for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$1/healthz" && return 0; sleep 0.25; done; return 1; }

port="$(pickport)"
MDREVIEW_DATA="$scratch/data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/s.log" 2>&1 &
srv=$!
waitup "$port" || { echo "FAIL - local instance never came up"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

node "$here/scripts/share-visibility-check.mjs" "http://127.0.0.1:$port/"
