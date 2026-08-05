#!/usr/bin/env python3
"""Custody slice 6a (#361): the unowned-record tripwire.

Reports records matching the unowned-and-unreviewed predicate #272 shipped in reconcile.py:
`owner == ""` AND `custody_reviewed_at` is unset (never stamped by a human `confirm` or
`quarantine`). Delegates to Reconciler.unowned() -- reconcile.py's own predicate -- rather than
re-deriving it here, so this script and `python -m mdreview.reconcile list`'s "AWAITING REVIEW"
section can never drift apart. Read-only: it never writes a record.

Exit code IS the tripwire signal: 0 when clean, 1 when >=1 unowned-and-unreviewed record is
found, so it can be wired into a check later (#114, 6b).

Scope note (#361 vs #114): this is slice 6a only -- the script and its check
(tests/custody_tripwire_selfcheck.py), exercised against a synthetic fixture. It is not armed
anywhere: no default data dir, no $MDREVIEW_DATA fallback, no schedule. `<data_dir>` is a
required argument so this can never silently resolve to whatever data dir happens to be in the
caller's environment. Slice 6b (#114, blocked on #113) is baselining the known-legacy set and
wiring this against production; that is a deliberately separate, still-blocked piece of work.

Usage:
    python3 scripts/custody_tripwire.py <data_dir>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def find_findings(data_dir):
    """Records matching the #272 predicate (owner=="" AND custody_reviewed_at unset), newest
    first. `data_dir` is expected to be a real store layout (a directory of <rid>/meta.json
    subdirectories); the caller is responsible for pointing this at one.

    Imports mdreview.reconcile lazily, AFTER the caller has pointed MDREVIEW_DATA at this same
    data_dir (see main()): mdreview.config reads MDREVIEW_DATA and os.makedirs()s it as an
    IMPORT-TIME side effect, so importing at module load, before argv is parsed, would makedirs
    an unrelated default ("/data") instead of the directory this script was actually told to
    scan.
    """
    from mdreview.reconcile import Reconciler
    from mdreview.store import Store
    rec = Reconciler(Store(data_dir))
    return [r for r in rec.unowned() if not r["custody_reviewed_at"]]


def report(data_dir, findings):
    if not findings:
        print("custody tripwire: clean (0 unowned-and-unreviewed records in %s)" % data_dir)
        return
    print("custody tripwire: %d unowned-and-unreviewed record(s) in %s"
          % (len(findings), data_dir))
    for r in findings:
        print("  rid: %s  title=%r  created=%s" % (r["rid"], r["title"] or "(none)", r["created"]))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python3 scripts/custody_tripwire.py <data_dir>", file=sys.stderr)
        return 2
    data_dir = argv[0]
    if not os.path.isdir(data_dir):
        print("refused: not a directory: %s" % data_dir, file=sys.stderr)
        return 2

    # See find_findings' docstring: set BEFORE the deferred mdreview import, to the exact
    # directory we were told to scan (never a stale/inherited value), so config.py's import-time
    # os.makedirs(MDREVIEW_DATA) is a no-op on a directory that already exists, not a write to
    # some unrelated default.
    os.environ["MDREVIEW_DATA"] = data_dir

    findings = find_findings(data_dir)
    report(data_dir, findings)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
