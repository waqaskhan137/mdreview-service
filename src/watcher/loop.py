"""The poll loop: seed a cursor, long-poll /wait for turn==agent flips, claim-before-spawn each hit.

handle() is single-flight (caps-check, then claim the lease, then spawn ONLY on a 200); run() drives
the edge-triggered /wait cursor and the WC-3 pending set (capacity-skipped reviews retried as slots
free, never via a busy-spun cursor). The two terminal gates (arming, per-review cap) skip BEFORE any
claim so the cursor advances without entering `pending`.
"""
import os
import sys
import time
import urllib.error

from .arming import _is_armed
from .config import ATTEMPT_WINDOW_S, BASE, MAX_ATTEMPTS_PER_REVIEW, NET_BACKOFF_S, OWNER, WAIT_TIMEOUT_S, log
from .http import _http
from .spawn import _at_capacity, _per_review_capped, _reap, _spawn


# ---- Step 3: claim-before-spawn (single-flight) ----
def handle(review_id):
    """Caps-check FIRST, then claim the lease, then spawn ONLY on a 200. Returns True if spawned.

    A 409 is another owner (or a stale-but-reclaimed lease) — SKIP, do not spawn (normal, not an
    error). Any other non-200 is logged and skipped."""
    if _at_capacity():
        log.info("at capacity, deferring review %s (pending)", review_id)
        return False   # caller holds it in the pending set; cursor still advances (WC-3)
    status, body = _http("POST", "/api/reviews/%s/handoff" % review_id,
                         {"state": "working", "owner": OWNER}, timeout=WAIT_TIMEOUT_S + 5)
    if status == 200:
        _spawn(review_id)
        return True
    if status == 409:
        log.info("review %s lease held by %s — skip", review_id, (body or {}).get("owner"))
        return False
    log.warning("review %s claim failed (HTTP %s) — skip", review_id, status)
    return False


# ---- Step 1+2: seed the cursor, long-poll, advance ----
def seed_cursor():
    """Default seed = now, so the watcher only acts on flips AFTER it starts (no startup stampede).
    WATCH_SINCE=0 / --backlog is the off-by-default opt-in to process the existing agent-turn backlog."""
    if os.environ.get("WATCH_SINCE") == "0" or "--backlog" in sys.argv:
        return 0.0
    return time.time()


def run():
    cursor = seed_cursor()
    pending = set()   # WC-3: reviews skipped at capacity, drained as slots free (not a /wait re-spin)
    log.info("owner=%s base=%s cursor=%.3f (backlog=%s)", OWNER, BASE, cursor, cursor == 0.0)
    while True:
        try:
            status, body = _http(
                "GET",
                "/api/reviews/wait?turn=agent&since=%s&timeout=%s" % (cursor, WAIT_TIMEOUT_S),
                timeout=WAIT_TIMEOUT_S + 5,
            )
        except urllib.error.URLError as e:
            # network error: log, bounded backoff, re-poll the SAME cursor (never advance past an
            # unprocessed edge — the cursor is the watcher's only durable position).
            log.warning("wait error (%s) — backing off %.0fs, cursor unchanged", e.reason, NET_BACKOFF_S)
            _drain_pending(pending)
            time.sleep(NET_BACKOFF_S)
            continue

        if status != 200:
            log.warning("wait got HTTP %s — backing off %.0fs", status, NET_BACKOFF_S)
            time.sleep(NET_BACKOFF_S)
            continue

        rows = body.get("reviews", [])
        if not rows:                       # timeout ({"reviews":[],"timeout":true})
            _reap()                        # collect finished children, freeing concurrency slots
            _drain_pending(pending)        # use the idle tick to retry capacity-skipped reviews
            continue                       # re-poll, cursor UNCHANGED

        # Hit: advance the cursor past everything seen, then handle each (WC-3: we advance even for
        # capacity-skipped rows and hold them in `pending`, so /wait is never busy-spun on a stale edge).
        cursor = max([cursor] + [r.get("turn_updated", 0) for r in rows])
        for r in rows:
            rid = r.get("id")
            if not rid:
                continue
            if not _is_armed(rid):
                # C3 W1: TERMINAL skip BEFORE handle() — never claims a lease, never the caps, and
                # NEVER enters `pending` (the cursor already advanced, so /wait won't busy-spin; a
                # later re-Send is a fresh turn_updated flip /wait re-surfaces on its own).
                log.info("review %s not armed — skip (no claim)", rid)
                continue
            if _per_review_capped(rid):
                # C3 W1: SECOND terminal gate, after arming and before handle() — same no-claim,
                # no-`pending` discipline as the arming skip. This bounds the RE-SEND / RE-SURFACE
                # loop (one review repeatedly flipped back to turn==agent), NOT a crash-loop (a
                # crashed child strands and is never auto-relaunched). The cursor already advanced;
                # a later re-Send AFTER the window slides is a fresh edge /wait re-surfaces on its own.
                log.info("review %s at per-review cap (%d spawns / %.0fs window) — skip (no claim); "
                         "bounding the re-Send/re-surface loop, not a crash-loop",
                         rid, MAX_ATTEMPTS_PER_REVIEW, ATTEMPT_WINDOW_S)
                continue
            if not handle(rid):           # C2, UNCHANGED: only capacity/409/error reach here
                if _at_capacity():
                    pending.add(rid)       # retry as slots free, not via an un-advanced cursor
        _drain_pending(pending)


def _drain_pending(pending):
    """Retry capacity-skipped reviews as slots free (WC-3 default), so a review deferred at the
    concurrency/hourly cap is re-claimed when a child exits — not left to a /wait busy-spin."""
    if not pending or _at_capacity():
        return
    for rid in list(pending):
        if _at_capacity():
            break
        if handle(rid):
            pending.discard(rid)
