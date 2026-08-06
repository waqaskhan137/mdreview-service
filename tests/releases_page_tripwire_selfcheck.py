#!/usr/bin/env python3
"""releases page pipeline selfcheck (#373): proves the tripwire actually works, against a
synthetic fixture -- no network, no live GitHub state. Matches the standard
tests/custody_tripwire_selfcheck.py set for this project: real behaviour on a fixture, then two
mutations, each required to change a NAMED assertion's outcome, not merely "the script still ran".

  1. Real behaviour: scripts/gen_releases_page.py, run through its actual CLI (offline
     --releases-file mode) against a synthetic 3-release fixture, produces a page the REAL
     scripts/releases_page_tripwire.py calls clean -- and names the newest tag doing it.

  2. MUTATION A -- break the generator so the page is stale: render_page's sort direction is
     flipped (reverse=True -> reverse=False), the exact shape of bug that produced the real
     v0.2.0-while-v0.5.3-runs incident this issue reports (oldest leads instead of newest). Run
     THROUGH THE SAME CLI against the SAME fixture. The REAL (unmutated) tripwire, given this
     stale page, must fail -- by name: it must name the newest fixture tag as the reason, not
     merely return nonzero.

  3. MUTATION B -- neuter the tripwire itself: the check() comparison is patched to report clean
     unconditionally. Run against the EXACT stale page from mutation A -- the same input the real
     tripwire correctly rejected. The neutered tripwire must now wrongly pass it, and this
     selfcheck must notice that: the SAME "does it correctly flag this stale page" assertion used
     in step 2 is reused here and must flip from catching to silently passing (the #361
     technique) -- proving this selfcheck would notice the tripwire going silent, not just that
     the happy path stays green.

Run: python3 tests/releases_page_tripwire_selfcheck.py
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPTS = os.path.join(REPO, "scripts")
GEN_SCRIPT = os.path.join(SCRIPTS, "gen_releases_page.py")
TRIPWIRE_SCRIPT = os.path.join(SCRIPTS, "releases_page_tripwire.py")
SCRATCH = os.path.join(REPO, ".scratch", "releases_page_tripwire_check")

REPO_SLUG = "acme/widget"
OLDEST_TAG = "v1.0.0"
MIDDLE_TAG = "v1.1.0"
NEWEST_TAG = "v1.2.0"


def build_fixture():
    """Three releases, oldest to newest by published_at. Only NEWEST_TAG is the "must lead the
    page" release; the other two exist so sort-order bugs have something to sort wrong."""
    def rel(tag, published_at):
        return {
            "tag_name": tag,
            "name": "%s test release" % tag,
            "draft": False,
            "prerelease": False,
            "published_at": published_at,
            "html_url": "https://github.com/%s/releases/tag/%s" % (REPO_SLUG, tag),
            "body_html": "<p>Notes for %s.</p>" % tag,
        }
    return [
        rel(OLDEST_TAG, "2026-01-01T00:00:00Z"),
        rel(MIDDLE_TAG, "2026-02-01T00:00:00Z"),
        rel(NEWEST_TAG, "2026-03-01T00:00:00Z"),
    ]


def run_gen(script_path, releases_json_path, output_html_path):
    return subprocess.run(
        [sys.executable, script_path, output_html_path, "--releases-file", releases_json_path],
        cwd=REPO, capture_output=True, text=True, timeout=30,
    )


def run_tripwire(script_path, releases_json_path, page_html_path):
    return subprocess.run(
        [sys.executable, script_path, releases_json_path, page_html_path],
        cwd=REPO, capture_output=True, text=True, timeout=30,
    )


def flags_stale_by_name(result, tag):
    """True iff the tripwire correctly rejected a stale page: nonzero exit, output says STALE,
    and it names the specific tag that's missing/not-leading -- reused verbatim in mutation B, so
    that check flipping False there is the "silence noticed" signal."""
    ok = (result.returncode == 1
          and "STALE" in result.stdout
          and tag in result.stdout)
    return ok, "exit=%s stdout=%r" % (result.returncode, result.stdout.strip()[:300])


fails = []
def check(label, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)
        if detail:
            print("         " + detail)


shutil.rmtree(SCRATCH, ignore_errors=True)
os.makedirs(SCRATCH)

releases = build_fixture()
fixture_path = os.path.join(SCRATCH, "releases.json")
with open(fixture_path, "w", encoding="utf-8") as f:
    json.dump(releases, f)

