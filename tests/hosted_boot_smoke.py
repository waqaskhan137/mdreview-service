#!/usr/bin/env python3
"""Hosted boot smoke — the ONLY check that runs with the exact staging env (REQUIRE_AUTH=1 +
ALLOW_PROXY_PLANE=0 + an inert PROXY_SECRET). The fail-closed unit tests don't set REQUIRE_AUTH, so
without this a `config.py` guard change could silently reintroduce the staging crash-loop (the R2-NEW
finding: config.py's import-time guard hard-requires PROXY_SECRET when REQUIRE_AUTH=1, so staging
must carry an inert one). Runs each case in a SUBPROCESS because that guard fires at module import.

Run: python3 tests/hosted_boot_smoke.py
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "src")
DATA = os.path.join(REPO, ".scratch", "boot_smoke_data")

# The exact env the staging compose sets (secrets are throwaway test values here).
STAGING_ENV = {
    "MDREVIEW_REQUIRE_AUTH": "1",
    "MDREVIEW_ALLOW_PROXY_PLANE": "0",
    "MDREVIEW_PROXY_SECRET": "inert-not-consumed-with-plane-off",  # satisfies config.py's import guard
    "MDREVIEW_SESSION_SECRET": "test-session-secret",
    "MDREVIEW_TOKEN_PEPPER": "test-token-pepper",
    "MDREVIEW_OWNER_EMAIL": "owner@example.com",
    "MDREVIEW_PUBLIC_BASE": "https://staging.mdreview.space",
    "MDREVIEW_ALLOW_STUB_EMAIL": "1",
    "MDREVIEW_DATA": DATA,
    "PYTHONPATH": SRC,
}
# Do exactly what `python -m mdreview.hosted` does up to (not including) serve_forever: import config
# (fires the guard), then build_hosted (fires the hosted-build guards). No port, no docker needed.
BOOT = ("import mdreview.config as c; from mdreview.store import Store; "
        "from mdreview.hosted.compose import build_hosted; "
        "build_hosted(Store(c.DATA_DIR)); print('BOOT_OK')")

# #188 guard, exercised in-process rather than over HTTP because this file's whole shape is
# "boot a build in a subprocess and read stdout" — there is no server here to talk to. In-process is
# also the honest level for it: the rule lives in the decorator, and server.py only renders the
# exception it raises.
#
# This runs with MDREVIEW_ENABLE_LATEX=1, which is the ONLY automated lane that imports
# latex_review at all. That matters beyond #188: templates.py imports the exception type from
# mdreview.errors at module scope, so any rename that misses a reference makes `import latex_review`
# raise at Services.__init__ and the container never serves. CI gates the :dev image on this file,
# and the flag lives in Dockerfile.latex rather than the compose, so without this case a broken
# rename would publish a green image that then fails to boot on staging.
GUARD = r'''
import mdreview.config as c
from mdreview.store import Store
from mdreview.hosted.compose import build_hosted
from mdreview.errors import ReviewWriteRejected

app = build_hosted(Store(c.DATA_DIR))
# Proves the flag actually took effect; without this the rest could pass vacuously on a build where
# app.reviews is the bare ReviewService and no guard exists at all.
assert type(app.reviews).__name__ == "LatexAwareReviews", type(app.reviews).__name__

TEX = "\\documentclass{article}\n\\begin{document}\nhi\n\\end{document}\n"
MD = "# Reading copy\n\n- a list item\n"

def rejects(fn):
    try:
        fn()
    except ReviewWriteRejected:
        return True
    return False

# 1. Markdown reviews are untouched. This is the regression that matters most: the decorator wraps
#    app.reviews for EVERY kind, so an ungated guard would 400 the product's primary write path.
md_id = app.reviews.create(MD, "md")
app.reviews.put_source(md_id, MD + "\nmore prose\n")
app.reviews.put_source(md_id, "")

# 2. A latex review accepts real TeX, on create and on update.
tex_id = app.reviews.create(TEX, "tex", kind="latex")
app.reviews.put_source(tex_id, TEX + "% edited\n")

# 3. ...and rejects a body that could never compile.
assert rejects(lambda: app.reviews.create(MD, "bad", kind="latex")), "create latex with markdown"
assert rejects(lambda: app.reviews.put_source(tex_id, MD)), "put markdown into latex"
assert rejects(lambda: app.reviews.put_source(tex_id, "")), "put empty into latex"
assert rejects(lambda: app.reviews.put_source(tex_id, "   \n")), "put blank into latex"

# 4. A blank latex CREATE stays legal (start a paper, fill it in later).
app.reviews.create("", "blank", kind="latex")

# 5. The rejected writes did not land — a guard that rejects after writing would pass 3 and fail here.
assert app.reviews.read_source(tex_id).startswith("\\documentclass"), "good source survived"

# 6. The OTHER user of this exception type still works. template_smoke.py never constructs
#    TemplateService or references UnknownTemplate, so nothing in the repo covered the unknown-id
#    route until now — and that is precisely the path a botched rename turns from a 400 into a 500.
try:
    app.reviews.create("", "t", kind="latex", template="no-such-template")
    raise AssertionError("unknown template id was accepted")
except ReviewWriteRejected as e:
    assert e.status == 400, e.status
    assert e.payload.get("available"), e.payload
print("GUARD_OK")
'''

def run(env_overrides, script=BOOT):
    env = dict(os.environ); env.update(STAGING_ENV); env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", script], env=env,
                          capture_output=True, text=True, timeout=60)

fails = []
def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: fails.append(label)

os.makedirs(DATA, exist_ok=True)

# 1. The staging env boots — no SystemExit at import or in build_hosted. This is what prevents the
#    crash-loop the health gate would have masked.
r = run({})
check("staging env (REQUIRE_AUTH=1, ALLOW_PROXY_PLANE=0, inert PROXY_SECRET) boots",
      r.returncode == 0 and "BOOT_OK" in r.stdout)
if r.returncode != 0:
    print("    stderr:", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "(none)")

# 2. Drop the inert secret and the SAME env refuses to boot — proving the guard is real (so the inert
#    secret is load-bearing, not cargo). If this ever passes, config.py's guard was weakened; that is
#    a security decision for the non-hosted path and must not happen silently (see the plan's deferred
#    config.py-hosted-aware refactor).
r = run({"MDREVIEW_PROXY_SECRET": ""})
check("without PROXY_SECRET the REQUIRE_AUTH=1 build refuses to boot (guard is real)",
      r.returncode != 0 and "MDREVIEW_PROXY_SECRET" in (r.stdout + r.stderr))

# 3. The same env with latex enabled boots. This is what actually executes `import latex_review`,
#    which nothing else in CI does — see the comment on GUARD.
r = run({"MDREVIEW_ENABLE_LATEX": "1"})
check("staging env with MDREVIEW_ENABLE_LATEX=1 boots (latex_review imports cleanly)",
      r.returncode == 0 and "BOOT_OK" in r.stdout)
if r.returncode != 0:
    print("    stderr:", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "(none)")

# 4. #188: the latex write guard rejects a body that cannot compile, and — the part that would
#    break the product if wrong — leaves markdown reviews alone.
r = run({"MDREVIEW_ENABLE_LATEX": "1", "MDREVIEW_DATA": DATA + "_latex",
         # Creating latex reviews enqueues compiles, and the worker mkdtemps a latexjob-* dir under
         # MDREVIEW_LATEX_WORKDIR, which defaults to the OS temp dir. Keep those inside the project's
         # gitignored .scratch/, per CLAUDE.md's rule that nothing lands outside the repo.
         "MDREVIEW_LATEX_WORKDIR": os.path.join(REPO, ".scratch", "boot_smoke_latexjobs")},
        script=GUARD)
check("#188 latex source guard rejects non-TeX writes and spares markdown reviews",
      r.returncode == 0 and "GUARD_OK" in r.stdout)
if r.returncode != 0:
    print("    stderr:", r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "(none)")

print(("FAILED: " + ", ".join(fails)) if fails else "hosted boot smoke: all clear")
sys.exit(1 if fails else 0)
