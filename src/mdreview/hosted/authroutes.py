"""The /auth/* routes, dispatched through the core's feature-module seam (the same `handle(h, m,
path) -> bool` protocol the latex module uses), so the core router needs ZERO changes to gain native
auth. The module owns its own responses (it sets the session cookie directly on the handler, which is
a BaseHTTPRequestHandler).

Routes:
  POST /auth/magic-link  {email}     issue a login link. CONSTANT response (enumeration-safe): the
                                     caller cannot tell whether the address exists or was throttled.
  GET  /auth/redeem?token=..         a confirm PAGE (no consumption). A bare GET (mail-scanner
                                     prefetch) therefore cannot burn the single-use token.
  POST /auth/redeem  token=..        confirm: verify + consume the token, link/create the account,
                                     mint the session, Set-Cookie, 303 -> /.
  GET  /auth/session                 the SPA's identity + CSRF token; slides the session's lifetime.
  POST /auth/logout                  clear the session (CSRF-checked).
"""
import html
import json
from urllib.parse import parse_qs, urlparse

_SEC_HEADERS = (("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"))


class AuthModule:
    def __init__(self, store, users, sessions, magic, accounts, identity_store):
        self.store = store
        self.users = users
        self.sessions = sessions
        self.magic = magic
        self.accounts = accounts
        self.id_store = identity_store

    # ---- low-level response (the core _send hardcodes its headers; we need Set-Cookie) ----
    @staticmethod
    def _respond(h, code, body, ctype="application/json", cookies=None, location=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h.send_response(code)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(body)))
        for k, v in _SEC_HEADERS:
            h.send_header(k, v)
        if location:
            h.send_header("Location", location)
        for c in (cookies or []):
            h.send_header("Set-Cookie", c)
        h.end_headers()
        if body:
            h.wfile.write(body)

    def _json(self, h, code, obj, cookies=None):
        self._respond(h, code, json.dumps(obj), "application/json", cookies=cookies)

    @staticmethod
    def _client_ip(h):
        return h.headers.get("X-Real-IP") or h.client_address[0]

    @staticmethod
    def _form(h):
        n = int(h.headers.get("Content-Length", 0) or 0)
        raw = h.rfile.read(n).decode("utf-8", "replace") if n else ""
        return {k: v[0] for k, v in parse_qs(raw).items()}

    # ---- dispatch ----
    def handle(self, h, m, path):
        if not path.startswith("/auth/"):
            return False
        if path == "/auth/magic-link" and m == "POST":
            return self._magic_link(h)
        if path == "/auth/redeem" and m == "GET":
            return self._redeem_page(h)
        if path == "/auth/redeem" and m == "POST":
            return self._redeem(h)
        if path == "/auth/session" and m == "GET":
            return self._session(h)
        if path == "/auth/logout" and m == "POST":
            return self._logout(h)
        return False

    # ---- POST /auth/magic-link ----
    def _magic_link(self, h):
        email = (h._body_json().get("email") or "").strip()
        # issue() applies the abuse limits internally and never sends when throttled; we ignore its
        # status and ALWAYS return the same body, so a caller cannot enumerate addresses or probe the
        # rate state. The write path (send_log, audit) is serialized under the store lock.
        with self.store.lock:
            self.magic.issue(email, self._client_ip(h))
        self._json(h, 200, {"ok": True,
                            "message": "If that address can sign in, a link is on its way."})
        return True

    # ---- GET /auth/redeem (confirm page; does NOT consume) ----
    def _redeem_page(self, h):
        token = parse_qs(urlparse(h.path).query).get("token", [""])[0]
        safe = html.escape(token)
        page = (
            "<!doctype html><meta charset=utf-8><meta name=viewport "
            "content='width=device-width,initial-scale=1'>"
            "<title>Confirm sign-in</title>"
            "<body style='font-family:system-ui;max-width:32rem;margin:4rem auto;padding:0 1rem'>"
            "<h1>Confirm your sign-in</h1>"
            "<p>Click the button to finish signing in to mdreview.</p>"
            "<form method='POST' action='/auth/redeem'>"
            "<input type='hidden' name='token' value='" + safe + "'>"
            "<button type='submit' style='font-size:1rem;padding:.6rem 1.2rem'>"
            "Confirm sign-in</button></form>"
            "<p style='color:#666;font-size:.85rem'>This link is valid once and expires shortly.</p>"
            "</body>")
        self._respond(h, 200, page, "text/html; charset=utf-8")
        return True

    # ---- POST /auth/redeem (verify + consume + mint session) ----
    def _redeem(self, h):
        token = self._form(h).get("token", "")
        email = self.magic.redeem(token)               # verifies MAC, expiry, and single-use nonce
        if not email:
            self._respond(h, 400,
                          "<!doctype html><meta charset=utf-8><title>Link invalid</title>"
                          "<body style='font-family:system-ui;max-width:32rem;margin:4rem auto'>"
                          "<h1>This link is invalid or expired</h1>"
                          "<p>Request a fresh sign-in link.</p></body>",
                          "text/html; charset=utf-8")
            return True
        with self.store.lock:
            uid, created = self.accounts.resolve_verified_email(email)
            if created:
                self.id_store.audit("account_created", uid=uid, email=email, ip=self._client_ip(h))
        cookie_value, _csrf = self.sessions.mint(uid, email)
        self.id_store.audit("login", uid=uid, email=email, ip=self._client_ip(h), detail="magic-link")
        self._respond(h, 303, b"", "text/plain",
                      cookies=[self.sessions.set_cookie_header(cookie_value)], location="/")
        return True

    # ---- GET /auth/session (identity + CSRF; slides the lifetime) ----
    def _session(self, h):
        cookie = self.sessions.read_cookie(h)
        sess = self.sessions.verify(cookie) if cookie else None
        if not sess or not self.users.is_active(sess.uid):
            self._json(h, 200, {"authenticated": False})
            return True
        cookies = None
        if sess.should_refresh(self.sessions.refresh_after_s):
            fresh_value, fresh_csrf = self.sessions.mint(sess.uid, sess.email)
            cookies = [self.sessions.set_cookie_header(fresh_value)]
            csrf = fresh_csrf
        else:
            csrf = sess.csrf
        self._json(h, 200, {"authenticated": True, "uid": sess.uid, "email": sess.email,
                            "csrf": csrf}, cookies=cookies)
        return True

    # ---- POST /auth/logout (CSRF-checked) ----
    def _logout(self, h):
        cookie = self.sessions.read_cookie(h)
        sess = self.sessions.verify(cookie) if cookie else None
        if sess and not self.sessions.check_csrf(sess, h.headers.get("X-CSRF-Token", "")):
            # A valid session present but no matching CSRF token -> refuse (a cross-site forced logout
            # is still state-changing). No session -> nothing to protect, fall through and clear.
            self._json(h, 403, {"error": "missing or invalid CSRF token"})
            return True
        if sess:
            self.id_store.audit("logout", uid=sess.uid, email=sess.email, ip=self._client_ip(h))
        self._respond(h, 200, json.dumps({"ok": True}), "application/json",
                      cookies=[self.sessions.clear_cookie_header()])
        return True
