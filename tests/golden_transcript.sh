#!/usr/bin/env bash
# golden_transcript.sh BASE_A BASE_B [MODE] [SECRET]   (MR-092; tier-aware since #103)
#
# Byte-identical oracle: drives the SAME scripted request sequence against two running mdreview
# instances and diffs the normalized transcripts. Exit 0 = identical (+ prints the transcript),
# 1 = drift (unified diff printed), 2 = usage/setup error.
#
# MODE (default "local"):
#   local  - REQUIRE_AUTH off. No auth headers; the everything-open transcript.
#   hosted - REQUIRE_AUTH on. Every request is authenticated as the OWNER (oauth2-proxy-vouched
#            headers, proxy secret = SECRET) so the same sequence runs, PLUS a block of #103
#            access-denial probes that pin the read-order inversion: an unauthenticated caller and
#            an authenticated non-owner, against both an existing and an absent review.
#
# Normalization (a transcript line is "STEP METHOD PATH -> CODE" + body): volatile values are
# stamped out before comparison - the created review id (captured per instance), comment ids
# (c + 10 alnum), and epoch-timestamp values for a fixed key set. HTML/binary bodies compare as
# sha256, so page bytes still gate byte-identity without dumping HTML into the transcript. The
# durable owner key (provider:sub) is deterministic given the fixed headers, so it is NOT stamped:
# it must match before-vs-after, which is the point.
#
# Run each instance on a scratch port with a FRESH throwaway MDREVIEW_DATA (gitignored .scratch/),
# never the live :8139 / :8137 or the mdreview-data volume. tests/access_seam_oracle.py drives this.
set -u
A="${1:-}"; B="${2:-}"; MODE="${3:-local}"; SECRET="${4:-}"
[ -n "$A" ] && [ -n "$B" ] || { echo "usage: $0 BASE_A BASE_B [MODE] [SECRET]" >&2; exit 2; }

