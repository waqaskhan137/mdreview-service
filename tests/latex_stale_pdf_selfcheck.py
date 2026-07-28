#!/usr/bin/env python3
"""latex_stale_pdf_selfcheck.py — the stale-PDF contract (#205).

THE BUG: a failed recompile leaves the previous `paper.pdf` on disk, and nothing recorded which
revision produced it. Two distinct failures followed, and a check that only exercises ok-then-failed
sees NEITHER of them, because that path has the revision in session memory:

  A. COLD LOAD (fresh page, no prior `ok` this session) — the viewer had no `pdfRev`, so it
     announced "No PDF yet, the compile failed" while a perfectly good PDF sat next to it.
  B. STALE DOWNLOAD — `#dlbtn` kept the href the `ok` branch set, so Download handed over a
     previous revision's document with nothing saying so.

  C. LEGACY — every status.json already on disk predates `pdf_revision`. Those cannot be
     retro-fitted, so the honest answer is "unknown". Reading `status.json`'s `revision` instead
     would be a CONFIDENT LIE: that is the ATTEMPTED revision, i.e. the one whose PDF was never
     written.

This asserts the server contract for all three. The rendered DOM is stage 8's job, in real Chrome.

Run: python3 tests/latex_stale_pdf_selfcheck.py     (exit 0 = pass)
"""
import json
import os
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
    print(("ok   - " if cond else "FAIL - ") + name + (("  (" + detail + ")") if detail and not cond else ""))
    if not cond:
        failed.append(name)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


data = tempfile.mkdtemp(prefix="mdr205-")
port = free_port()
env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), MDREVIEW_ENABLE_LATEX="1",
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), PYTHONPATH=os.path.join(ROOT, "src"))
srv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            get(base + "/healthz"); break
        except Exception:
            time.sleep(0.25)

    body = json.dumps({"title": "stale", "kind": "latex",
                       "source": "\\documentclass{article}\\begin{document}Hi\\end{document}"}).encode()
    req = urllib.request.Request(base + "/api/reviews", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        rid = json.load(r)["id"]
    latex_dir = os.path.join(data, rid, "latex")
    os.makedirs(latex_dir, exist_ok=True)
    time.sleep(1.5)   # let the initial compile attempt settle before we overwrite its status

    def plant(status):
        with open(os.path.join(latex_dir, "status.json"), "w") as f:
            json.dump(status, f)

    def put_pdf():
        with open(os.path.join(latex_dir, "paper.pdf"), "wb") as f:
            f.write(b"%PDF-1.4\n% pretend\n%%EOF\n")

    def compile_json():
        code, _, raw = get("%s/api/latex/%s/compile" % (base, rid))
        return code, json.loads(raw)

    # ---- A: failed compile at v4, a good PDF from v3 on disk -------------------------------------
    put_pdf()
    plant({"state": "failed", "revision": 4, "pdf_revision": 3, "finished_at": time.time(),
           "log_tail": "! Undefined control sequence."})
    code, st = compile_json()
    check("A: /compile reports has_pdf when a PDF is on disk", st.get("has_pdf") is True, str(st))
    check("A: /compile names the PDF's own revision (3), not the attempted one (4)",
          st.get("pdf_revision") == 3 and st.get("revision") == 4, str(st))

    code, hdrs, raw = get("%s/api/latex/%s/pdf" % (base, rid))
    check("A: /pdf still serves the surviving document", code == 200 and raw.startswith(b"%PDF"))
    check("A: /pdf names the served revision in a header (machine caller, no page state)",
          hdrs.get("X-PDF-Revision") == "3", "headers=%s" % {k: v for k, v in hdrs.items() if k.startswith("X-")})
    check("A: /pdf states the compile state in a header",
          hdrs.get("X-Compile-State") == "failed", str(hdrs.get("X-Compile-State")))

    # ---- C: LEGACY status.json, written before pdf_revision existed ------------------------------
    plant({"state": "failed", "revision": 4, "finished_at": time.time(), "log_tail": "boom"})
    code, st = compile_json()
    check("C: legacy status reports pdf_revision null, not a guess", st.get("pdf_revision") is None, str(st))
    check("C: legacy status does NOT fall back to the attempted revision",
          st.get("pdf_revision") != st.get("revision"),
          "would display a confident lie: the attempted revision's PDF was never written")
    check("C: has_pdf is still true, so the viewer can show it as 'unknown revision'",
          st.get("has_pdf") is True, str(st))
    code, hdrs, _ = get("%s/api/latex/%s/pdf" % (base, rid))
    check("C: /pdf omits X-PDF-Revision rather than inventing one",
          "X-PDF-Revision" not in hdrs, "header present: %s" % hdrs.get("X-PDF-Revision"))

    # ---- B: no PDF at all -> honest "none", not a stale claim ------------------------------------
    os.remove(os.path.join(latex_dir, "paper.pdf"))
    plant({"state": "failed", "revision": 4, "pdf_revision": None, "finished_at": time.time(),
           "log_tail": "boom"})
    code, st = compile_json()
    check("B: has_pdf is false when no document exists", st.get("has_pdf") is False, str(st))
    code, _, _ = get("%s/api/latex/%s/pdf" % (base, rid))
    check("B: /pdf 404s when there is nothing to serve", code == 404, "got %s" % code)

    # ---- preservation: a failure must not FORGET which revision the surviving PDF came from ------
    # Importing latex_review pulls in mdreview.config, which makedirs DATA_DIR at import time and
    # defaults to /data (read-only here). Point it at the throwaway dir first.
    os.environ["MDREVIEW_DATA"] = data
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from latex_review.compiler import CompileWorker, _KEEP          # noqa: E402
    check("preservation: _write_status defaults pdf_revision to the _KEEP sentinel",
          CompileWorker._write_status.__defaults__[-1] is _KEEP,
          "a plain None default would clear the field on every failure")
finally:
    srv.terminate()
    shutil.rmtree(data, ignore_errors=True)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all stale-PDF cases pass"))
sys.exit(1 if failed else 0)