# ---- 1. Real behaviour: real generator + real tripwire, synthetic fixture -----------------------
good_page = os.path.join(SCRATCH, "page_good.html")
r_gen = run_gen(GEN_SCRIPT, fixture_path, good_page)
check("generator CLI (offline --releases-file mode) exits 0", r_gen.returncode == 0,
      "stdout=%r stderr=%r" % (r_gen.stdout.strip(), r_gen.stderr.strip()[:300]))

r_check = run_tripwire(TRIPWIRE_SCRIPT, fixture_path, good_page)
check("real tripwire calls the real generator's output clean, names the newest tag (%s)"
      % NEWEST_TAG,
      r_check.returncode == 0 and "clean" in r_check.stdout and NEWEST_TAG in r_check.stdout,
      "exit=%s stdout=%r" % (r_check.returncode, r_check.stdout.strip()[:300]))

# ---- 2. MUTATION A: break the generator (sort direction flipped) so the page goes stale ---------
with open(GEN_SCRIPT, encoding="utf-8") as f:
    gen_src = f.read()

SORT_NEEDLE = 'sorted(releases, key=lambda r: r.get("published_at") or "", reverse=True)'
if SORT_NEEDLE not in gen_src:
    check("mutation harness: expected sort needle found in scripts/gen_releases_page.py "
          "(script changed -- update this check's needle)", False)
    stale_page = None
else:
    mutated_gen_src = gen_src.replace(
        SORT_NEEDLE,
        'sorted(releases, key=lambda r: r.get("published_at") or "", reverse=False)  '
        '# MUTATED (#373 selfcheck): oldest leads instead of newest')
    mutated_gen = os.path.join(SCRATCH, "mutated_gen_releases_page.py")
    with open(mutated_gen, "w", encoding="utf-8") as f:
        f.write(mutated_gen_src)

    stale_page = os.path.join(SCRATCH, "page_stale.html")
    r_gen_mut = run_gen(mutated_gen, fixture_path, stale_page)
    check("mutated generator still runs (produces a page, just the wrong one)",
          r_gen_mut.returncode == 0, "stderr=%r" % r_gen_mut.stderr.strip()[:300])

    r_tripwire_on_stale = run_tripwire(TRIPWIRE_SCRIPT, fixture_path, stale_page)
    ok_a, detail_a = flags_stale_by_name(r_tripwire_on_stale, NEWEST_TAG)
    check("MUTATION CAUGHT (generator sort flipped, oldest leads): the REAL tripwire fails by "
          "name -- names %s as stale, not just a nonzero exit" % NEWEST_TAG,
          ok_a, detail_a)

# ---- 3. MUTATION B: neuter the tripwire itself, point it at the SAME stale page ------------------
if stale_page is not None:
    with open(TRIPWIRE_SCRIPT, encoding="utf-8") as f:
        tripwire_src = f.read()

    CHECK_RETURN_NEEDLE = 'if present and leads:\n        return True, "newest release %s is represented and leads the page" % tag'
    NEUTER_NEEDLE = 'def main(argv=None):'
    if CHECK_RETURN_NEEDLE not in tripwire_src or NEUTER_NEEDLE not in tripwire_src:
        check("mutation harness: expected anchors found in scripts/releases_page_tripwire.py "
              "(script changed -- update this check's needles)", False)
    else:
        neutered_check = (
            'def check(releases, page_html):  # MUTATED (#373 selfcheck): always reports clean\n'
            '    return True, "MUTATED: always clean"\n\n\n')
        neutered_src = tripwire_src[:tripwire_src.index('def check(')] + neutered_check \
            + tripwire_src[tripwire_src.index(NEUTER_NEEDLE):]
        neutered_script = os.path.join(SCRATCH, "neutered_releases_page_tripwire.py")
        with open(neutered_script, "w", encoding="utf-8") as f:
            f.write(neutered_src)

        r_neutered = run_tripwire(neutered_script, fixture_path, stale_page)
        ok_b, detail_b = flags_stale_by_name(r_neutered, NEWEST_TAG)
        check("SILENCE NOTICED: the SAME 'flags stale by name' assertion from step 2 fails "
              "once the tripwire's check() is neutered -- proves this selfcheck would catch the "
              "tripwire going silent, not just that it fires once on a lucky path",
              not ok_b, detail_b)
        check("neutered tripwire exits 0 (wrongly) on the exact page the real one correctly "
              "rejected -- the false-clean this mutation exists to catch",
              r_neutered.returncode == 0 and "clean" in r_neutered.stdout,
              "exit=%s stdout=%r" % (r_neutered.returncode, r_neutered.stdout.strip()[:300]))

print(("FAILED: " + "; ".join(fails)) if fails else "releases page tripwire selfcheck: all clear")
sys.exit(1 if fails else 0)
