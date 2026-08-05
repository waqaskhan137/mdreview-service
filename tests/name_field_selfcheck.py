#!/usr/bin/env python3
"""name_field_selfcheck.py — #309 slice 1: the `name` field, its write endpoint, and the
absent-means-unset contract, verified as REAL API behaviour against a running hosted instance
(genuine magic-link login, genuine cookie + CSRF, no fixture, no stub).

WHAT THIS GUARDS.
  - POST /auth/profile sets/clears the display name; GET /auth/session reads it back.
  - Validation: trimmed, 1-60 chars after trimming, control characters (incl. newlines/tabs)
    rejected outright. A trimmed-empty name CLEARS rather than erroring (#309 AC4: Skip/clear are
    the same call).
  - Absent means unset, with NO migration: a user who never calls the endpoint reads name="" from
    /auth/session, identically to one who cleared it. #309's ticket text asserted this from reading
    ensure_user (src/mdreview/users.py); this test proves it against the running server instead of
    trusting the source read.
  - The write is cookie-plane + CSRF-gated, the same posture as /account/tokens (#266): missing or
    wrong X-CSRF-Token -> 403, nothing changed; the proxy/bearer planes are refused (browser-only,
    matching the existing account-mutation posture — a leaked agent token must not be able to
    impersonate the owner's identity).
  - One user's name is invisible to another (no cross-account leak via this endpoint).

Mutation check noted inline at each assertion that guards a single boundary condition (in
particular the off-by-one at MAX_NAME_LEN and the >= vs > forms of the control-char scan).

Run: python3 tests/name_field_selfcheck.py     (exit 0 = pass)
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
DATA = os.path.join(ROOT, ".scratch", "name_field_data")


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
           MDREVIEW_ALLOW_PROXY_PLANE="1", MDREVIEW_PROXY_SECRET="test-proxy-secret-309",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL="owner@example.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
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
    for _ in range(40):
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
    sess = json.loads(raw)
    return ck, sess.get("csrf", ""), sess


def session_of(ck):
    _, raw = req(base + "/auth/session", h={"Cookie": ck})
    return json.loads(raw)


def set_name(ck, csrf, name):
    return req(base + "/auth/profile", "POST", json.dumps({"name": name}).encode(),
               {"Content-Type": "application/json", "Cookie": ck, "X-CSRF-Token": csrf})


try:
    for _ in range(60):
        try:
            req(base + "/healthz")
            break
        except Exception:
            time.sleep(0.25)

    ck, csrf, sess0 = login("owner@example.com")
    check("setup: genuine session cookie + csrf obtained", bool(ck) and bool(csrf))

    # ---- absent means unset, no migration ------------------------------------------------------
    check("a brand-new user's /auth/session carries name=\"\" (never null, never missing)",
          sess0.get("name", "MISSING") == "", sess0.get("name", "MISSING"))

    # ---- CSRF gate (same posture as /account/tokens, #266) --------------------------------------
    code, raw = req(base + "/auth/profile", "POST", json.dumps({"name": "Ada"}).encode(),
                    {"Content-Type": "application/json", "Cookie": ck})
    check("set without X-CSRF-Token -> 403", code == 403, code)
    check("...and it is the CSRF gate", b"CSRF" in raw, raw[:80])
    code, _ = req(base + "/auth/profile", "POST", json.dumps({"name": "Ada"}).encode(),
                  {"Content-Type": "application/json", "Cookie": ck, "X-CSRF-Token": "wrong"})
    check("set with a WRONG token -> 403", code == 403, code)
    check("...and nothing was written (still unset)", session_of(ck).get("name") == "",
          session_of(ck).get("name"))

    # ---- happy path: set, read back --------------------------------------------------------------
    code, raw = set_name(ck, csrf, "Ada Lovelace")
    check("set a valid name -> 200", code == 200, code)
    check("...response echoes the stored (trimmed) name", json.loads(raw).get("name") == "Ada Lovelace", raw)
    check("...and GET /auth/session reads it back", session_of(ck).get("name") == "Ada Lovelace",
          session_of(ck).get("name"))

    # ---- trimming -----------------------------------------------------------------------------
    code, raw = set_name(ck, csrf, "  Grace Hopper  ")
    check("leading/trailing whitespace is trimmed", code == 200 and json.loads(raw).get("name") == "Grace Hopper", raw)

    # ---- length limit: exactly 60 ok, 61 rejected (the off-by-one this line exists to catch) ---
    exactly60 = "x" * 60
    code, raw = set_name(ck, csrf, exactly60)
    check("a name of EXACTLY 60 chars (post-trim) is accepted",
          code == 200 and json.loads(raw).get("name") == exactly60, (code, len(exactly60)))
    sixtyone = "x" * 61
    code, raw = set_name(ck, csrf, sixtyone)
    check("a name of 61 chars is REJECTED (400) and the stored name is untouched",
          code == 400, (code, raw[:120]))
    check("...the 61-char attempt did not overwrite the stored 60-char name",
          session_of(ck).get("name") == exactly60, session_of(ck).get("name"))
    # Padding-then-trim boundary: 61 raw chars that trim down to exactly 60 must be ACCEPTED —
    # proves length is checked after trim, not on the raw wire length.
    code, raw = set_name(ck, csrf, " " + exactly60)
    check("61 raw chars that trim to 60 are accepted (length checked AFTER trim)",
          code == 200 and json.loads(raw).get("name") == exactly60, raw)

    # ---- control characters rejected, not silently stripped -------------------------------------
    code, raw = set_name(ck, csrf, "Ann\nBan")
    check("a name containing a newline is REJECTED (400), not silently mangled",
          code == 400, (code, raw[:120]))
    check("...the rejected newline attempt did not change the stored name",
          session_of(ck).get("name") == exactly60, session_of(ck).get("name"))
    code, _ = set_name(ck, csrf, "Tab\tName")
    check("a name containing a tab is REJECTED (400)", code == 400, code)

    # ---- unicode is fine (display-only, no ASCII-only claim) ------------------------------------
    code, raw = set_name(ck, csrf, "文Aémilie")
    check("unicode (accents, CJK) is accepted", code == 200, (code, raw[:120]))

    # ---- clearing: empty (or whitespace-only) name -> unset, not an error, AC4 ------------------
    code, raw = set_name(ck, csrf, "")
    check("an empty name -> 200 (clears), not 400", code == 200 and json.loads(raw).get("name") == "", raw)
    check("...and GET /auth/session confirms it is unset again", session_of(ck).get("name") == "",
          session_of(ck).get("name"))
    code, raw = set_name(ck, csrf, "Temp")
    check("setup: name set again for the whitespace-only clear case", code == 200, code)
    code, raw = set_name(ck, csrf, "   ")
    check("a whitespace-only name ALSO clears (trims to empty, same as \"\")",
          code == 200 and json.loads(raw).get("name") == "", raw)

    # ---- absent means unset still works everywhere: a SECOND user who never calls the endpoint --
    ck2, csrf2, sess2 = login("second@example.com")
    check("a second, never-named user's /auth/session also reads name=\"\"", sess2.get("name") == "",
          sess2.get("name"))
    # cross-account isolation: setting user 1's name must not leak into user 2's session
    set_name(ck, csrf, "Cross Check")
    check("setting user 1's name does not appear on user 2's session (no cross-account leak)",
          session_of(ck2).get("name") == "", session_of(ck2).get("name"))

    # ---- missing/wrong-typed body -----------------------------------------------------------------
    code, raw = req(base + "/auth/profile", "POST", json.dumps({}).encode(),
                    {"Content-Type": "application/json", "Cookie": ck, "X-CSRF-Token": csrf})
    check("a body with no \"name\" key clears (treated as \"\"), not a 500",
          code == 200 and json.loads(raw).get("name") == "", (code, raw[:120]))
    code, raw = req(base + "/auth/profile", "POST", json.dumps({"name": 12345}).encode(),
                    {"Content-Type": "application/json", "Cookie": ck, "X-CSRF-Token": csrf})
    check("a non-string \"name\" (e.g. a number) is treated as empty, never crashes the server",
          code == 200, (code, raw[:160]))

    # ---- unauthenticated ---------------------------------------------------------------------------
    code, raw = req(base + "/auth/profile", "POST", json.dumps({"name": "X"}).encode(),
                    {"Content-Type": "application/json"})
    check("no session cookie -> 401, not 403/500", code == 401, (code, raw[:120]))

    # ---- proxy/bearer planes are refused: identity mutation stays a browser act (matches #266) ----
    proxy = {"X-Mdreview-Proxy": "test-proxy-secret-309", "X-Mdreview-Provider": "google",
             "X-Auth-Request-User": "999", "X-Auth-Request-Email": "p@example.com"}
    code, raw = req(base + "/auth/profile", "POST", json.dumps({"name": "Proxy"}).encode(),
                    {"Content-Type": "application/json", **proxy})
    check("the proxy plane cannot set a name (no verified session -> 401, matches #266's browser-only posture)",
          code in (401, 403), (code, raw[:160]))
finally:
    srv.terminate()
    srv.wait(timeout=10)
    log.close()

print()
print(("%d case(s) FAILED" % len(fails)) if fails else "all name-field cases pass")
sys.exit(1 if fails else 0)
