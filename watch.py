#!/usr/bin/env python3
"""mdreview watcher: auto-pick-up the handoff baton (MR-056 loop core + MR-057 launcher, C2).

A stdlib-only sibling of mcp_server.py, run where the operator's agent runs. It long-polls the
service's C1 /wait endpoint for reviews newly flipped to turn==agent (the "Send to agent" baton),
claims each review's cooperative lease (POST /handoff {state:working}), and — on a winning claim —
spawns the operator's configured launch command (default Claude headless). It is a CREDENTIALED
process spawner, so its load-bearing safety property is the fail-closed trusted-base check (Step 0):
it refuses to start against a base it cannot vouch for, rather than warn-and-continue.

The launch mechanism is a GENERIC, operator-configured command template (WC-2): the loop only knows
"spawn this argv with this env." Nothing Claude-specific lives in the loop — env is the entire
interface (REVIEW_ID / MDREVIEW_BASE / MDREVIEW_OWNER, Step 4). That genericity is exactly what lets
the tests drive a stub launch command instead of a real model.

Crash model (B1, verified against app.py:629-636): a child that exits before `hand_back` STRANDS its
review at turn==agent. The server bumps `turn_updated` only on a real reviewer->agent flip, NOT on a
{state:working} lease write, so the edge-triggered /wait?since=cursor never re-surfaces a stranded
review. The watcher therefore does NOT auto-relaunch — it reaps + logs the exit and moves on. The
failure mode is a fail-safe UNDER-spawn (the human recovers via the 180s stale banner, or a
--backlog/restart re-seed), not a relaunch storm. C2 has no crash-retry by design; the per-review
attempt cap for paths where relaunches DO happen is C3.

NOT containerized, NOT imported by app.py, NOT started by compose. `python3 watch.py` is the only
way it runs (mirrors `MDREVIEW_BASE=… python3 mcp_server.py`).

Config (all env, stdlib-idiomatic):
  MDREVIEW_BASE              service base url (default http://localhost:8137, same as mcp_server.py)
  WATCH_TRUSTED_BASE        operator's explicit vouch; EXACT-match of MDREVIEW_BASE allows a
                            non-loopback base. Unset => loopback only. (No wildcard/prefix. C3
                            adds the relaxation.)
  WATCH_OWNER               stable lease owner id; default pid-derived (see _watcher_id / WC-5)
  WATCH_SINCE               "0" (or --backlog) to opt into the existing agent-turn backlog; default=now
  WATCH_WAIT_TIMEOUT_S      client long-poll timeout (default 25; server caps it to its WAIT_TIMEOUT_S)
  WATCH_LAUNCH_CMD          launch command, argv via a JSON array (preferred) or a shlex string;
                            spawned WITHOUT a shell. Unset => DEFAULT_LAUNCH_CMD (Claude headless).
  WATCH_MAX_CONCURRENT      max simultaneous live children (default 3); enforced BEFORE the claim.
  WATCH_MAX_LAUNCHES_PER_HOUR  rolling 3600s spawn cap (default 30); at the cap, defer (no claim).
"""
import collections
import json
import os
import shlex
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("MDREVIEW_BASE", "http://localhost:8137").rstrip("/")
WAIT_TIMEOUT_S = float(os.environ.get("WATCH_WAIT_TIMEOUT_S", "25"))
NET_BACKOFF_S = 2.0     # bounded backoff on a network error (re-poll the SAME cursor)
CAP_BACKOFF_S = 5.0     # bounded backoff while at capacity (the WC-3 fallback; pending-set is default)

MAX_CONCURRENT = int(os.environ.get("WATCH_MAX_CONCURRENT", "3"))
MAX_LAUNCHES_PER_HOUR = int(os.environ.get("WATCH_MAX_LAUNCHES_PER_HOUR", "30"))
LAUNCH_WINDOW_S = 3600.0

# Default launch command when WATCH_LAUNCH_CMD is unset. Claude headless, reading the child env
# contract (REVIEW_ID/MDREVIEW_BASE/MDREVIEW_OWNER) — the ONLY Claude-specific knowledge in this
# file, and it lives in a constant, never in the loop. Operators override via WATCH_LAUNCH_CMD.
DEFAULT_LAUNCH_CMD = [
    "claude", "-p",
    "You are the mdreview handoff agent. The review id is in $REVIEW_ID, the service base in "
    "$MDREVIEW_BASE, your lease owner id in $MDREVIEW_OWNER. Renew the lease with ping_working, "
    "read the open comments, apply the requested edits via update_source, resolve what you "
    "addressed, then hand_back to the reviewer.",
]


