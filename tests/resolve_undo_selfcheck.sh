#!/usr/bin/env bash
# resolve_undo_selfcheck.sh — #287's runnable regression check (AC1-AC6, AC9): boots a real
# throwaway local instance, hands off to scripts/resolve-undo-check.mjs, which seeds its own
# fixture comments over the REAL API and samples the RENDERED outcome in headless Chrome, both
# themes. AC7 (view-only readers) needs a different tier's access policy and lives in
# resolve_viewonly_selfcheck.sh instead. AC8 is NOT delivered (latex-viewer.html has no Resolved
# panel to recover into — see the PR/run report); this file only exercises viewer.html.
#
#   bash tests/resolve_undo_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/resolve_undo_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/s.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up on :$port"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

rid=$(python3 - "$port" <<'PY'
import json, sys, urllib.request
port = sys.argv[1]
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
md = "# Fixture\n\nBlock one.\n\nBlock two.\n\nBlock three.\n\nBlock four.\n\nBlock five.\n"
r = urllib.request.Request("http://127.0.0.1:%s/api/reviews" % port,
                            data=json.dumps({"markdown": md, "title": "resolve-undo"}).encode(),
                            headers={"Content-Type": "application/json"}, method="POST")
print(json.load(op.open(r, timeout=15))["id"])
PY
)
[ -n "$rid" ] || { echo "FAIL - could not create a review"; exit 1; }

node "$here/scripts/resolve-undo-check.mjs" "http://127.0.0.1:$port/review/$rid"
