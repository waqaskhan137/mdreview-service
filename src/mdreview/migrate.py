"""Backfill `owner` on existing owner-less reviews so they survive the Phase 1 fail-closed
can_access gate. Idempotent: only sets owner where it is missing. Run ONCE before flipping
MDREVIEW_REQUIRE_AUTH on an instance that already has pre-auth reviews, or those reviews 404 for
everyone.

Usage:  python -m mdreview.migrate <owner_user_id>
        owner_user_id = the canonical provider:sub (e.g. google:100706495352040931339).
"""
import json
import os
import sys

from mdreview.config import DATA_DIR
from mdreview.store import Store


def backfill_owner(store, owner_id):
    """Set owner=owner_id on every review dir that has no owner. Returns (changed, skipped)."""
    changed = skipped = 0
    for rid in os.listdir(store.data_dir):
        if not store.exists(rid):
            continue
        p = os.path.join(store.dir(rid), "meta.json")
        m = store.read_json(p, {})
        if m.get("owner"):
            skipped += 1
            continue
        m["owner"] = owner_id
        store.write_text(p, json.dumps(m))
        changed += 1
    return changed, skipped


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not argv[0].strip():
        print("usage: python -m mdreview.migrate <owner_user_id>", file=sys.stderr)
        return 2
    changed, skipped = backfill_owner(Store(DATA_DIR), argv[0].strip())
    print("backfill: owner=%s set on %d review(s), %d already owned" % (argv[0].strip(), changed, skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
