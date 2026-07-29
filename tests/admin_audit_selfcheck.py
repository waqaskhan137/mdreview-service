#!/usr/bin/env python3
"""admin_audit_selfcheck.py — the auth-audit read endpoint, GET /admin/audit (#144).

WHAT THIS GUARDS. auth_audit was a write-only sink: every admin action and auth event lands
there, but nothing could read it back, so "who did what to whom" was invisible in the product.
#144 adds the v1 read the owner accepted 2026-07-29: newest-first, `limit` + `before` (ts)
cursor pagination, unfiltered, RAW fields (emails, IPs) to admins. The gate is the same
cookie-plane-admin gate as the rest of /admin/*; a READ carries no CSRF requirement (#146
gates writes only).

Cases:
  - anonymous -> 401; non-admin cookie -> 403 ("admin only", indistinguishable from token-plane);
    admin bearer token -> 403 (cookie-plane only, an admin's leaked API token reads nothing).
  - admin cookie -> 200 with newest-first events carrying raw email + ip.
  - an admin ACTION (blocklist add) surfaces with actor uid, parsed target, and detail.
  - limit bounds the page; before=<next_before> pages on with no overlap, all strictly older.

Mutation check: drop the `/admin/audit` route or its gate in adminroutes.py, or the `before`
filter in IdentityStore.recent_audit, and a case below fails.

Run: python3 tests/admin_audit_selfcheck.py     (exit 0 = pass)
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
DATA = os.path.join(ROOT, ".scratch", "admin_audit_data")

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
           MDREVIEW_PROXY_SECRET="inert-not-a-plane",       # boot requires it; the plane stays off
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
    print(("  ok   " if cond else "  FAIL ") + name
          + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


def login(email):
    """A GENUINE browser session (the account_tokens_csrf_selfcheck pattern): magic link via the
    stub-email server log, redeemed for Set-Cookie."""
    seen = len(re.findall(r"auth/redeem\?token=", open(log_path).read()))
    req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
        {"Content-Type": "application/json"})
    tok = None
    for _ in range(40):                                     # poll, not a fixed sleep (CI jitter)
        hits = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", open(log_path).read())
        if len(hits) > seen:
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

    admin_ck, admin_csrf = login("o@e.com")                 # MDREVIEW_OWNER_EMAIL -> admin
    user_ck, _ = login("u@e.com")                           # a plain member
    check("setup: admin + member sessions", bool(admin_ck) and bool(user_ck))

    # ---- the gate: exactly the /admin/* posture ------------------------------------------------
    code, _ = req(base + "/admin/audit")
    check("anonymous -> 401", code == 401, code)
    code, raw = req(base + "/admin/audit", h={"Cookie": user_ck})
    check("non-admin cookie -> 403 'admin only'", code == 403 and b"admin only" in raw, code)
    code, raw = req(base + "/account/tokens", "POST", json.dumps({"label": "x"}).encode(),
                    {"Content-Type": "application/json", "Cookie": admin_ck,
                     "X-CSRF-Token": admin_csrf})
    bearer = json.loads(raw).get("token", "") if code == 201 else ""
    code, raw = req(base + "/admin/audit", h={"Authorization": "Bearer " + bearer})
    check("admin's own BEARER token -> 403 (cookie plane only)", code == 403, code)

    # ---- the read: raw fields, newest-first ----------------------------------------------------
    code, raw = req(base + "/admin/audit", h={"Cookie": admin_ck})
    d = json.loads(raw) if code == 200 else {}
    ev = d.get("events", [])
    check("admin cookie -> 200 with events (logins already audited)", code == 200 and len(ev) >= 4,
          (code, len(ev)))
    check("newest-first (ts non-increasing)",
          all(ev[i]["ts"] >= ev[i + 1]["ts"] for i in range(len(ev) - 1)))
    check("raw email visible (stated PII policy, not redacted)",
          any(e.get("email") == "u@e.com" for e in ev))
    check("ip present on events", any(e.get("ip") for e in ev))

    # ---- an admin action surfaces with actor + parsed target -----------------------------------
    code, _ = req(base + "/admin/blocklist", "POST",
                  json.dumps({"value": "spam@x.com", "kind": "email"}).encode(),
                  {"Content-Type": "application/json", "Cookie": admin_ck,
                   "X-CSRF-Token": admin_csrf})
    check("setup: blocklist add (the audited admin act) -> 201", code == 201, code)
    _, raw = req(base + "/admin/audit", h={"Cookie": admin_ck})
    ev = json.loads(raw).get("events", [])
    hit = next((e for e in ev if e["event"] == "admin_block_add"), None)
    check("admin action appears newest-first", hit is not None and ev[0]["event"] == "admin_block_add")
    check("actor uid recorded", bool(hit and hit.get("actor")))
    check("target parsed out of the detail prefix", bool(hit) and hit.get("target") == "spam@x.com",
          hit and hit.get("target"))
    check("detail carries the remainder, not the target= prefix",
          bool(hit) and hit.get("detail") == "kind=email", hit and hit.get("detail"))

    # ---- pagination: limit bounds, before pages on, no overlap ---------------------------------
    code, raw = req(base + "/admin/audit?limit=2", h={"Cookie": admin_ck})
    d = json.loads(raw)
    p1 = d.get("events", [])
    check("limit=2 -> exactly 2 events + next_before", len(p1) == 2 and d.get("next_before"),
          (len(p1), d.get("next_before")))
    code, raw = req(base + "/admin/audit?limit=2&before=%s" % d["next_before"],
                    h={"Cookie": admin_ck})
    p2 = json.loads(raw).get("events", [])
    check("before=<next_before> -> the NEXT page, strictly older, no overlap",
          len(p2) >= 1 and all(e["ts"] < d["next_before"] for e in p2)
          and not ({(e["ts"], e["event"]) for e in p1} & {(e["ts"], e["event"]) for e in p2}))
    code, _ = req(base + "/admin/audit?before=nonsense", h={"Cookie": admin_ck})
    check("malformed before -> 400", code == 400, code)
finally:
    srv.terminate()
    srv.wait(timeout=10)
    log.close()
    shutil.rmtree(DATA, ignore_errors=True)

print()
print(("%d case(s) FAILED" % len(fails)) if fails else "all /admin/audit cases pass")
sys.exit(1 if fails else 0)
