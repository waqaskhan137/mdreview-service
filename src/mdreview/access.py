"""Access/identity seam (#103): the two injected interfaces the composition root wires by tier.

The core makes NO access decision inline. `Services` picks one (IdentityProvider, AccessPolicy) pair
on the existing REQUIRE_AUTH switch:

  - REQUIRE_AUTH off -> OperatorIdentity + OpenPolicy: a single trusted operator, everything open
    (byte-identical to the pre-#103 local/single-user path: uid None, owner "", lists unscoped).
  - REQUIRE_AUTH on  -> ProxyBearerIdentity + OwnerPolicy: the oauth2-proxy-vouched header / Bearer
    resolver plus owner-only access (a review is readable/writable/deletable only by the account that
    owns it; a non-owner is indistinguishable from absent).

This is a behaviour-preserving extraction: the logic here is byte-identical to the pre-#103
server.H (_principal / _authz) and reviews.ReviewService (can_access / list_reviews). Ownership is
still the durable provider:sub key, delegated to reviews.can_access so it is NOT re-implemented or
re-keyed here (re-keying is the #97 failure class the ticket forbids). Stdlib only; imports no
hosted module (the hosted identity store is #67).
"""
import hmac


class Principal:
    """The resolved caller.

    uid   - the durable owner key provider:sub (None for the local operator). Never re-keyed (#97).
    email - the vouched email on the cookie plane; "" otherwise (forward-looking, mirrors the header).
    is_admin - the platform-admin role (#102). Grants the admin user-management surface (list / ban /
               revoke / blocklist). Resolved from the user record by the hosted identity provider;
               always False on the local tier and for an anonymous caller. Being an admin does NOT by
               itself grant super-access to another account's document (see super_read).
    super_read - the SEPARATE, off-by-default platform grant (#102) that lets an admin READ a document
               they do not own, as an audited Confinement exception (CustodyPolicy). Least-privilege:
               it is read-only (there is no super-write/super-delete grant, by construction) and it is
               NOT implied by is_admin - an admin must be explicitly granted it, and every use is
               audited. False everywhere unless a hosted user record explicitly holds the grant.
    is_anonymous - True when no active user could be resolved on a require-auth tier; the handler
               answers such a caller with 401 (identity demanded) once the policy has denied.
    plane - the auth transport the attribution + token-management branch on: "cookie" (human via
            oauth2-proxy), "token" (agent via Bearer), or "local" (auth off). Not an access decision,
            only who-authored / which-surface metadata, kept byte-identical to the pre-#103 planes.
    """

    def __init__(self, uid=None, email="", is_admin=False, super_read=False, is_anonymous=False,
                 plane="local"):
        self.uid = uid
        self.email = email
        self.is_admin = is_admin
        self.super_read = super_read
        self.is_anonymous = is_anonymous
        self.plane = plane


# ---- REQUIRE_AUTH off: single operator, everything open ----------------------------------------
class OperatorIdentity:
    """Local / single-user tier: every request is the one trusted operator. Never anonymous; uid None
    so a created review stays owner-'' and lists stay unscoped, exactly as the pre-#103 local path."""

    def principal(self, request):
        return Principal(uid=None, plane="local")


class OpenPolicy:
    """Everything-open ownership: any EXISTING review is fully accessible to the operator. Existence
    still gates (a missing/deleted review is not readable) so a GET on an absent id stays 404,
    byte-identical to the pre-#103 `not exists(rid)` arm. No scoping; new reviews are stamped owner-''.
    """

    def __init__(self, reviews):
        self._reviews = reviews

    def can_read(self, principal, rid):
        return self._reviews.exists(rid)

    def can_write(self, principal, rid):
        return self._reviews.exists(rid)

    def can_delete(self, principal, rid):
        return self._reviews.exists(rid)

    def scope_list(self, principal):
        return None

    def stamp_owner(self, principal):
        return ""


# ---- REQUIRE_AUTH on: oauth2-proxy header / Bearer, owner-only ----------------------------------
class ProxyBearerIdentity:
    """Hosted-tier identity, byte-identical to the pre-#103 server.H._principal fused with the
    is_active gate that lived in _require_user. Bearer -> a per-user API token; else the
    oauth2-proxy-vouched identity header, trusted ONLY behind the nginx proxy secret (constant-time
    compare; an empty secret is already refused at boot in config). A caller that does not resolve to
    an ACTIVE user is anonymous (the handler turns that into 401)."""

    def __init__(self, users, store, proxy_secret):
        self._users = users
        self._store = store
        self._proxy_secret = proxy_secret

    def principal(self, request):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            uid = self._users.resolve(auth)
            if uid and self._users.is_active(uid):
                return Principal(uid=uid, plane="token")
            return Principal(is_anonymous=True, plane="token")
        # Cookie plane: trust the identity header ONLY behind the nginx proxy secret. Fail closed -
        # an empty PROXY_SECRET would make compare_digest("","") pass (config also refuses to boot).
        if self._proxy_secret and hmac.compare_digest(
                request.headers.get("X-Mdreview-Proxy", ""), self._proxy_secret):
            uid = self._users.canonical(request.headers.get("X-Mdreview-Provider", ""),
                                        request.headers.get("X-Auth-Request-User", ""))
            if uid:
                email = request.headers.get("X-Auth-Request-Email", "")
                with self._store.lock:
                    self._users.ensure_user(uid, email)
                if self._users.is_active(uid):
                    return Principal(uid=uid, email=email, plane="cookie")
        return Principal(is_anonymous=True, plane="cookie")


class OwnerPolicy:
    """Owner-only access, byte-identical to reviews.can_access plus the hosted list scoping. A review
    is accessible only by the account that owns it; a missing owner fails closed (a legacy,
    un-backfilled review is inaccessible until `python -m mdreview.migrate` stamps it). The owner-key
    match is delegated to reviews.can_access, NOT re-implemented here, so provider:sub is never
    re-keyed (#97). A non-owner or absent review is denied; the handler answers 404 (indistinguishable
    from absent) so ownership is not probeable."""

    def __init__(self, reviews):
        self._reviews = reviews

    def _owns(self, principal, rid):
        return self._reviews.exists(rid) and self._reviews.can_access(rid, principal.uid)

    def can_read(self, principal, rid):
        return self._owns(principal, rid)

    def can_write(self, principal, rid):
        return self._owns(principal, rid)

    def can_delete(self, principal, rid):
        return self._owns(principal, rid)

    def scope_list(self, principal):
        return principal.uid

    def stamp_owner(self, principal):
        return principal.uid
