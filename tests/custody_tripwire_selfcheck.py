#!/usr/bin/env python3
"""Custody slice 6a (#361) selfcheck: the unowned-record tripwire, against a synthetic fixture.

The predicate (#272, stable): a record is unowned-and-unreviewed when `owner == ""` AND
`custody_reviewed_at` is unset. scripts/custody_tripwire.py flags exactly those records and
exits non-zero when it finds any. This proves three things, none of them "it ran without
crashing":

  1. Real behaviour on a synthetic fixture covering all four owned/reviewed combinations --
     exit code AND what gets reported -- for EACH combination, not just the aggregate. Only the
     unowned+unreviewed combination is a finding; the other three must never be flagged (a
     tripwire that cries wolf on normal records gets ignored, per the ticket).

  2. Mutation-testing the predicate: scripts/custody_tripwire.py is patched to drop the
     custody_reviewed_at half (the predicate degrades to owner=="" alone -- the exact pre-#272
     bug #272's own description calls out). Run against the SAME fixture, the SAME
     "no false positives" assertion this file uses for the real script now evaluates False,
     because the quarantined record (unowned+reviewed, cccc000003) gets wrongly flagged. That
     is this check catching that regression BY NAME, not merely noting the script still runs.

  3. Mutation-testing the fixture: the planted finding (dddd000004) is quarantined in place
     (custody_reviewed_at stamped, exactly what a human `quarantine` call would do), so nothing
     in the fixture matches any more. The REAL script is asserted to flip to exit 0 / "clean" --
     proving this check notices genuine silence and would equally have caught the tripwire
     failing to fire in step 1, rather than treating "exited 0" as success on its own. A guard
     against the degenerate "clean because empty" reading: the mutated fixture is asserted to
     still hold all four records.

Run: python3 tests/custody_tripwire_selfcheck.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "src")
SCRIPT = os.path.join(REPO, "scripts", "custody_tripwire.py")
SCRATCH = os.path.join(REPO, ".scratch", "custody_tripwire_check")
FIXTURE = os.path.join(SCRATCH, "fixture")
CLEAN_FIXTURE = os.path.join(SCRATCH, "fixture_clean")
MUTATED_SCRIPT = os.path.join(SCRATCH, "mutated_custody_tripwire.py")

# The four combinations. Only dddd000004 (unowned, never reviewed) is a finding.
OWNED_REVIEWED = "aaaa000001"       # owner set, custody_reviewed_at set (confirm stamps both)
OWNED_UNREVIEWED = "bbbb000002"     # owner set, custody_reviewed_at never touched (the common
                                     # case: most owned records were never run through reconcile)
UNOWNED_REVIEWED = "cccc000003"     # owner=="", custody_reviewed_at set (quarantine)
UNOWNED_UNREVIEWED = "dddd000004"   # owner=="", custody_reviewed_at unset -- THE finding
ALL_RIDS = [OWNED_REVIEWED, OWNED_UNREVIEWED, UNOWNED_REVIEWED, UNOWNED_UNREVIEWED]
MUST_NOT_FLAG = [OWNED_REVIEWED, OWNED_UNREVIEWED, UNOWNED_REVIEWED]


def seed(base, rid, meta):
    d = os.path.join(base, rid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(meta))


def build_fixture(base):
    seed(base, OWNED_REVIEWED,
         {"id": OWNED_REVIEWED, "owner": "github:1", "title": "owned-reviewed",
          "created": 1, "custody_reviewed_at": 1700000001})
    seed(base, OWNED_UNREVIEWED,
         {"id": OWNED_UNREVIEWED, "owner": "github:2", "title": "owned-unreviewed", "created": 2})
    seed(base, UNOWNED_REVIEWED,
         {"id": UNOWNED_REVIEWED, "owner": "", "title": "unowned-quarantined",
          "created": 3, "custody_reviewed_at": 1700000003})
    seed(base, UNOWNED_UNREVIEWED,
         {"id": UNOWNED_UNREVIEWED, "owner": "", "title": "unowned-never-reviewed", "created": 4})
    # A non-record file at the data-dir root (every real MDREVIEW_DATA has one, e.g. users.json).
    # Reconciler.unowned() walks os.listdir(data_dir); this proves a stray file is skipped rather
    # than crashing store.exists()/read_json.
    with open(os.path.join(base, "users.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"users": {}, "tokens": {}}))


def run_tripwire(script_path, data_dir):
    # PYTHONPATH belt-and-suspenders: the real script self-locates `mdreview` via __file__, but
    # the MUTATED copy below lives outside scripts/ and needs this to import at all.
    env = {k: v for k, v in os.environ.items() if not k.startswith("MDREVIEW_")}
    env["PYTHONPATH"] = SRC
    return subprocess.run([sys.executable, script_path, data_dir], env=env, cwd=REPO,
                          capture_output=True, text=True, timeout=30)


def no_false_positives(stdout):
    """True iff none of the three must-not-flag rids appear in the report. Returns (ok, bad)."""
    bad = [rid for rid in MUST_NOT_FLAG if rid in stdout]
    return (len(bad) == 0, bad)


fails = []
def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)
        if detail:
            print("         " + detail)


shutil.rmtree(SCRATCH, ignore_errors=True)
os.makedirs(SCRATCH)
build_fixture(FIXTURE)

# ---- 1. Real behaviour: exit code AND report content, for each of the four fixture shapes ------
r = run_tripwire(SCRIPT, FIXTURE)

check("exits non-zero (1) when the fixture holds one unowned-and-unreviewed record",
      r.returncode == 1, "exit=%s stdout=%r" % (r.returncode, r.stdout.strip()[:200]))

check("reports exactly 1 unowned-and-unreviewed record",
      "1 unowned-and-unreviewed record" in r.stdout, r.stdout.strip()[:200])

check("flags the unowned+unreviewed record (%s) -- the one true finding" % UNOWNED_UNREVIEWED,
      UNOWNED_UNREVIEWED in r.stdout, r.stdout.strip()[:200])

check("does NOT flag the owned+reviewed record (%s)" % OWNED_REVIEWED,
      OWNED_REVIEWED not in r.stdout, r.stdout.strip()[:200])

check("does NOT flag the owned+unreviewed record (%s)" % OWNED_UNREVIEWED,
      OWNED_UNREVIEWED not in r.stdout, r.stdout.strip()[:200])

check("does NOT flag the unowned+reviewed/quarantined record (%s)" % UNOWNED_REVIEWED,
      UNOWNED_REVIEWED not in r.stdout, r.stdout.strip()[:200])

ok, bad = no_false_positives(r.stdout)
check("no false positives overall (the 'no false positives' assertion this check reuses below)",
      ok, "wrongly flagged: %r" % bad)

check("stray non-record file at the data-dir root (users.json) does not crash the scan",
      r.returncode in (0, 1), "exit=%s stderr=%r" % (r.returncode, r.stderr.strip()[:200]))

# ---- 2. Mutation-test the PREDICATE: drop the custody_reviewed_at half --------------------------
# This is the pre-#272 bug verbatim: with the field ignored, "unowned" alone is the whole
# predicate, so the quarantined record (reviewed, deliberately left unowned) becomes a false
# positive it must never be.
with open(SCRIPT, encoding="utf-8") as f:
    original_src = f.read()

NEEDLE = '    return [r for r in rec.unowned() if not r["custody_reviewed_at"]]'
if NEEDLE not in original_src:
    check("mutation harness: expected predicate line found in scripts/custody_tripwire.py "
          "(script changed -- update this check's NEEDLE)", False)
else:
    mutated_src = original_src.replace(
        NEEDLE,
        '    return list(rec.unowned())  # MUTATED (#361 selfcheck): dropped custody_reviewed_at')
    with open(MUTATED_SCRIPT, "w", encoding="utf-8") as f:
        f.write(mutated_src)

    r_mut = run_tripwire(MUTATED_SCRIPT, FIXTURE)
    ok_mut, bad_mut = no_false_positives(r_mut.stdout)
    check("MUTATION CAUGHT (predicate): dropping the custody_reviewed_at half makes the SAME "
          "'no false positives' assertion fail by name -- the quarantined record (%s) is now "
          "wrongly flagged" % UNOWNED_REVIEWED,
          not ok_mut and UNOWNED_REVIEWED in bad_mut,
          "mutated stdout=%r" % r_mut.stdout.strip()[:300])

# ---- 3. Mutation-test the FIXTURE: quarantine the planted finding, prove silence is noticed -----
# Same fixture, in place: dddd000004 gets custody_reviewed_at stamped (what a human `quarantine`
# call does), so all four records are now clean. The REAL (unmutated) script must flip to exit 0.
shutil.copytree(FIXTURE, CLEAN_FIXTURE)
with open(os.path.join(CLEAN_FIXTURE, UNOWNED_UNREVIEWED, "meta.json"), encoding="utf-8") as f:
    m = json.load(f)
m["custody_reviewed_at"] = 1700000099
with open(os.path.join(CLEAN_FIXTURE, UNOWNED_UNREVIEWED, "meta.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(m))

check("mutated fixture still holds all four records (silence must mean 'clean', not 'empty')",
      len(os.listdir(CLEAN_FIXTURE)) == 5,  # 4 records + users.json
      "entries=%r" % sorted(os.listdir(CLEAN_FIXTURE)))

r_clean = run_tripwire(SCRIPT, CLEAN_FIXTURE)
check("SILENCE NOTICED: once the planted finding is quarantined, the real script exits 0 and "
      "explicitly reports 0 findings (not merely 'no crash') -- the same script that alarmed "
      "in step 1 on the unmutated fixture",
      r_clean.returncode == 0 and "clean (0 unowned-and-unreviewed" in r_clean.stdout,
      "exit=%s stdout=%r" % (r_clean.returncode, r_clean.stdout.strip()[:200]))

print(("FAILED: " + "; ".join(fails)) if fails else "custody tripwire selfcheck: all clear")
sys.exit(1 if fails else 0)
