#!/usr/bin/env python3
"""share_scope_selfcheck.py — #284: owned-row share badges + the inbound `scope=shared` list.

WHAT THIS GUARDS. Two additive, hosted-only read paths added to GET /api/reviews:

  Part 1 (badges): an owned row gains `share_public` / `share_count` ONLY when non-default (the
  kind/template precedent) — so U (unshared) must carry NEITHER key, never a falsy 0/None.

  Part 2 (`?scope=shared`): a caller's inbound named shares, via a WHITELIST row — never the raw
  summary(), never `project`/`source_path`/`session`/owner uid. Membership is EXACTLY a named grant
  to the caller's own uid: a public-only document (P below) must NEVER surface here (that is the
  firehose custody.CustodyPolicy.scope_list's docstring forbids — #284 D1), a third account with no
  grant gets `{"reviews":[]}`, and the scope widens LIST only (can_write/can_delete stay owner-only,
  checked directly against the shared doc).

  D2 (self-revoke): a grantee may remove ONLY their own named-share row via the pre-existing DELETE
  .../shares?email= convenience. Authorization is exact-string ("user:" + caller uid) — a second
  grantee's attempt to revoke via a DIFFERENT grantee's email must be refused (404) and leave that
  row intact; a genuine self-revoke both removes the row AND revokes the underlying read access.

  D3: the whitelist's `from_email` carries the owner's LOCAL-PART ONLY — computed server-side, so
  the full address never reaches the grantee's browser at all (not merely hidden by the UI).

Local tier (REQUIRE_AUTH off) is asserted separately: `share_public`/`share_count` must never
appear on ANY row (the two keys are gated behind getattr(app,"shares",None), which is None on that
tier by construction), and the row's key set must match a fixed baseline exactly — the same
additive-default-safe posture kind/template/resolved_by_human already established.

Run: python3 tests/share_scope_selfcheck.py     (exit 0 = pass)
"""
import json, os, re, shutil, socket, subprocess, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, ".scratch", "share_scope_data")
FAILED = [0]


def ok(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label + (("  (" + str(detail) + ")") if (not cond and detail) else ""))
    if not cond:
        FAILED[0] += 1


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    # Empty ProxyHandler: an enabled-but-dead system proxy otherwise swallows loopback requests that
    # curl would serve fine (a known trap on this machine).
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with op.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ============================================================== hosted instance, multi-user =====
shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="0", MDREVIEW_PROXY_SECRET="inert",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL="a@example.com", MDREVIEW_ALLOW_STUB_EMAIL="1",
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
    AH = login("a@example.com")     # A: owner of every doc below
    BH = login("b@example.com")     # B: named grantee (comment) on S
    DH = login("d@example.com")     # D: named grantee (view) on S; also the self-revoke actor
    CH = login("c@example.com")     # C: no grant anywhere
    ANON = {"Content-Type": "application/json"}

    def mkdoc(title):
        _, raw = req(base + "/api/reviews", "POST",
                     json.dumps({"title": title, "markdown": "# t\n\npara\n"}).encode(), AH)
        return json.loads(raw)["id"]

    def gr(headers):
        _, raw = req(base + "/api/reviews", h=headers)
        return {r["id"]: r for r in json.loads(raw).get("reviews", [])}

    def gr_shared(headers):
        _, raw = req(base + "/api/reviews?scope=shared", h=headers)
        return json.loads(raw).get("reviews", [])

    P = mkdoc("public only")
    req(base + f"/api/reviews/{P}/public", "POST", None, AH)

    S = mkdoc("shared to two")
    req(base + f"/api/reviews/{S}/shares", "POST",
        json.dumps({"email": "b@example.com", "right": "comment"}).encode(), AH)
    req(base + f"/api/reviews/{S}/shares", "POST",
        json.dumps({"email": "d@example.com", "right": "view"}).encode(), AH)

    U = mkdoc("unshared")

    M = mkdoc("public AND named")     # both badges at once on the SAME row
    req(base + f"/api/reviews/{M}/public", "POST", None, AH)
    req(base + f"/api/reviews/{M}/shares", "POST",
        json.dumps({"email": "b@example.com", "right": "view"}).encode(), AH)

    # ---- 1. Part 1: owned-row badges, additive-default-safe (key ABSENCE, not falsy) -----------
    print("1. GET /api/reviews as the owner: share_public / share_count present only when non-default")
    rows = gr(AH)
    ok("P: share_public == 'view'", rows[P].get("share_public") == "view", rows[P])
    ok("P: share_count ABSENT (key not in row)", "share_count" not in rows[P], rows[P])
    ok("S: share_count == 2", rows[S].get("share_count") == 2, rows[S])
    ok("S: share_public ABSENT", "share_public" not in rows[S], rows[S])
    ok("U: NEITHER key present", "share_public" not in rows[U] and "share_count" not in rows[U], rows[U])
    ok("M: BOTH keys present on the same row (public AND named)",
       rows[M].get("share_public") == "view" and rows[M].get("share_count") == 1, rows[M])

    # ---- 2. Part 2: scope=shared whitelist + membership invariants ------------------------------
    print("2. GET /api/reviews?scope=shared — membership + row whitelist")
    b_shared = {r["id"]: r for r in gr_shared(BH)}
    ok("B's scope=shared contains exactly {S, M} (named grants only)",
       set(b_shared.keys()) == {S, M}, list(b_shared.keys()))
    ok("P (public-only, no named grant to B) does NOT appear", P not in b_shared)
    srow = b_shared.get(S, {})
    ok("S row: right == 'comment'", srow.get("right") == "comment", srow)
    ok("S row: from_email is A's LOCAL-PART only (#284 D3, never the full address)",
       srow.get("from_email") == "a" and "@" not in (srow.get("from_email") or ""), srow)
    for leaked in ("project", "source_path", "session", "owner"):
        ok(f"S row never carries {leaked!r}", leaked not in srow, srow)
    ok("S row carries exactly the whitelisted keys",
       set(srow.keys()) == {"id", "title", "kind", "created", "source_updated",
                             "feedback_updated", "right", "from_email"}, sorted(srow.keys()))

    print("3. a third account with zero grants gets an empty list; anonymous is refused")
    ok("C: GET /api/reviews?scope=shared -> {\"reviews\":[]}", gr_shared(CH) == [])
    st, _ = req(base + "/api/reviews?scope=shared", h=ANON)
    ok("anonymous GET /api/reviews?scope=shared -> 401", st == 401, st)

    print("4. GET /api/reviews (no scope) as B is unaffected — B owns nothing")
    st, raw = req(base + "/api/reviews", h=BH)
    ok("B's owned list is empty (owns nothing; A's docs never leak into it)",
       st == 200 and json.loads(raw).get("reviews") == [], raw)

    print("5. widen LIST only: as B (comment-right on S), write/delete on S still answer as today")
    st, _ = req(base + f"/api/reviews/{S}/source", "PUT",
                json.dumps({"markdown": "# hacked"}).encode(), BH)
    ok("PUT .../source as B -> 404 (can_write stays owner-only)", st == 404, st)
    st, _ = req(base + f"/api/reviews/{S}", "DELETE", None, BH)
    ok("DELETE /api/reviews/{S} as B -> 404 (can_delete stays owner-only)", st == 404, st)

    # ---- 6. D2: self-revoke — exact-own-row authorization ----------------------------------------
    print("6. D2 self-revoke: a grantee may remove ONLY their own row")
    st, _ = req(base + f"/api/reviews/{S}/shares?email=" + "b%40example.com",
                "DELETE", None, DH)  # D tries to revoke B's row via B's email
    ok("D attempting to revoke B's share (by B's email) -> 404, refused", st == 404, st)
    still = {r["id"] for r in gr_shared(BH)}
    ok("B's share on S is STILL intact after D's attempt", S in still, still)

    st, _ = req(base + f"/api/reviews/{S}/shares?email=" + "d%40example.com",
                "DELETE", None, DH)  # D revokes their OWN row
    ok("D revoking their OWN row (by their own email) -> 200", st == 200, st)
    d_after = {r["id"] for r in gr_shared(DH)}
    ok("S is gone from D's scope=shared (the row was actually removed)", S not in d_after, d_after)
    st, _ = req(base + f"/api/reviews/{S}/status", h=DH)
    ok("D's underlying READ access is also gone (self-revoke is destructive, not a hide flag)",
       st == 404, st)

    print("7. owner-initiated revoke still works unchanged (regression)")
    st, _ = req(base + f"/api/reviews/{S}/shares?email=" + "b%40example.com",
                "DELETE", None, AH)
    ok("A (owner) revoking B's share -> 200", st == 200, st)
    ok("B's scope=shared no longer contains S", S not in {r["id"] for r in gr_shared(BH)})

    st, _ = req(base + f"/api/reviews/{S}/shares?email=" + "nobody%40example.com",
                "DELETE", None, ANON)
    ok("anonymous DELETE .../shares -> 401", st == 401, st)

finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except Exception:
        srv.kill()

# ============================================================== local tier: byte-identical =======
print("8. local tier (REQUIRE_AUTH off): the new keys never appear; row shape is unchanged")
LDATA = os.path.join(ROOT, ".scratch", "share_scope_local_data")
shutil.rmtree(LDATA, ignore_errors=True)
os.makedirs(LDATA)
lport = free()
lenv = dict(os.environ, MDREVIEW_DATA=LDATA, PORT=str(lport),
            MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), PYTHONPATH=os.path.join(ROOT, "src"))
llog = open(os.path.join(LDATA, "s.log"), "w")
lsrv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=lenv, stdout=llog, stderr=llog)
lbase = "http://127.0.0.1:%d" % lport
try:
    for _ in range(80):
        try:
            req(lbase + "/healthz"); break
        except Exception:
            time.sleep(.25)
    _, raw = req(lbase + "/api/reviews", "POST",
                 json.dumps({"title": "local doc", "markdown": "# x"}).encode())
    lrid = json.loads(raw)["id"]
    st, raw = req(lbase + "/api/reviews")
    lrows = {r["id"]: r for r in json.loads(raw).get("reviews", [])}
    lrow = lrows.get(lrid, {})
    BASELINE_KEYS = {"id", "title", "created", "source_updated", "project", "source_path",
                     "session", "owner", "revision", "notes_total", "notes_addressed", "turn",
                     "status"}
    ok("local row has NEITHER share_public NOR share_count",
       "share_public" not in lrow and "share_count" not in lrow, lrow)
    ok("local row's key set is exactly the pre-#284 baseline (nothing added)",
       set(lrow.keys()) == BASELINE_KEYS, sorted(lrow.keys()))
    st, raw = req(lbase + "/api/reviews?scope=shared")
    ok("local tier: ?scope=shared answers 200 {\"reviews\":[]} rather than erroring",
       st == 200 and json.loads(raw).get("reviews") == [], (st, raw))
finally:
    lsrv.terminate()
    try:
        lsrv.wait(timeout=5)
    except Exception:
        lsrv.kill()

print("\n" + ("%d case(s) failed" % FAILED[0] if FAILED[0] else "all share-scope cases pass"))
sys.exit(1 if FAILED[0] else 0)
