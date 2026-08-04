#!/usr/bin/env bash
# theme_toggle_selfcheck.sh — #285's runnable regression check: starts the servers, wires the
# fixtures, and runs scripts/theme-check.mjs over the full 3-state x 5-page toggle matrix.
#
# Two instances because the five pages do not live on one plane: a LOCAL instance serves the
# dashboard, /account and both viewers (MDREVIEW_ENABLE_LATEX=1 so /review/{latex} serves
# latex-viewer.html), and a HOSTED instance serves /admin (the console shell is hosted-only;
# it is served unauthenticated, and the toggle mounts synchronously, before any session fetch,
# so no login flow is needed). The markdown fixture carries a mermaid diagram and a python
# fence so the AC-5 consumer checks (Mermaid retheme, keysheet, hljs) have something to sample.
#
# All assertions live in scripts/theme-check.mjs as computed-value checks with named findings;
# this wrapper only provisions. Requires node >= 21 (built-in WebSocket) and a Chrome/Chromium
# (CHROME= to override discovery).
#   bash tests/theme_toggle_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/theme_toggle_data"
rm -rf "$scratch"; mkdir -p "$scratch"

freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
p1="$(freeport)"; p2="$(freeport)"
cleanup(){ [ -n "${srv1:-}" ] && kill "$srv1" 2>/dev/null; [ -n "${srv2:-}" ] && kill "$srv2" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/local" PORT="$p1" MDREVIEW_WEB_DIR="$here/web/app" MDREVIEW_ENABLE_LATEX=1 \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/local.log" 2>&1 &
srv1=$!
MDREVIEW_DATA="$scratch/hosted" PORT="$p2" MDREVIEW_WEB_DIR="$here/web/app" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_PROXY_SECRET=inert-not-a-plane \
  MDREVIEW_SESSION_SECRET=s MDREVIEW_TOKEN_PEPPER=p MDREVIEW_OWNER_EMAIL=o@e.com \
  MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_PUBLIC_BASE=https://l.test \
  PYTHONPATH="$here/src" python3 -m mdreview.hosted >"$scratch/hosted.log" 2>&1 &
srv2=$!

for pair in "$p1:local" "$p2:hosted"; do
  port="${pair%%:*}"; name="${pair##*:}"; up=0
  for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
  [ "$up" = "1" ] || { echo "FAIL - $name server never came up on :$port"; sed -n '1,8p' "$scratch/$name.log"; exit 1; }
done

# Markdown fixture: a mermaid diagram (AC 5a samples a rect fill inside its SVG) and a python
# fence with keywords (AC 5c samples .hljs-keyword). The keysheet needs no fixture.
mkfixture(){ python3 - "$1" <<'PY'
import json, sys, urllib.request
md = ("# Theme fixture\n\nBody paragraph.\n\n"
      "```mermaid\ngraph TD; A[Start] --> B[End];\n```\n\n"
      "```python\ndef check():\n    return True\n```\n")
req = urllib.request.Request("http://127.0.0.1:%s/api/reviews" % sys.argv[1],
    data=json.dumps({"markdown": md}).encode(), headers={"Content-Type": "application/json"})
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
print(json.load(op.open(req, timeout=15))["id"])
PY
}
mklatex(){ python3 - "$1" <<'PY'
import json, sys, urllib.request
tex = "\\documentclass{article}\n\\begin{document}\nTheme fixture.\n\\end{document}\n"
req = urllib.request.Request("http://127.0.0.1:%s/api/reviews" % sys.argv[1],
    data=json.dumps({"markdown": tex, "kind": "latex"}).encode(),
    headers={"Content-Type": "application/json"})
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
print(json.load(op.open(req, timeout=15))["id"])
PY
}
rid="$(mkfixture "$p1")" || { echo "FAIL - could not create the markdown fixture"; exit 1; }
lrid="$(mklatex "$p1")"  || { echo "FAIL - could not create the latex fixture"; exit 1; }

node "$here/scripts/theme-check.mjs" \
  --base "http://127.0.0.1:$p1" --review "$rid" --latex "$lrid" \
  --admin "http://127.0.0.1:$p2"
rc=$?
rm -rf "$scratch"
exit "$rc"
