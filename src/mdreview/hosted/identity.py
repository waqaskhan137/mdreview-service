"""HostedIdentity — the three caller planes (#67 priority 3) — and AccountService — verified-email
account linking (#67 priority 1 / D1).

HostedIdentity.principal resolves the caller in ONE fixed order, and the order is a security
property (read it in one place):

  1. Agent plane   `mdr_` Bearer HMAC token  -> UNCHANGED (UserService.resolve). Keys to provider:sub.
  2. Browser plane the app-owned session cookie (SessionService.verify). The real native-auth plane.
  3. Proxy plane   the TRANSITIONAL oauth2-proxy vouched header, trusted only behind PROXY_SECRET.
                   Behind a flag so it can be retired (rollout 2e) once the session plane is proven;
                   until then session-first means the two planes never both decide a request.

A request that matches none of the three is NOT rejected here — it yields an anonymous Principal, and
the injected AccessPolicy decides (a public read later serves it; everything else 404s today). The
anonymous principal keeps plane="cookie" so a require-auth denial surfaces as the browser 401/redirect
rather than an agent 401.

AccountService.resolve_verified_email is the D1 linking rule. Given a VERIFIED email it returns the
ONE durable uid:
  - an existing identity for that email  -> that uid (the LINK; magic-link and Google converge here);
  - else an existing federated owner in users.json with that email -> ADOPT their provider:sub
    (so google:<sub> owners are unaffected; migration is a no-op);
  - else a brand-new native account keyed email:<email>.
The uid is NEVER re-keyed (re-keying is the #97 failure class), and the store's UNIQUE email index
structurally forbids two uids for one verified email.
"""
import hmac
import sqlite3

from mdreview.access import Principal
from mdreview.hosted.identity_store import normalize_email
from mdreview.hosted.sessions import SessionService


class HostedIdentity:
    def __init__(self, users, store, sessions, proxy_secret="", allow_proxy_plane=True):
        self._users = users
        self._store = store                     # core Store (for the ensure_user lock on the proxy plane)
        self._sessions = sessions
        self._proxy_secret = proxy_secret
        self._allow_proxy_plane = allow_proxy_plane

    def _caps(self, uid):
        """The platform-admin capabilities carried on the Principal (#102), resolved from the user
        record. super_read is off unless explicitly granted and is NEVER implied by is_admin."""
        return {"is_admin": self._users.is_admin(uid), "super_read": self._users.can_super_read(uid)}

    def principal(self, request):
        # 1. Agent plane: mdr_ Bearer HMAC token (unchanged, primary programmatic door).
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            uid = self._users.resolve(auth)
            if uid and self._users.is_active(uid):
                return Principal(uid=uid, plane="token", **self._caps(uid))
            return Principal(is_anonymous=True, plane="token")

        # 2. Browser plane: the app-owned signed session cookie. session_ok adds the admin
        # session-revoke cutoff on top of is_active, so a force-logout rejects a pre-cutoff cookie.
        cookie = SessionService.read_cookie(request)
        if cookie:
            sess = self._sessions.verify(cookie)
            if sess and self._users.session_ok(sess.uid, sess.iat):
                return Principal(uid=sess.uid, email=sess.email, plane="cookie",
                                 **self._caps(sess.uid))
            # A present-but-invalid/expired cookie falls through to the proxy plane / anonymous,
            # exactly as no cookie would; a stale cookie must never harden into a 401 that a valid
            # proxy header could have satisfied during the transition.

        # 3. Proxy plane (transitional): trust the vouched identity header ONLY behind PROXY_SECRET.
        if self._allow_proxy_plane and self._proxy_secret and hmac.compare_digest(
                request.headers.get("X-Mdreview-Proxy", ""), self._proxy_secret):
            uid = self._users.canonical(request.headers.get("X-Mdreview-Provider", ""),
                                        request.headers.get("X-Auth-Request-User", ""))
            if uid:
                email = request.headers.get("X-Auth-Request-Email", "")
                with self._store.lock:
                    self._users.ensure_user(uid, email)
                if self._users.is_active(uid):
                    return Principal(uid=uid, email=email, plane="cookie", **self._caps(uid))

        return Principal(is_anonymous=True, plane="cookie")


class AccountService:
    """The verified-email -> durable-uid linking rule (#67 D1). Mutating calls (create_identity,
    ensure_user) assume the caller holds store.lock, like the rest of the write path."""

    def __init__(self, users, identity_store):
        self._users = users
        self._id = identity_store

    def resolve_verified_email(self, email):
        """Return (uid, created). `email` MUST already be provider-verified (magic-link redemption
        proves inbox control). Idempotent: a repeat login for the same email returns the same uid
        with created=False."""
        e = normalize_email(email)
        if not e:
            return None, False

        # (a) Already an identity -> LINK to it (native-first, or a previously-adopted federated uid).
        uid = self._id.find_uid_by_email(e)
        if uid:
            return uid, False

        # (b) Adopt an existing federated owner (users.json) so their provider:sub is preserved.
        existing = self._users.find_by_email(e)
        if existing:
            try:
                self._id.create_identity(existing, e)
            except sqlite3.IntegrityError:
                # A concurrent create linked it first; the email is unique, so re-resolve wins.
                existing = self._id.find_uid_by_email(e) or existing
            return existing, False

        # (c) Brand-new verified email -> a native account keyed email:<email>, in BOTH stores (the
        # account/token record in users.json, the durable identity + link row in sqlite).
        uid = self._users.canonical("email", e)
        self._users.ensure_user(uid, e)
        try:
            self._id.create_identity(uid, e)
        except sqlite3.IntegrityError:
            # Lost a create race; the UNIQUE email index means the winner's uid is authoritative.
            return (self._id.find_uid_by_email(e) or uid), False
        return uid, True
