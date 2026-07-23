"""The /admin/* platform-admin routes (#102), dispatched through the core feature-module seam (the
same `handle(h, m, path) -> bool` protocol AuthModule/latex use), so the core router needs zero
changes to gain the admin surface.

This is the MODERATE-risk half of #102: user management (the operational lever open membership
lacked). It does NOT itself grant document super-access - it can turn the super_read capability on
for a user, but reading a non-owned doc is CustodyPolicy's audited path, separately.

Gate (defence in depth beyond routing): the caller must be an authenticated admin ON THE COOKIE
PLANE. Cookie-plane-only mirrors /account/tokens - a high-value management surface is a browser act,
never an agent-token door; an admin's leaked API token therefore cannot ban users or grant super_read.
A non-admin (or an anonymous, or a token-plane) caller is refused before any handler runs, so
"a non-admin cannot reach admin routes" holds by construction.

Every state-changing action is AUDITED to the identity-side sink (IdentityStore.audit ->
auth_audit), recording the ACTOR uid and the target: "who armed it" is as auditable as the
CustodyPolicy "who used it" record. (The audit split, identity-arch section 6: admin user actions
are identity-side; document access is core-side via _audit().)

Routes:
  GET    /admin/users                              list accounts (uid, email, status, roles).
  POST   /admin/users/{uid}/ban                    ban (reject sessions AND tokens at next request).
  POST   /admin/users/{uid}/unban                  reinstate.
  POST   /admin/users/{uid}/admin        {value}   grant/revoke the admin role.
  POST   /admin/users/{uid}/super-read   {value}   grant/revoke the audited document super-READ grant.
  POST   /admin/users/{uid}/revoke-tokens          delete all of a user's API tokens.
  POST   /admin/users/{uid}/revoke-sessions        force-logout (invalidate sessions; account stays).
  GET    /admin/blocklist                          list blocked emails/IPs.
  POST   /admin/blocklist            {value, kind, note}   block an email or IP.
  DELETE /admin/blocklist/{value}                  unblock.
"""
import json
import re
from urllib.parse import unquote

_USER_ACTION = re.compile(
    r"/admin/users/(.+)/(ban|unban|admin|super-read|revoke-tokens|revoke-sessions)")
_BLOCK_ITEM = re.compile(r"/admin/blocklist/(.+)")


class AdminModule:
    def __init__(self, store, users, identity_store):
        self.store = store
        self.users = users
        self.id_store = identity_store

    @staticmethod
    def _json(h, code, obj):
        h._json(code, obj)          # reuse the core JSON responder (its headers suit same-origin admin)

    @staticmethod
    def _client_ip(h):
        return h.headers.get("X-Real-IP") or h.client_address[0]

    def _audit(self, h, actor, event, target, detail=""):
        info = ("target=%s" % target) + ((" " + detail) if detail else "")
        self.id_store.audit(event, uid=actor, ip=self._client_ip(h), detail=info)

    def handle(self, h, m, path):
        if path != "/admin" and not path.startswith("/admin/"):
            return False

        # ---- gate: authenticated admin on the cookie (browser) plane only ----
        p = h._principal()
        if p.is_anonymous:
            self._json(h, 401, {"error": "authentication required"})
            return True
        if p.plane != "cookie" or not p.is_admin:
            # Same 403 for a non-admin and for an admin on the token plane: the admin surface is not
            # reachable by an agent token, and non-admin membership must not learn the surface exists.
            self._json(h, 403, {"error": "admin only"})
            return True

        if path == "/admin/users" and m == "GET":
            self._json(h, 200, {"users": self.users.list_users()})
            return True

        mo = _USER_ACTION.fullmatch(path)
        if mo and m == "POST":
            return self._user_action(h, p, unquote(mo.group(1)), mo.group(2))

        if path == "/admin/blocklist" and m == "GET":
            self._json(h, 200, {"blocklist": self.id_store.block_list()})
            return True
        if path == "/admin/blocklist" and m == "POST":
            return self._block_add(h, p)
        mo = _BLOCK_ITEM.fullmatch(path)
        if mo and m == "DELETE":
            return self._block_remove(h, p, unquote(mo.group(1)))

        self._json(h, 404, {"error": "no admin route", "method": m, "path": path})
        return True

    # ---- user actions ----
    def _user_action(self, h, actor, uid, action):
        body = h._body_json()
        value = bool(body.get("value", True))

        # Self-lockout guards: an admin cannot ban themselves or drop their own admin role (which
        # keeps at least one reachable admin and avoids fixing a lockout by editing the volume).
        if action == "ban" and uid == actor.uid:
            self._json(h, 400, {"error": "an admin cannot ban themselves"})
            return True
        if action == "admin" and uid == actor.uid and not value:
            self._json(h, 400, {"error": "an admin cannot revoke their own admin role"})
            return True

        with self.store.lock:
            if action == "ban":
                ok, event, detail = self.users.set_status(uid, "banned"), "admin_user_banned", ""
            elif action == "unban":
                ok, event, detail = self.users.set_status(uid, "active"), "admin_user_unbanned", ""
            elif action == "admin":
                ok = self.users.set_admin(uid, value)
                event = "admin_role_granted" if value else "admin_role_revoked"
                detail = "value=%s" % value
            elif action == "super-read":
                ok = self.users.set_super_read(uid, value)
                event = "admin_super_read_granted" if value else "admin_super_read_revoked"
                detail = "value=%s" % value
            elif action == "revoke-tokens":
                n = self.users.revoke_all_tokens(uid)
                ok, event, detail = True, "admin_tokens_revoked", "count=%d" % n
            else:                                             # revoke-sessions
                ok, event, detail = self.users.revoke_sessions(uid), "admin_sessions_revoked", ""

        if not ok:
            self._json(h, 404, {"error": "no such user"})
            return True
        self._audit(h, actor.uid, event, uid, detail)
        self._json(h, 200, {"ok": True, "uid": uid, "action": action})
        return True

    # ---- blocklist ----
    def _block_add(self, h, actor):
        body = h._body_json()
        value = (body.get("value") or "").strip()
        kind = (body.get("kind") or "").strip()
        if not value or kind not in ("email", "ip"):
            self._json(h, 400, {"error": "value and kind ('email' or 'ip') are required"})
            return True
        with self.store.lock:
            stored = self.id_store.block_add(value, kind, (body.get("note") or "").strip())
        self._audit(h, actor.uid, "admin_block_add", stored, "kind=%s" % kind)
        self._json(h, 201, {"ok": True, "value": stored, "kind": kind})
        return True

    def _block_remove(self, h, actor, value):
        with self.store.lock:
            removed = self.id_store.block_remove(value)
        if not removed:
            self._json(h, 404, {"error": "not blocklisted"})
            return True
        self._audit(h, actor.uid, "admin_block_remove", value)
        self._json(h, 200, {"ok": True, "value": value})
        return True
