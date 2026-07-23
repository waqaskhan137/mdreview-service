#!/usr/bin/env python3
"""tests/comment_bid_smoke.py  (issue #15)

The content-derived block id (`bid`) must round-trip through CommentService.create and be validated
to a selector-safe charset before storage. `bid` is what lets a whole-block comment re-anchor by
CONTENT after a live-reload renumber (see web/app/viewer.html); the backend must persist it (else the
fix is inert) and must reject an injected bid, since the viewer looks it up via `.blk[data-bid="…"]`
and a stray quote would break that selector. Exit 0 pass, 1 fail. No server, no network.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mdreview.store import Store              # noqa: E402
from mdreview.comments import CommentService  # noqa: E402

_fails = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _fails.append(label)


def stored_anchor(svc, rid, anchor):
    """create() then read the persisted comment back off disk (not the in-memory return)."""
    svc.create(rid, anchor, "note")
    return svc.list(rid)[-1]["anchor"]

BASE = {"quoted_text", "block_num", "start", "end"}


def main():
    store = Store(tempfile.mkdtemp())
    rid = "r" * 10
    os.makedirs(store.dir(rid), exist_ok=True)
    svc = CommentService(store)

    a = stored_anchor(svc, rid, {"quoted_text": "", "block_num": "5", "bid": "3da4139"})
    check("valid hex bid persists", a.get("bid") == "3da4139")
    check("valid-bid anchor = 4 base fields + bid", set(a) == BASE | {"bid"})
    check("bid with duplicate -N suffix persists", stored_anchor(svc, rid, {"bid": "811c9dc5-2"}).get("bid") == "811c9dc5-2")
    check("injected bid (contains quote) dropped -> key absent", "bid" not in stored_anchor(svc, rid, {"bid": 'a" onx'}))
    check("garbage bid dropped -> key absent", "bid" not in stored_anchor(svc, rid, {"bid": "ZZZ; drop"}))
    # the additive-default-safe property: a comment with no bid is byte-identical to the old 4-field anchor
    check("no bid -> unchanged 4-field anchor", set(stored_anchor(svc, rid, {"quoted_text": "", "block_num": "3"})) == BASE)

    if _fails:
        print("FAILED: %d" % len(_fails))
        return 1
    print("PASS: bid round-trip + sanitize + anchor whitelist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