# ---- Step 0: fail-closed trusted-base check (the security crux) ----
def check_trusted_base(base):
    """Return True iff `base` is provably trusted. EXACT membership / EXACT string match — never a
    substring test (so localhost.evil.com is refused). Unset WATCH_TRUSTED_BASE => loopback only."""
    host = urllib.parse.urlparse(base).hostname   # "localhost", "127.0.0.1", "::1", or a real host
    trust = os.environ.get("WATCH_TRUSTED_BASE")
    if not trust:
        # default-allow LOOPBACK ONLY. ::1 is the IPv6 loopback urlparse yields for an [::1] base.
        return host in ("localhost", "127.0.0.1", "::1")
    # explicit vouch: EXACT string match of the full normalized base. No wildcard, no prefix.
    return trust.rstrip("/") == base


def require_trusted_base_or_exit(base):
    """Run the Step 0 check BEFORE any network call; refuse-and-exit (sys.exit(2)) on failure.

    The refusal names BOTH MDREVIEW_BASE (the actual) and WATCH_TRUSTED_BASE (the vouch, or
    "(unset)") [WC-1] so a brittle exact-match mismatch (http vs https, :443 vs bare,
    localhost vs 127.0.0.1) is self-explaining. The fix for a paper-cut mismatch is the better
    message, NOT a looser comparand — the strictness IS the control. No bypass env (C3's relaxation)."""
    if check_trusted_base(base):
        return
    trust = os.environ.get("WATCH_TRUSTED_BASE") or "(unset)"
    sys.stderr.write(
        "watch.py refusing to start: untrusted base.\n"
        "  MDREVIEW_BASE=%s does not match WATCH_TRUSTED_BASE=%s\n"
        "  (unset => loopback only: localhost/127.0.0.1/::1; otherwise an EXACT match is required.)\n"
        % (base, trust)
    )
    sys.exit(2)


# ---- HTTP helper: branch on status, do NOT raise on 409 ----
def _http(method, path, body=None, timeout=None):
    """Return (status, parsed_body). Unlike mcp_server.py's http(), this catches HTTPError and
    returns its (.code, body) so a 409 from the lease claim is a normal skip signal, not an
    exception. Raises only on a real transport failure (URLError), which the loop backs off on."""
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.code, _parse(r.read())
    except urllib.error.HTTPError as e:
        # HTTPError carries .code and is itself a readable response — a 409 is a normal signal here.
        return e.code, _parse(e.read())


