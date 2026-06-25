"""The fail-closed startup gates — the security crux.

The watcher is a credentialed process spawner, so before any network call it must prove (Step 0) it
is talking to a base it can vouch for, and that it has a real launch command to honour. Both refusals
are STARTUP exits (sys.exit(2)), never per-review ones — a spawn-time exit would claim a lease and
strand a review at turn==agent. arming.py supplies the one escape hatch (run un-vouched for armed
reviews only).
"""
import os
import sys
import urllib.parse

from .arming import arming_configured, launch_configured


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
