#!/usr/bin/env bash
# history_compare_selfcheck.sh: #310's runnable regression check. The History modal's Compare
# button called an undefined renderCompare() (deleted by `7fcd840`/#208 while its call site, CSS
# and the renderDiff/paintDiff helpers were all left behind). Boots a real throwaway local
# instance, hands off to scripts/history-compare-check.mjs, which pushes real revisions over
# PUT /source and samples the RENDERED outcome (the two pickers, their real option values, the
# actual diff text, and the mode/label pair) in headless Chrome with the console captured.
#
#   bash tests/history_compare_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/history_compare_data"
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
md = "# Doc\n\nALPHA-v0 marker line.\n\nShared unchanged line.\n"
r = urllib.request.Request("http://127.0.0.1:%s/api/reviews" % port,
                            data=json.dumps({"markdown": md, "title": "history-compare"}).encode(),
                            headers={"Content-Type": "application/json"}, method="POST")
print(json.load(op.open(r, timeout=15))["id"])
PY
)
[ -n "$rid" ] || { echo "FAIL - could not create a review"; exit 1; }

# Second fixture: a fresh review with NO archived rounds (HISTVERS.length===1), every review's
# default state until an agent pushes a revision. Compare's own too-few-versions branch has to
# stay consistent here too, not just once there are 2+ versions to pick from.
zrid=$(python3 - "$port" <<'PY'
import json, sys, urllib.request
port = sys.argv[1]
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
r = urllib.request.Request("http://127.0.0.1:%s/api/reviews" % port,
                            data=json.dumps({"markdown": "# Doc\n\nOnly one version exists.\n",
                                              "title": "history-compare-zero-round"}).encode(),
                            headers={"Content-Type": "application/json"}, method="POST")
print(json.load(op.open(r, timeout=15))["id"])
PY
)
[ -n "$zrid" ] || { echo "FAIL - could not create the zero-round review"; exit 1; }

node "$here/scripts/history-compare-check.mjs" "http://127.0.0.1:$port/review/$rid" "http://127.0.0.1:$port/review/$zrid"
