#!/usr/bin/env python3
"""latex_recompile_selfcheck.py — POST /api/latex/{rid}/recompile (#250).

THE GAP THIS GUARDS: _self_heal deliberately never retries a failed compile at the current
revision (its docstring: the 2s poll must not stack compiles against a persistently-failing
source). Before #250 that left a TRANSIENT failure — a CTAN blip, a template download miss —
stranded at `failed` forever, with a no-op source edit as the only user remedy. The explicit POST
is the one sanctioned exception; the poll must stay inert.

Three parts, mirroring the AC groups:
  A  plain local instance, fed a deliberately malformed LaTeX fixture (an undefined control
     sequence) so every real compile deterministically ends `failed` regardless of whether
     tectonic happens to be installed on the machine running this check — a TeX error when it
     is (this exact posture is verified live against staging review ad8722a00e in #250's
     grounding), "tectonic binary not found" when it is not. Either way `failed` is exactly the
     fixture the retry ACs need: retry works, pdf_revision survives via _KEEP, 404s, 507 on a
     full disk. Anti-stacking itself (AC 4) is checked twice: once at the HTTP level (a
     byte-stable finished_at across repeated polls) and once directly against `_self_heal`'s
     recorded enqueue calls with no server (A2, the same style as B below) — the HTTP form alone
     cannot distinguish "no enqueue" from "enqueued a redo that left status.json untouched".
  B  CompileWorker coalescing, asserted directly with no server (AC 5): N clicks can never make
     more than 1 queued + 1 redo.
  C  hosted instance (stub email, magic-link from the log — the pubcopy stand-up): 401 anonymous,
     404 non-owner, 403 cookie-without-CSRF, 200 with it, 200 bearer-token-without-CSRF (the
     documented sharing posture).

Run: python3 tests/latex_recompile_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
failed = []


def check(name, cond, detail=""):
    print(("ok   - " if cond else "FAIL - ") + name + (("  (" + str(detail) + ")") if detail and not cond else ""))
    if not cond:
        failed.append(name)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(url, method="GET", data=None, headers=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def wait_state(base, rid, states, tries=60):
    st = {}
    for _ in range(tries):
        _, _, raw = req("%s/api/latex/%s/compile" % (base, rid))
        st = json.loads(raw)
        if st.get("state") in states:
            return st
        time.sleep(0.5)
    return st


def boot(env_extra, module="mdreview"):
    data = tempfile.mkdtemp(prefix="mdr250-")
    port = free_port()
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), MDREVIEW_ENABLE_LATEX="1",
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
               PYTHONPATH=os.path.join(ROOT, "src"), **env_extra)
    log = open(os.path.join(data, "server.log"), "w")
    srv = subprocess.Popen([sys.executable, "-m", module], env=env, stdout=log, stderr=log)
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            req(base + "/healthz"); break
        except Exception:
            time.sleep(0.25)
    return srv, base, data


# ================= A: local tier — retry, anti-stacking, _KEEP, 404s, 507 =====================
srv, base, data = boot({})
try:
    # #355: the create arm reads "markdown", not "source" — posting under the wrong key silently
    # creates an EMPTY-bodied review (POST /api/reviews accepts a missing markdown field with no
    # error). That accidentally still fails to compile ("no legal \end found"), so this case used
    # to pass, but for a reason its own comment misstated ("tectonic absent locally" — false on a
    # machine that has tectonic).
    #
    # The fixture must fail for a STATED, environment-independent reason, not an accidental empty
    # body: three checks below (state == "failed", a strictly newer finished_at, and _KEEP) all
    # require a compile that fails at the current revision. A well-formed document like a bare
    # "hi" body compiles clean wherever tectonic is present (verified locally: exit 0, PDF
    # produced) and would never reach `failed` at all, so the fixture is a deliberately malformed
    # document (an undefined control sequence) instead: tectonic present -> TeX error, tectonic
    # absent -> "binary not found". Both ends in `failed`.
    body = json.dumps({"title": "recompile", "kind": "latex",
                       "markdown": "\\documentclass{article}\\begin{document}"
                                   "\\mdreviewSelfcheckUndefinedXyz\\end{document}"}).encode()
    _, _, raw = req(base + "/api/reviews", "POST", body, {"Content-Type": "application/json"})
    rid = json.loads(raw)["id"]
    st1 = wait_state(base, rid, ("failed",))
    check("A: local compile deterministically fails (malformed fixture)", st1.get("state") == "failed", st1)
    t1 = st1.get("finished_at")

    # Anti-stacking: polls do not retry a failed compile at the current revision.
    for _ in range(4):
        _, _, raw = req(base + "/api/latex/%s/compile" % rid)
    stp = json.loads(raw)
    check("A: repeated polls never re-enqueue (finished_at byte-stable)", stp.get("finished_at") == t1,
          "%r vs %r" % (stp.get("finished_at"), t1))

    # THE FEATURE: the explicit POST is the retry path.
    code, _, raw = req(base + "/api/latex/%s/recompile" % rid, "POST")
    stq = json.loads(raw)
    check("A: POST /recompile returns 200 with the status shape", code == 200 and "state" in stq, (code, stq))
    check("A: response carries has_pdf and pdf_revision", "has_pdf" in stq and "pdf_revision" in stq, stq)
    st2 = wait_state(base, rid, ("failed",))
    check("A: the compile actually re-ran (strictly newer finished_at)",
          st2.get("finished_at") and t1 and st2["finished_at"] > t1, (t1, st2.get("finished_at")))

    # _KEEP: a surviving PDF's revision is not forgotten by the re-failure.
    latex_dir = os.path.join(data, rid, "latex")
    with open(os.path.join(latex_dir, "paper.pdf"), "wb") as f:
        f.write(b"%PDF-1.4\n%%EOF\n")
    with open(os.path.join(latex_dir, "status.json"), "w") as f:
        json.dump({"state": "failed", "revision": 0, "pdf_revision": 0,
                   "finished_at": time.time(), "log_tail": "x"}, f)
    code, _, raw = req(base + "/api/latex/%s/recompile" % rid, "POST")
    st3 = wait_state(base, rid, ("failed",))
    check("A: pdf_revision survives a recompile re-failure (_KEEP)",
          st3.get("pdf_revision") == 0 and st3.get("has_pdf") is True, st3)

    # 404s: non-latex rid and absent rid.
    _, _, raw = req(base + "/api/reviews", "POST",
                    json.dumps({"title": "md", "markdown": "# hi"}).encode(),
                    {"Content-Type": "application/json"})
    md_rid = json.loads(raw)["id"]
    code, _, _ = req(base + "/api/latex/%s/recompile" % md_rid, "POST")
    check("A: non-latex rid -> 404", code == 404, code)
    code, _, _ = req(base + "/api/latex/%s/recompile" % ("0" * 10), "POST")
    check("A: absent rid -> 404", code == 404, code)
finally:
    srv.terminate(); shutil.rmtree(data, ignore_errors=True)

# 507: the floor is read at import, so it blocks the CREATE too. Create on a normal instance,
# then restart the SAME data dir under an absurd floor and probe only the recompile.
srv, base, data = boot({})
try:
    # Must look enough like TeX to pass the #188 create-time guard (a non-empty body with none of
    # \documentclass/\begin{document}/\input/\include is rejected 400 before a review even exists).
    # This case doesn't care whether the compile itself ok's or fails (wait_state below accepts
    # either) so, unlike case A, correctness doesn't force a malformed body — but reuse the same
    # deliberately-broken shape anyway: it fails fast (no font/glyph-list fetch tail), where a
    # valid document pays the full bundle-download cost off-image (~7s, verified locally) for an
    # outcome this case discards either way.
    body = json.dumps({"title": "floor", "kind": "latex",
                       "markdown": "\\documentclass{article}\\begin{document}"
                                   "\\mdreviewSelfcheckUndefinedXyz\\end{document}"}).encode()
    _, _, raw = req(base + "/api/reviews", "POST", body, {"Content-Type": "application/json"})
    rid2 = json.loads(raw)["id"]
    wait_state(base, rid2, ("failed", "ok"))
finally:
    srv.terminate()
port2 = free_port()
env2 = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port2), MDREVIEW_ENABLE_LATEX="1",
            MDREVIEW_DISK_FLOOR=str(10 ** 18),
            MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
            PYTHONPATH=os.path.join(ROOT, "src"))
srv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env2,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
base2 = "http://127.0.0.1:%d" % port2
try:
    for _ in range(60):
        try:
            req(base2 + "/healthz"); break
        except Exception:
            time.sleep(0.25)
    code, _, _ = req(base2 + "/api/latex/%s/recompile" % rid2, "POST")
    check("A: disk under floor -> 507, never a silent 200", code == 507, code)
finally:
    srv.terminate(); shutil.rmtree(data, ignore_errors=True)

# ============ A2: _self_heal anti-stacking, asserted directly against the recorded calls =========
# The HTTP-level "finished_at byte-stable" check above only proves status.json was not REWRITTEN.
# It cannot tell that from "no enqueue call": CompileWorker.enqueue's mid-compile branch (rid ==
# self._running) marks _redo and returns WITHOUT touching status.json at all, so a poll that lands
# while a redo is already in flight can enqueue and still leave finished_at untouched. Confirmed
# empirically: mutating _self_heal's revision guard from `<` to `<=` (so it re-enqueues a failed
# compile at the CURRENT revision, exactly the regression this case exists to catch) left the
# byte-stable check green in 2/2 runs; the suite still went red, but only on OTHER checks racing
# against ~7-8s network-bound compiles, which is a fragile, indirect way to catch a direct logic
# bug. Assert on the recorded enqueue calls instead, exactly as case B asserts on CompileWorker
# with no server.
os.environ.setdefault("MDREVIEW_DATA", tempfile.mkdtemp(prefix="mdr250a2-"))
sys.path.insert(0, os.path.join(ROOT, "src"))
from latex_review.module import LatexModule                 # noqa: E402


class _HealWorker:
    def __init__(self, status):
        self._status = status
        self.enqueued = []

    def status(self, rid):
        return self._status

    def enqueue(self, rid):
        self.enqueued.append(rid)


class _HealReviews:
    def __init__(self, revision):
        self._revision = revision

    def meta(self, rid):
        return {"revision": self._revision}


# The orphan path MUST still enqueue (a stubbed-out heal that never fires would pass the next
# assertion vacuously): a PDF built from an older revision with nothing pending.
heal_worker_stale = _HealWorker({"state": "ok", "revision": 0})
heal_mod_stale = LatexModule(None, _HealReviews(1), None, heal_worker_stale)
for _ in range(5):
    heal_mod_stale._self_heal("stale")
check("A2: self_heal enqueues the true orphan path (PDF older than current revision)",
      heal_worker_stale.enqueued == ["stale"] * 5, heal_worker_stale.enqueued)

# THE GAP THIS GUARDS (module docstring, verbatim): a failed compile at the CURRENT revision must
# never be re-enqueued by the poll, so a persistently-failing source cannot stack compiles.
heal_worker_current = _HealWorker({"state": "failed", "revision": 1})
heal_mod_current = LatexModule(None, _HealReviews(1), None, heal_worker_current)
for _ in range(5):
    heal_mod_current._self_heal("current")
check("A2: self_heal never re-enqueues a failed compile at the current revision",
      heal_worker_current.enqueued == [], heal_worker_current.enqueued)

# ================= B: CompileWorker coalescing, no server (AC 5) ==============================
os.environ["MDREVIEW_DATA"] = tempfile.mkdtemp(prefix="mdr250b-")
sys.path.insert(0, os.path.join(ROOT, "src"))
from latex_review.compiler import CompileWorker            # noqa: E402


class _Store:
    def read_json(self, *_a, **_k): return None
    def write_text(self, *_a, **_k): pass
    def dir(self, rid): return os.path.join(os.environ["MDREVIEW_DATA"], rid)


class _Reviews:
    def meta(self, rid): return {"revision": 1}


w = CompileWorker(_Store(), _Reviews(), None)               # thread NOT started: pure state assertions
w.enqueue("r1"); w.enqueue("r1")
check("B: two clicks while idle -> ONE queue entry", w._q.qsize() == 1 and "r1" in w._queued,
      (w._q.qsize(), w._queued))
w._queued.discard("r1"); w._q.get()
w._running = "r1"
w.enqueue("r1")
check("B: a click mid-compile -> redo only, nothing queued",
      "r1" in w._redo and w._q.qsize() == 0, (w._redo, w._q.qsize()))

# ================= C: hosted tier — auth, CSRF, token plane ===================================
srv, base, data = boot({
    "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_ALLOW_PROXY_PLANE": "0",
    "MDREVIEW_PROXY_SECRET": "inert", "MDREVIEW_SESSION_SECRET": "test-session-secret",
    "MDREVIEW_TOKEN_PEPPER": "test-pepper", "MDREVIEW_OWNER_EMAIL": "owner@example.com",
    "MDREVIEW_ALLOW_STUB_EMAIL": "1", "MDREVIEW_PUBLIC_BASE": "https://local.test",
}, module="mdreview.hosted")
try:
    def login(email):
        req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
            {"Content-Type": "application/json"})
        time.sleep(0.3)
        with open(os.path.join(data, "server.log")) as f:
            toks = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", f.read())
        r = urllib.request.Request(base + "/auth/redeem",
                                   data=("token=" + toks[-1]).encode(),
                                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                                   method="POST")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k): return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(r, timeout=15)
        except urllib.error.HTTPError as e:
            resp = e
        cookie = resp.headers.get("Set-Cookie", "").split(";")[0]
        _, _, raw = req(base + "/auth/session", headers={"Cookie": cookie})
        return cookie, json.loads(raw).get("csrf", "")

    owner_cookie, owner_csrf = login("owner@example.com")
    _, _, raw = req(base + "/api/reviews", "POST",
                    json.dumps({"title": "auth", "kind": "latex", "source": "x"}).encode(),
                    {"Content-Type": "application/json", "Cookie": owner_cookie,
                     "X-CSRF-Token": owner_csrf})
    rid = json.loads(raw)["id"]

    code, _, _ = req(base + "/api/latex/%s/recompile" % rid, "POST")
    check("C: anonymous POST -> 401", code == 401, code)

    other_cookie, other_csrf = login("other@example.com")
    code, _, _ = req(base + "/api/latex/%s/recompile" % rid, "POST",
                     headers={"Cookie": other_cookie, "X-CSRF-Token": other_csrf})
    check("C: authenticated non-owner -> 404 (not probeable)", code == 404, code)

    code, _, _ = req(base + "/api/latex/%s/recompile" % rid, "POST",
                     headers={"Cookie": owner_cookie})
    check("C: cookie plane WITHOUT CSRF -> 403", code == 403, code)
    code, _, _ = req(base + "/api/latex/%s/recompile" % rid, "POST",
                     headers={"Cookie": owner_cookie, "X-CSRF-Token": owner_csrf})
    check("C: cookie plane WITH CSRF -> 200", code == 200, code)

    _, _, raw = req(base + "/account/tokens", "POST",
                    json.dumps({"label": "t"}).encode(),
                    {"Content-Type": "application/json", "Cookie": owner_cookie,
                     "X-CSRF-Token": owner_csrf})
    tok = json.loads(raw).get("token", "")
    code, _, _ = req(base + "/api/latex/%s/recompile" % rid, "POST",
                     headers={"Authorization": "Bearer " + tok})
    check("C: bearer-token plane without CSRF -> 200 (documented posture)", code == 200, code)
finally:
    srv.terminate(); shutil.rmtree(data, ignore_errors=True)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all recompile cases pass"))
sys.exit(1 if failed else 0)
