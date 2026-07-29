#!/usr/bin/env python3
"""account_tokens_csrf_selfcheck.py — CSRF on the /account/tokens write arms (#266).

WHAT THIS GUARDS. POST /account/tokens (mint) and DELETE /account/tokens/{id} (revoke) are
state-changing browser acts. Before #266 neither checked X-CSRF-Token, so a cross-site request
from any page a signed-in user visited could silently revoke their agents' tokens (denial of
access, not disclosure). The gate is the documented sharing posture (SharingModule._owner,
mutating=True): a request carrying a VERIFIED app-owned session cookie must present the
per-session token; the transitional proxy plane and the bearer-token plane carry no such cookie
and pass unchanged.

THE PLANE TRAP THIS TEST EXISTS TO AVOID (epic #273): tests/auth_smoke.py's cookie() helper
sends X-Mdreview-Proxy headers — that is the PROXY plane, which must NOT be CSRF-gated. A
403-without-token case written with it would assert the wrong plane. This test logs in the way a
browser does (magic link -> redeem -> Set-Cookie) and asserts on that genuine session cookie,
like tests/account_shares_selfcheck.py.

Mutation check: delete either `if not self._csrf_ok()` guard in src/mdreview/server.py and the
matching 403 case below fails.

Run: python3 tests/account_tokens_csrf_selfcheck.py     (exit 0 = pass)
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
DATA = os.path.join(ROOT, ".scratch", "account_tokens_csrf_data")
PROXY_SECRET = "test-proxy-secret-266"


def free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # ignore any system proxy
    try:
        with op.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA, exist_ok=True)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="1", MDREVIEW_PROXY_SECRET=PROXY_SECRET,
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL="o@e.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://l.test",
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
           PYTHONPATH=os.path.join(ROOT, "src"))
log_path = os.path.join(DATA, "s.log")
log = open(log_path, "w")
srv = subprocess.Popen([sys.executable, "-m", "mdreview.hosted"], env=env, stdout=log, stderr=log)
base = "http://127.0.0.1:%d" % port

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


def login(email):
    """A GENUINE browser session: magic link (stub email -> server log) redeemed for Set-Cookie."""
    req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
        {"Content-Type": "application/json"})
    tok = None
    for _ in range(40):                                     # poll, not a fixed sleep (CI jitter)
        hits = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", open(log_path).read())
        if hits:
            tok = hits[-1]
            break
        time.sleep(0.25)
    class NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NR, urllib.request.ProxyHandler({}))
    rq = urllib.request.Request(base + "/auth/redeem", data=("token=" + (tok or "")).encode(),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                method="POST")
    try:
        rs = op.open(rq, timeout=15)
    except urllib.error.HTTPError as e:
        rs = e
    ck = rs.headers.get("Set-Cookie", "").split(";")[0]
    _, raw = req(base + "/auth/session", h={"Cookie": ck})
    return ck, json.loads(raw).get("csrf", "")


try:
    for _ in range(60):
        try:
            req(base + "/healthz")
            break
        except Exception:
            time.sleep(0.25)

    ck, csrf = login("o@e.com")
    check("setup: genuine session cookie + csrf obtained", bool(ck) and bool(csrf))

    # ---- cookie plane: mint ------------------------------------------------------------------
    body = json.dumps({"label": "x"}).encode()
    ct = {"Content-Type": "application/json"}
    code, raw = req(base + "/account/tokens", "POST", body, {**ct, "Cookie": ck})
    check("mint without X-CSRF-Token -> 403", code == 403, code)
    check("...and the 403 is the CSRF gate", b"CSRF" in raw, raw[:80])
    code, _ = req(base + "/account/tokens", "POST", body,
                  {**ct, "Cookie": ck, "X-CSRF-Token": "wrong"})
    check("mint with a WRONG token -> 403", code == 403, code)
    code, raw = req(base + "/account/tokens", "POST", body,
                    {**ct, "Cookie": ck, "X-CSRF-Token": csrf})
    tok = json.loads(raw).get("token", "") if code == 201 else ""
    check("mint WITH the token -> 201, mdr_...", code == 201 and tok.startswith("mdr_"), code)
    tid = ""
    code, raw = req(base + "/account/tokens", h={"Cookie": ck})
    if code == 200:
        ids = [t["tok_id"] for t in json.loads(raw).get("tokens", [])]
        tid = ids[0] if ids else ""
    check("GET list needs no CSRF (reads exempt)", code == 200 and tid != "", code)

    # ---- cookie plane: revoke ----------------------------------------------------------------
    code, raw = req(base + "/account/tokens/" + tid, "DELETE", h={"Cookie": ck})
    check("revoke without X-CSRF-Token -> 403", code == 403 and b"CSRF" in raw, code)
    _, raw = req(base + "/account/tokens", h={"Cookie": ck})
    still = any(t["tok_id"] == tid for t in json.loads(raw).get("tokens", []))
    check("...and the token SURVIVED the blocked revoke", still)
    code, _ = req(base + "/account/tokens/" + tid, "DELETE",
                  h={"Cookie": ck, "X-CSRF-Token": csrf})
    check("revoke WITH the token -> 200", code == 200, code)
    _, raw = req(base + "/account/tokens", h={"Cookie": ck})
    check("...and it is gone", not any(t["tok_id"] == tid
                                       for t in json.loads(raw).get("tokens", [])))

    # ---- proxy plane: NO gate (the auth_smoke cookie() plane; must keep working) ---------------
    proxy = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
             "X-Auth-Request-User": "999", "X-Auth-Request-Email": "p@example.com"}
    code, raw = req(base + "/account/tokens", "POST", body, {**ct, **proxy})
    ptok = json.loads(raw).get("token", "") if code == 201 else ""
    check("proxy plane mints WITHOUT any CSRF token -> 201", code == 201, code)
    _, raw = req(base + "/account/tokens", h=proxy)
    pid = (json.loads(raw).get("tokens") or [{}])[0].get("tok_id", "")
    code, _ = req(base + "/account/tokens/" + pid, "DELETE", h=proxy)
    check("proxy plane revokes WITHOUT any CSRF token -> 200", code == 200, code)

    # ---- bearer plane: unchanged cookie-plane-only posture ------------------------------------
    code, raw = req(base + "/account/tokens", "POST", body, {**ct, **proxy})
    ptok = json.loads(raw).get("token", "")
    code, raw = req(base + "/account/tokens", "POST", body,
                    {**ct, "Authorization": "Bearer " + ptok})
    check("bearer plane mint -> 403 browser-only (unchanged)",
          code == 403 and b"browser" in raw, (code, raw[:80]))
finally:
    srv.terminate()
    srv.wait(timeout=10)
    log.close()

print()
print(("%d case(s) FAILED" % len(fails)) if fails else "all /account/tokens CSRF cases pass")
sys.exit(1 if fails else 0)
