#!/usr/bin/env python3
"""account_shares_selfcheck.py — GET /api/account/shares (#262).

WHAT THIS GUARDS. The account page answers "what of mine can other people reach". Getting that
wrong in the permissive direction is a privacy bug: showing a user someone else's shared documents,
or failing to show them their own live public links. Both fail silently.

The gate is ReviewService.can_access per review, deliberately NOT shares.created_by — created_by
records who GRANTED a share, a different question from who OWNS the document, and conflating them
would let a grantee-who-granted see a review they do not own.

Cases: public-only, named-share-only, neither (must be ABSENT, not returned empty), grantee email
resolved rather than a raw user:<provider:sub>, a second user seeing none of the first's, 401.

Run: python3 tests/account_shares_selfcheck.py     (exit 0 = pass)
"""
import json,os,re,socket,subprocess,sys,tempfile,time,urllib.request
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
ck,csrf=login("o@e.com"); other,ocsrf=login("x@e.com")
H={"Content-Type":"application/json","Cookie":ck,"X-CSRF-Token":csrf}
def mk(t):
    _,raw=req(base+"/api/reviews","POST",json.dumps({"title":t,"markdown":"# x"}).encode(),H)
    return json.loads(raw)["id"]
a,b,c=mk("public one"),mk("named one"),mk("neither")
req(base+f"/api/reviews/{a}/public","POST",b"{}",H)
req(base+f"/api/reviews/{b}/shares","POST",json.dumps({"email":"x@e.com","right":"comment"}).encode(),H)
st,raw=req(base+"/api/account/shares",h={"Cookie":ck})
d=json.loads(raw); ids={i["id"] for i in d["items"]}
FAILED=[0]
def ok(n,c):
    print(("ok   - " if c else "FAIL - ")+n)
    if not c: FAILED[0]+=1
ok("200 for the owner", st==200)
ok("public review listed", a in ids)
ok("named-share review listed", b in ids)
ok("review with neither is ABSENT", c not in ids)
ok("public right reported", any(i["id"]==a and i["public"] for i in d["items"]))
sh=[i for i in d["items"] if i["id"]==b][0]["shares"]
ok("grantee email resolved (not a raw uid)", sh and sh[0]["email"]=="x@e.com")
ok("grantee right reported", sh and sh[0]["right"]=="comment")
st2,raw2=req(base+"/api/account/shares",h={"Cookie":other})
ok("a different user sees NONE of mine", st2==200 and not json.loads(raw2)["items"])
st3,_=req(base+"/api/account/shares")
ok("anonymous -> 401", st3==401)
srv.terminate()
print("\n" + ("%d case(s) failed" % FAILED[0] if FAILED[0] else "all account-shares cases pass"))
sys.exit(1 if FAILED[0] else 0)
