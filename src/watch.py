#!/usr/bin/env python3
"""mdreview watcher: auto-pick-up the handoff baton (MR-056 loop core + MR-057 launcher, C2).

A stdlib-only sibling of mcp_server.py, run where the operator's agent runs. It long-polls the
service's C1 /wait endpoint for reviews newly flipped to turn==agent (the "Send to agent" baton),
claims each review's cooperative lease (POST /handoff {state:working}), and — on a winning claim —
spawns the operator's configured launch command; with WATCH_LAUNCH_CMD unset it REFUSES to start
(exit 2 with guidance) — there is no runnable default. It is a CREDENTIALED process spawner, so its
load-bearing safety property is the fail-closed trusted-base check (Step 0): it refuses to start
against a base it cannot vouch for, rather than warn-and-continue.

The launch mechanism is a GENERIC, operator-configured command template (WC-2): the loop only knows
"spawn this argv with this env." Nothing Claude-specific lives in the loop — env is the entire
interface (REVIEW_ID / MDREVIEW_BASE / MDREVIEW_OWNER, Step 4). That genericity is exactly what lets
the tests drive a stub launch command instead of a real model.

Crash model (B1, verified against app.py:629-636): a child that exits before `hand_back` STRANDS its
review at turn==agent. The server bumps `turn_updated` only on a real reviewer->agent flip, NOT on a
{state:working} lease write, so the edge-triggered /wait?since=cursor never re-surfaces a stranded
review. The watcher therefore does NOT auto-relaunch — it reaps + logs the exit and moves on. The
failure mode is a fail-safe UNDER-spawn (the human recovers via the 180s stale banner, or a
--backlog/restart re-seed), not a relaunch storm. There is no crash-retry by design. The per-review
attempt cap (WATCH_MAX_ATTEMPTS_PER_REVIEW) bounds the path where spawns DO repeat — the re-Send /
re-surface loop (one review flipped back to turn==agent again and again) — never a crash-loop.

NOT containerized, NOT imported by app.py, NOT started by compose. `python3 watch.py` is the only
way it runs (mirrors `MDREVIEW_BASE=… python3 mcp_server.py`).

Config (all env, stdlib-idiomatic):
  MDREVIEW_BASE              service base url (default http://localhost:8137, same as mcp_server.py)
  WATCH_TRUSTED_BASE        operator's explicit vouch; EXACT-match of MDREVIEW_BASE allows a
                            non-loopback base. Unset => loopback only. (No wildcard/prefix.)
  WATCH_ARMED_FILE          local allowlist file (C3): one review id per line, `#` comments,
                            bad/`*` tokens dropped-and-logged. Re-read per check (live-editable).
                            When configured, the watcher runs on an un-vouched non-loopback base
                            but spawns ONLY armed reviews (un-armed skipped without a lease claim).
  WATCH_ARMED               inline armed id-list (comma/space-separated), unioned with the file;
                            fixed at process start (the file is the live-editable surface).
  WATCH_OWNER               stable lease owner id; default pid-derived (see _watcher_id / WC-5)
  WATCH_SINCE               "0" (or --backlog) to opt into the existing agent-turn backlog; default=now
  WATCH_WAIT_TIMEOUT_S      client long-poll timeout (default 25; server caps it to its WAIT_TIMEOUT_S)
  WATCH_LAUNCH_CMD          launch command, argv via a JSON array (preferred) or a shlex string;
                            spawned WITHOUT a shell. Required; unset => the watcher exits 2 at
                            startup with guidance (must-configure stub, no runnable default).
  WATCH_MAX_CONCURRENT      max simultaneous live children (default 3); enforced BEFORE the claim.
  WATCH_MAX_LAUNCHES_PER_HOUR  rolling 3600s spawn cap (default 30); at the cap, defer (no claim).
  WATCH_MAX_ATTEMPTS_PER_REVIEW  per-review spawn cap (default 5) over WATCH_ATTEMPT_WINDOW_S; once a
                            single review id hits it in the window, that review is skipped (no claim)
                            until its window slides. Bounds the re-Send / re-surface loop (one review
                            repeatedly flipped back to turn==agent), NOT a crash-loop (a crashed child
                            strands and is never auto-relaunched). Composes with the global caps above.
  WATCH_ATTEMPT_WINDOW_S    rolling window (default 3600s) for the per-review attempt cap.
  WATCH_LOG_FILE            MR-067: operational log file. UNSET => log to stderr only (the default,
                            preserving "wherever the operator redirected"); SET => ALSO append to that
                            exact path. No baked-in path (the watcher has no /data mount). Holds the
                            structured exit-code + stderr-tail records that make a crashed run
                            diagnosable.
  WATCH_VERBOSE / --verbose raise the log level INFO->DEBUG.

On a crashed child (non-zero exit, no hand_back) the watcher captures the child's stderr tail to the
log AND — after a MANDATORY /status re-check that it is still stranded at turn==agent (so it never
stomps a successful hand_back) — POSTs hand_back{state:blocked,"agent process exited N without
finishing"} so the reviewer's banner shows "agent run stopped" instead of a frozen spinner. Still B1:
no relaunch (visibility, not retry). The viewer gets a short fixed reason; raw stderr is log-only.
"""
import collections
import json
import logging
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

