#!/usr/bin/env python3
"""review_meta_identity_selfcheck.py — #368 follow-up: GET /api/reviews/{rid} and .../feedback
must not disclose the document owner's raw uid to a reader who is not entitled to it, verified
as REAL API behaviour against a running hosted instance (genuine magic-link logins, no fixture).

THE DEFECT (reproduced live, prod, before this fix).
  curl https://app.mdreview.space/api/reviews/{rid}, with NO cookie and NO token, against a
  PUBLIC review, returned `"owner": "google:100706495352040931339"` in cleartext. #368's fix to
  the comments payload did not touch this: ReviewService.summary()/feedback() both return
  dict(meta.json) WHOLESALE, and `owner` sits in meta.json unconditionally, so the SAME identity
  the comments fix removed was still one route over.

THE FIX UNDER TEST (H._visible_meta, the SAME entitlement predicate _visible_comments uses).
  `owner` is visible only when the caller is the document owner (AccessPolicy.can_write --
  owner-only on every tier); everyone else gets None there. Every other meta key was audited:
  source_updated_by is #289's role literal ("reviewer" or absent), never a uid; agent_status.
  owner/message (handoff.py) are caller-supplied free text (an agent's own opaque session id,
  MCP's own words for it), never server-derived from login, the same "a chosen label is not the
  leak" reasoning #309's display name established -- so this check also pins that agent_status
  is NOT redacted, to catch a future "let's be thorough" mutation that over-redacts it.

WHO SEES WHAT.
  - owner:    the real `owner` uid on both GET /api/reviews/{rid} and .../feedback (their own
              document -- entitled).
  - a named grantee (view-only, the same non-owner case that matters for the comments fix):
              `owner` is None on both routes, on a review they can still fully READ.
  - anonymous (no cookie, no token), the actual reproduction: `owner` is None, AND the raw
              response body never contains "google:"/"email:" or the owner's literal test uid,
              on EITHER route.
  Also confirms (not asserts to fail on drift, just documents): GET /api/reviews (no scope) and
  ?scope=shared were audited and are unaffected -- see the #368 follow-up commit message for why
  -- so this file does not re-test them; share_scope_selfcheck.py / share_scope_adversarial_
  selfcheck.py already pin the whitelist shape of ?scope=shared.

Run: python3 tests/review_meta_identity_selfcheck.py     (exit 0 = pass)
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
DATA = os.path.join(ROOT, ".scratch", "review_meta_identity_data")
OWNER_EMAIL = "owner368b@example.com"
GRANTEE_EMAIL = "grantee368b@example.com"
OWNER_UID = "email:" + OWNER_EMAIL

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


def free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    try:
        with OPENER.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA, exist_ok=True)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="1", MDREVIEW_PROXY_SECRET="test-proxy-secret-368b",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL=OWNER_EMAIL, MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://l.test",
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
           PYTHONPATH=os.path.join(ROOT, "src"))
log_path = os.path.join(DATA, "s.log")
log = open(log_path, "w")
srv = subprocess.Popen([sys.executable, "-m", "mdreview.hosted"], env=env, stdout=log, stderr=log)
base = "http://127.0.0.1:%d" % port


def login(email):
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
    return ck, sess.get("csrf", "")


def hdr(ck, csrf=None):
    h = {"Content-Type": "application/json", "Cookie": ck}
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


try:
    for _ in range(60):
        try:
            req(base + "/healthz")
            break
        except Exception:
            time.sleep(0.25)

    ock, ocsrf = login(OWNER_EMAIL)
    gck, gcsrf = login(GRANTEE_EMAIL)
    check("setup: two genuine sessions obtained", bool(ock) and bool(gck))

    _, raw = req(base + "/api/reviews", "POST",
                 json.dumps({"title": "meta identity probe", "markdown": "# x\n\nbody"}).encode(),
                 hdr(ock, ocsrf))
    rid = json.loads(raw)["id"]
    check("setup: review created", bool(rid), raw[:200])

    code, _ = req(base + f"/api/reviews/{rid}/shares", "POST",
                  json.dumps({"email": GRANTEE_EMAIL, "right": "view"}).encode(), hdr(ock, ocsrf))
    check("setup: view-only grantee invited", code == 201, code)
    code, _ = req(base + f"/api/reviews/{rid}/public", "POST", b"{}", hdr(ock, ocsrf))
    check("setup: review made public", code == 200, code)

    # ---- owner: entitled, full attribution on both routes -----------------------------------------
    print("\n1. the owner (entitled) sees the real owner uid on both routes")
    code, raw = req(base + f"/api/reviews/{rid}", h={"Cookie": ock})
    meta = json.loads(raw)
    check("owner GET /api/reviews/{rid} -> 200", code == 200, code)
    check("...owner field == the real uid", meta.get("owner") == OWNER_UID, meta.get("owner"))
    code, raw = req(base + f"/api/reviews/{rid}/feedback", h={"Cookie": ock})
    fb = json.loads(raw)
    check("owner GET .../feedback -> 200", code == 200, code)
    check("...owner field == the real uid", fb.get("owner") == OWNER_UID, fb.get("owner"))

    # ---- named (view-only) grantee: can still READ, but owner is None -----------------------------
    print("2. a named view-only grantee can read the document, but owner is None")
    code, raw = req(base + f"/api/reviews/{rid}", h={"Cookie": gck})
    gmeta = json.loads(raw)
    check("grantee GET /api/reviews/{rid} -> 200 (they CAN read)", code == 200, code)
    check("...title/markdown-adjacent fields still present (not a blanket lockout)",
          gmeta.get("title") == "meta identity probe", gmeta.get("title"))
    check("...owner field is None", gmeta.get("owner") is None, gmeta.get("owner"))
    code, raw = req(base + f"/api/reviews/{rid}/feedback", h={"Cookie": gck})
    gfb = json.loads(raw)
    check("grantee GET .../feedback -> 200", code == 200, code)
    check("...owner field is None", gfb.get("owner") is None, gfb.get("owner"))

    # ---- THE HEADLINE ASSERTION: anonymous, no cookie, no token ------------------------------------
    print("3. anonymous (no cookie, no token) — the actual reproduction")
    code, raw = req(base + f"/api/reviews/{rid}")
    body_text = raw.decode()
    ameta = json.loads(raw)
    check("anonymous GET /api/reviews/{rid} on a public review -> 200 (D3: public is readable)",
          code == 200, code)
    check("...owner field is None", ameta.get("owner") is None, ameta.get("owner"))
    check("...raw response body contains no \"email:\"/\"google:\" tagged uid",
          "email:" not in body_text and "google:" not in body_text, body_text[:200])
    check("...raw response body does not contain the owner's literal test email",
          OWNER_EMAIL not in body_text, body_text[:200])

    code, raw = req(base + f"/api/reviews/{rid}/feedback")
    fb_body_text = raw.decode()
    afb = json.loads(raw)
    check("anonymous GET .../feedback -> 200", code == 200, code)
    check("...owner field is None", afb.get("owner") is None, afb.get("owner"))
    check("...raw response body contains no \"email:\"/\"google:\" tagged uid",
          "email:" not in fb_body_text and "google:" not in fb_body_text, fb_body_text[:200])
    check("...raw response body does not contain the owner's literal test email",
          OWNER_EMAIL not in fb_body_text, fb_body_text[:200])

    # ---- agent_status is DELIBERATELY untouched (self-reported, not a second leak) ----------------
    print("4. agent_status stays as-is — self-reported, not server-derived, not redacted")
    code, _ = req(base + f"/api/reviews/{rid}/handoff", "POST",
                  json.dumps({"state": "working", "owner": "agent-session-xyz",
                             "message": "on it"}).encode(), hdr(ock, ocsrf))
    check("setup: handoff lease claimed", code == 200, code)
    code, raw = req(base + f"/api/reviews/{rid}")
    astatus = json.loads(raw).get("agent_status") or {}
    check("anonymous still reads agent_status.owner verbatim (caller-chosen label, not identity)",
          astatus.get("owner") == "agent-session-xyz", json.loads(raw).get("agent_status"))

    # ---- the plain (unscoped) list route and ?scope=shared: confirm, don't just assume ------------
    print("5. GET /api/reviews (unscoped) and ?scope=shared — confirmed already safe, unchanged")
    code, raw = req(base + "/api/reviews")
    check("anonymous GET /api/reviews (unscoped list) -> 401 (never reaches list_reviews)",
          code == 401, code)
    code, raw = req(base + "/api/reviews", h={"Cookie": gck})
    grows = {r["id"]: r for r in json.loads(raw).get("reviews", [])}
    check("grantee's OWNED list never contains the owner's document (they don't own it)",
          rid not in grows, list(grows.keys()))
    code, raw = req(base + "/api/reviews?scope=shared", h={"Cookie": gck})
    srows = {r["id"]: r for r in json.loads(raw).get("reviews", [])}
    check("grantee's scope=shared row for this doc carries no 'owner' key (pre-existing whitelist)",
          rid in srows and "owner" not in srows[rid], srows.get(rid))

finally:
    srv.terminate()
    srv.wait(timeout=10)
    log.close()

print()
print(("%d case(s) FAILED" % len(fails)) if fails else "all #368 review-meta-identity cases pass")
sys.exit(1 if fails else 0)
