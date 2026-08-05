#!/usr/bin/env python3
"""latex_empty_create_selfcheck.py — POST /api/reviews {kind:"latex"} with no body (#363).

THE GAP THIS GUARDS: #363 asked whether an empty latex create (201, empty source) is deliberate
or an accident. It is deliberate: `_require_tex` (latex_review/decorator.py) passes
allow_empty=True only on create, and hosted_boot_smoke.py already asserts "A blank latex CREATE
stays legal (start a paper, fill it in later)" with no template involved at all. #355 shows the
cost of that permissiveness going undocumented: a fixture posted its content under "source"
instead of "markdown", the create arm silently ignored the unknown key, and a 201 with an EMPTY
document passed for "created" — a test then asserted behaviour against a document nobody wrote.
This suite does not change that decision (a mixed "empty is an error unless a template supplies
the source" rule was considered and rejected: the hosted_boot_smoke.py case above has no template
and is still asserted legal, so a stricter rule would break a deliberate, CI-gated assertion). It
pins the DOCUMENTED behaviour instead, at the API layer, so a future change to it is a decision,
not a silent regression:

  1. #355's exact shape: content posted under the wrong key ("source", not "markdown") -> 201,
     source is empty. This is the trap itself, not just the empty-create rule in isolation.
  2. no markdown, no template -> 201, source is empty (the case hosted_boot_smoke.py asserts
     in-process; this asserts it over the real HTTP API).
  3. no markdown, WITH a template -> 201, source is the template's starter .tex (seeding runs
     before the empty-body carve-out, so the two arms are independent; a template create is never
     silently empty).
  4. the markdown (non-latex) kind allows an empty create too — this is not a latex/markdown
     asymmetry, it's a create/edit asymmetry: latex's PUT rejects empty (already covered by
     hosted_boot_smoke.py case 3), create does not, for either kind.

No compile is awaited anywhere here (an empty or malformed source enqueues a compile that will
fail, and waiting for it just eats the ~7-8s tectonic bundle pull #363 separately flags) — every
assertion below reads back GET .../source, never /api/latex/{id}/compile.

Run: python3 tests/latex_empty_create_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
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


def boot():
    data = tempfile.mkdtemp(prefix="mdr363-")
    port = free_port()
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), MDREVIEW_ENABLE_LATEX="1",
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
               PYTHONPATH=os.path.join(ROOT, "src"))
    log = open(os.path.join(data, "server.log"), "w")
    srv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env, stdout=log, stderr=log)
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            req(base + "/healthz"); break
        except Exception:
            time.sleep(0.25)
    return srv, base, data


def create(base, body):
    code, _, raw = req(base + "/api/reviews", "POST", json.dumps(body).encode(),
                       {"Content-Type": "application/json"})
    return code, raw


def source_of(base, rid):
    code, _, raw = req(base + "/api/reviews/%s/source" % rid)
    return code, raw


srv, base, data = boot()
try:
    # 0. Sanity: MDREVIEW_ENABLE_LATEX=1 actually installed the decorator, or every case below
    #    would pass vacuously against a plain ReviewService that never runs _require_tex at all.
    code, raw = create(base, {"title": "sanity", "kind": "latex", "markdown": "not tex at all"})
    check("sanity: the #188 guard is live (non-tex latex create -> 400)", code == 400, (code, raw[:200]))

    # 1. #355's exact shape: content under the WRONG key ("source"), "markdown" absent entirely.
    tex = "\\documentclass{article}\n\\begin{document}\nhi\n\\end{document}\n"
    code, raw = create(base, {"title": "wrong-key", "kind": "latex", "source": tex})
    check("1: wrong-key create -> 201 (documented, not a 500/400)", code == 201, (code, raw[:200]))
    rid = json.loads(raw).get("id") if code == 201 else None
    if rid:
        scode, sraw = source_of(base, rid)
        check("1: wrong-key create's source is EMPTY (the content never arrived)",
              scode == 200 and sraw == b"", (scode, sraw[:80]))

    # 2. No markdown, no template -> 201, empty source. The case hosted_boot_smoke.py asserts
    #    in-process ("A blank latex CREATE stays legal"); this is the same claim over real HTTP.
    code, raw = create(base, {"title": "blank", "kind": "latex"})
    check("2: no markdown, no template -> 201", code == 201, (code, raw[:200]))
    rid2 = json.loads(raw).get("id") if code == 201 else None
    if rid2:
        scode, sraw = source_of(base, rid2)
        check("2: blank latex create's source is empty", scode == 200 and sraw == b"", (scode, sraw[:80]))

    # 3. No markdown, WITH a template -> 201, source is the template's starter, never empty. Proves
    #    the empty-body carve-out and template seeding are independent arms: a template create is
    #    never silently empty, even though it also supplies no "markdown".
    code, raw = create(base, {"title": "templated", "kind": "latex", "markdown": "", "template": "ieee"})
    check("3: empty markdown + template=ieee -> 201", code == 201, (code, raw[:200]))
    rid3 = json.loads(raw).get("id") if code == 201 else None
    if rid3:
        scode, sraw = source_of(base, rid3)
        check("3: templated create's source is the seeded starter, NOT empty",
              scode == 200 and sraw.strip().startswith(b"\\documentclass"),
              (scode, sraw[:80]))

    # 4. The markdown (non-latex) kind allows an empty create too: this is a create/edit
    #    asymmetry (PUT is strict for latex, lax for markdown), not a latex/markdown asymmetry at
    #    create time. looks_like_latex("", "") is False (empty body has no preamble to detect), so
    #    this does not trip the MR-100 "looks like LaTeX" 400 either.
    code, raw = create(base, {"title": "blank-md"})
    check("4: markdown kind, no body -> 201 (create-time symmetry with latex)", code == 201, (code, raw[:200]))
    rid4 = json.loads(raw).get("id") if code == 201 else None
    if rid4:
        scode, sraw = source_of(base, rid4)
        check("4: blank markdown create's source is empty", scode == 200 and sraw == b"", (scode, sraw[:80]))
finally:
    srv.terminate(); srv.wait(timeout=10); shutil.rmtree(data, ignore_errors=True)

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all empty-latex-create cases pass"))
sys.exit(1 if failed else 0)
