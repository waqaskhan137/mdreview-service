"""In-flight children, the three independent caps, reaping, the crash signal, and the launch spawn.

Single-threaded state of the one poll loop, so no locking: _inflight tracks live Popen handles per
review (concurrency cap + reaping), _launch_times is a rolling-window deque (launches/hour cap), and
_review_attempts is the per-review spawn cap. _spawn runs ONLY after loop.handle() wins the lease;
_reap collects finished children and, on a non-zero exit, signals the reviewer (B1: never relaunch).
"""
import collections
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error

from .config import (
    ATTEMPT_WINDOW_S, BASE, LAUNCH_WINDOW_S, MAX_ATTEMPTS_PER_REVIEW, MAX_CONCURRENT,
    MAX_LAUNCHES_PER_HOUR, OWNER, WAIT_TIMEOUT_S, log,
)
from .http import _http


# ---- in-flight children + caps (Step 5) ----
# _inflight: live child Popen handles, keyed by review id (the concurrency cap + reaping).
# _launch_times: a rolling-window deque of spawn timestamps (the launches/hour cap). Both are
# single-threaded state of the one poll loop, so no locking is needed.
_inflight = {}                       # review_id -> Popen
_launch_times = collections.deque()  # spawn timestamps, oldest first
# Per-review spawn timestamps for WATCH_MAX_ATTEMPTS_PER_REVIEW. Mirrors _launch_times, but keyed
# per review id. A key's deque is pruned (deleted) when it empties on eviction, so the dict does not
# grow unbounded across many one-shot reviews on a long-running watcher.
_review_attempts = {}                # review_id -> collections.deque[spawn timestamp]


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
        tail = _read_errtail(proc)   # MR-067: drain + close the child's stderr temp file
        if code == 0:
            log.info("child for review %s exited 0 (reaped)", rid)
        else:
            # A non-zero exit is logged but NOT retried (B1). MR-067: capture the stderr tail + the
            # resolved argv to the operator log so the crash is diagnosable, then signal the reviewer.
            log.warning("child for review %s exited %s (reaped; no relaunch — see crash model B1); argv=%r",
                        rid, code, getattr(proc, "_argv", None))
            if tail.strip():
                log.warning("child for review %s stderr tail:\n%s", rid, tail.strip())
            _signal_crash(rid, code)


def _read_errtail(proc, limit=2000):
    """MR-067: read the tail of a reaped child's captured stderr and close the temp file. Best-effort
    (a missing/unreadable file yields "")."""
    errf = getattr(proc, "_errf", None)
    if errf is None:
        return ""
    try:
        errf.seek(0)
        data = errf.read()
        return data[-limit:].decode("utf-8", "replace")
    except Exception:                # pragma: no cover — diagnostic read must never crash the loop
        return ""
    finally:
        try:
            errf.close()
        except Exception:
            pass


def _signal_crash(rid, code):
    """MR-067 (issue #26): flip a CRASHED review (non-zero child, no hand_back) back to the reviewer
    with a 'blocked' signal the viewer renders as 'agent run stopped', so the reviewer is not left on
    a frozen 'working' spinner. MANDATORY /status re-check FIRST (the conflation guard): SKIP the
    signal if the child already handed the turn back (turn != "agent") or set state "done" — an
    arbitrary launch command can POST a successful hand_back and THEN exit non-zero in teardown, and
    an unconditional signal would stomp that 'done' with a false 'stopped'. Only a genuine crash
    leaves turn=="agent" (stale 'working' lease), which is exactly the case we signal. Best-effort:
    any read/POST failure logs and returns — the 180s stale banner + the MR-066 pickup cue still
    recover. The viewer gets a SHORT FIXED reason; raw stderr stays in the operator log (no-auth)."""
    try:
        st, body = _http("GET", "/api/reviews/%s/status" % rid, timeout=WAIT_TIMEOUT_S + 5)
    except urllib.error.URLError as e:
        log.warning("crash-signal: /status read failed for %s (%s) — skip signal", rid, e.reason)
        return
    if st != 200:
        log.warning("crash-signal: /status HTTP %s for %s — skip signal", st, rid)
        return
    turn = (body or {}).get("turn")
    state = ((body or {}).get("agent_status") or {}).get("state")
    if turn != "agent" or state == "done":
        log.info("crash-signal: review %s already handed back (turn=%s state=%s) — no false 'stopped'",
                 rid, turn, state)
        return
    msg = "agent process exited %s without finishing" % code
    s2, _ = _http("POST", "/api/reviews/%s/handoff" % rid,
                  {"to": "reviewer", "state": "blocked", "owner": OWNER, "message": msg},
                  timeout=WAIT_TIMEOUT_S + 5)
    if s2 == 200:
        log.warning("crash-signal: review %s flipped to reviewer (%r)", rid, msg)
    else:
        log.warning("crash-signal: review %s handoff HTTP %s — skip (stale banner recovers)", rid, s2)


