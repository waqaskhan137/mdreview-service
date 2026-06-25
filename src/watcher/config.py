"""Process configuration: env-derived constants, the logger, and the stable owner id.

All env reads happen here, once, at import — the rest of the package imports these names. The
config docstrings for every WATCH_* var live in the package __init__; this module is the wiring.
"""
import logging
import os
import re
import socket
import sys

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

# ---- C3 arming / allowlist sources (parsed in arming.py) ----
_RID_RE = re.compile(r"[A-Za-z0-9]{4,40}")   # the server-generated id shape (RID), reused
WATCH_ARMED_FILE = os.environ.get("WATCH_ARMED_FILE")
# The env id-list is fixed at process start (env cannot change in-process); the FILE is the
# live-editable surface (re-read per check). Comma/space-separated; bad tokens dropped-and-logged.
_WATCH_ARMED_ENV_RAW = os.environ.get("WATCH_ARMED")


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
