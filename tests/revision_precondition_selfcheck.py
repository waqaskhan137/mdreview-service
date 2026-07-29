#!/usr/bin/env python3
"""revision_precondition_selfcheck.py — the #288 edit-precondition seam (epic #273, slice A1).

WHAT THIS GUARDS. The document is gaining a second writer (the human editor, slices B/C), so a
write needs an optimistic-concurrency guard or the slower writer silently destroys the faster
one's edit. The token is `revision` (monotonic, single writer: snapshot_round), NEVER
`source_updated` (wall clock, collision-prone). The contract under test:

  - GET /source issues the token atomically WITH the body (ETag, same response, read under
    store.lock) — a separate /status fetch is forbidden by design as the token source.
  - PUT /source honors If-Match (browser path) or an `expected_revision` body key (MCP path):
    stale -> 409 and NOTHING is written; current -> 200; absent -> today's unconditional write
    (the no-break contract for every existing caller).
  - The 409 payload and the update_source tool description both carry the re-read-and-re-apply,
    never-resend instruction (without it, the plausible agent reaction to a bare 409 is to
    resend its stale buffer, destroying the human's edit with a 200).
  - MCP get_source stays the raw document verbatim; the token is opt-in per call
    (with_revision=true -> {"source", "revision"} envelope). A default-on envelope is a
    breaking change and forbidden.
  - GET /status reports `revision` (explicitly defaulted) and `can_edit` derived from the same
    custody can_write the PUT enforces: owner/local true; share grantee and anonymous false.
  - LatexAwareReviews.put_source is an explicit override and widened WITH the core signature,
    so a guarded latex write must not TypeError/500.

Mutation checks: drop the expected_revision compare in ReviewService.put_source and the 409
cases fail; narrow the latex override back to (rid, markdown) and the latex case fails; wrap
get_source's default result in an envelope and the verbatim case fails.

Run: python3 tests/revision_precondition_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, ".scratch", "revision_precondition_data")
PROXY_SECRET = "test-proxy-secret-288"

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


def boot(module, extra_env):
    port = free()
    data = os.path.join(DATA, module.replace(".", "_"))
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data)
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), PYTHONPATH=SRC,
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), **extra_env)
    proc = subprocess.Popen([sys.executable, "-m", module], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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


# ================= local tier: the HTTP seam =================
def local_http_cases(base):
    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "# Doc v0\n\nbody0", "title": "t"})
    rid = json.loads(raw)["id"]
    check("setup: review created", code == 201 and bool(rid), code)

    code, raw, _ = req(base + "/api/reviews/%s/status" % rid)
    st = json.loads(raw)
    check("fresh /status: revision present and explicitly 0", code == 200 and st.get("revision") == 0,
          (code, st.get("revision")))
    check("fresh /status: can_edit true on the local tier", st.get("can_edit") is True, st.get("can_edit"))

    code, raw, hdrs = req(base + "/api/reviews/%s/source" % rid)
    check("GET /source: body verbatim + ETag carries revision 0",
          code == 200 and raw.decode() == "# Doc v0\n\nbody0" and hdrs.get("ETag") == '"0"',
          (code, hdrs.get("ETag")))

    # stale If-Match FIRST: 409 and nothing written
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "LOST"},
                       {"If-Match": '"5"'})
    payload = json.loads(raw)
    check("PUT with stale If-Match -> 409", code == 409, code)
    low = (payload.get("error") or "").lower()
    check("409 payload instructs re-read + re-apply and forbids resending",
          "re-read" in low and "never resend" in low, payload)
    check("409 payload names expected vs current revision",
          payload.get("expected_revision") == 5 and payload.get("current_revision") == 0, payload)
    code, raw, hdrs = req(base + "/api/reviews/%s/source" % rid)
    check("...and the stale PUT wrote NOTHING (body + ETag unchanged)",
          raw.decode() == "# Doc v0\n\nbody0" and hdrs.get("ETag") == '"0"', hdrs.get("ETag"))

    # current If-Match: the write lands and the token moves
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "# Doc v1"},
                       {"If-Match": '"0"'})
    check("PUT with current If-Match -> 200, revision bumps to 1",
          code == 200 and json.loads(raw).get("revision") == 1, code)
    code, raw, hdrs = req(base + "/api/reviews/%s/source" % rid)
    check("...and GET /source now serves v1 with ETag 1",
          raw.decode() == "# Doc v1" and hdrs.get("ETag") == '"1"', hdrs.get("ETag"))

    # NO precondition: today's unconditional write, regression-pinned
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "# Doc v2"})
    check("PUT without any precondition stays unconditional -> 200 (no-break)",
          code == 200 and json.loads(raw).get("revision") == 2, code)

    # MCP transport path: expected_revision as a body key
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT",
                       {"markdown": "LOST", "expected_revision": 1})
    check("PUT with stale body expected_revision -> 409", code == 409, code)
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid)
    check("...and wrote nothing", raw.decode() == "# Doc v2")
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT",
                       {"markdown": "# Doc v3", "expected_revision": 2})
    check("PUT with current body expected_revision -> 200, revision 3",
          code == 200 and json.loads(raw).get("revision") == 3, code)

    # RFC edges on the header
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "# Doc v4"},
                       {"If-Match": "*"})
    check("If-Match: * means no precondition -> 200", code == 200, code)
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": "LOST"},
                       {"If-Match": '"abc"'})
    check("malformed If-Match -> 400, nothing written", code == 400, code)
    code, raw, _ = req(base + "/api/reviews/%s/source" % rid)
    check("...body still v4 after the malformed attempt", raw.decode() == "# Doc v4")

    code, raw, _ = req(base + "/api/reviews/%s/status" % rid)
    st = json.loads(raw)
    check("/status tracks the moved token (revision 4)", st.get("revision") == 4, st.get("revision"))
    return rid


# ================= MCP wrapper: routing, envelope, wording =================
def mcp_cases(base, rid):
    from mcp import client, tools

    # routing no-break: omitted expected_revision -> byte-identical body to today
    check("route(update_source) without expected_revision -> body exactly {markdown} (no-break)",
          client.route("update_source", {"id": "x", "markdown": "m"})
          == ("PUT", "/api/reviews/x/source", {"markdown": "m"}))
    check("route(update_source) with expected_revision -> body carries it",
          client.route("update_source", {"id": "x", "markdown": "m", "expected_revision": 7})[2]
          == {"markdown": "m", "expected_revision": 7})

    # tool-surface wording, pinned (the 409 contract is words or it is nothing)
    tool = {t["name"]: t for t in tools.TOOLS}
    upd = tool["update_source"]
    low = upd["description"].lower()
    check("update_source description carries the 409 re-read/never-resend contract",
          "409" in low and "re-read" in low and "never resend" in low)
    prop = upd["inputSchema"]["properties"].get("expected_revision", {})
    check("update_source schema: expected_revision integer and OPTIONAL (not required)",
          prop.get("type") == "integer" and "expected_revision" not in upd["inputSchema"]["required"])
    gs = tool["get_source"]
    check("get_source schema: with_revision is opt-in boolean; id stays the only required arg",
          gs["inputSchema"]["properties"].get("with_revision", {}).get("type") == "boolean"
          and gs["inputSchema"]["required"] == ["id"])

    # live wrapper calls against the booted local server
    client.BASE = base
    raw = client.http(*client.route("get_source", {"id": rid}))
    check("wrapper get_source default result is the raw document VERBATIM", raw == "# Doc v4")
    env = json.loads(client.get_source_with_revision(rid))
    check("with_revision envelope: source + revision from the SAME response",
          env.get("source") == "# Doc v4" and env.get("revision") == 4, env.get("revision"))

    try:
        client.http(*client.route("update_source",
                                  {"id": rid, "markdown": "LOST", "expected_revision": 1}))
        check("wrapper stale update_source raises ToolError", False)
    except client.ToolError as e:
        msg = str(e).lower()
        check("wrapper stale update_source -> ToolError surfacing 409 + the instruction",
              "409" in msg and "never resend" in msg, str(e)[:120])
    raw = client.http(*client.route("update_source", {"id": rid, "markdown": "# Doc v5"}))
    check("wrapper update_source WITHOUT the parameter still writes (no-break)",
          json.loads(raw).get("revision") == 5)


# ================= latex decorator: the widened override =================
def latex_decorator_cases():
    from mdreview.store import Store
    from mdreview.comments import CommentService
    from mdreview.reviews import ReviewService
    from mdreview.errors import ReviewWriteRejected
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
        svc.put_source(rid, tex1, expected_revision=0)   # the widened signature — must not TypeError
    check("latex override accepts expected_revision (no TypeError) and writes",
          svc.read_source(rid) == tex1 and svc.meta(rid).get("revision") == 1)
    check("...and the recompile was enqueued for the guarded write", worker.enqueued == [rid, rid])
    try:
        with store.lock:
            svc.put_source(rid, tex0, expected_revision=0)
        check("latex stale write raises", False)
    except ReviewWriteRejected as e:
        check("latex stale write -> 409, nothing written, no extra enqueue",
              e.status == 409 and svc.read_source(rid) == tex1 and worker.enqueued == [rid, rid])


# ================= hosted tier: can_edit is custody can_write =================
def hosted_cases(base):
    owner1 = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
              "X-Auth-Request-User": "owner1", "X-Auth-Request-Email": "owner1@example.com"}
    owner2 = {"X-Mdreview-Proxy": PROXY_SECRET, "X-Mdreview-Provider": "google",
              "X-Auth-Request-User": "owner2", "X-Auth-Request-Email": "owner2@example.com"}

    code, raw, _ = req(base + "/api/reviews", "POST", {"markdown": "# H", "title": "h"}, owner1)
    rid = json.loads(raw)["id"]
    check("hosted setup: owner created a review", code == 201 and bool(rid), code)

    code, raw, _ = req(base + "/api/reviews/%s/status" % rid, h=owner1)
    st = json.loads(raw)
    check("hosted /status for the OWNER: can_edit true + revision present",
          code == 200 and st.get("can_edit") is True and st.get("revision") == 0, (code, st))

    # provision owner2 (invites are existing-account-only), then grant a COMMENT share
    req(base + "/api/reviews", h=owner2)
    code, raw, _ = req(base + "/api/reviews/%s/shares" % rid, "POST",
                       {"email": "owner2@example.com", "right": "comment"}, owner1)
    check("hosted setup: comment share granted", code == 201, (code, raw[:80]))
    code, raw, _ = req(base + "/api/reviews/%s/status" % rid, h=owner2)
    st = json.loads(raw)
    check("hosted /status for a comment-share GRANTEE: readable but can_edit FALSE",
          code == 200 and st.get("can_edit") is False, (code, st.get("can_edit")))

    # public share: an anonymous reader sees the status but can_edit stays false
    code, _, _ = req(base + "/api/reviews/%s/public" % rid, "POST", {}, owner1)
    check("hosted setup: made public", code == 200, code)
    code, raw, _ = req(base + "/api/reviews/%s/status" % rid)
    st = json.loads(raw)
    check("hosted /status for an ANONYMOUS public reader: can_edit FALSE",
          code == 200 and st.get("can_edit") is False, (code, st.get("can_edit")))


def main():
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(DATA, exist_ok=True)

    print("-- local tier --")
    lproc, lbase = boot("mdreview", {})
    try:
        rid = local_http_cases(lbase)
        print("-- mcp wrapper --")
        mcp_cases(lbase, rid)
    finally:
        lproc.terminate()
        lproc.wait(timeout=10)

    print("-- latex decorator (unit) --")
    latex_decorator_cases()

    print("-- hosted tier --")
    hproc, hbase = boot("mdreview.hosted", {
        "MDREVIEW_REQUIRE_AUTH": "1", "MDREVIEW_ALLOW_PROXY_PLANE": "1",
        "MDREVIEW_PROXY_SECRET": PROXY_SECRET, "MDREVIEW_SESSION_SECRET": "s",
        "MDREVIEW_TOKEN_PEPPER": "p", "MDREVIEW_OWNER_EMAIL": "o@e.com",
        "MDREVIEW_ALLOW_STUB_EMAIL": "1", "MDREVIEW_PUBLIC_BASE": "https://l.test",
    })
    try:
        hosted_cases(hbase)
    finally:
        hproc.terminate()
        hproc.wait(timeout=10)

    print()
    print(("%d case(s) FAILED" % len(fails)) if fails else "all #288 revision-precondition cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