def _at_capacity():
    """At capacity iff the concurrency cap OR the rolling launches/hour cap is hit. Reap first so a
    just-finished child frees its slot, and evict stale launch timestamps so the hourly window slides.

    The caps bound NORMAL-load spend — many DISTINCT reviews flipped to agent — and are a cheap
    backstop. They do NOT bound a "crash-loop": under the edge-triggered design a crashed child
    strands (under-spawn, B1), it does not relaunch, so there is no storm to bound. The
    repeated-spawn path is the re-Send / re-surface loop (one review flipped back to turn==agent
    again and again); the PER-REVIEW cap (_per_review_capped) bounds a single id there, composing
    with these two GLOBAL caps — all three are independent ceilings a spawn must pass."""
    _reap()
    if len(_inflight) >= MAX_CONCURRENT:
        return True
    cutoff = time.time() - LAUNCH_WINDOW_S
    while _launch_times and _launch_times[0] < cutoff:
        _launch_times.popleft()
    return len(_launch_times) >= MAX_LAUNCHES_PER_HOUR


def _per_review_capped(review_id):
    """True iff this review id has hit WATCH_MAX_ATTEMPTS_PER_REVIEW spawns within the rolling
    WATCH_ATTEMPT_WINDOW_S window. Evict timestamps older than the window first (same slide as
    _at_capacity), then compare `len >= cap`. PRUNE the key when its deque empties on eviction, so
    the per-review dict does not grow unbounded across many one-shot reviews.

    This is a TERMINAL gate, NOT a "retry when a slot frees": it means "this review has had its turns
    this window," so run() skips it without claiming and without entering `pending`; only a genuinely
    new edge after the window slides re-spawns it. It bounds the RE-SEND / RE-SURFACE loop — one
    review repeatedly returned to turn==agent (a human who keeps pressing Send, an agent that hands
    back and is re-Sent, a --backlog re-seed) — NOT a crash-loop: a crashed child strands its review
    (turn_updated unchanged ⇒ /wait never re-surfaces it) and is never auto-relaunched, so there is no
    crash-loop for this cap to bound. It COMPOSES with the global caps (all three must pass to spawn)."""
    dq = _review_attempts.get(review_id)
    if dq is None:
        return False
    cutoff = time.time() - ATTEMPT_WINDOW_S
    while dq and dq[0] < cutoff:
        dq.popleft()
    if not dq:
        del _review_attempts[review_id]   # prune the empty key (memory-leak guard)
        return False
    return len(dq) >= MAX_ATTEMPTS_PER_REVIEW


# ---- launch template parsing (WC-2: argv, NEVER a shell) ----
def _launch_argv():
    """Resolve WATCH_LAUNCH_CMD to an argv list: a JSON array (preferred) or a shlex-split string.
    The result is spawned WITHOUT a shell (no shell=True, no id interpolation into a command string)
    — env is the interface, so the template needs no placeholder.

    Defensive, not the gate: the user-facing exit-2-with-guidance lives ONLY in main()
    (require_launch_configured_or_exit), which runs at startup before any spawn. By the time
    _launch_argv() is reached, WATCH_LAUNCH_CMD is guaranteed set, so the unset branch is unreachable
    in normal operation — it raises (rather than do list(None) -> opaque TypeError) so a future
    refactor that drops the startup gate fails loud."""
    raw = os.environ.get("WATCH_LAUNCH_CMD")
    if not raw:
        raise RuntimeError("WATCH_LAUNCH_CMD unset — should have been caught at startup by "
                           "require_launch_configured_or_exit(); DEFAULT_LAUNCH_CMD is an inert "
                           "sentinel with no runnable default")
    try:
        argv = json.loads(raw)
    except ValueError:
        return shlex.split(raw)          # not JSON: a shell-style string, split into argv
    if isinstance(argv, list):
        return argv
    # parsed as JSON but not an array (a bare string/object/number) — shlex its raw text and say so,
    # rather than silently producing surprising argv.
    sys.stderr.write("watch.py: WATCH_LAUNCH_CMD parsed as JSON but is not an array; "
                     "falling back to shlex.split of the raw string\n")
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
    # MR-067: capture the child's stderr to a real temp FILE (not subprocess.PIPE) — a chatty
    # multi-minute agent would fill a 64KB pipe buffer and DEADLOCK if nobody reads until reap;
    # an OS file never blocks the writer. _reap reads its tail on a non-zero exit.
    errf = tempfile.TemporaryFile(mode="w+b")
    argv = _launch_argv()
    proc = subprocess.Popen(argv, env=child_env, stderr=errf)   # non-blocking; never shell=True
    proc._errf = errf                            # MR-067: read on reap (Popen accepts ad-hoc attrs)
    proc._argv = argv                            # MR-067: the resolved argv, logged in the crash record
    now = time.time()
    _inflight[review_id] = proc
    _launch_times.append(now)
    _review_attempts.setdefault(review_id, collections.deque()).append(now)   # per-review cap
    log.info("spawned child for review %s (owner=%s pid=%d, inflight=%d)",
             review_id, OWNER, proc.pid, len(_inflight))
    return proc