def _parse(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


# ---- watcher id (stable per process; distinct across processes) ----
def _watcher_id():
    """owner = WATCH_OWNER if set, else pid-derived, computed ONCE at startup.

    WC-5: a pid-derived id changes on RESTART, so a restarted watcher does NOT own its predecessor's
    leases — a still-live child renewing under the OLD MDREVIEW_OWNER is foreign to the new watcher,
    which 409s and skips that review (correct: no double-spawn of a live in-flight child). Recovery
    rides the child's own MDREVIEW_OWNER renewal + the MR-055 stale-takeover, not an assumed ownership.
    A set WATCH_OWNER persists across restart (the operator's choice, not the default)."""
    env = os.environ.get("WATCH_OWNER")
    if env:
        return env
    return "watch-%s-%d" % (socket.gethostname(), os.getpid())


OWNER = _watcher_id()


# ---- in-flight children + caps (Step 5) ----
# _inflight: live child Popen handles, keyed by review id (the concurrency cap + reaping).
# _launch_times: a rolling-window deque of spawn timestamps (the launches/hour cap). Both are
# single-threaded state of the one poll loop, so no locking is needed.
_inflight = {}                       # review_id -> Popen
_launch_times = collections.deque()  # spawn timestamps, oldest first


def _reap():
    """Collect finished children: remove them from the in-flight set (freeing a concurrency slot)
    and log the exit code. The watcher does NOT re-flip, re-claim, or relaunch — a child that exited
    before hand_back STRANDS its review at turn==agent (B1), which the edge-triggered /wait never
    re-surfaces, so reaping is the whole of the watcher's lifecycle duty. Recovery is the human (the
    180s stale banner) or a --backlog/restart re-seed, never an auto-relaunch."""
    for rid, proc in list(_inflight.items()):
        code = proc.poll()
        if code is None:
            continue                 # still running
        del _inflight[rid]
        if code == 0:
            print("child for review %s exited 0 (reaped)" % rid)
        else:
            # A non-zero exit is logged but NOT retried. If the child handed back before dying the
            # baton is already with the reviewer; if it crashed before hand_back the baton is
            # stranded at turn==agent (B1) and recovery is the human / a backlog re-seed.
            print("child for review %s exited %s (reaped; no relaunch — see crash model B1)"
                  % (rid, code))


def _at_capacity():
    """At capacity iff the concurrency cap OR the rolling launches/hour cap is hit. Reap first so a
    just-finished child frees its slot, and evict stale launch timestamps so the hourly window slides.

    The caps bound NORMAL-load spend — many DISTINCT reviews flipped to agent — and are a cheap
    backstop. They do NOT bound a "crash-loop": under C2's edge-triggered design a crashed child
    strands (under-spawn, B1), it does not relaunch, so there is no storm to bound. The only
    repeated-relaunch path is a --backlog/restart re-seed, bounded by restart frequency. The
    per-review attempt cap (for paths where relaunches DO happen) is C3."""
    _reap()
    if len(_inflight) >= MAX_CONCURRENT:
        return True
    cutoff = time.time() - LAUNCH_WINDOW_S
    while _launch_times and _launch_times[0] < cutoff:
        _launch_times.popleft()
    return len(_launch_times) >= MAX_LAUNCHES_PER_HOUR


# ---- launch template parsing (WC-2: argv, NEVER a shell) ----
def _launch_argv():
    """Resolve WATCH_LAUNCH_CMD to an argv list: a JSON array (preferred) or a shlex-split string.
    Unset => DEFAULT_LAUNCH_CMD. The result is spawned WITHOUT a shell (no shell=True, no id
    interpolation into a command string) — env is the interface, so the template needs no
    placeholder."""
    raw = os.environ.get("WATCH_LAUNCH_CMD")
    if not raw:
        return list(DEFAULT_LAUNCH_CMD)
    try:
        argv = json.loads(raw)
        if not isinstance(argv, list):
            raise ValueError
        return argv
    except ValueError:
        return shlex.split(raw)


# ---- spawn the launch command with the child env contract (Step 4) ----
def _spawn(review_id):
    """Spawn the launch command for `review_id`, non-blocking, tracked. The child env contract:
    REVIEW_ID (which review), MDREVIEW_BASE (same service), MDREVIEW_OWNER (the watcher's OWNER that
    just won the lease — so the child's ping_working is a same-owner 200, not a foreign 409). The
    child owns the heartbeat (it renews the lease per the MR-053 agent contract); the watcher does
    NOT run per-child renewal timers — it only tracks the Popen for the cap + reaping."""
    child_env = dict(os.environ)
    child_env["REVIEW_ID"] = review_id
    child_env["MDREVIEW_BASE"] = BASE
    child_env["MDREVIEW_OWNER"] = OWNER          # winning owner: child renews the SAME lease
    proc = subprocess.Popen(_launch_argv(), env=child_env)   # non-blocking; never shell=True
    _inflight[review_id] = proc
    _launch_times.append(time.time())
    print("spawned child for review %s (owner=%s pid=%d, inflight=%d)"
          % (review_id, OWNER, proc.pid, len(_inflight)))
    return proc


# ---- Step 3: claim-before-spawn (single-flight) ----
def handle(review_id):
    """Caps-check FIRST, then claim the lease, then spawn ONLY on a 200. Returns True if spawned.

    A 409 is another owner (or a stale-but-reclaimed lease) — SKIP, do not spawn (normal, not an
    error). Any other non-200 is logged and skipped."""
    if _at_capacity():
        print("at capacity, deferring review %s (pending)" % review_id)
        return False   # caller holds it in the pending set; cursor still advances (WC-3)
    status, body = _http("POST", "/api/reviews/%s/handoff" % review_id,
                         {"state": "working", "owner": OWNER}, timeout=WAIT_TIMEOUT_S + 5)
    if status == 200:
        _spawn(review_id)
        return True
    if status == 409:
        print("review %s lease held by %s — skip" % (review_id, (body or {}).get("owner")))
        return False
    print("review %s claim failed (HTTP %s) — skip" % (review_id, status))
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
    print("watch.py: owner=%s base=%s cursor=%.3f (backlog=%s)"
          % (OWNER, BASE, cursor, cursor == 0.0))
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
            print("wait error (%s) — backing off %.0fs, cursor unchanged" % (e.reason, NET_BACKOFF_S))
            _drain_pending(pending)
            time.sleep(NET_BACKOFF_S)
            continue

        if status != 200:
            print("wait got HTTP %s — backing off %.0fs" % (status, NET_BACKOFF_S))
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
            if rid and not handle(rid):
                if _at_capacity():
                    pending.add(rid)       # retry as slots free, not via an un-advanced cursor
        _drain_pending(pending)


def _drain_pending(pending):
    """Retry capacity-skipped reviews as slots free (WC-3 default). With the MR-056 stub _at_capacity()
    this is a no-op; the seam exists so MR-057's real caps drain cleanly without a /wait busy-spin."""
    if not pending or _at_capacity():
        return
    for rid in list(pending):
        if _at_capacity():
            break
        if handle(rid):
            pending.discard(rid)


def main():
    require_trusted_base_or_exit(BASE)   # Step 0: FIRST, before any network call. Refuse-and-exit.
    try:
        run()
    except KeyboardInterrupt:
        print("watch.py: stopped")


if __name__ == "__main__":
    main()
