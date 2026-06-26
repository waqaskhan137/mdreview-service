"""The startup sequence — the `python -m watcher` entry point.

Order is load-bearing: configure logging, run the fail-closed trusted-base crux FIRST (before any
network call), then the must-configure launch gate, then announce arming, then enter the loop. Both
require_*_or_exit gates are startup exits, never spawn-time ones (a spawn-time exit would strand a
review at turn==agent).
"""
from .arming import armed_ids, arming_configured
from .config import BASE, _setup_logging, log
from .loop import run
from .safety import require_launch_configured_or_exit, require_trusted_base_or_exit


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
