#!/usr/bin/env python3
"""Manual resolve smoke (#187) — the human sign-off route, POST /api/reviews/{id}/resolve.

The owner's decision (recorded on #187, 2026-07-29): a manual resolve is APPROVAL-CLASS, so the
route is cookie-plane human-only. That gives this check four load-bearing assertions no other test
makes, each of which is a silent policy hole if it regresses:

  - the BEARER PLANE IS REFUSED here (403) for a token that can otherwise WRITE the review — the
    deliberate divergence from the sharing posture, proven by first writing with that very token;
  - NO MCP TOOL exists for the capability, in any plane (the tool list is grepped);
  - the flag is STICKY (a new comment does not un-resolve) and REVERSIBLE (un-resolve restores the
    derived status), and the override shows on /api/reviews, the summary, AND /status;
  - a review never manually resolved keeps a BYTE-IDENTICAL meta.json across reads (the
    additive-default-safe contract kind/turn already follow).

Plus the ordinary write-route posture: owner-only (non-owner 404, anonymous 401), CSRF-checked on
the app-session cookie plane, boolean-body validated, and the local tier (no auth plane) still
serves the dashboard's plain fetch.

Boots real servers (hosted composition + local) on scratch ports with fresh data dirs under
.scratch/ — never the live instance. Run: python3 tests/manual_resolve_smoke.py
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "src")
WEB = os.path.join(REPO, "web", "app")
SCRATCH = os.path.join(REPO, ".scratch", "manual_resolve")
SESSION_SECRET = "resolve-smoke-session-secret"
PROXY_SECRET = "resolve-smoke-proxy-secret"
PEPPER = "resolve-smoke-pepper"

sys.path.insert(0, SRC)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # dead loopback proxy guard

OWNER = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
         "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com"}
NONOWNER = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
            "X-Auth-Request-User": "owner2", "X-Auth-Request-Email": "owner2@example.com"}

fails = []


def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)
        if detail:
            print("         " + str(detail)[:200])


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def req(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with OPENER.open(r, timeout=10) as resp:
            raw = resp.read()
            code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        code = e.code
    try:
        return code, json.loads(raw.decode() or "{}")
    except ValueError:
        return code, {}


def boot(module, data, extra_env):
    os.makedirs(data, exist_ok=True)
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("MDREVIEW_")}
    env.update({"PYTHONPATH": SRC, "MDREVIEW_DATA": data, "PORT": str(port),
                "MDREVIEW_WEB_DIR": WEB, **extra_env})
    proc = subprocess.Popen([sys.executable, "-m", module], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(100):
        if proc.poll() is not None:
            sys.exit("FAIL: %s exited on boot (rc=%s)" % (module, proc.returncode))
        try:
            if OPENER.open(base + "/healthz", timeout=5).status == 200:
                return proc, base
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    proc.terminate()
    sys.exit("FAIL: %s did not answer /healthz" % module)


shutil.rmtree(SCRATCH, ignore_errors=True)
DATA = os.path.join(SCRATCH, "hosted-data")
procs = []
try:
    # ---- hosted composition (build_hosted: CustodyPolicy + sessions + CSRF) ---------------------
    proc, base = boot("mdreview.hosted", DATA, {
        "MDREVIEW_SESSION_SECRET": SESSION_SECRET, "MDREVIEW_TOKEN_PEPPER": PEPPER,
        "MDREVIEW_OWNER_EMAIL": "owner1@example.com",
        "MDREVIEW_PUBLIC_BASE": "https://resolve.smoke.invalid",
        "MDREVIEW_ALLOW_STUB_EMAIL": "1",
        "MDREVIEW_ALLOW_PROXY_PLANE": "1", "MDREVIEW_PROXY_SECRET": PROXY_SECRET,
    })
    procs.append(proc)

    # Owner (proxy plane, plane="cookie") authors a review with ONE OPEN comment: the exact state
    # the ticket names — derivable status can never read "resolved" here.
    code, out = req(base, "POST", "/api/reviews",
                    {"markdown": "# R\n\nbody", "title": "resolve-smoke"}, OWNER)
    rid = out.get("id", "")
    check("owner creates a review", code == 201 and rid, out)
    code, out = req(base, "POST", "/api/reviews/%s/comments" % rid,
                    {"anchor": {}, "text": "open comment"}, OWNER)
    check("owner posts an (open) comment", code == 201, out)
    code, out = req(base, "GET", "/api/reviews/%s" % rid, None, OWNER)
    check("derived status is 'feedback' with an open comment", out.get("status") == "feedback", out)
    code, out = req(base, "GET", "/api/reviews/%s/status" % rid, None, OWNER)
    check("/status reports the derived status too (#187 additive field)",
          code == 200 and out.get("status") == "feedback", out)

    meta_path = os.path.join(DATA, rid, "meta.json")
    with open(meta_path, "rb") as f:
        check("meta.json carries no resolve keys before any resolve",
              b"resolved_by_human" not in f.read())

    # A REAL app-session cookie for the owner: minted with the server's secret AND a session row in
    # the server's identity.db, so verify() + the #223 jti liveness check both pass.
    from mdreview.hosted.identity_store import IdentityStore
    from mdreview.hosted.sessions import SessionService, COOKIE_NAME
    cookie, csrf = SessionService(
        SESSION_SECRET, records=IdentityStore(os.path.join(DATA, "identity.db"))
    ).mint("google:owner1", "owner1@example.com")
    SESS = {"Cookie": "%s=%s" % (COOKIE_NAME, cookie)}

    # ---- CSRF: the cookie plane must present the bound token ------------------------------------
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": True},
                    {**SESS, "X-CSRF-Token": "wrong"})
    check("session cookie with a WRONG CSRF token -> 403", code == 403, (code, out))
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": True}, SESS)
    check("session cookie with NO CSRF token -> 403", code == 403, (code, out))

    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": "yes"},
                    {**SESS, "X-CSRF-Token": csrf})
    check("non-boolean body -> 400", code == 400, (code, out))

    # ---- THE FEATURE: resolve from the browser, status overrides everywhere ---------------------
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": True},
                    {**SESS, "X-CSRF-Token": csrf})
    check("cookie plane + CSRF resolves (200, status 'resolved')",
          code == 200 and out.get("status") == "resolved", (code, out))
    code, out = req(base, "GET", "/api/reviews", None, OWNER)
    rows = {r.get("id"): r for r in out.get("reviews", [])}
    check("GET /api/reviews reports 'resolved' despite the open comment",
          rows.get(rid, {}).get("status") == "resolved", out)
    code, out = req(base, "GET", "/api/reviews/%s/status" % rid, None, OWNER)
    check("/status reports 'resolved'", out.get("status") == "resolved", out)

    # Sticky: a NEW comment after the resolve must not flap the status back.
    code, out = req(base, "POST", "/api/reviews/%s/comments" % rid,
                    {"anchor": {}, "text": "late comment"}, OWNER)
    check("a new comment still lands on a resolved review", code == 201, out)
    code, out = req(base, "GET", "/api/reviews/%s" % rid, None, OWNER)
    check("the manual resolve is STICKY under the new comment",
          out.get("status") == "resolved", out)

    # ---- the divergence: a bearer token that CAN write is refused HERE --------------------------
    code, out = req(base, "POST", "/account/tokens", {"label": "smoke"}, OWNER)
    token = out.get("token", "")
    check("owner mints an agent token", code == 201 and token.startswith("mdr_"), (code, out))
    BEARER = {"Authorization": "Bearer " + token}
    code, out = req(base, "PUT", "/api/reviews/%s/source" % rid, {"markdown": "# R2\n\nv2"}, BEARER)
    check("that token CAN write the document (PUT source 200)", code == 200, (code, out))
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": False}, BEARER)
    check("the SAME token is REFUSED on /resolve (403; approval-class, human-only)",
          code == 403, (code, out))
    code, out = req(base, "GET", "/api/reviews/%s" % rid, None, OWNER)
    check("the refused bearer call changed nothing (still resolved)",
          out.get("status") == "resolved", out)

    # ---- no MCP tool, in any plane (grep of the tool list, per the AC) ---------------------------
    with open(os.path.join(SRC, "mcp", "tools.py"), encoding="utf-8") as f:
        names = re.findall(r'"name":\s*"([^"]+)"', f.read())
    offenders = [n for n in names if re.search(r"resolve|unresolve", n) and n != "resolve_comment"]
    check("no review-resolve MCP tool exists (resolve_comment is the pre-existing comment workflow)",
          not offenders, offenders)

    # ---- reversible: the same route un-resolves and the derived status returns ------------------
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": False},
                    {**SESS, "X-CSRF-Token": csrf})
    check("un-resolve returns the derived status ('feedback', two open comments)",
          code == 200 and out.get("status") == "feedback", (code, out))
    with open(meta_path, "rb") as f:
        check("un-resolve removes both keys from meta.json", b"resolved_" not in f.read())

    # ---- owner-only, like every write route ------------------------------------------------------
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": True}, NONOWNER)
    check("authenticated non-owner -> 404 (not probeable)", code == 404, (code, out))
    code, out = req(base, "POST", "/api/reviews/%s/resolve" % rid, {"resolved": True}, {})
    check("anonymous -> 401", code == 401, (code, out))

    # ---- regression: an untouched review's meta.json is BYTE-IDENTICAL across reads -------------
    code, out = req(base, "POST", "/api/reviews", {"markdown": "# U", "title": "untouched"}, OWNER)
    rid2 = out.get("id", "")
    with open(os.path.join(DATA, rid2, "meta.json"), "rb") as f:
        before = f.read()
    req(base, "GET", "/api/reviews", None, OWNER)
    req(base, "GET", "/api/reviews/%s" % rid2, None, OWNER)
    req(base, "GET", "/api/reviews/%s/status" % rid2, None, OWNER)
    with open(os.path.join(DATA, rid2, "meta.json"), "rb") as f:
        after = f.read()
    check("a never-resolved review's meta.json is byte-identical after list/summary/status reads",
          before == after and b"resolved_by_human" not in after)

    # ---- local tier (no auth plane): the dashboard's plain fetch still works --------------------
    lproc, lbase = boot("mdreview", os.path.join(SCRATCH, "local-data"), {})
    procs.append(lproc)
    code, out = req(lbase, "POST", "/api/reviews", {"markdown": "# L", "title": "local"})
    lrid = out.get("id", "")
    check("local tier creates a review", code == 201 and lrid, out)
    code, out = req(lbase, "POST", "/api/reviews/%s/resolve" % lrid, {"resolved": True})
    check("local tier resolves with no cookie/CSRF (no auth plane to satisfy)",
          code == 200 and out.get("status") == "resolved", (code, out))
finally:
    for p in procs:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()

print()
if fails:
    print("FAILED: %d case(s): %s" % (len(fails), "; ".join(fails)))
    sys.exit(1)
print("manual resolve smoke: all cases passed")
