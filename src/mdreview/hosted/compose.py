"""The hosted composition root (#67 priority 7 / custody Decision 1 — the fail-closed-BUILD core of
#109).

`build_hosted` is reached ONLY by `python -m mdreview.hosted` (the hosted Docker image's CMD). The
selection of the real owner-only policy is therefore a property of the BUILD, not of a runtime flag:
there is no env var in this path that yields OpenPolicy. A hosted build is consequently INCAPABLE of
serving with the ownership check off — the #97 root fault (MDREVIEW_REQUIRE_AUTH defaulting open
behind a secret-only guard) is not a reachable state here. This deliberately does NOT reintroduce a
"hosted defaults off" flag; the worst case for a misconfigured hosted build is refuse-to-boot, never
serve-open. The LOCAL tier (`python -m mdreview`) is untouched: it keeps OperatorIdentity/OpenPolicy
and its open, no-accounts promise by design.

The boot guard here is unconditional (independent of REQUIRE_AUTH): a hosted build refuses to start
without the session secret (and the token pepper; and the proxy secret while the transitional plane
is enabled). config.py additionally requires the session secret whenever REQUIRE_AUTH is on, so the
existing transitional path is covered too.
"""
import os
from urllib.parse import urlparse

from mdreview import config
from mdreview.server import Services
from mdreview.hosted.authroutes import AuthModule
from mdreview.hosted.custody import CustodyPolicy
from mdreview.hosted.identity import AccountService, HostedIdentity
from mdreview.hosted.identity_store import IdentityStore
from mdreview.hosted.magiclink import MagicLinkService, StubEmailSender
from mdreview.hosted.sessions import SessionService


def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def canonical_base():
    """The VERIFIED base the magic-link is built from — NOT the raw MDREVIEW_PUBLIC_BASE echoed into
    a link unchecked, and never the client-supplied Host header. Must be an absolute https:// URL with
    a host; otherwise the hosted build refuses to boot (a bogus base would send login links to the
    wrong, possibly attacker-influenced, origin)."""
    base = (config.PUBLIC_BASE or "").rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(
            "hosted build requires MDREVIEW_PUBLIC_BASE to be an absolute https:// URL "
            "(got %r); magic-link URLs are built from it" % base)
    return base


def build_hosted(store):
    # --- unconditional fail-closed boot guard (a property of the hosted build) ---
    if not config.SESSION_SECRET:
        raise SystemExit("hosted build requires MDREVIEW_SESSION_SECRET (session + magic-link signing)")
    if not config.TOKEN_PEPPER:
        raise SystemExit("hosted build requires MDREVIEW_TOKEN_PEPPER (agent-token digests)")
    allow_proxy_plane = os.environ.get("MDREVIEW_ALLOW_PROXY_PLANE", "1").lower() in ("1", "true", "yes")
    if allow_proxy_plane and not config.PROXY_SECRET:
        raise SystemExit("hosted build with the transitional proxy plane on requires MDREVIEW_PROXY_SECRET "
                         "(or set MDREVIEW_ALLOW_PROXY_PLANE=0 to retire it)")
    link_base = canonical_base()

    # --- core services (reviews/comments/assets/handoff/users/modules), then OVERRIDE the seam ---
    app = Services(store)

    id_store = IdentityStore(os.path.join(config.DATA_DIR, "identity.db"))
    sessions = SessionService(
        config.SESSION_SECRET,
        ttl_s=_env_int("MDREVIEW_SESSION_TTL_S", 43200),
        secure=True)
    magic = MagicLinkService(
        config.SESSION_SECRET, id_store, StubEmailSender(), link_base,
        ttl_s=_env_int("MDREVIEW_MAGICLINK_TTL_S", 900),
        max_per_address=_env_int("MDREVIEW_MAGICLINK_MAX_PER_ADDRESS", 3),
        max_per_ip=_env_int("MDREVIEW_MAGICLINK_MAX_PER_IP", 10),
        global_daily_budget=_env_int("MDREVIEW_MAGICLINK_DAILY_BUDGET", 500))
    accounts = AccountService(app.users, id_store)

    # The authoritative, UNCONDITIONAL selection: the hosted resolver + CustodyPolicy. CustodyPolicy
    # IS the owner-only Confinement contract (fail-closed on a missing owner) PLUS the audited,
    # off-by-default admin super-READ exception (#102); named-share (#101/#68) is still a future
    # extension. Bound to the FINAL app.reviews (the latex wrapper when enabled).
    app.identity = HostedIdentity(app.users, store, sessions, config.PROXY_SECRET, allow_proxy_plane)
    app.policy = CustodyPolicy(app.reviews)

    app.modules.append(AuthModule(store, app.users, sessions, magic, accounts, id_store))
    return app
