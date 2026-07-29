#!/usr/bin/env python3
"""review_shares_email_selfcheck.py — GET /api/reviews/{id}/shares carries `email` (#267).

WHAT THIS GUARDS. The viewers' share panel labels each grantee from this payload. Before #267 it
printed the raw `user:<provider:sub>` subject under a comment promising an email, so a proxy-plane
grantee displayed as `google:117…`. The fix resolves `email` server-side in SharingModule._shares
exactly the way _account_shares (#262) already does. The contract under test:

  - a resolvable subject (an account we know the email for) yields that address;
  - an unresolvable subject yields `""`, passed through and NEVER invented from the uid (magic-link
    uids happen to decode to an address; proxy-plane uids would decode to a lie);
  - `subject` and `right` stay in the payload unchanged (revoke keys on the raw subject).

The unresolvable row is planted straight into shares.db: the invite API refuses unknown emails by
design (v1 invites existing accounts only), so an orphaned/proxy-plane share cannot be created
through the front door. ShareStore opens a fresh WAL connection per call, so the server sees it.

Run: python3 tests/review_shares_email_selfcheck.py     (exit 0 = pass)
"""
import json,os,re,socket,sqlite3,subprocess,sys,tempfile,time,urllib.request
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def free():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p
def req(u,m="GET",d=None,h=None):
    r=urllib.request.Request(u,data=d,headers=h or {},method=m)
    try:
        with urllib.request.urlopen(r,timeout=15) as x: return x.status,x.read()
    except urllib.error.HTTPError as e: return e.code,e.read()
data=tempfile.mkdtemp(); port=free()
env=dict(os.environ,MDREVIEW_DATA=data,PORT=str(port),MDREVIEW_REQUIRE_AUTH="1",
    MDREVIEW_ALLOW_PROXY_PLANE="0",MDREVIEW_PROXY_SECRET="inert",
    MDREVIEW_SESSION_SECRET="s",MDREVIEW_TOKEN_PEPPER="p",MDREVIEW_OWNER_EMAIL="o@e.com",
    MDREVIEW_ALLOW_STUB_EMAIL="1",MDREVIEW_PUBLIC_BASE="https://l.test",
    MDREVIEW_WEB_DIR=os.path.join(ROOT,"web","app"),PYTHONPATH=os.path.join(ROOT,"src"))
log=open(os.path.join(data,"s.log"),"w")
srv=subprocess.Popen([sys.executable,"-m","mdreview.hosted"],env=env,stdout=log,stderr=log)
base="http://127.0.0.1:%d"%port
for _ in range(60):
    try: req(base+"/healthz"); break
    except Exception: time.sleep(.25)
def login(email):
    req(base+"/auth/magic-link","POST",json.dumps({"email":email}).encode(),{"Content-Type":"application/json"})
    time.sleep(.3)
    tok=re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)",open(os.path.join(data,"s.log")).read())[-1]
    class NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*a,**k): return None
    op=urllib.request.build_opener(NR)
    rq=urllib.request.Request(base+"/auth/redeem",data=("token="+tok).encode(),
        headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try: rs=op.open(rq,timeout=15)
    except urllib.error.HTTPError as e: rs=e
    ck=rs.headers.get("Set-Cookie","").split(";")[0]
    _,raw=req(base+"/auth/session",h={"Cookie":ck}); return ck,json.loads(raw).get("csrf","")
ck,csrf=login("o@e.com"); login("x@e.com")           # grantee must exist: v1 invites known accounts
H={"Content-Type":"application/json","Cookie":ck,"X-CSRF-Token":csrf}
_,raw=req(base+"/api/reviews","POST",json.dumps({"title":"shares email","markdown":"# x"}).encode(),H)
rid=json.loads(raw)["id"]
req(base+f"/api/reviews/{rid}/shares","POST",json.dumps({"email":"x@e.com","right":"comment"}).encode(),H)
# The unresolvable grantee: a proxy-plane-shaped subject with no account behind it, planted
# directly (see the docstring for why the API cannot create this state).
ORPHAN="user:google:117000000000000000000"
conn=sqlite3.connect(os.path.join(data,"shares.db"))
conn.execute("INSERT OR REPLACE INTO shares (rid,subject,grant_right,created,created_by) VALUES (?,?,?,?,?)",
    (rid,ORPHAN,"view",time.time(),"email:o@e.com"))
conn.commit(); conn.close()
st,raw=req(base+f"/api/reviews/{rid}/shares",h={"Cookie":ck})
d=json.loads(raw); rows={s.get("subject"):s for s in d.get("shares",[])}
known=rows.get("user:email:x@e.com"); orphan=rows.get(ORPHAN)
FAILED=[0]
def ok(n,c):
    print(("ok   - " if c else "FAIL - ")+n)
    if not c: FAILED[0]+=1
ok("owner GET /shares -> 200", st==200)
ok("every named share carries an email key", d.get("shares") and all("email" in s for s in d["shares"]))
ok("resolvable subject yields the address", known is not None and known.get("email")=="x@e.com")
ok("unresolvable subject yields \"\" (never invented)", orphan is not None and orphan.get("email")=="")
ok("subject preserved raw (revoke keys on it)", known is not None and known.get("subject")=="user:email:x@e.com")
ok("right preserved", known is not None and known.get("right")=="comment")
srv.terminate()
print("\n" + ("%d case(s) failed" % FAILED[0] if FAILED[0] else "all review-shares email cases pass"))
sys.exit(1 if FAILED[0] else 0)
