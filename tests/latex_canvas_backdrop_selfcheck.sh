#!/usr/bin/env bash
# latex_canvas_backdrop_selfcheck.sh — #333, asserted as a RENDERED OUTCOME.
#
# The failure mode this guards is specific and has happened here before (#265): a CSS-TEXT
# assertion stays green while the rendered thing is wrong. So this boots a real server, loads the
# real latex viewer in headless Chrome, and samples the COMPUTED background colour of .pdfpane in
# BOTH themes, comparing against --canvas resolved from the same document.
#
# Why compare against a resolved token rather than a hex literal: theme.css declares --canvas with
# light-dark(), so getPropertyValue returns the raw light-dark(...) TEXT, not a colour. A probe
# element is the only way to read what the browser actually resolved (the #285 lesson).
#
#   bash tests/latex_canvas_backdrop_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/latex_canvas_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" MDREVIEW_ENABLE_LATEX=1 \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/s.log" 2>&1 &
srv=$!
up=0; for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

rid=$(python3 - "$port" <<'PY'
import json,sys,urllib.request
port=sys.argv[1]
body=json.dumps({"title":"canvas probe","markdown":"\\documentclass{article}\\begin{document}x\\end{document}","kind":"latex"}).encode()
r=urllib.request.Request(f"http://127.0.0.1:{port}/api/reviews",data=body,headers={"Content-Type":"application/json"},method="POST")
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
print(json.load(op.open(r,timeout=15))["id"])
PY
)
[ -n "$rid" ] || { echo "FAIL - could not create a latex review"; exit 1; }
node "$here/scripts/latex-canvas-check.mjs" "http://127.0.0.1:$port/review/$rid"
