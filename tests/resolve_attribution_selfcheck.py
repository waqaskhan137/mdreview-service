#!/usr/bin/env python3
"""resolve_attribution_selfcheck.py — #287 D2: comment-resolve attribution is plane-derived, not
hardcoded "agent".

WHAT THIS GUARDS. Before #287, POST .../comments/{cid}/resolve hardcoded `by="agent"` in BOTH
server.py (the route arm) and comments.py (`apply_transition`'s resolve branch ignored the `by`
argument it was given). #287 adds a human "Resolve" trigger to viewer.html's comment card, so a
person clicking it must be recorded as the reviewer — recording a human's resolve as the agent's
is the exact lie #187's attribution-truth rule exists to prevent ("an agent must never mark its
own work done"), mirrored.

Two guards, each independently load-bearing (see the mutation notes in the run report):
  - server.py's resolve arm derives `by` from the authenticated plane: cookie -> reviewer; local +
    X-Mdreview-Client: viewer -> reviewer (the #289 disambiguator, reused rather than reply's
    spoofable body-role fallback, since resolve is can_write like the #289 source-PUT arm, not
    can_comment like reply); everything else -> agent (token plane; local without the header).
  - comments.py's apply_transition resolve branch actually USES `by` (normalized: recognized
    values pass through, anything else falls back to "agent", preserving every pre-#287 caller's
    observed behaviour — MCP resolve_comment, tests, curl).

Local tier stays UNCHANGED by design (verified here): golden_transcript.sh's local-mode resolve
call carries no X-Mdreview-Client header, so it keeps reading "agent", exactly as before #287.
Hosted tier's cookie-plane call (golden_transcript.sh's OWNER-authenticated sequence) now reads
"reviewer" — a real, RECORDED drift confirmed against tests/access_seam_oracle.py; see the run
report for the three affected transcript fields (resolved_by, status_history[].by, and the
optional justification's thread[].author/role).

Run: python3 tests/resolve_attribution_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, ".scratch", "resolve_attribution_data")
PROXY_SECRET = "test-proxy-secret-287"

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name
          + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # bypass a dead loopback proxy


def req(u, m="GET", body=None, h=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(u, data=data, headers=h or {}, method=m)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with OPENER.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def boot(module, data, extra_env, log_path=None):
    port = free()
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data)
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), PYTHONPATH=SRC,
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), **extra_env)
    out = open(log_path, "w") if log_path else subprocess.DEVNULL
    proc = subprocess.Popen([sys.executable, "-m", module], env=env, stdout=out, stderr=out)
    base = "http://127.0.0.1:%d" % port
    for _ in range(80):
        if proc.poll() is not None:
            sys.exit("FAIL: %s exited on boot (rc=%s)" % (module, proc.returncode))
        try:
            if OPENER.open(base + "/healthz", timeout=5).status == 200:
                return proc, base
        except (urllib.error.URLError, OSError):
            time.sleep(0.15)
    proc.terminate()
    sys.exit("FAIL: %s did not answer /healthz" % module)


def mkcomment(base, rid, h=None):
    _, raw = req(base + "/api/reviews/%s/comments" % rid, "POST",
                 {"anchor": {"quoted_text": "x", "block_num": "1"}, "text": "hi"}, h)
    return json.loads(raw)["comment_id"]


# ================= local tier: header-gated, unchanged default =================
def local_cases(base):
    _, raw = req(base + "/api/reviews", "POST", {"markdown": "d0", "title": "t"})
    rid = json.loads(raw)["id"]
    check("setup: review created", bool(rid))

    # No X-Mdreview-Client header — the pre-#287 default MUST survive unchanged (this is exactly
    # golden_transcript.sh's local-mode resolve call: local plane, no such header).
    cid = mkcomment(base, rid)
    code, raw = req(base + "/api/reviews/%s/comments/%s/resolve" % (rid, cid), "POST", {})
    c = json.loads(raw)
    check("local, no header -> 200", code == 200, code)
    check("...resolved_by stays \"agent\" (unchanged default, golden-transcript-critical)",
          c.get("resolved_by") == "agent", c.get("resolved_by"))
    check("...status_history resolve entry stays by=\"agent\"",
          c["status_history"][-1] == {"from": "open", "to": "resolved", "by": "agent",
                                       "ts": c["status_history"][-1]["ts"]})

    # With the header — the SAME seam editguard.js's PUT /source already uses (#289), reused here
    # so a human's click on the local/single-operator tier is not misattributed to the agent.
    cid2 = mkcomment(base, rid)
    code, raw = req(base + "/api/reviews/%s/comments/%s/resolve" % (rid, cid2), "POST", {},
                     {"X-Mdreview-Client": "viewer"})
    c2 = json.loads(raw)
    check("local, X-Mdreview-Client: viewer -> 200", code == 200, code)
    check("...resolved_by is \"reviewer\" (#287's new local-tier path)",
          c2.get("resolved_by") == "reviewer", c2.get("resolved_by"))
    check("...status_history resolve entry is by=\"reviewer\"",
          c2["status_history"][-1]["by"] == "reviewer")

    # Reopen's attribution is OUT OF #287's scope (D2 only concerns resolve) and must stay
    # hardcoded "reviewer" regardless of plane/header — a regression here would be a DIFFERENT bug.
    code, raw = req(base + "/api/reviews/%s/comments/%s/reopen" % (rid, cid2), "POST", {})
    c3 = json.loads(raw)
    check("reopen stays by=\"reviewer\" unconditionally (unchanged, not part of D2)",
          c3["status_history"][-1]["by"] == "reviewer" and c3.get("resolved_by") is None)


# ================= hosted tier: cookie (human) vs token (agent) =================
def hosted_cases(base):
    proxy = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
             "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com"}
    code, raw = req(base + "/api/reviews", "POST", {"markdown": "s0", "title": "s"}, proxy)
    rid = json.loads(raw)["id"]
    check("hosted setup: review created on the proxy/cookie plane", code == 201 and bool(rid), code)

    # -- cookie plane (a human, proxy-vouched) -----------------------------------------------
    cid = mkcomment(base, rid, proxy)
    code, raw = req(base + "/api/reviews/%s/comments/%s/resolve" % (rid, cid), "POST",
                     {"justification": "done"}, proxy)
    c = json.loads(raw)
    check("cookie-plane resolve -> 200", code == 200, code)
    check("...resolved_by == \"reviewer\" (the human)", c.get("resolved_by") == "reviewer",
          c.get("resolved_by"))
    check("...status_history resolve entry by == \"reviewer\"",
          c["status_history"][-1]["by"] == "reviewer")
    check("...the optional justification thread entry is ALSO attributed to reviewer "
          "(not left as a hardcoded agent note under a human resolve)",
          c["thread"][-1]["author"] == "reviewer" and c["thread"][-1]["role"] == "reviewer",
          c["thread"][-1])

    # -- token plane (an agent, Bearer) ------------------------------------------------------
    code, raw = req(base + "/account/tokens", "POST", {"label": "t"}, proxy)
    btok = json.loads(raw).get("token", "") if code == 201 else ""
    check("bearer setup: token minted", code == 201 and btok.startswith("mdr_"), code)
    bearer = {"Authorization": "Bearer " + btok}

    cid2 = mkcomment(base, rid, proxy)
    code, raw = req(base + "/api/reviews/%s/comments/%s/resolve" % (rid, cid2), "POST",
                     {"justification": "done via mcp"}, bearer)
    c2 = json.loads(raw)
    check("token-plane resolve -> 200", code == 200, code)
    check("...resolved_by == \"agent\"", c2.get("resolved_by") == "agent", c2.get("resolved_by"))
    check("...status_history resolve entry by == \"agent\"",
          c2["status_history"][-1]["by"] == "agent")
    check("...the justification thread entry stays attributed to agent",
          c2["thread"][-1]["author"] == "agent" and c2["thread"][-1]["role"] == "agent")

    # -- #103 access-denial matrix is UNTOUCHED by #287 (spot-checked directly here since the
    # oracle's diff-based denial scan goes blind once ANY other row legitimately drifts — see the
    # run report) --------------------------------------------------------------------------------
    nonowner = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
                "X-Auth-Request-User": "owner2", "X-Auth-Request-Email": "owner2@example.com"}
    code, _ = req(base + "/api/reviews/%s" % rid, "GET")
    check("unauthenticated, existing review -> 401 (unchanged)", code == 401, code)
    code, _ = req(base + "/api/reviews/%s" % rid, "GET", h=nonowner)
    check("authenticated non-owner, existing review -> 404 (unchanged)", code == 404, code)
    code, _ = req(base + "/api/reviews/nope00000000", "GET")
    check("unauthenticated, absent review -> 401, not 404 (unchanged, inversion-critical)",
          code == 401, code)
    code, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "x"})
    check("unauthenticated write -> 401 (unchanged)", code == 401, code)
    code, _ = req(base + "/api/reviews/%s" % rid, "DELETE", h=nonowner)
    check("non-owner delete -> 404 (unchanged)", code == 404, code)


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(DATA, exist_ok=True)

    print("-- local tier --")
    ldata = os.path.join(DATA, "local")
    lproc, lbase = boot("mdreview", ldata, {})
    try:
        local_cases(lbase)
    finally:
        lproc.terminate()
        lproc.wait(timeout=10)

    print("-- hosted tier --")
    hdata = os.path.join(DATA, "hosted")
    hlog = os.path.join(DATA, "hosted.log")
    hproc, hbase = boot("mdreview.hosted", hdata, {
        "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_ALLOW_PROXY_PLANE": "1",
        "MDREVIEW_PROXY_SECRET": PROXY_SECRET, "MDREVIEW_SESSION_SECRET": "s",
        "MDREVIEW_TOKEN_PEPPER": "p", "MDREVIEW_OWNER_EMAIL": "owner1@example.com",
        "MDREVIEW_ALLOW_STUB_EMAIL": "1", "MDREVIEW_PUBLIC_BASE": "https://l.test",
    }, log_path=hlog)
    try:
        hosted_cases(hbase)
    finally:
        hproc.terminate()
        hproc.wait(timeout=10)

    print()
    print(("%d case(s) FAILED" % len(fails)) if fails else "all #287 D2 resolve-attribution cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
