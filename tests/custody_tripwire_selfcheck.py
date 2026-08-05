#!/usr/bin/env python3
"""Custody slice 6a (#361) selfcheck: the unowned-record tripwire, against a synthetic fixture.

The predicate (#272, stable): a record is unowned-and-unreviewed when `owner == ""` AND
`custody_reviewed_at` is unset. scripts/custody_tripwire.py flags exactly those records and
exits non-zero when it finds any. This proves four things, none of them "it ran without
crashing":

  1. Real behaviour on a synthetic fixture covering all four owned/reviewed combinations --
     exit code AND what gets reported -- for EACH combination, not just the aggregate. Only the
     unowned+unreviewed combination is a finding; the other three must never be flagged (a
     tripwire that cries wolf on normal records gets ignored, per the ticket). Also asserts the
     script is read-only: every meta.json is byte-identical after the scan.

  2. Mutation-testing the predicate, owner-half intact: scripts/custody_tripwire.py is patched
     to drop the custody_reviewed_at half (the predicate degrades to owner=="" alone -- the
     exact pre-#272 bug #272's own description calls out). Run against the SAME fixture, the
     SAME "no false positives" assertion this file uses for the real script now evaluates
     False, because the quarantined record (unowned+reviewed, cccc000003) gets wrongly flagged.

  3. Mutation-testing the predicate, custody_reviewed_at-half intact: the mirror mutation --
     find_findings is replaced with a version that ignores `owner` and flags on
     custody_reviewed_at alone. The owned+unreviewed record (bbbb000002) now gets wrongly
     flagged. Together, 2 and 3 show the check catches EITHER half of the predicate going
     missing, by name, not merely noting the script still runs.

  4. Mutation-testing the fixture: the planted finding (dddd000004) is quarantined in place
     (custody_reviewed_at stamped, exactly what a human `quarantine` call would do), so nothing
     in the fixture matches any more. The exact same "fires on the planted record" assertion
     used in step 1 is re-run against this clean fixture and asserted to now be FALSE -- the
     identical check going red on a silenced tripwire, not a fresh always-green condition. The
     "exit 0 / explicitly reports 0 findings" true-negative is asserted alongside it, and a
     guard against the degenerate "clean because empty" reading: the mutated fixture is
     asserted to still hold all four records.

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


def fires_on_planted_record(result):
    """True iff the run correctly alarmed on exactly the planted unowned-and-unreviewed record:
    non-zero exit, the count says 1, and the finding's rid is named. Reused verbatim in step 4 --
    the SAME assertion, pointed at a fixture where the planted record was quarantined, must flip
    to False, or this check would not notice a tripwire that stopped firing."""
    ok = (result.returncode == 1
          and "1 unowned-and-unreviewed record" in result.stdout
          and UNOWNED_UNREVIEWED in result.stdout)
    return ok, "exit=%s stdout=%r" % (result.returncode, result.stdout.strip()[:200])


def snapshot(base):
    return {rid: open(os.path.join(base, rid, "meta.json"), "rb").read() for rid in ALL_RIDS}


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
before_snap = snapshot(FIXTURE)

# ---- 1. Real behaviour: exit code AND report content, for each of the four fixture shapes ------
r = run_tripwire(SCRIPT, FIXTURE)

fires_ok, fires_detail = fires_on_planted_record(r)
check("fires on the planted record: exit 1, count says 1, names the finding (%s)"
      % UNOWNED_UNREVIEWED, fires_ok, fires_detail)

check("does NOT flag the owned+reviewed record (%s)" % OWNED_REVIEWED,
      OWNED_REVIEWED not in r.stdout, r.stdout.strip()[:200])

check("does NOT flag the owned+unreviewed record (%s)" % OWNED_UNREVIEWED,
      OWNED_UNREVIEWED not in r.stdout, r.stdout.strip()[:200])

check("does NOT flag the unowned+reviewed/quarantined record (%s)" % UNOWNED_REVIEWED,
      UNOWNED_REVIEWED not in r.stdout, r.stdout.strip()[:200])

ok, bad = no_false_positives(r.stdout)
check("no false positives overall (the 'no false positives' assertion mutation tests reuse below)",
      ok, "wrongly flagged: %r" % bad)

check("stray non-record file at the data-dir root (users.json) does not crash the scan",
      r.returncode in (0, 1), "exit=%s stderr=%r" % (r.returncode, r.stderr.strip()[:200]))

after_snap = snapshot(FIXTURE)
check("read-only: all four meta.json files are byte-identical after the scan",
      before_snap == after_snap,
      "changed=%r" % [rid for rid in ALL_RIDS if before_snap[rid] != after_snap[rid]])

# ---- 2. Mutation-test the PREDICATE, owner-half intact: drop the custody_reviewed_at half -------
# This is the pre-#272 bug verbatim: with the field ignored, "unowned" alone is the whole
# predicate, so the quarantined record (reviewed, deliberately left unowned) becomes a false
# positive it must never be.
with open(SCRIPT, encoding="utf-8") as f:
    original_src = f.read()

RETURN_NEEDLE = '    return [r for r in rec.unowned() if not r["custody_reviewed_at"]]'
GUARD_NEEDLE = 'if __name__ == "__main__":'
if RETURN_NEEDLE not in original_src or GUARD_NEEDLE not in original_src:
    check("mutation harness: expected anchors found in scripts/custody_tripwire.py "
          "(script changed -- update this check's needles)", False)
else:
    mutated_src_a = original_src.replace(
        RETURN_NEEDLE,
        '    return list(rec.unowned())  # MUTATED (#361 selfcheck): dropped custody_reviewed_at')
    MUTATED_SCRIPT_A = os.path.join(SCRATCH, "mutated_drop_reviewed_at.py")
    with open(MUTATED_SCRIPT_A, "w", encoding="utf-8") as f:
        f.write(mutated_src_a)

    r_mut_a = run_tripwire(MUTATED_SCRIPT_A, FIXTURE)
    ok_mut_a, bad_mut_a = no_false_positives(r_mut_a.stdout)
    check("MUTATION CAUGHT (predicate, dropped custody_reviewed_at): the SAME 'no false "
          "positives' assertion fails by name -- the quarantined record (%s) is now wrongly "
          "flagged" % UNOWNED_REVIEWED,
          not ok_mut_a and UNOWNED_REVIEWED in bad_mut_a,
          "mutated stdout=%r" % r_mut_a.stdout.strip()[:300])

    # ---- 3. Mirror mutation, custody_reviewed_at-half intact: drop the owner=="" half ------------
    # find_findings is replaced wholesale (inserted right before the __main__ guard, so its later
    # definition wins in the module namespace) with a version that scans every record and flags on
    # custody_reviewed_at alone. The owned+unreviewed record must now be a false positive.
    mutated_find_findings = (
        'def find_findings(data_dir):  # MUTATED (#361 selfcheck): dropped owner==""\n'
        '    from mdreview.store import Store\n'
        '    store = Store(data_dir)\n'
        '    out = []\n'
        '    for rid in os.listdir(data_dir):\n'
        '        if not store.exists(rid):\n'
        '            continue\n'
        '        m = store.read_json(os.path.join(store.dir(rid), "meta.json"), {})\n'
        '        if not m.get("custody_reviewed_at"):\n'
        '            out.append({"rid": rid, "title": m.get("title", ""),\n'
        '                        "created": m.get("created", 0)})\n'
        '    return out\n\n\n')
    mutated_src_b = original_src.replace(GUARD_NEEDLE, mutated_find_findings + GUARD_NEEDLE)
    MUTATED_SCRIPT_B = os.path.join(SCRATCH, "mutated_drop_owner.py")
    with open(MUTATED_SCRIPT_B, "w", encoding="utf-8") as f:
        f.write(mutated_src_b)

    r_mut_b = run_tripwire(MUTATED_SCRIPT_B, FIXTURE)
    ok_mut_b, bad_mut_b = no_false_positives(r_mut_b.stdout)
    check("MUTATION CAUGHT (predicate, dropped owner==\"\"): the SAME 'no false positives' "
          "assertion fails by name -- the owned+unreviewed record (%s) is now wrongly flagged"
          % OWNED_UNREVIEWED,
          not ok_mut_b and OWNED_UNREVIEWED in bad_mut_b,
          "mutated stdout=%r" % r_mut_b.stdout.strip()[:300])

# ---- 4. Mutation-test the FIXTURE: quarantine the planted finding, prove silence is noticed -----
# Same fixture, in place: dddd000004 gets custody_reviewed_at stamped (what a human `quarantine`
# call does), so all four records are now clean. The exact same fires_on_planted_record assertion
# used in step 1 is re-run here and must flip to False -- this check going red on a silenced
# tripwire, not a fresh always-green condition standing in for it.
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
silent_fires_ok, silent_detail = fires_on_planted_record(r_clean)
check("SILENCE NOTICED: the SAME 'fires on the planted record' assertion from step 1 fails by "
      "name once the planted record is quarantined -- proves this check would catch a tripwire "
      "that stopped firing, not just one that fires on the wrong thing",
      not silent_fires_ok, silent_detail)

check("true negative: the now-clean fixture exits 0 and explicitly reports 0 findings (not "
      "merely 'no crash')",
      r_clean.returncode == 0 and "clean (0 unowned-and-unreviewed" in r_clean.stdout,
      "exit=%s stdout=%r" % (r_clean.returncode, r_clean.stdout.strip()[:200]))

print(("FAILED: " + "; ".join(fails)) if fails else "custody tripwire selfcheck: all clear")
sys.exit(1 if fails else 0)
