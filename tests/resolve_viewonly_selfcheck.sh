#!/usr/bin/env bash
# resolve_viewonly_selfcheck.sh — #287 AC7: view-only readers never see the Resolve trigger, and
# the server refuses what the UI must not offer. Boots a real hosted-tier instance, has the owner
# (proxy plane) create a review + one open comment and make it PUBLIC (D3: public shares are
# view-only), then hands off to scripts/resolve-viewonly-check.mjs, which loads the review in a
# cookie-less headless Chrome tab — a real anonymous reader — and samples the rendered outcome.
#
#   bash tests/resolve_viewonly_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/resolve_viewonly_data"
rm -rf "$scratch"; mkdir -p "$scratch"
freeport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
port="$(freeport)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$scratch/d" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" PYTHONPATH="$here/src" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=1 MDREVIEW_PROXY_SECRET=viewonly-test-secret \
  MDREVIEW_SESSION_SECRET=s MDREVIEW_TOKEN_PEPPER=p MDREVIEW_OWNER_EMAIL=owner1@example.com \
  MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_PUBLIC_BASE=https://l.test \
  python3 -m mdreview.hosted >"$scratch/s.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = 1 ] || { echo "FAIL - server never came up on :$port"; sed -n '1,8p' "$scratch/s.log"; exit 1; }

info=$(python3 - "$port" <<'PY'
import json, sys, urllib.request
port = sys.argv[1]
base = "http://127.0.0.1:%s" % port
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
owner = {"X-Mdreview-Proxy": "viewonly-test-secret", "X-Mdreview-Provider": "google",
         "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com",
         "Content-Type": "application/json"}

def call(path, body=None, method="POST", headers=None):
    hdrs = dict(headers or owner)
    data = json.dumps(body).encode() if body is not None else (b"{}" if method == "POST" else None)
    req = urllib.request.Request(base + path, data=data, headers=hdrs, method=method)
    try:
        r = op.open(req, timeout=15)
        return r.status, (json.load(r) if r.status != 204 else None)
    except urllib.error.HTTPError as e:
        return e.code, None

rid = call("/api/reviews", {"markdown": "# t\n\npara\n", "title": "viewonly"})[1]["id"]
call("/api/reviews/%s/comments" % rid,
     {"anchor": {"block_num": "1", "quoted_text": ""}, "text": "a note"})
pub_status, _ = call("/api/reviews/%s/public" % rid, None)
# Server-side half of AC7: the UI must not offer what the server 404s. An anonymous POST to
# resolve (no comment_id needed to prove the point — even a nonexistent one) must be refused
# before any comment lookup, same as every other write on a review this caller does not own.
anon_status, _ = call("/api/reviews/%s/comments/cXXXXXXXXXX/resolve" % rid, {}, headers={"Content-Type": "application/json"})
print(json.dumps({"rid": rid, "pub_status": pub_status, "anon_resolve_status": anon_status}))
PY
)
[ -n "$info" ] || { echo "FAIL - could not seed the public-review fixture"; exit 1; }
rid=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['rid'])" "$info")
pub_status=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['pub_status'])" "$info")
anon_status=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['anon_resolve_status'])" "$info")
echo "setup: POST /public -> $pub_status (want 200), anonymous POST .../resolve -> $anon_status (want 401/404, never 200)"
[ "$pub_status" = "200" ] || { echo "FAIL - could not make the review public"; exit 1; }
case "$anon_status" in
  401|404) echo "  ok   - server refuses an anonymous resolve (matches the UI's gate)";;
  *) echo "  FAIL - server allowed/mis-refused an anonymous resolve (status=$anon_status)"; exit 1;;
esac

node "$here/scripts/resolve-viewonly-check.mjs" "http://127.0.0.1:$port/review/$rid"
