#!/usr/bin/env python3
"""comment_gate_selfcheck.py — /status.can_comment agrees with POST /comments (#320).

WHAT THIS GUARDS. A reader who may not comment was still offered the comment composer, because the
viewer had no way to ask. It posted, the custody policy correctly refused with 404, and the viewer
reported that as "Could not save comment" — which reads as a server fault, not as "you have
view-only access". #320 adds can_comment to /status so the viewer can gate its author surfaces.

The contract under test is the AGREEMENT, not the flag: for every principal shape, can_comment must
predict the POST outcome exactly. A flag that drifts from the gate is worse than no flag, because
the viewer would then hide the composer from someone allowed to comment, or offer it to someone who
is not — the bug this fixes, back again from the other side.

Principals covered: owner, named share right=comment, named share right=view, public-link reader
who is signed in but holds no named grant, and anonymous.

Run: python3 tests/comment_gate_selfcheck.py     (exit 0 = pass)
"""
import json, os, re, shutil, socket, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, ".scratch", "comment_gate_data")
FAILED = [0]


def ok(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILED[0] += 1


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    # Empty ProxyHandler: an enabled-but-dead system proxy otherwise swallows loopback requests that
    # curl would serve fine.
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="0", MDREVIEW_PROXY_SECRET="inert",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL="owner@e.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://l.test",
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
           PYTHONPATH=os.path.join(ROOT, "src"))
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
    tok = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)",
                     open(os.path.join(DATA, "s.log")).read())[-1]

    class NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None

    op = urllib.request.build_opener(NR, urllib.request.ProxyHandler({}))
    rq = urllib.request.Request(base + "/auth/redeem", data=("token=" + tok).encode(),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                method="POST")
    try:
        rs = op.open(rq, timeout=15)
    except urllib.error.HTTPError as e:
        rs = e
    ck = rs.headers.get("Set-Cookie", "").split(";")[0]
    _, raw = req(base + "/auth/session", h={"Cookie": ck})
    return {"Content-Type": "application/json", "Cookie": ck,
            "X-CSRF-Token": json.loads(raw).get("csrf", "")}


try:
    OH = login("owner@e.com")
    GH = login("grantee@e.com")
    ANON = {"Content-Type": "application/json"}

    def mkdoc(title):
        _, raw = req(base + "/api/reviews", "POST",
                     json.dumps({"title": title, "markdown": "# t\n\npara\n"}).encode(), OH)
        return json.loads(raw)["id"]

    def flag(rid, hdr):
        st, raw = req(base + "/api/reviews/%s/status" % rid, h=hdr)
        if st != 200:
            return None
        return json.loads(raw).get("can_comment")

    def posts(rid, hdr):
        st, _ = req(base + "/api/reviews/%s/comments" % rid, "POST",
                    json.dumps({"anchor": {"block_num": "1"}, "text": "note"}).encode(), hdr)
        return st

    # rid, header, label, expected can_comment
    cases = []

    a = mkdoc("comment share")
    req(base + "/api/reviews/%s/shares" % a, "POST",
        json.dumps({"email": "grantee@e.com", "right": "comment"}).encode(), OH)
    cases.append((a, OH, "owner on own document", True))
    cases.append((a, GH, "named share right=comment", True))

    b = mkdoc("view share")
    req(base + "/api/reviews/%s/shares" % b, "POST",
        json.dumps({"email": "grantee@e.com", "right": "view"}).encode(), OH)
    cases.append((b, GH, "named share right=view", False))

    c = mkdoc("public only")
    req(base + "/api/reviews/%s/public" % c, "POST", None,
        {"Cookie": OH["Cookie"], "X-CSRF-Token": OH["X-CSRF-Token"]})
    cases.append((c, GH, "public link, signed in, no grant", False))

    print("1. /status.can_comment carries the right value")
    for rid, hdr, label, want in cases:
        ok("%-34s -> can_comment=%s" % (label, want), flag(rid, hdr) is want)

    print("2. it AGREES with what POST /comments actually does (the invariant)")
    for rid, hdr, label, want in cases:
        st = posts(rid, hdr)
        allowed = (st == 201)
        ok("%-34s flag=%s post=%s" % (label, flag(rid, hdr), st), allowed is want)

    print("3. anonymous is refused and told to sign in, not told view-only")
    # 401 (not 404) is what the viewer keys "Sign in to comment" off; a 404 here would send an
    # anonymous visitor the wrong message entirely.
    ok("anonymous POST -> 401", posts(c, ANON) == 401)

    print("4. a refused post keeps what the human typed (#334, carried forward by #286)")
    # #286 changed the MECHANISM (composer now closes immediately and posts optimistically; a
    # refused post's text lives in a retryable in-thread card, not in a composer the human has to
    # notice is still open) while keeping the GUARANTEE #334 introduced: a refusal never loses
    # what was typed. Assert the contract that now holds, not the old close-timing shape.
    for name in ("viewer.html", "latex-viewer.html"):
        src = open(os.path.join(ROOT, "web", "app", name)).read()
        ok("%-18s a refused post keeps the text in a retryable card" % name,
           "Not posted — your text is kept." in src
           and re.search(r"data-act=.?retry", src) is not None
           and re.search(r"data-act=.?discard", src) is not None)

    print("5. the viewers gate their author surfaces on the flag")
    for name in ("viewer.html", "latex-viewer.html"):
        src = open(os.path.join(ROOT, "web", "app", name)).read()
        ok("%-18s reads can_comment from /status" % name, "can_comment!==false" in src)
        ok("%-18s openPop refuses without it" % name,
           re.search(r"function openPop\([^)]*\)\{[^}]*?if\(!CAN_COMMENT\)return;", src, re.S) is not None)
        ok("%-18s 404 names view-only access" % name,
           "view-only access" in src and "r.status===404" in src)
        ok("%-18s hides author surfaces in CSS" % name, "body.viewonly .greply" in src)
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except Exception:
        srv.kill()

print("\n" + ("%d case(s) failed" % FAILED[0] if FAILED[0] else "all comment-gate cases pass"))
sys.exit(1 if FAILED[0] else 0)
