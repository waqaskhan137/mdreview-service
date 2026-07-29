#!/usr/bin/env python3
"""source_csrf_attribution_selfcheck.py — session-keyed CSRF on PUT /source + the
source_updated_by attribution lifecycle (#289, epic #273 slice A2).

WHAT THIS GUARDS. The document is gaining a browser editor (slices B/C), so PUT /source becomes
a state-changing browser act and needs the CSRF posture the other browser write arms already
have — and each draft needs an author so agents know when the human edited under them.

  - CSRF keys on a VERIFIED SESSION, never on `plane` (epic #273 round-1 finding 1): only a
    request carrying a verified app-owned session cookie must present X-CSRF-Token. The
    predicate is a bound app.check_csrf composed in build_hosted (next to app.sessions), reached
    from the core PUT arm via getattr, so core never imports mdreview.hosted and the local tier
    (no attribute) has no gate — it has no cookie plane to protect.
  - The proxy-vouched plane and the bearer-token plane pass untouched. THE PLANE TRAP (epic
    #273): tests/auth_smoke.py's cookie() helper sends X-Mdreview-Proxy headers — that IS the
    proxy plane, so a 403 case written with it would assert the wrong plane. The 403 cases below
    log in the way a browser does (magic link -> redeem -> Set-Cookie), like
    tests/account_tokens_csrf_selfcheck.py; the proxy headers appear only in the must-PASS
    regression rows.
  - Attribution lifecycle (a requirement, not an implementer choice): a reviewer write (cookie
    session, proxy plane, or local plane + X-Mdreview-Client: viewer) SETS
    meta.source_updated_by = "reviewer"; an agent write DELETES the key; readers default
    "agent" via .get(...). GET /status echoes it; an all-agent-plane review keeps a meta.json,
    round.json and non-/status responses with no trace of the key.
  - round.json["by"] is copied from the OUTGOING meta before the overwrite, so each archived
    round names the author of the draft it archived (absent = agent, the same reader default).
  - LatexAwareReviews.put_source is an explicit override widened WITH the core signature, so a
    latex write with updated_by must not TypeError/500.

Mutation checks: drop the check_csrf gate in the PUT arm and the 403 cases fail; key the gate on
plane == "cookie" and the proxy-plane pass row fails; replace the subtractive delete with a
set-both-values write and the key-deleted / no-trace rows fail; stop copying "by" in
snapshot_round and the history attribution row fails; narrow the latex override and the latex
row fails.

Run: python3 tests/source_csrf_attribution_selfcheck.py     (exit 0 = pass)
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
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, ".scratch", "source_csrf_attribution_data")
PROXY_SECRET = "test-proxy-secret-289"

sys.path.insert(0, SRC)
# The latex unit section imports mdreview in-process, and mdreview.config makedirs DATA_DIR at
# import time — point it into the scratch dir BEFORE any mdreview import (default is /data).
os.environ["MDREVIEW_DATA"] = os.path.join(DATA, "inprocess_config")

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name
          + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


def free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # bypass any system proxy


def req(u, m="GET", body=None, h=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(u, data=data, headers=h or {}, method=m)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with OPENER.open(r, timeout=15) as x:
            return x.status, x.read(), x.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def boot(module, data, extra_env, log_path=None):
    port = free()
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data)
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), PYTHONPATH=SRC,
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), **extra_env)
    out = open(log_path, "w") if log_path else subprocess.DEVNULL
    proc = subprocess.Popen([sys.executable, "-m", module], env=env, stdout=out, stderr=out)
    base = "http://127.0.0.1:%d" % port
    for _ in range(80):
        if proc.poll() is not None:
            sys.exit("FAIL: %s exited on boot (rc=%s)" % (module, proc.returncode))
        try:
            if OPENER.open(base + "/healthz", timeout=5).status == 200:
                return proc, base
        except (urllib.error.URLError, OSError):
            time.sleep(0.15)
    proc.terminate()
    sys.exit("FAIL: %s did not answer /healthz" % module)


def meta_on_disk(data, rid):
    with open(os.path.join(data, rid, "meta.json")) as f:
        return json.load(f)


def status_by(base, rid, h=None):
    _, raw, _ = req(base + "/api/reviews/%s/status" % rid, h=h)
    return json.loads(raw).get("source_updated_by")


# ================= local tier: attribution lifecycle, no CSRF gate =================
def local_cases(base, data):
    # Import-graph pin: the core server module must not pull in mdreview.hosted (the CSRF seam is
    # reached via getattr on an attribute only build_hosted sets).
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; import mdreview.server; "
         "sys.exit(1 if any(m.startswith('mdreview.hosted') for m in sys.modules) else 0)"],
        env=dict(os.environ, PYTHONPATH=SRC), capture_output=True)
    check("core import graph: mdreview.server never imports mdreview.hosted", r.returncode == 0)

    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "d0", "title": "t"})
    rid = json.loads(raw)["id"]
    check("setup: review created", code == 201 and bool(rid), code)
    check("fresh review: /status defaults source_updated_by to \"agent\"",
          status_by(base, rid) == "agent")
    check("fresh review: meta.json on disk carries NO source_updated_by",
          "source_updated_by" not in meta_on_disk(data, rid))

    # agent write (local plane, no viewer header): key stays absent
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "d1"})
    check("local agent PUT (no header) -> 200, no CSRF gate on the local tier", code == 200, code)
    check("...meta response carries no source_updated_by (all-agent, no trace)",
          "source_updated_by" not in json.loads(raw))
    check("...and /status still reads \"agent\"", status_by(base, rid) == "agent")

    # reviewer write: the local plane's viewer header sets the key
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "d2"},
                       {"X-Mdreview-Client": "viewer"})
    check("local viewer-header PUT -> 200 and /status reads \"reviewer\"",
          code == 200 and status_by(base, rid) == "reviewer", code)
    check("...meta.json on disk SET to reviewer",
          meta_on_disk(data, rid).get("source_updated_by") == "reviewer")

    # agent write again: the SUBTRACTIVE half — the key is DELETED, not overwritten
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "d3"})
    check("agent PUT after a reviewer write -> 200 and /status back to \"agent\"",
          code == 200 and status_by(base, rid) == "agent", code)
    check("...and the key is DELETED from meta.json on disk (subtractive, not set-agent)",
          "source_updated_by" not in meta_on_disk(data, rid))

    # history: each archived round names the author of the draft it archived
    _, raw, _ = req(base + "/api/reviews/%s/history" % rid)
    rounds = {r["round"]: r for r in json.loads(raw)["rounds"]}
    check("history round 2 (archived the reviewer draft d2) carries by=reviewer",
          rounds.get(2, {}).get("by") == "reviewer", rounds.get(2))
    check("history rounds 0+1 (agent drafts) carry NO by key (reader default = agent)",
          "by" not in rounds.get(0, {}) and "by" not in rounds.get(1, {}))
    _, raw, _ = req(base + "/api/reviews/%s/history/2" % rid)
    check("single-round read carries the same attribution", json.loads(raw).get("by") == "reviewer")

    # all-agent-plane review: no trace of the field on disk or on any non-/status response
    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "a0", "title": "aa"})
    rid2 = json.loads(raw)["id"]
    req(base + "/api/reviews/%s/source" % rid2, "PUT", {"markdown": "a1"})
    _, meta_raw, _ = req(base + "/api/reviews/%s" % rid2)
    _, fb_raw, _ = req(base + "/api/reviews/%s/feedback" % rid2)
    _, hist_raw, _ = req(base + "/api/reviews/%s/history" % rid2)
    on_disk = open(os.path.join(data, rid2, "meta.json")).read()
    rj = open(os.path.join(data, rid2, "history", "round-0", "round.json")).read()
    check("all-agent review: no source_updated_by/by anywhere but /status",
          all(b"source_updated_by" not in x for x in (meta_raw, fb_raw, hist_raw))
          and "source_updated_by" not in on_disk and '"by"' not in rj)


# ================= MCP tool surface: agents must be told to look =================
def mcp_description_case():
    from mcp import tools
    tool = {t["name"]: t for t in tools.TOOLS}
    check("get_status tool description names source_updated_by",
          "source_updated_by" in tool["get_status"]["description"])


# ================= latex decorator: the override widened again =================
def latex_decorator_cases():
    from mdreview.store import Store
    from mdreview.comments import CommentService
    from mdreview.reviews import ReviewService
    from latex_review.decorator import LatexAwareReviews

    data = os.path.join(DATA, "latex_unit")
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data)

    class StubWorker:
        def __init__(self):
            self.enqueued = []

        def enqueue(self, rid):
            self.enqueued.append(rid)

    store = Store(data)
    worker = StubWorker()
    svc = LatexAwareReviews(ReviewService(store, CommentService(store)), worker)
    tex0 = "\\documentclass{article}\\begin{document}v0\\end{document}"
    tex1 = "\\documentclass{article}\\begin{document}v1\\end{document}"
    rid = svc.create(tex0, "paper", kind="latex")
    with store.lock:
        svc.put_source(rid, tex1, expected_revision=0, updated_by="reviewer")
    check("latex override accepts updated_by (no TypeError), writes + enqueues + attributes",
          svc.read_source(rid) == tex1 and svc.meta(rid).get("source_updated_by") == "reviewer"
          and worker.enqueued == [rid, rid])
    with store.lock:
        svc.put_source(rid, tex0, updated_by="agent")
    check("latex agent write deletes the key through the widened override",
          "source_updated_by" not in svc.meta(rid) and worker.enqueued == [rid, rid, rid])


# ================= hosted tier: the CSRF gate + plane regressions =================
def login(base, log_path, email):
    """A GENUINE browser session: magic link (stub email -> server log) redeemed for Set-Cookie.
    NOT auth_smoke's cookie() helper, which is the proxy plane."""
    req(base + "/auth/magic-link", "POST", {"email": email})
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
    _, raw, _ = req(base + "/auth/session", h={"Cookie": ck})
    return ck, json.loads(raw).get("csrf", "")


