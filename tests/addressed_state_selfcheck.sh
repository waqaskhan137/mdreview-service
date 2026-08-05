#!/usr/bin/env bash
# addressed_state_selfcheck.sh — #331's runnable regression check for the viewer's ADDRESSED
# comment-card state.
#
# ADDRESSED = an OPEN thread (status != resolved) whose most recent entry is authored by the
# agent (web/app/viewer.html's isAddressed()). This provisions a real throwaway local instance,
# seeds four comment threads over the local-tier comments API covering the state's exact
# boundaries (open/agent-last, open/human-last, resolved/agent-last, reopened/agent-last), then
# hands off to scripts/addressed-check.mjs, which samples the COMPUTED render in headless Chrome.
# All assertions live there, named — this wrapper only provisions.
#
#   bash tests/addressed_state_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/addressed_state_data"
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

ids=$(python3 - "$port" <<'PY'
import json
import sys
import urllib.request

port = sys.argv[1]
base = "http://127.0.0.1:%s" % port
# Empty ProxyHandler: an enabled-but-dead system proxy otherwise silently swallows loopback
# requests that curl serves fine (bit this project before).
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    return json.load(opener.open(req, timeout=15))


md = "# Fixture\n\nBlock one.\n\nBlock two.\n\nBlock three.\n\nBlock four.\n"
rid = call("/api/reviews", {"markdown": md})["id"]


def make(block_num, thread):
    """thread: [(role, text), ...]. First entry creates the comment; the rest are replies."""
    role0, text0 = thread[0]
    cid = call("/api/reviews/%s/comments" % rid,
               {"anchor": {"block_num": str(block_num), "quoted_text": ""},
                "text": text0, "role": role0})["comment_id"]
    for role, text in thread[1:]:
        call("/api/reviews/%s/comments/%s/reply" % (rid, cid), {"text": text, "role": role})
    return cid


# A: open, agent replied last -> ADDRESSED
a = make(1, [("reviewer", "Is this right?"), ("agent", "Fixed, see the diff.")])
# B: open, agent answered but the human pushed back last -> NOT addressed
b = make(2, [("reviewer", "Is this right?"), ("agent", "Fixed."), ("reviewer", "Still not quite.")])
# C: resolved (agent's own entry is trivially last) -> NEVER addressed, it's a .rcard now
c = make(3, [("reviewer", "Typo here.")])
call("/api/reviews/%s/comments/%s/resolve" % (rid, c), {"justification": "Fixed the typo."})
# D: reopened WITHOUT a trailing reviewer entry, so the agent is still the thread's last speaker
# -> ADDRESSED (status != resolved, not the narrower/wrong status === 'open')
d = make(4, [("reviewer", "Second typo."), ("agent", "Fixed that one too.")])
call("/api/reviews/%s/comments/%s/resolve" % (rid, d), {})
call("/api/reviews/%s/comments/%s/reopen" % (rid, d), {})

print(json.dumps({"rid": rid, "a": a, "b": b, "c": c, "d": d}))
PY
)
[ -n "$ids" ] || { echo "FAIL - could not seed the comment fixture"; exit 1; }
rid=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['rid'])" "$ids")

node "$here/scripts/addressed-check.mjs" "http://127.0.0.1:$port/review/$rid" "$ids"
