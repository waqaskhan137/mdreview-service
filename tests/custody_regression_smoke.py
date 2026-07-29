#!/usr/bin/env python3
"""Custody regression smoke (#115) — the executable check the #97 incident lacked.

#97 happened because three things were simultaneously true: a hosted instance could run with
ownership enforcement OFF, creation therefore wrote owner="", and a blind bulk-stamp then swept every
un-owned document onto one uid. This asserts all three are now impossible, so the failure class
cannot silently return.

Deliberately complements tests/hosted_boot_smoke.py rather than repeating it: that one proves the
STAGING env boots and that PROXY_SECRET is load-bearing. This one proves the DEFAULT posture (no
ownership env at all) refuses, that no env var can talk a hosted build into serving open, and that
the bulk-stamp path is gone.

Each case runs in a SUBPROCESS: the guards fire at import/build time, so they cannot be re-observed
in one interpreter.

Section 6 (#272) additionally proves the reconcile tool persists the human custody decision:
confirm/quarantine stamp custody_reviewed_at, quarantine never binds an owner, and an untouched
record stays byte-identical.

Run: python3 tests/custody_regression_smoke.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "src")
DATA = os.path.join(REPO, ".scratch", "custody_regression_data")

# A COMPLETE, valid hosted env. Cases below remove from it, so a check can never pass merely because
# some other secret was missing.
FULL_ENV = {
    "MDREVIEW_REQUIRE_AUTH": "1",
    "MDREVIEW_ALLOW_PROXY_PLANE": "0",
    "MDREVIEW_PROXY_SECRET": "inert-not-consumed-with-plane-off",
    "MDREVIEW_SESSION_SECRET": "test-session-secret",
    "MDREVIEW_TOKEN_PEPPER": "test-token-pepper",
    "MDREVIEW_OWNER_EMAIL": "owner@example.com",
    "MDREVIEW_PUBLIC_BASE": "https://staging.mdreview.space",
    "MDREVIEW_ALLOW_STUB_EMAIL": "1",
    "MDREVIEW_DATA": DATA,
    "PYTHONPATH": SRC,
}

# What `python -m mdreview.hosted` does up to (not including) serve_forever.
BUILD = ("import mdreview.config as c; from mdreview.store import Store; "
         "from mdreview.hosted.compose import build_hosted; "
         "app = build_hosted(Store(c.DATA_DIR)); ")
BOOT_OK = BUILD + "print('BOOT_OK')"
POLICY = BUILD + "print('POLICY=' + type(app.policy).__name__)"


def run(code, env_overrides=None, bare=False):
    """bare=True starts from an EMPTY mdreview env — the shipped default, not a test-tuned one."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MDREVIEW_")}
    if not bare:
        env.update(FULL_ENV)
    else:
        env.update({"MDREVIEW_DATA": DATA, "PYTHONPATH": SRC})
    env.update(env_overrides or {})
    return subprocess.run([sys.executable, "-c", code], env=env,
                          capture_output=True, text=True, timeout=60)


fails = []
def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)
        if detail:
            print("         " + detail)


os.makedirs(DATA, exist_ok=True)

# ---- 1. The DEFAULT posture refuses -------------------------------------------------------------
# The critic's gate on #115: a test that first sets a "hosted" flag would pass while prod stayed
# open. This exercises the SHIPPED DEFAULT — no ownership env whatsoever — and demands a refusal.
r = run(BOOT_OK, bare=True)
check("hosted build with NO ownership env refuses to boot (the #97 precondition)",
      r.returncode != 0 and "BOOT_OK" not in r.stdout,
      "exit=%s out=%r" % (r.returncode, r.stdout.strip()[:120]))

# ---- 2. Every ownership secret is individually load-bearing --------------------------------------
# Removing exactly one from an otherwise-complete env must still refuse, and must name it. Without
# this, one guard could be deleted and the suite would stay green because another still fired.
for var in ("MDREVIEW_SESSION_SECRET", "MDREVIEW_TOKEN_PEPPER", "MDREVIEW_OWNER_EMAIL"):
    r = run(BOOT_OK, {var: ""})
    check("without %s the hosted build refuses (guard is real)" % var,
          r.returncode != 0 and var in (r.stdout + r.stderr),
          "exit=%s" % r.returncode)

# ---- 3. A hosted build CANNOT be talked into serving open ----------------------------------------
# build_hosted wires CustodyPolicy by construction; no env var in that path yields OpenPolicy. #97's
# root cause was exactly an enforcement switch that could be off, so assert the switch does not exist.
r = run(POLICY)
check("a valid hosted build yields CustodyPolicy", "POLICY=CustodyPolicy" in r.stdout,
      r.stdout.strip()[:120] or r.stderr.strip()[-120:])

for tempting in ({"MDREVIEW_REQUIRE_AUTH": "0"}, {"MDREVIEW_REQUIRE_AUTH": ""},
                 {"MDREVIEW_ALLOW_PROXY_PLANE": "1", "MDREVIEW_REQUIRE_AUTH": "0"}):
    r = run(POLICY, tempting)
    opened = "POLICY=OpenPolicy" in r.stdout
    check("hosted build never degrades to OpenPolicy under %s" % tempting,
          not opened, r.stdout.strip()[:120])

# ---- 4. The blind bulk-stamp is gone (slice 3, #111) ---------------------------------------------
r = run("import mdreview.migrate", bare=True)
check("`mdreview.migrate` (the blind bulk owner-stamp) is not importable",
      r.returncode != 0, r.stdout.strip()[:120])

r = run("import runpy; runpy.run_module('mdreview.migrate')", bare=True)
check("`python -m mdreview.migrate` cannot be invoked", r.returncode != 0)

