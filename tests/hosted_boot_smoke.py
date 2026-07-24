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

def run(env_overrides):
    env = dict(os.environ); env.update(STAGING_ENV); env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", BOOT], env=env,
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

print(("FAILED: " + ", ".join(fails)) if fails else "hosted boot smoke: all clear")
sys.exit(1 if fails else 0)