transcript() { # $1 = base url, $2 = out file
  python3 - "$1" "$MODE" "$SECRET" > "$2" <<'PY'
import hashlib, json, re, sys, urllib.request, urllib.error

BASE = sys.argv[1].rstrip("/")
MODE = sys.argv[2]
SECRET = sys.argv[3]
# Bypass any system proxy for loopback: a dead 127.0.0.1 proxy poisons urllib (curl ignores it).
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Hosted identities (oauth2-proxy-vouched headers). OWNER authors the sequence; NONOWNER probes
# another account's access. provider:sub -> "google:owner1" / "google:owner2".
OWNER = {"X-Mdreview-Proxy": SECRET, "X-Mdreview-Provider": "google",
         "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com"}
NONOWNER = {"X-Mdreview-Proxy": SECRET, "X-Mdreview-Provider": "google",
            "X-Auth-Request-User": "owner2", "X-Auth-Request-Email": "owner2@example.com"}

VOLATILE = {"created", "source_updated", "comments_updated", "feedback_updated", "turn_updated",
            "ts", "created_at", "resolved_at", "finished_at", "at"}
CID_RE = re.compile(r"\bc[A-Za-z0-9]{10}\b")
rid = None

def scrub(x):
    if isinstance(x, dict):
        return {k: ("T" if k in VOLATILE and isinstance(v, (int, float)) else scrub(v))
                for k, v in x.items()}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    if isinstance(x, str):
        s = CID_RE.sub("CID", x.replace(BASE, "BASE"))
        if rid:
            s = s.replace(rid, "RID")
        return s
    return x

def req(method, path, body=None, accept=None, capture_rid=False, headers=None):
    global rid
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if accept:
        r.add_header("Accept", accept)
    # Hosted authenticates every request as the OWNER unless a probe overrides headers
    # (headers={} = unauthenticated; NONOWNER = a different account). Local sends none.
    hdrs = headers if headers is not None else (OWNER if MODE == "hosted" else {})
    for k, v in hdrs.items():
        r.add_header(k, v)
    try:
        with OPENER.open(r, timeout=10) as resp:
            code, raw, ct = resp.status, resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        code, raw, ct = e.code, e.read(), e.headers.get("Content-Type", "")
    if capture_rid:
        rid = json.loads(raw.decode())["id"]
    shown_path = CID_RE.sub("CID", path.replace(rid, "RID") if rid else path)
    print(f"### {method} {shown_path} -> {code}")
    if "application/json" in ct:
        try:
            print(json.dumps(scrub(json.loads(raw.decode())), sort_keys=True))
        except ValueError:
            print("nonjson sha256=" + hashlib.sha256(raw).hexdigest())
    else:
        print(f"{ct.split(';')[0]} len={len(raw)} sha256=" + hashlib.sha256(raw).hexdigest())
    return code, raw

req("GET", "/healthz")
req("GET", "/api")
req("GET", "/api/reviews")
req("POST", "/api/reviews",
    {"markdown": "# Golden\n\nfirst body", "title": "golden", "project": "oracle"},
    capture_rid=True)
req("GET", f"/api/reviews/{rid}")
req("GET", f"/api/reviews/{rid}/source")
req("GET", f"/api/reviews/{rid}/status")
req("PUT", f"/api/reviews/{rid}/source", {"markdown": "# Golden v2\n\nsecond body"})
req("GET", f"/api/reviews/{rid}/history")
_, raw = req("POST", f"/api/reviews/{rid}/comments",
             {"anchor": {"quoted_text": "second body", "block_num": "1", "start": None,
                         "end": None}, "text": "a note"})
cid = json.loads(raw.decode())["comment_id"]
req("GET", f"/api/reviews/{rid}/comments")
req("POST", f"/api/reviews/{rid}/comments/{cid}/reply", {"text": "re", "role": "reviewer"})
req("POST", f"/api/reviews/{rid}/comments/{cid}/resolve", {"justification": "done"})
req("POST", f"/api/reviews/{rid}/comments/{cid}/reopen", {"text": "again"})
req("DELETE", f"/api/reviews/{rid}/comments/{cid}")
req("GET", f"/api/reviews/{rid}/feedback")
req("GET", f"/api/reviews/{rid}/assets")
req("GET", "/", accept="application/json")
req("GET", f"/review/{rid}")           # the MARKDOWN viewer page — must be byte-identical
# GET / (the dashboard page) is DELIBERATELY not byte-compared: MR-098 adds a kind-guarded LATEX
# chip + badge to web/app/dashboard.html. That is an intended feature change (epic 3.5), additive
# and guarded on r.kind==="latex", so a markdown-only dashboard renders identically (verified by
# `git diff <baseline> -- web/app/dashboard.html`). Byte-identity applies to the API + the markdown
# viewer, which this transcript exercises; the dashboard's inert-for-markdown bytes are excluded.
req("GET", "/static/nope.js")

# --- #103 access-denial probes (hosted only): the read-order inversion (can_read consulted BEFORE
# identity is demanded) MUST keep these outcomes. An unauthenticated caller 401s BEFORE the
# exists/404 distinction, so it 401s even for an ABSENT review (the row a naive "exists-first"
# inversion would wrongly turn into 404). An authenticated non-owner is 404 (fail-closed, not 403/
# 200). Neither the unauth PUT nor the non-owner DELETE mutates, so the owner's review survives for
# the delete below. ---
if MODE == "hosted":
    req("GET", f"/api/reviews/{rid}", headers={})                     # unauthenticated, existing -> 401
    req("GET", f"/api/reviews/{rid}", headers=NONOWNER)               # non-owner, existing      -> 404
    req("GET", "/api/reviews/nope00000000", headers={})              # unauthenticated, ABSENT  -> 401 (inversion-critical)
    req("GET", "/api/reviews/nope00000000", headers=NONOWNER)        # non-owner, ABSENT        -> 404
    req("PUT", f"/api/reviews/{rid}/source", {"markdown": "x"}, headers={})  # unauth write      -> 401 (no write)
    req("DELETE", f"/api/reviews/{rid}", headers=NONOWNER)            # non-owner delete         -> 404 (no delete)

req("DELETE", f"/api/reviews/{rid}")
req("GET", f"/api/reviews/{rid}/status")
req("GET", "/definitely/not/a/route")
PY
}

TA="$(mktemp)"; TB="$(mktemp)"
transcript "$A" "$TA" || { echo "FAIL: transcript against $A errored" >&2; exit 2; }
transcript "$B" "$TB" || { echo "FAIL: transcript against $B errored" >&2; exit 2; }

if diff -u "$TA" "$TB"; then
  echo "OK: transcripts identical ($(grep -c '^###' "$TA") steps) [mode=$MODE]"
  cat "$TA"                       # the shared normalized transcript, for the PR record
  exit 0
else
  echo "FAIL: transcript drift between $A and $B [mode=$MODE]" >&2
  exit 1
fi
