#!/usr/bin/env python3
"""latex_edit_ui_selfcheck.py — the latex-viewer.html edit UI's exact HTTP contract (#291, epic
#273 slice C).

WHAT THIS GUARDS. Slice C adds no new server code: the ETag/If-Match precondition (#288), the
session-keyed CSRF + X-Mdreview-Client attribution seam (#289), and the write guard's snapshot
ordering (#188) all landed already. This selfcheck is therefore NOT re-testing those seams in the
abstract (their own selfchecks do that) — it pins the ONE thing genuinely new: that the EXACT
request the browser's Save button issues, against a LATEX review specifically, produces the three
outcomes the editor's JS branches on, and that they stay DISTINCT:

  - Enter edit: GET /source's ETag (never a separate /status read) seeds the textarea's revision.
  - Save (valid .tex, current revision): PUT with If-Match + X-Mdreview-Client: viewer -> 200,
    revision bumps, source_updated_by == "reviewer" (this combination — a LATEX review, over HTTP,
    with the viewer header — was not exercised by #288/#289's own selfchecks, which use markdown
    reviews for the local-tier attribution cases).
  - Save (body fails the #188 guard, current revision): 400, revision UNCHANGED, source on disk
    UNCHANGED (AC 7a — nothing written).
  - Save (body passes the guard, stale revision): 409, revision UNCHANGED, source UNCHANGED
    (the precondition case, same contract as slice B).
  - Save (body fails the guard AND the revision is stale, both at once): 400, not 409 — pins the
    ORDER LatexAwareReviews.put_source uses (_require_tex before the inner precondition compare).
    If that order ever flips, the editor would show "changed by the agent" for what is actually
    invalid content, which is exactly the conflation AC 7a/7b forbid.
  - The served /review/{rid} page for a latex review carries the new markup (#editbtn, #edittext,
    #editsave, #editcancel, #editerr) and the mutual-exclusion CSS hook (body.editing) — a coarse
    but real regression pin: strip the UI and this fails without needing a browser.

Mutation checks: reorder the guard/precondition checks in LatexAwareReviews.put_source and the
"both at once" case flips from 400 to 409; drop the X-Mdreview-Client attribution and the
source_updated_by case fails; revert the served-page markup and the page-content case fails.

Run: python3 tests/latex_edit_ui_selfcheck.py     (exit 0 = pass)
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
WEB = os.path.join(ROOT, "web", "app")
DATA = os.path.join(ROOT, ".scratch", "latex_edit_ui_data")

VALID_TEX = "\\documentclass{article}\\begin{document}v0\\end{document}"
VALID_TEX_V1 = "\\documentclass{article}\\begin{document}v1 saved by the reviewer\\end{document}"
NOT_TEX = "# Reading notes\n\nThis is plain markdown, not a paper.\n"

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
    hdrs = dict(h or {})
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    r = urllib.request.Request(u, data=data, headers=hdrs, method=m)
    try:
        with OPENER.open(r, timeout=15) as x:
            return x.status, x.read(), x.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def boot():
    port = free()
    shutil.rmtree(DATA, ignore_errors=True)
    os.makedirs(DATA)
    env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), PYTHONPATH=SRC,
               MDREVIEW_WEB_DIR=WEB, MDREVIEW_ENABLE_LATEX="1")
    proc = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(80):
        if proc.poll() is not None:
            sys.exit("FAIL: mdreview exited on boot (rc=%s)" % proc.returncode)
        try:
            if OPENER.open(base + "/healthz", timeout=5).status == 200:
                return proc, base
        except (urllib.error.URLError, OSError):
            time.sleep(0.15)
    proc.terminate()
    sys.exit("FAIL: mdreview did not answer /healthz")


def get_source(base, rid):
    code, raw, hdrs = req(base + "/api/reviews/%s/source" % rid)
    return code, raw.decode(), (hdrs.get("ETag") or "").strip('"')


def status_of(base, rid):
    _, raw, _ = req(base + "/api/reviews/%s/status" % rid)
    return json.loads(raw)


def main():
    proc, base = boot()
    try:
        # ================= served page: the new markup actually shipped =================
        code, raw, _ = req(base + "/api/reviews", "POST",
                           {"markdown": VALID_TEX, "title": "paper", "kind": "latex"})
        check("setup: latex review created", code == 201, code)
        rid = json.loads(raw)["id"]

        code, page, _ = req(base + "/review/%s" % rid)
        page_text = page.decode()
        check("GET /review/{rid} for a latex review -> 200", code == 200, code)
        for marker in ('id="editbtn"', 'id="edittext"', 'id="editsave"', 'id="editcancel"',
                       'id="editerr"', 'id="editpane"', "X-Mdreview-Client", "If-Match",
                       "body.editing"):
            check("served latex-viewer.html contains %r" % marker, marker in page_text)

        # ================= can_edit: the button's gate, for a latex review specifically =========
        st0 = status_of(base, rid)
        check("fresh latex /status: can_edit true on the local tier", st0.get("can_edit") is True,
              st0.get("can_edit"))
        check("fresh latex /status: revision 0", st0.get("revision") == 0, st0.get("revision"))

        # ================= enter-edit: the token comes from GET /source, not /status ============
        code, text, rev = get_source(base, rid)
        check("GET /source: body verbatim + ETag carries revision 0",
              code == 200 and text == VALID_TEX and rev == "0", (code, text, rev))

        # ================= Save: valid .tex, current revision -> 200, reviewer attribution ======
        code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": VALID_TEX_V1},
                           {"If-Match": '"' + rev + '"', "X-Mdreview-Client": "viewer"})
        meta = json.loads(raw) if raw else {}
        check("Save valid .tex at the current revision -> 200, revision bumps to 1",
              code == 200 and meta.get("revision") == 1, (code, meta))
        check("...and the LOCAL-tier viewer header attributes the write to \"reviewer\"",
              status_of(base, rid).get("source_updated_by") == "reviewer")
        code, text, rev = get_source(base, rid)
        check("...and GET /source now serves the saved text with ETag 1",
              code == 200 and text == VALID_TEX_V1 and rev == "1", (code, rev))

        # ================= Save: guard-failing body, CURRENT revision -> 400, AC 7a =============
        code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": NOT_TEX},
                           {"If-Match": '"' + rev + '"', "X-Mdreview-Client": "viewer"})
        body400 = json.loads(raw) if raw else {}
        check("Save a body failing the #188 guard -> 400 (not 409, not 200)", code == 400, code)
        check("...the rejection names the review kind and what is missing",
              "latex" in (body400.get("error") or "") and "documentclass" in (body400.get("error") or ""),
              body400)
        code2, text2, rev2 = get_source(base, rid)
        check("...and NOTHING was written: source + ETag unchanged (buffer-preserving contract)",
              text2 == VALID_TEX_V1 and rev2 == "1", (text2 == VALID_TEX_V1, rev2))

        # ================= Save: guard-passing body, STALE revision -> 409 ======================
        code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT",
                           {"markdown": "\\documentclass{article}\\begin{document}stale attempt"
                                       "\\end{document}"},
                           {"If-Match": '"0"', "X-Mdreview-Client": "viewer"})   # 0 is stale; now at 1
        check("Save a guard-passing body at a STALE revision -> 409", code == 409, code)
        code2, text2, rev2 = get_source(base, rid)
        check("...and NOTHING was written either (source + ETag still unchanged)",
              text2 == VALID_TEX_V1 and rev2 == "1", (text2 == VALID_TEX_V1, rev2))

        # ================= Save: BOTH a bad body AND a stale revision -> 400, guard wins =========
        # This pins the ORDER LatexAwareReviews.put_source uses. If the precondition compare ever
        # moved ahead of _require_tex, this would flip to 409 — the editor would then tell the
        # reviewer "changed by the agent" for a save that was never valid LaTeX to begin with,
        # exactly the conflation AC 7a/7b are written to forbid.
        code, raw, _ = req(base + "/api/reviews/%s/source" % rid, "PUT", {"markdown": NOT_TEX},
                           {"If-Match": '"0"', "X-Mdreview-Client": "viewer"})
        check("Save a body that is BOTH invalid AND at a stale revision -> 400, the guard wins",
              code == 400, code)
        code2, text2, rev2 = get_source(base, rid)
        check("...and still nothing written", text2 == VALID_TEX_V1 and rev2 == "1",
              (text2 == VALID_TEX_V1, rev2))

        # ================= a non-owner never sees the Edit gate ================================
        # No named-share/anonymous fixture is set up here (that gate is #288's own contract, tested
        # there against custody can_write generically) — this only confirms the latex /status ARM
        # reads the same field, which is the one thing specific to this review kind.
        check("can_edit key name matches the button's gate exactly",
              "can_edit" in status_of(base, rid))
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    print()
    print(("%d case(s) FAILED" % len(fails)) if fails else "all #291 latex edit UI cases pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
