#!/usr/bin/env python3
"""Phase 1 auth core verification. Starts a throwaway REQUIRE_AUTH instance and exercises both
planes (cookie via simulated nginx headers, token via Bearer), isolation, spoofing, and the
token-mint boundary. Run: python3 .scratch/ph1_auth_test.py"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PORT = 8199
BASE = "http://127.0.0.1:%d" % PORT
SECRET = "test-proxy-secret-xyz"
PEPPER = "test-token-pepper-abc"
DATA = os.path.join(REPO, ".scratch", "auth_smoke_data")
fails = []
def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: fails.append(label)

def req(method, path, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    if data is not None: r.add_header("Content-Type", "application/json")
    # bypass any system proxy for loopback
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=10) as resp:
            return resp.code, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def cookie(sub, email):
    return {"X-Mdreview-Proxy": SECRET, "X-Mdreview-Provider": "google",
            "X-Auth-Request-User": sub, "X-Auth-Request-Email": email}

# --- Test A: config fails closed when REQUIRE_AUTH on but secrets unset ---
env_noboot = {**os.environ, "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_PROXY_SECRET": "",
              "MDREVIEW_TOKEN_PEPPER": "", "MDREVIEW_DATA": DATA, "PORT": str(PORT+1),
              "PYTHONPATH": os.path.join(REPO, "src")}
p = subprocess.run([sys.executable, "-m", "mdreview"], env=env_noboot,
                   capture_output=True, text=True, timeout=15)
check("A. refuses to boot with REQUIRE_AUTH on and secrets unset (fail closed)",
      p.returncode != 0 and "PROXY_SECRET" in (p.stderr + p.stdout))

# --- start the real instance ---
os.makedirs(DATA, exist_ok=True)
env = {**os.environ, "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_PROXY_SECRET": SECRET,
       "MDREVIEW_TOKEN_PEPPER": PEPPER, "MDREVIEW_DATA": DATA, "PORT": str(PORT),
       "PYTHONPATH": os.path.join(REPO, "src")}
srv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            if req("GET", "/healthz")[0] == 200: break
        except Exception: pass
        time.sleep(0.1)

    check("B. /healthz open (no auth)", req("GET", "/healthz")[0] == 200)
    check("C. tokenless+cookieless GET /api/reviews -> 401", req("GET", "/api/reviews")[0] == 401)
    check("D. forged identity header WITHOUT proxy secret -> 401 (no trust)",
          req("GET", "/api/reviews", {"X-Mdreview-Provider": "google", "X-Auth-Request-User": "evil"})[0] == 401)

    # cookie plane user A creates a review
    ca = cookie("111", "a@example.com")
    code, out = req("POST", "/api/reviews", ca, {"markdown": "# A doc", "title": "A"})
    rid_a = json.loads(out).get("id") if code == 201 else None
    check("E. cookie-plane create (201, owner stamped)", code == 201 and rid_a)
    code, out = req("GET", "/api/reviews", ca)
    check("F. A sees own review in list", code == 200 and any(r["id"] == rid_a for r in json.loads(out)["reviews"]))

    # A mints a token (cookie plane), agent uses it
    code, out = req("POST", "/account/tokens", ca, {"label": "laptop"})
    tok = json.loads(out).get("token") if code == 201 else None
    check("G. cookie-plane token mint (mdr_...)", code == 201 and (tok or "").startswith("mdr_"))
    bearer = {"Authorization": "Bearer " + (tok or "x")}
    code, out = req("POST", "/api/reviews", bearer, {"markdown": "# agent doc", "title": "agent"})
    rid_ag = json.loads(out).get("id") if code == 201 else None
    check("H. agent (Bearer) create -> 201, owned by A", code == 201 and rid_ag)
    code, out = req("GET", "/api/reviews", bearer)
    check("I. agent token sees A's reviews (same owner)", code == 200 and any(r["id"] == rid_ag for r in json.loads(out)["reviews"]))

    # isolation: user B
    cb = cookie("222", "b@example.com")
    code, out = req("GET", "/api/reviews", cb)
    check("J. B's list does NOT include A's reviews (isolation)",
          code == 200 and not any(r["id"] in (rid_a, rid_ag) for r in json.loads(out)["reviews"]))
    check("K. B GET A's review -> 404 (not 403, no existence leak)", req("GET", "/api/reviews/%s" % rid_a, cb)[0] == 404)
    check("L. B DELETE A's review -> 404", req("DELETE", "/api/reviews/%s" % rid_a, cb)[0] == 404)
    check("M. B GET A's source -> 404", req("GET", "/api/reviews/%s/source" % rid_a, cb)[0] == 404)

    # token plane cannot manage tokens
    check("N. token plane POST /account/tokens -> 403 (mint is cookie-only)",
          req("POST", "/account/tokens", bearer, {})[0] == 403)
    # A can revoke own token; then it stops working
    tid = json.loads(req("GET", "/account/tokens", ca)[1])["tokens"][0]["tok_id"]
    check("O. A revokes own token -> 200", req("DELETE", "/account/tokens/%s" % tid, ca)[0] == 200)
    check("P. revoked token now 401", req("GET", "/api/reviews", bearer)[0] == 401)
finally:
    srv.terminate()
    try: srv.wait(timeout=5)
    except Exception: srv.kill()

print("\n" + ("PASS: all %d checks" % 16 if not fails else "FAILED: " + "; ".join(fails)))
sys.exit(1 if fails else 0)
