"""C3 arming / allowlist: a LOCAL operator gate (never an HTTP capability).

The allowlist is operator-local config the service never sees: a file path WATCH_ARMED_FILE
(primary, live-editable) unioned with an inline env id-list WATCH_ARMED. On a no-auth public
instance a review CANNOT arm itself — there is no service route to set this; the watcher reads it
from disk/env. Arming relaxes C2's Step-0 refusal: un-vouched non-loopback runs IFF arming is
configured, and then only ARMED reviews are spawned (un-armed are skipped without a lease claim).
"""
import os

from .config import _RID_RE, _WATCH_ARMED_ENV_RAW, WATCH_ARMED_FILE, log


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
