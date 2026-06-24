#!/usr/bin/env python3
"""mdreview watcher: auto-pick-up the handoff baton (MR-056, C2 loop core).

A stdlib-only sibling of mcp_server.py, run where the operator's agent runs. It long-polls the
service's C1 /wait endpoint for reviews newly flipped to turn==agent (the "Send to agent" baton),
claims each review's cooperative lease (POST /handoff {state:working}), and — on a winning claim —
spawns a launch command. It is a CREDENTIALED process spawner, so its load-bearing safety property
is the fail-closed trusted-base check (Step 0): it refuses to start against a base it cannot vouch
for, rather than warn-and-continue.

MR-056 SCOPE: the fail-closed check, the /wait long-poll + cursor advance, and claim-before-spawn
single-flight, spawning a PLACEHOLDER command (WATCH_LAUNCH_CMD, default a no-op) so the claim/skip
logic is testable. The real generic launch template, child env contract, and caps are MR-057.

NOT containerized, NOT imported by app.py, NOT started by compose. `python3 watch.py` is the only
way it runs (mirrors `MDREVIEW_BASE=… python3 mcp_server.py`).

Config (all env, stdlib-idiomatic):
  MDREVIEW_BASE          service base url (default http://localhost:8137, same as mcp_server.py)
  WATCH_TRUSTED_BASE     operator's explicit vouch; EXACT-match of MDREVIEW_BASE allows a non-loopback
                         base. Unset => loopback only. (No wildcard/prefix. C3 adds the relaxation.)
  WATCH_OWNER            stable lease owner id; default pid-derived (see _watcher_id / WC-5)
  WATCH_SINCE            "0" (or --backlog) to opt into the existing agent-turn backlog; default = now
  WATCH_WAIT_TIMEOUT_S   client long-poll timeout (default 25; server caps it to its own WAIT_TIMEOUT_S)
  WATCH_LAUNCH_CMD       placeholder launch command (argv via json array or shlex; default no-op)
"""
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


# ---- caps stub (real caps are MR-057) ----
def _at_capacity():
    """MR-056 stub: never at capacity. MR-057 wires the real concurrency + launches/hour caps."""
    return False


# ---- placeholder spawn (real launch template + child env contract are MR-057) ----
def _spawn_placeholder(review_id):
    """Spawn a PLACEHOLDER so "claimed -> spawned" is observable. WATCH_LAUNCH_CMD as a json array
    (preferred) or a shlex string, spawned via Popen with an argv list and env= — NEVER shell=True.
    Default is a no-op. The real generic template + child env contract are MR-057; the seam (env=,
    argv list, non-blocking Popen) is left clean here."""
    raw = os.environ.get("WATCH_LAUNCH_CMD")
    if not raw:
        argv = [sys.executable, "-c", "pass"]   # no-op placeholder
    else:
        try:
            argv = json.loads(raw)
            if not isinstance(argv, list):
                raise ValueError
        except ValueError:
            argv = shlex.split(raw)
    child_env = dict(os.environ)
    child_env["REVIEW_ID"] = review_id          # minimal seam; full contract is MR-057
    child_env["MDREVIEW_BASE"] = BASE
    child_env["MDREVIEW_OWNER"] = OWNER
    proc = subprocess.Popen(argv, env=child_env)   # non-blocking; never shell=True
    print("spawned placeholder for review %s (owner=%s pid=%d)" % (review_id, OWNER, proc.pid))
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
        _spawn_placeholder(review_id)
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
