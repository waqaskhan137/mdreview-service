#!/usr/bin/env bash
# reading_font_selfcheck.sh — the document reading surface, asserted as a RENDERED OUTCOME.
#
# The owner reverted the reading face and size on 2026-08-05: #277 put "Source Serif 4" at the
# front of --font-serif and #279 dropped the viewer's body from 20px to 18px. Both are undone.
#
# This pins the RESULT rather than the source text, because the interesting failure is silent: a
# future ticket re-adds a webfont to the front of the stack, or nudges the body size again as part
# of a re-skin, and nobody notices until the owner is reading a different document than they chose.
# So it samples what the browser computed for the real article body, and asserts the face that
# actually rendered via document.fonts.check — not merely what the CSS says.
#
#   bash tests/reading_font_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/reading_font_data"
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

rid=$(python3 - "$port" <<'PY'
import json,sys,urllib.request
port=sys.argv[1]
body=json.dumps({"title":"reading font probe","markdown":"# Heading\n\nA paragraph of prose long enough to be read.\n"}).encode()
r=urllib.request.Request(f"http://127.0.0.1:{port}/api/reviews",data=body,
                         headers={"Content-Type":"application/json"},method="POST")
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
print(json.load(op.open(r,timeout=15))["id"])
PY
)
[ -n "$rid" ] || { echo "FAIL - could not create a review"; exit 1; }
node "$here/scripts/reading-font-check.mjs" "http://127.0.0.1:$port/review/$rid"
