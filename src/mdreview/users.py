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