def hosted_cases(base, log_path):
    ck, csrf = login(base, log_path, "o@e.com")
    check("hosted setup: genuine session cookie + csrf obtained", bool(ck) and bool(csrf))

    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "s0", "title": "s"},
                       {"Cookie": ck})
    rid = json.loads(raw)["id"]
    check("hosted setup: review created on the session plane", code == 201 and bool(rid), code)

    # -- verified session WITHOUT / WITH the token ------------------------------------------------
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "LOST"},
                       {"Cookie": ck})
    check("session PUT without X-CSRF-Token -> 403", code == 403, code)
    check("...and the 403 is the CSRF gate", b"CSRF" in raw, raw[:80])
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "LOST"},
                       {"Cookie": ck, "X-CSRF-Token": "wrong"})
    check("session PUT with a WRONG token -> 403", code == 403, code)
    code, raw, hdrs = req(base + "/api/reviews/%s/source" % rid, h={"Cookie": ck})
    check("...and the blocked PUTs wrote NOTHING (body + ETag unchanged)",
          raw.decode() == "s0" and hdrs.get("ETag") == '"0"', hdrs.get("ETag"))
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "s1"},
                       {"Cookie": ck, "X-CSRF-Token": csrf})
    check("session PUT WITH the token -> 200, unchanged behavior",
          code == 200 and json.loads(raw).get("revision") == 1, code)
    check("...and the session write attributes \"reviewer\"",
          status_by(base, rid, h={"Cookie": ck}) == "reviewer")
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "LOST"},
                       {"Cookie": ck, "X-CSRF-Token": csrf, "If-Match": '"0"'})
    check("CSRF pass does not bypass the #288 precondition: stale If-Match still 409",
          code == 409, code)

    # -- proxy plane: MUST keep writing with no token (round-1 finding 1, the regression row) -----
    proxy = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
             "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com"}
    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "p0", "title": "p"}, proxy)
    prid = json.loads(raw)["id"]
    check("proxy setup: review created on the proxy plane", code == 201 and bool(prid), code)
    code, raw, _ = req(base + "/api/reviews/%s/source" % prid, "PUT", {"markdown": "p1"}, proxy)
    check("proxy-plane PUT with NO CSRF token still succeeds (finding-1 regression)",
          code == 200, code)
    check("...and the proxy write attributes \"reviewer\" (a vouched human)",
          status_by(base, prid, h=proxy) == "reviewer")

    # -- bearer plane: unchanged, and the agent write DELETES the key (one-review sequence) -------
    code, raw, _ = req(base + "/account/tokens", "POST", {"label": "t"}, proxy)
    btok = json.loads(raw).get("token", "") if code == 201 else ""
    check("bearer setup: token minted", code == 201 and btok.startswith("mdr_"), code)
    bearer = {"Authorization": "Bearer " + btok}
    code, raw, _ = req(base + "/api/reviews/%s/source" % prid, "PUT", {"markdown": "p2"}, bearer)
    check("bearer-plane PUT with no CSRF token unchanged -> 200", code == 200, code)
    check("...and the agent write flips the SAME review back to the \"agent\" default "
          "(reviewer -> agent, key deleted)",
          status_by(base, prid, h=bearer) == "agent"
          and "source_updated_by" not in json.loads(raw))


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(DATA, exist_ok=True)

    print("-- local tier --")
    ldata = os.path.join(DATA, "local")
    lproc, lbase = boot("mdreview", ldata, {})
    try:
        local_cases(lbase, ldata)
    finally:
        lproc.terminate()
        lproc.wait(timeout=10)

    print("-- mcp tool surface --")
    mcp_description_case()

    print("-- latex decorator (unit) --")
    latex_decorator_cases()

    print("-- hosted tier --")
    hdata = os.path.join(DATA, "hosted")
    hlog = os.path.join(DATA, "hosted.log")
    hproc, hbase = boot("mdreview.hosted", hdata, {
        "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_ALLOW_PROXY_PLANE": "1",
        "MDREVIEW_PROXY_SECRET": PROXY_SECRET, "MDREVIEW_SESSION_SECRET": "s",
        "MDREVIEW_TOKEN_PEPPER": "p", "MDREVIEW_OWNER_EMAIL": "o@e.com",
        "MDREVIEW_ALLOW_STUB_EMAIL": "1", "MDREVIEW_PUBLIC_BASE": "https://l.test",
    }, log_path=hlog)
    try:
        hosted_cases(hbase, hlog)
    finally:
        hproc.terminate()
        hproc.wait(timeout=10)

    print()
    print(("%d case(s) FAILED" % len(fails)) if fails else "all #289 CSRF + attribution cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
