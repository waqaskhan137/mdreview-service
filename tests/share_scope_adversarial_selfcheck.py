#!/usr/bin/env python3
"""share_scope_adversarial_selfcheck.py — #284 from the attacker's side.

DELIBERATELY SEPARATE from share_scope_selfcheck.py. That one was written alongside the feature;
this one was written independently against the same contract, because an implementation and its
own test share blind spots. Both must pass. The questions:

  1. can grantee B revoke grantee A's row?           (cross-grantee tamper)
  2. can a stranger with no grant see the doc in ?scope=shared?
  3. can a stranger revoke anything on it?
  4. does ?scope=shared leak a doc that is only PUBLIC (no named grant)?
  5. does the inbound row leak fields beyond the whitelist?
  6. does the owner's full email escape anywhere in the grantee's payload?
"""
import json, os, re, shutil, socket, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WT = ROOT
DATA = os.path.join(ROOT, ".scratch", "share_adversarial_data")
FAILED = [0]


def ok(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else "  (%s)" % detail))
    if not cond:
        FAILED[0] += 1


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


shutil.rmtree(DATA, ignore_errors=True); os.makedirs(DATA)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="0", MDREVIEW_PROXY_SECRET="inert",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL="owner@e.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://l.test",
           MDREVIEW_WEB_DIR=os.path.join(WT, "web", "app"),
           PYTHONPATH=os.path.join(WT, "src"))
log = open(os.path.join(DATA, "s.log"), "w")
srv = subprocess.Popen([sys.executable, "-m", "mdreview.hosted"], env=env, stdout=log, stderr=log)
base = "http://127.0.0.1:%d" % port
for _ in range(80):
    try:
        req(base + "/healthz"); break
    except Exception:
        time.sleep(.25)


def login(email):
    req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
        {"Content-Type": "application/json"})
    time.sleep(.3)
    tok = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", open(os.path.join(DATA, "s.log")).read())[-1]

    class NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None

    op = urllib.request.build_opener(NR, urllib.request.ProxyHandler({}))
    rq = urllib.request.Request(base + "/auth/redeem", data=("token=" + tok).encode(),
                                headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        rs = op.open(rq, timeout=15)
    except urllib.error.HTTPError as e:
        rs = e
    ck = rs.headers.get("Set-Cookie", "").split(";")[0]
    _, raw = req(base + "/auth/session", h={"Cookie": ck})
    j = json.loads(raw)
    return {"Content-Type": "application/json", "Cookie": ck, "X-CSRF-Token": j.get("csrf", "")}, j


try:
    OWNER, ow = login("owner@e.com")
    A, aj = login("grantee-a@e.com")
    B, bj = login("grantee-b@e.com")
    STRANGER, sj = login("stranger@e.com")

    _, raw = req(base + "/api/reviews", "POST",
                 json.dumps({"title": "shared doc", "markdown": "# x"}).encode(), OWNER)
    rid = json.loads(raw)["id"]
    _, raw = req(base + "/api/reviews", "POST",
                 json.dumps({"title": "public only", "markdown": "# p"}).encode(), OWNER)
    prid = json.loads(raw)["id"]
    req(base + "/api/reviews/%s/public" % prid, "POST", None,
        {"Cookie": OWNER["Cookie"], "X-CSRF-Token": OWNER["X-CSRF-Token"]})

    for who, hdr in (("grantee-a@e.com", A), ("grantee-b@e.com", B)):
        st, _ = req(base + "/api/reviews/%s/shares" % rid, "POST",
                    json.dumps({"email": who, "right": "comment"}).encode(), OWNER)
    print("setup: rid shared to A and B; prid is public-only\n")

    def shared_ids(hdr):
        st, raw = req(base + "/api/reviews?scope=shared", h=hdr)
        try:
            return st, [r.get("id") for r in json.loads(raw).get("reviews", [])], json.loads(raw)
        except Exception:
            return st, [], {}

    print("1. cross-grantee tamper — B tries to revoke A's row")
    a_uid = aj.get("uid") or aj.get("sub") or ""
    st, _ = req(base + "/api/reviews/%s/shares?subject=%s" % (rid, urllib.request.quote("user:" + a_uid)),
                "DELETE", None, {"Cookie": B["Cookie"], "X-CSRF-Token": B["X-CSRF-Token"]})
    ok("B revoking A's row is refused", st in (403, 404), "got %s" % st)
    st, ids, _ = shared_ids(A)
    ok("A still sees the document afterwards", rid in ids, "A sees %s" % ids)

    print("\n2-3. a stranger with no grant")
    st, ids, _ = shared_ids(STRANGER)
    ok("stranger's scope=shared is empty", ids == [], "got %s" % ids)
    st, _ = req(base + "/api/reviews/%s/shares?subject=%s" % (rid, urllib.request.quote("user:" + a_uid)),
                "DELETE", None, {"Cookie": STRANGER["Cookie"], "X-CSRF-Token": STRANGER["X-CSRF-Token"]})
    ok("stranger cannot revoke anything (404, not probeable)", st == 404, "got %s" % st)

    print("\n4. a PUBLIC-only document must never appear in scope=shared")
    st, ids, _ = shared_ids(A)
    ok("public-only doc absent from A's inbound list", prid not in ids, "A sees %s" % ids)

    print("\n5-6. the inbound row's shape and the owner's address")
    st, ids, payload = shared_ids(A)
    row = next((r for r in payload.get("reviews", []) if r.get("id") == rid), {})
    # The groom's ACTUAL whitelist, quoted from groom-284.md rather than guessed. My first run
    # flagged feedback_updated as extra, which was my expectation being wrong, not the code.
    allowed = {"id", "title", "kind", "created", "source_updated", "feedback_updated",
               "right", "from_email"}
    extra = set(row) - allowed
    ok("no fields beyond the whitelist", not extra, "extra=%s" % sorted(extra))
    # The four the groom forbids BY NAME. My first allowed-set wrongly permitted `project`,
    # so this asserts them explicitly instead of relying on the set difference.
    for forbidden in ("project", "source_path", "session"):
        ok("row never leaks %r" % forbidden, forbidden not in row, "present=%r" % row.get(forbidden))
    ok("row never leaks the owner uid",
       not any(isinstance(v, str) and v.startswith("user:") for v in row.values()),
       "row=%s" % row)
    blob = json.dumps(payload)
    ok("owner's FULL address never appears", "owner@e.com" not in blob,
       "from_email=%r" % row.get("from_email"))
    ok("from_email is the local-part only", row.get("from_email") in ("owner", None, ""),
       "got %r" % row.get("from_email"))

    print("\n7. self-revoke really is allowed for one's own row")
    b_uid = bj.get("uid") or bj.get("sub") or ""
    st, _ = req(base + "/api/reviews/%s/shares?subject=%s" % (rid, urllib.request.quote("user:" + b_uid)),
                "DELETE", None, {"Cookie": B["Cookie"], "X-CSRF-Token": B["X-CSRF-Token"]})
    ok("B may revoke B's own row", st == 200, "got %s" % st)
    st, ids, _ = shared_ids(B)
    ok("B no longer sees it", rid not in ids, "B sees %s" % ids)
    st, ids, _ = shared_ids(A)
    ok("A is UNAFFECTED by B's self-revoke", rid in ids, "A sees %s" % ids)
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except Exception:
        srv.kill()

print("\n" + ("%d adversarial case(s) FAILED" % FAILED[0] if FAILED[0] else "all adversarial cases pass"))
sys.exit(1 if FAILED[0] else 0)
