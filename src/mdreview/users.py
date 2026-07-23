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
    def __init__(self, store, pepper, owner_email=""):
        self.store = store
        self._pepper = (pepper or "").encode()
        # The one email crowned owner (=> admin). Injected from config.OWNER_EMAIL, exactly as the
        # pepper is injected (the core reads no env directly). Empty => no owner (see _is_owner_email).
        self._owner_email = (owner_email or "").strip().lower()

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

    def _is_owner_email(self, email):
        """True IFF `email` equals the configured owner email, case-insensitively. An UNSET owner email
        matches no one, so an instance with no configured owner has no owner and no stranger can
        self-crown. This is the SOLE source of owner-ship: never first-registrant order (#67 H1)."""
        return bool(self._owner_email) and (email or "").strip().lower() == self._owner_email

    def ensure_user(self, uid, email):
        """Auto-provision a user on first sign-in (the proxy plane vetted them; the native plane proved
        inbox control). Idempotent; refreshes the stored email. is_owner is pinned to the configured
        MDREVIEW_OWNER_EMAIL — NEVER the first registrant (#67 H1) — and is_admin follows is_owner
        (explicit non-owner admin grants are #102, and OR in here then; none exist yet, so a
        de-crowned account keeps NO admin). Both flags are RECONCILED to the current verified email on
        every call, so a legacy first-registrant crown is dropped and an owner-email match is honoured.
        Caller holds store.lock."""
        if not uid:
            return None
        data = self._load()
        u = data["users"].get(uid)
        owner = self._is_owner_email(email if u is None else (email or u.get("email")))
        if u is None:
            data["users"][uid] = {"email": email or "", "status": "active",
                                  "is_owner": owner, "is_admin": owner, "created": time.time()}
            self._save(data)
            return uid
        dirty = False
        if email and u.get("email") != email:
            u["email"] = email
            dirty = True
        if bool(u.get("is_owner")) != owner:
            u["is_owner"] = owner
            dirty = True
        if bool(u.get("is_admin")) != owner:            # is_admin follows is_owner (no grants yet, #102)
            u["is_admin"] = owner
            dirty = True
        if dirty:
            self._save(data)
        return uid

    def is_active(self, uid):
        u = self._load()["users"].get(uid)
        return bool(u) and u.get("status", "active") == "active"

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