# No module may define a bulk owner-stamp under any name, so a rename cannot smuggle it back.
scan = ("import os,re,sys;"
        "src=os.environ['PYTHONPATH'];"
        "hits=[(p,f) for r_,_,fs in os.walk(os.path.join(src,'mdreview')) for f in fs"
        " if f.endswith('.py') for p in [os.path.join(r_,f)]"
        " if re.search(r'def\\s+(backfill_owner|bulk_stamp|stamp_all)', open(p, encoding='utf-8').read())];"
        "print('HITS=' + repr(hits))")
r = run(scan, bare=True)
check("no module defines a bulk owner-stamp (backfill_owner/bulk_stamp/stamp_all)",
      "HITS=[]" in r.stdout, r.stdout.strip()[:200])

# ---- 5. Creation never falls back to an operator uid ---------------------------------------------
# stamp_owner binds to the CREATING principal. With no principal it must blow up, not quietly return
# some default/operator uid — that fallback is precisely how a stranger's doc became the owner's.
probe = ("from mdreview.hosted.custody import CustodyPolicy;"
         "p = CustodyPolicy.__new__(CustodyPolicy);"
         "\ntry:\n"
         "    v = p.stamp_owner(None)\n"
         "    print('RETURNED=' + repr(v))\n"
         "except Exception as e:\n"
         "    print('REFUSED=' + type(e).__name__)\n")
r = run(probe, bare=True)
check("stamp_owner(None) refuses rather than returning a fallback uid",
      "REFUSED=" in r.stdout and "RETURNED=" not in r.stdout,
      r.stdout.strip()[:120] or r.stderr.strip()[-120:])

# ---- 6. reconcile persists the human custody decision (#272) -------------------------------------
# The durable baseline observable for custody slice 5: confirm/quarantine stamp
# meta["custody_reviewed_at"] at decision time, quarantine writes without binding an owner, list
# separates never-reviewed from quarantined, and a record the tool never touched stays
# byte-identical. Exercises the REAL CLI (python -m mdreview.reconcile) against a throwaway dir.
RDATA = os.path.join(REPO, ".scratch", "custody_regression_data", "reconcile")
shutil.rmtree(RDATA, ignore_errors=True)


def seed(rid, meta):
    os.makedirs(os.path.join(RDATA, rid), exist_ok=True)
    with open(os.path.join(RDATA, rid, "meta.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta))


def meta_of(rid):
    with open(os.path.join(RDATA, rid, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def reconcile(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("MDREVIEW_")}
    env.update({"MDREVIEW_DATA": RDATA, "PYTHONPATH": SRC})
    return subprocess.run([sys.executable, "-m", "mdreview.reconcile"] + list(args),
                          env=env, capture_output=True, text=True, timeout=60)


seed("aaaa000001", {"id": "aaaa000001", "owner": "", "title": "untouched-pending", "created": 1})
seed("bbbb000002", {"id": "bbbb000002", "owner": "", "title": "to-quarantine", "created": 2})
seed("cccc000003", {"id": "cccc000003", "owner": "", "title": "to-confirm", "created": 3})
seed("dddd000004", {"id": "dddd000004", "owner": "github:9", "title": "owned", "created": 4})
untouched_path = os.path.join(RDATA, "aaaa000001", "meta.json")
with open(untouched_path, "rb") as f:
    untouched_before = f.read()

r = reconcile("confirm", "cccc000003", "github:42")
m = meta_of("cccc000003")
check("confirm binds the owner AND stamps custody_reviewed_at (epoch int)",
      r.returncode == 0 and m.get("owner") == "github:42"
      and isinstance(m.get("custody_reviewed_at"), int) and m.get("custody_reviewed_at", 0) > 0,
      "exit=%s meta=%r" % (r.returncode, m))

r = reconcile("quarantine", "bbbb000002")
m = meta_of("bbbb000002")
check("quarantine stamps custody_reviewed_at WITHOUT binding an owner",
      r.returncode == 0 and m.get("owner") == ""
      and isinstance(m.get("custody_reviewed_at"), int) and m.get("custody_reviewed_at", 0) > 0,
      "exit=%s meta=%r" % (r.returncode, m))

r = reconcile("quarantine", "dddd000004")
check("quarantine refuses an owned record",
      r.returncode != 0 and meta_of("dddd000004").get("custody_reviewed_at") is None,
      "exit=%s err=%r" % (r.returncode, r.stderr.strip()[:120]))

r = reconcile("quarantine", "eeee999999")
check("quarantine refuses an unknown rid", r.returncode != 0,
      "exit=%s out=%r" % (r.returncode, r.stdout.strip()[:120]))

r = reconcile("confirm", "aaaa000001", "no-colon-sub")
check("confirm still refuses a malformed owner id", r.returncode != 0,
      "exit=%s" % r.returncode)

r = reconcile("list")
out = r.stdout
awaiting = out.find("AWAITING REVIEW")
quar = out.find("QUARANTINED")
check("list separates never-reviewed from quarantined (sections present, records in the right one)",
      r.returncode == 0 and 0 <= awaiting < quar
      and awaiting < out.find("aaaa000001") < quar < out.find("bbbb000002")
      and "cccc000003" not in out and "dddd000004" not in out,
      out.strip()[:200])

with open(untouched_path, "rb") as f:
    untouched_after = f.read()
check("a record the tool never wrote stays byte-identical (list is read-only)",
      untouched_after == untouched_before,
      "before=%r after=%r" % (untouched_before[:80], untouched_after[:80]))

print(("FAILED: " + ", ".join(fails)) if fails else "custody regression smoke: all clear")
sys.exit(1 if fails else 0)