# ---- logging (MR-067 / issue #26): structured, timestamped operational log ----
# stderr ALWAYS (preserves today's "wherever the operator redirected stdout/err" default); a
# FileHandler is added ONLY when WATCH_LOG_FILE is set — the watcher is the non-containerized sibling
# with no /data mount, so there is no sane baked-in path to default into. `--verbose` (or WATCH_VERBOSE)
# raises the level INFO->DEBUG. Call _setup_logging() once, first thing in main().
log = logging.getLogger("watch")


def _setup_logging():
    if log.handlers:                                 # idempotent (a re-import / double call is a no-op)
        return
    log.setLevel(logging.DEBUG if ("--verbose" in sys.argv or os.environ.get("WATCH_VERBOSE"))
                 else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s watch.py: %(message)s")
    sh = logging.StreamHandler()                     # stderr
    sh.setFormatter(fmt)
    log.addHandler(sh)
    path = os.environ.get("WATCH_LOG_FILE")
    if path:
        fh = logging.FileHandler(path)               # append; the documented diagnosable location
        fh.setFormatter(fmt)
        log.addHandler(fh)
        log.info("logging to %s", path)


BASE = os.environ.get("MDREVIEW_BASE", "http://localhost:8137").rstrip("/")
WAIT_TIMEOUT_S = float(os.environ.get("WATCH_WAIT_TIMEOUT_S", "25"))
NET_BACKOFF_S = 2.0     # bounded backoff on a network error (re-poll the SAME cursor)
CAP_BACKOFF_S = 5.0     # bounded backoff while at capacity (the WC-3 fallback; pending-set is default)

MAX_CONCURRENT = int(os.environ.get("WATCH_MAX_CONCURRENT", "3"))
MAX_LAUNCHES_PER_HOUR = int(os.environ.get("WATCH_MAX_LAUNCHES_PER_HOUR", "30"))
LAUNCH_WINDOW_S = 3600.0

# Per-review attempt cap: bound a single review id's spawns within a rolling window so one
# non-converging review cannot eat the global hourly budget across many re-Sends. This is a THIRD,
# independent ceiling that COMPOSES with the two global caps above (never replaces them).
MAX_ATTEMPTS_PER_REVIEW = int(os.environ.get("WATCH_MAX_ATTEMPTS_PER_REVIEW", "5"))
ATTEMPT_WINDOW_S = float(os.environ.get("WATCH_ATTEMPT_WINDOW_S", "3600"))

# Inert must-configure stub: there is NO runnable default launch command. WATCH_LAUNCH_CMD is
# required; when it is unset the watcher refuses to start (require_launch_configured_or_exit in
# main() exits 2 with guidance) rather than spawn anything. The sentinel is None — never a runnable
# argv — so no Claude (or any) command lives in the loop. The agent command AND its permission
# stance are an explicit one-time operator choice (see README "Watcher" runbook for the recipes),
# not a baked-in default that silently no-ops headless. _launch_argv() raises if it ever sees the
# sentinel, because the startup gate guarantees WATCH_LAUNCH_CMD is set by the time it runs.
DEFAULT_LAUNCH_CMD = None


# ---- C3 arming / allowlist: a LOCAL operator gate (never an HTTP capability) ----
# The allowlist is operator-local config the service never sees: a file path WATCH_ARMED_FILE
# (primary, live-editable) unioned with an inline env id-list WATCH_ARMED. On a no-auth public
# instance a review CANNOT arm itself — there is no app.py route to set this; the watcher reads it
# from disk/env. Arming relaxes C2's Step-0 refusal: un-vouched non-loopback runs IFF arming is
# configured, and then only ARMED reviews are spawned (un-armed are skipped without a lease claim).
_RID_RE = re.compile(r"[A-Za-z0-9]{4,40}")   # the server-generated id shape (app.py RID), reused
WATCH_ARMED_FILE = os.environ.get("WATCH_ARMED_FILE")
# The env id-list is fixed at process start (env cannot change in-process); the FILE is the
# live-editable surface (re-read per check). Comma/space-separated; bad tokens dropped-and-logged.
_WATCH_ARMED_ENV_RAW = os.environ.get("WATCH_ARMED")


def arming_configured():
    """True iff EITHER arming source is set — even if the resulting allowlist is empty. "Configured
    but empty" is run-but-gate-everything (spawn nothing), NOT "unconfigured" (which would EXIT)."""
    return bool(WATCH_ARMED_FILE) or _WATCH_ARMED_ENV_RAW is not None


def launch_configured():
    """True iff the operator set a launch command. Mirrors arming_configured(): DEFAULT_LAUNCH_CMD is
    an inert sentinel (None), so an unset WATCH_LAUNCH_CMD means there is no runnable launch command
    and the watcher must refuse to start (require_launch_configured_or_exit in main())."""
    return bool(os.environ.get("WATCH_LAUNCH_CMD"))


def _valid_id(token, source):
    """A token is a valid armed id iff it fully matches the server id shape. A `*`/`ALL` wildcard,
    a typo, or any garbage FAILS this (N2: `*` is dropped-and-logged, NEVER treated as match-all),
    so a bad line never silently widens the allowlist and never crashes the watcher."""
    if _RID_RE.fullmatch(token):
        return True
    log.warning("ignoring invalid armed id %r from %s (not %s)"
          % (token, source, _RID_RE.pattern))
    return False


def _env_armed_ids():
    """Parse WATCH_ARMED (comma/space-separated id-list), keeping only valid id tokens."""
    if not _WATCH_ARMED_ENV_RAW:
        return set()
    tokens = _WATCH_ARMED_ENV_RAW.replace(",", " ").split()
    return {t for t in tokens if _valid_id(t, "WATCH_ARMED")}


def _file_armed_ids():
    """Re-read WATCH_ARMED_FILE on EACH call (default no-cache freshness: arm a review by appending
    a line, no restart). One id per line; blank lines and `#` comments ignored; whitespace stripped;
    each token validated. A missing/unreadable file is an empty allowlist (logged), not a crash."""
    if not WATCH_ARMED_FILE:
        return set()
    try:
        with open(WATCH_ARMED_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        log.warning("cannot read WATCH_ARMED_FILE=%s (%s) — treating as empty allowlist"
              % (WATCH_ARMED_FILE, e))
        return set()
    ids = set()
    for line in lines:
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        if _valid_id(token, "WATCH_ARMED_FILE"):
            ids.add(token)
    return ids


def armed_ids():
    """The unioned allowlist (env ∪ file). Re-reads the file each call for freshness."""
    return _env_armed_ids() | _file_armed_ids()


def _is_armed(review_id):
    """The default-safe hinge. True iff arming is NOT configured (⇒ byte-for-byte C2: every review
    is "armed") OR review_id is in the unioned allowlist. Consulted whenever arming is configured,
    on EVERY base (C3-Q1: a single base-independent gate; the base check decides run-vs-exit, this
    decides which reviews)."""
    if not arming_configured():
        return True
    return review_id in armed_ids()


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

    Decision table (C3 relaxes only row 4's CONSEQUENCE when arming is configured):
      - loopback                                  => run (C2, unchanged)
      - non-loopback + exact WATCH_TRUSTED_BASE   => run (C2, unchanged)
      - non-loopback + no vouch + arming CONFIGURED => RUN (do NOT exit) — run-but-gate per review
      - non-loopback + no vouch + NO arming       => EXIT 2 (C2 PRESERVED byte-for-byte)

    The refusal names BOTH MDREVIEW_BASE (the actual) and WATCH_TRUSTED_BASE (the vouch, or
    "(unset)") [WC-1] so a brittle exact-match mismatch (http vs https, :443 vs bare,
    localhost vs 127.0.0.1) is self-explaining. The fix for a paper-cut mismatch is the better
    message, NOT a looser comparand — the strictness IS the control. C3 adds ONE escape hatch:
    configuring arming (WATCH_ARMED_FILE/WATCH_ARMED) lets the watcher run un-vouched for armed
    reviews only; it does NOT weaken the refusal when arming is unconfigured."""
    if check_trusted_base(base):
        return
    if arming_configured():
        return   # C3 relaxation: un-vouched non-loopback runs, but only ARMED reviews are spawned
    trust = os.environ.get("WATCH_TRUSTED_BASE") or "(unset)"
    sys.stderr.write(
        "watch.py refusing to start: untrusted base.\n"
        "  MDREVIEW_BASE=%s does not match WATCH_TRUSTED_BASE=%s\n"
        "  (unset => loopback only: localhost/127.0.0.1/::1; otherwise an EXACT match is required.)\n"
        "  To run on this base, either vouch for it with WATCH_TRUSTED_BASE, or configure arming\n"
        "  (WATCH_ARMED_FILE/WATCH_ARMED) to run armed reviews only.\n"
        % (base, trust)
    )
    sys.exit(2)


def require_launch_configured_or_exit():
    """Refuse to start (sys.exit(2)) when WATCH_LAUNCH_CMD is unset — the must-configure gate.

    LOAD-BEARING: this is a STARTUP exit, never a per-review one. _spawn()/_launch_argv() run only
    AFTER handle() POSTs /handoff {state:working} and wins the lease on a 200; the server does NOT
    bump turn_updated on a {state:working} lease write (only on a real reviewer->agent flip), so a
    spawn-time exit would claim the lease, die, and STRAND the review at turn==agent with no
    re-surfacing on the edge-triggered /wait?since=cursor. Refusing at startup means no lease is ever
    claimed — the only failure mode that does not strand a review. The exit-with-guidance lives ONLY
    here; _launch_argv() merely asserts (it is unreachable unset once this gate has run)."""
    if launch_configured():
        return
    sys.stderr.write(
        "watch.py refusing to start: WATCH_LAUNCH_CMD is unset.\n"
        "  There is no runnable default launch command (a bare `claude -p` silently no-ops\n"
        "  headless), so the watcher will not claim a lease it cannot honour.\n"
        "  Set WATCH_LAUNCH_CMD to the agent command AND its permission stance (a JSON-array argv,\n"
        "  e.g. '[\"claude\",\"-p\",\"--permission-mode\",\"dontAsk\",\"--allowedTools\",\n"
        "  \"mcp__mdreview__*\",\"<prompt>\"]').\n"
        "  See the README \"Watcher (optional) — operator runbook\" for the scoped and full-autonomy\n"
        "  recipes and the prompt-injection trade-off.\n"
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


def _arming_startup_notice():
    """W2: when arming is configured, announce the armed-id count and that the gate is
    base-independent, so a silently-idle (empty-allowlist) watcher is never a surprise."""
    if not arming_configured():
        return
    n = len(armed_ids())
    msg = ("arming active: %d ids armed; un-armed reviews are skipped on ALL bases "
           "(loopback/vouched included)" % n)
    if n == 0:
        msg += " — the allowlist is empty/non-matching, so the watcher will spawn NOTHING " \
               "until you arm a review"
    (log.warning if n == 0 else log.info)(msg)


def main():
    _setup_logging()                     # MR-067: configure the log sink before anything logs
    require_trusted_base_or_exit(BASE)   # Step 0: FIRST, before any network call. Refuse-and-exit.
    require_launch_configured_or_exit()  # must-configure gate: refuse-and-exit if WATCH_LAUNCH_CMD
                                         # unset. AFTER the trusted-base crux, BEFORE run() — a
                                         # startup exit, never spawn-time (would strand turn==agent).
    _arming_startup_notice()             # W2: announce the gate when arming is configured
    try:
        run()
    except KeyboardInterrupt:
        log.info("stopped")


if __name__ == "__main__":
    main()
