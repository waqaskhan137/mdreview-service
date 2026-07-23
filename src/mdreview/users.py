"""Users + per-user API tokens (Phase 1 multi-user). One file <DATA_DIR>/users.json holds the
account map (canonical id provider:sub -> record) and hashed API-token digests. Stdlib only.

Auth model: oauth2-proxy enforces the invite allowlist BEFORE any request reaches the app, so a
request on the cookie plane is, by construction, an allowlisted user -> auto-provision on first
sign-in. The token plane is validated here against per-user HMAC digests (pepper from env, never on
disk), so a users.json leak alone cannot forge a token. Reads are lock-free (consistent with the
meta.json reads elsewhere); mutating methods assume the caller holds store.lock, like ReviewService.
"""
import hashlib
import hmac
import json
import os
import secrets
import time


class UserService:
    def __init__(self, store, pepper):
        self.store = store
        self._pepper = (pepper or "").encode()

    def _path(self):
        return os.path.join(self.store.data_dir, "users.json")

    def _load(self):
        return self.store.read_json(self._path(), {"users": {}, "tokens": {}})

    def _save(self, data):                       # caller holds store.lock
        self.store.write_text(self._path(), json.dumps(data))

    # ---- identity (cookie plane) ----
    @staticmethod
    def canonical(provider, sub):
        """The ONE user id, used identically by both planes. provider:sub, never sub alone (two
        providers can share a numeric sub). Returns None if either part is missing."""
        provider = (provider or "").strip()
        sub = (sub or "").strip()
        return "%s:%s" % (provider, sub) if provider and sub else None

    def ensure_user(self, uid, email):
        """Auto-provision an allowlisted user on first sign-in (oauth2-proxy already vetted them).
        Idempotent; refreshes the stored email. The first user provisioned is the owner. Caller
        holds store.lock."""
        if not uid:
            return None
        data = self._load()
        u = data["users"].get(uid)
        if u is None:
            data["users"][uid] = {"email": email or "", "status": "active",
                                  "is_owner": not data["users"], "created": time.time()}
            self._save(data)
        elif email and u.get("email") != email:
            u["email"] = email
            self._save(data)
        return uid

    def is_active(self, uid):
        u = self._load()["users"].get(uid)
        return bool(u) and u.get("status", "active") == "active"

    # ---- platform-admin role + capabilities (#102) ----
    # is_admin / super_read live on the SAME user record is_active gates every plane on, so a ban and
    # a capability check read one source of truth. is_admin is grantable (set_admin); the instance
    # owner (is_owner, the first user provisioned) is admin by construction so there is always at
    # least one admin without hand-editing the data volume. super_read is NEVER implied by admin and
    # NEVER seeded - it is off by default and only an explicit set_super_read turns it on (#102).
    def is_admin(self, uid):
        u = self._load()["users"].get(uid)
        return bool(u) and (bool(u.get("is_admin")) or bool(u.get("is_owner")))

    def can_super_read(self, uid):
        u = self._load()["users"].get(uid)
        return bool(u) and bool(u.get("super_read"))

    def session_ok(self, uid, iat):
        """Cookie-plane gate: active AND the session was minted at/after any admin session-revoke
        cutoff. `sessions_invalid_before` (0 by default) is bumped by revoke_sessions so a force-logout
        rejects every session issued before it WITHOUT banning the account (a distinct lever). A stale
        agent token is revoked by deleting it, not by this cutoff, so tokens are unaffected."""
        u = self._load()["users"].get(uid)
        if not u or u.get("status", "active") != "active":
            return False
        cutoff = u.get("sessions_invalid_before", 0) or 0
        return not cutoff or (iat or 0) >= cutoff

    def list_users(self):
        """Every account, for the admin surface. is_admin folds in the owner (matching is_admin())."""
        return sorted(
            [{"uid": uid, "email": r.get("email", ""), "status": r.get("status", "active"),
              "is_owner": bool(r.get("is_owner")),
              "is_admin": bool(r.get("is_admin")) or bool(r.get("is_owner")),
              "super_read": bool(r.get("super_read")), "created": r.get("created", 0)}
             for uid, r in self._load()["users"].items()],
            key=lambda u: u["created"], reverse=True)

    def set_status(self, uid, status):
        """Ban (status='banned') or reinstate (status='active') an account. A banned account fails
        is_active, so its sessions AND tokens are rejected at the next request. Caller holds store.lock;
        returns True iff the user exists."""
        data = self._load()
        u = data["users"].get(uid)
        if not u:
            return False
        u["status"] = status
        self._save(data)
        return True

    def set_admin(self, uid, value):
        """Grant/revoke the admin role. The owner's implicit admin (is_owner) is not stored here and
        cannot be revoked this way, which keeps at least one admin. Caller holds store.lock."""
        data = self._load()
        u = data["users"].get(uid)
        if not u:
            return False
        u["is_admin"] = bool(value)
        self._save(data)
        return True

    def set_super_read(self, uid, value):
        """Grant/revoke the audited document super-READ capability (#102). Off by default; this is the
        ONLY way it is turned on. Caller holds store.lock; returns True iff the user exists."""
        data = self._load()
        u = data["users"].get(uid)
        if not u:
            return False
        u["super_read"] = bool(value)
        self._save(data)
        return True

    def revoke_all_tokens(self, uid):
        """Delete every API token belonging to uid (moderation / lost-device). Caller holds store.lock;
        returns the count removed."""
        data = self._load()
        victims = [tid for tid, r in data["tokens"].items() if r.get("uid") == uid]
        for tid in victims:
            del data["tokens"][tid]
        if victims:
            self._save(data)
        return len(victims)

    def revoke_sessions(self, uid):
        """Force-logout: invalidate every session minted before now (see session_ok). Distinct from a
        ban (the account stays active) and from token revoke (tokens are unaffected). Caller holds
        store.lock; returns True iff the user exists."""
        data = self._load()
        u = data["users"].get(uid)
        if not u:
            return False
        u["sessions_invalid_before"] = time.time()
        self._save(data)
        return True

    def find_by_email(self, email):
        """The existing account id whose stored email matches (case-insensitive), or None. Read-only.
        Used by the hosted native-auth linking (#67 D1) to ADOPT an existing federated owner's durable
        provider:sub when they first verify the same email via magic-link, so their reviews (keyed on
        that sub) do not fragment. A no-op for anyone who never uses the native path."""
        e = (email or "").strip().lower()
        if not e:
            return None
        for uid, rec in self._load()["users"].items():
            if (rec.get("email") or "").strip().lower() == e:
                return uid
        return None

    # ---- tokens (agent plane) ----
    def _digest(self, secret):
        return hmac.new(self._pepper, secret.encode(), hashlib.sha256).hexdigest()

    def mint_token(self, uid, label=""):
        """Return the plaintext token (shown ONCE). Store only its HMAC digest. Caller holds
        store.lock. Format: mdr_<tok_id>_<secret> (tok_id is the public handle for O(1) lookup +
        revoke; the secret is never stored)."""
        tok_id = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        data = self._load()
        data["tokens"][tok_id] = {"uid": uid, "hash": self._digest(secret),
                                  "label": label or "", "created": time.time()}
        self._save(data)
        return "mdr_%s_%s" % (tok_id, secret)

    def resolve(self, authorization):
        """Authorization header value -> uid or None. Constant-time digest compare; unknown/forged
        tokens resolve to None (the caller turns that into 401)."""
        if not authorization or not authorization.startswith("Bearer "):
            return None
        parts = authorization[7:].strip().split("_", 2)     # ["mdr", tok_id, secret]
        if len(parts) != 3 or parts[0] != "mdr":
            return None
        rec = self._load()["tokens"].get(parts[1])
        if not rec or not hmac.compare_digest(rec.get("hash", ""), self._digest(parts[2])):
            return None
        return rec.get("uid")

    def list_tokens(self, uid):
        toks = self._load()["tokens"]
        return sorted(
            [{"tok_id": tid, "label": r.get("label", ""), "created": r.get("created", 0)}
             for tid, r in toks.items() if r.get("uid") == uid],
            key=lambda t: t["created"], reverse=True)

    def revoke_token(self, uid, tok_id):
        """Remove a token IFF it belongs to uid (so one user cannot revoke another's). Caller holds
        store.lock. Returns True if a token was removed."""
        data = self._load()
        r = data["tokens"].get(tok_id)
        if not r or r.get("uid") != uid:
            return False
        del data["tokens"][tok_id]
        self._save(data)
        return True
