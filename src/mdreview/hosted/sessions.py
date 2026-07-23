"""The app-owned session cookie (#67 D2). mdreview mints and verifies its OWN signed session; it no
longer leans on oauth2-proxy's vouched header for the browser plane.

Token shape (compact, self-signed, symmetric — no external verifier exists in the build-minimal
design, so no JWT/JWKS): ``<payload_b64url>.<hmac_b64url>`` where payload is JSON
{uid, email, iat, exp, csrf} and the MAC is HMAC-SHA256(secret, payload_b64url). There is a single
algorithm and no alg field, so the JWT alg-confusion / alg:none class does not exist here. Any edit
to the payload (including exp) invalidates the MAC; verify() rejects on a constant-time MAC mismatch
before it trusts a single field.

Cookie attributes: HttpOnly (no JS theft of the session), Secure (HTTPS only), SameSite=Lax (a
cross-site POST does not carry it, which is the primary CSRF defence), Path=/, Max-Age=lifetime.
CSRF: a per-session token is embedded in the signed payload and echoed to the page via GET
/auth/session; a state-changing POST must present it in X-CSRF-Token, and check_csrf compares it in
constant time — defence-in-depth behind SameSite=Lax.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from http.cookies import SimpleCookie

COOKIE_NAME = "mdr_session"


def b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64url_decode(s):
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class SessionData:
    """A verified session. `should_refresh` drives the sliding-window re-issue (a live session past
    its refresh point is re-minted so an active user is not logged out at the fixed lifetime)."""

    def __init__(self, uid, email, iat, exp, csrf):
        self.uid = uid
        self.email = email
        self.iat = iat
        self.exp = exp
        self.csrf = csrf

    def should_refresh(self, refresh_after_s, now=None):
        now = time.time() if now is None else now
        return (now - self.iat) >= refresh_after_s


class SessionService:
    def __init__(self, secret, ttl_s=43200, refresh_after_s=None, secure=True):
        if not secret:
            # Defence in depth behind config's boot guard: never sign with an empty key (that would
            # make every session forgeable, since compare_digest("","") is True).
            raise ValueError("SessionService requires a non-empty secret")
        self._key = secret.encode("utf-8")
        self.ttl_s = int(ttl_s)
        # Default: re-issue once past the halfway mark of the lifetime.
        self.refresh_after_s = int(refresh_after_s if refresh_after_s is not None else ttl_s // 2)
        self.secure = secure

    def _mac(self, payload_b64):
        return b64url_encode(hmac.new(self._key, payload_b64.encode("ascii"),
                                       hashlib.sha256).digest())

    def mint(self, uid, email, now=None):
        """Return (cookie_value, csrf). A fresh CSRF token is bound to each minted session."""
        now = time.time() if now is None else now
        csrf = secrets.token_urlsafe(24)
        payload = {"uid": uid, "email": email or "", "iat": now, "exp": now + self.ttl_s,
                   "csrf": csrf}
        payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return payload_b64 + "." + self._mac(payload_b64), csrf

    def verify(self, cookie_value, now=None):
        """A verified SessionData, or None on any failure (bad shape, MAC mismatch, or expiry). The
        MAC is checked in constant time BEFORE any field is trusted, so a tampered payload never
        reaches the exp/uid logic."""
        now = time.time() if now is None else now
        if not cookie_value or "." not in cookie_value:
            return None
        payload_b64, _, sig = cookie_value.partition(".")
        if not payload_b64 or not sig:
            return None
        if not hmac.compare_digest(sig, self._mac(payload_b64)):
            return None
        try:
            payload = json.loads(b64url_decode(payload_b64))
        except (ValueError, json.JSONDecodeError):
            return None
        uid = payload.get("uid")
        exp = payload.get("exp", 0)
        if not uid or not isinstance(exp, (int, float)) or exp <= now:
            return None
        return SessionData(uid, payload.get("email", ""), payload.get("iat", 0), exp,
                           payload.get("csrf", ""))

    def check_csrf(self, session, provided):
        """Constant-time match of a client-supplied CSRF token against the session's bound token."""
        return bool(session) and bool(provided) and bool(session.csrf) and \
            hmac.compare_digest(session.csrf, provided)

    # ---- cookie header helpers ----
    def set_cookie_header(self, cookie_value):
        attrs = ["%s=%s" % (COOKIE_NAME, cookie_value), "Max-Age=%d" % self.ttl_s, "Path=/",
                 "HttpOnly", "SameSite=Lax"]
        if self.secure:
            attrs.append("Secure")
        return "; ".join(attrs)

    def clear_cookie_header(self):
        attrs = ["%s=" % COOKIE_NAME, "Max-Age=0", "Path=/", "HttpOnly", "SameSite=Lax"]
        if self.secure:
            attrs.append("Secure")
        return "; ".join(attrs)

    @staticmethod
    def read_cookie(request):
        """Extract the session cookie value from a request's Cookie header, or None."""
        raw = request.headers.get("Cookie", "")
        if not raw:
            return None
        try:
            jar = SimpleCookie()
            jar.load(raw)
        except Exception:
            return None
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel else None
