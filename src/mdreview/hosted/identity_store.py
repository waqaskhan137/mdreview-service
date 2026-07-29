"""The hosted identity store, on `sqlite3` (stdlib -> no new dependency). Storage only; the linking
POLICY lives in identity.AccountService, the send POLICY in magiclink.MagicLinkService.

Four tables, one file <DATA_DIR>/identity.db:

  identities    the durable user record. PK is `uid` = provider:sub (e.g. google:100.. or
                email:alice@x.com). D1 invariant: uid is NEVER re-keyed (re-keying is the #97
                failure class). `email` carries a UNIQUE index, which is the ACCOUNT-LINKING
                mechanism itself: one verified email maps to exactly one uid, so a second login
                path (magic-link then Google, or vice-versa) for the same verified email resolves
                to the existing uid instead of minting a divergent one.
  magic_nonces  consumed single-use magic-link ids. `consume_nonce` INSERTs the jti; the PK makes a
                replay fail atomically (IntegrityError) until the token expires and the row is pruned.
  send_log      one row per magic-link send attempt, for the abuse counters (per-address, per-IP,
                global daily budget) — #67 D3. Doubles as a send record.
  auth_audit    append-only auth events (magic-link issuance, login, account creation) — identity
                side of the audit split (#110 custody/doc-access audit is core-side, not here).

Thread-safety: the core runs a ThreadingHTTPServer, so a sqlite3 connection (check_same_thread) must
not cross threads. Every method opens its own short-lived connection (WAL + busy_timeout handle the
concurrency); at this scale the connect cost is negligible and the code stays obviously correct.
"""
import os
import sqlite3
import time


def normalize_email(email):
    """Canonical form used as the linking key. Lowercased + stripped so Alice@X.com and
    alice@x.com resolve to the ONE uid. Returns "" for falsy/blank input (callers reject that)."""
    return (email or "").strip().lower()


class IdentityStore:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        # A fresh connection per call (never shared across threads). WAL lets readers and the single
        # writer proceed without blocking; busy_timeout absorbs the brief write contention.
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS identities (
                    uid            TEXT PRIMARY KEY,
                    email          TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 1,
                    status         TEXT NOT NULL DEFAULT 'active',
                    created        REAL NOT NULL
                );
                -- The linking invariant, enforced by the schema: one verified email -> one uid.
                CREATE UNIQUE INDEX IF NOT EXISTS idx_identities_email ON identities(email);

                CREATE TABLE IF NOT EXISTS magic_nonces (
                    jti        TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS send_log (
                    id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    ip    TEXT NOT NULL,
                    ts    REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_send_log_ts ON send_log(ts);

                CREATE TABLE IF NOT EXISTS auth_audit (
                    id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts     REAL NOT NULL,
                    event  TEXT NOT NULL,
                    uid    TEXT,
                    email  TEXT,
                    ip     TEXT,
                    detail TEXT
                );

                -- Admin-managed abuse blocklist (#67 D3 / #102): a blocked email or IP is refused at
                -- the magic-link send path outright, the moderation lever open membership lacked. PK
                -- on the value makes add idempotent; kind narrows the match ('email' | 'ip').
                -- Per-session records (#223). The session cookie is self-signed, so before this
                -- table nothing on the server represented "this session": there was no way to tell
                -- one device from another and no way to end one without ending all of them (the
                -- account-wide sessions_invalid_before cutoff was the only lever).
                -- revoked is a flag rather than a DELETE so a revoked jti stays REJECTED for the
                -- life of the cookie; deleting the row would make it indistinguishable from a
                -- grandfathered pre-#223 cookie, which is accepted.
                CREATE TABLE IF NOT EXISTS sessions (
                    jti        TEXT PRIMARY KEY,
                    uid        TEXT NOT NULL,
                    created    REAL NOT NULL,
                    last_seen  REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    ip         TEXT,
                    user_agent TEXT,
                    revoked    INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_uid ON sessions(uid);

                CREATE TABLE IF NOT EXISTS blocklist (
                    value TEXT PRIMARY KEY,
                    kind  TEXT NOT NULL,
                    note  TEXT,
                    added REAL NOT NULL
                );
                """
            )

    # ---- identities (durable provider:sub, verified email, account linking) ----
    def find_uid_by_email(self, email):
        """The uid a verified email is already linked to, or None. This is the LINK lookup: a second
        login path for the same email must resolve here, not create a new uid."""
        e = normalize_email(email)
        if not e:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT uid FROM identities WHERE email=?", (e,)).fetchone()
            return row["uid"] if row else None

    def get_identity(self, uid):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM identities WHERE uid=?", (uid,)).fetchone()
            return dict(row) if row else None

    def create_identity(self, uid, email, email_verified=True):
        """Insert a new durable identity. Raises sqlite3.IntegrityError if the uid OR the email is
        already present (the UNIQUE email index is the linking guard against a divergent second uid);
        the caller treats that as "already linked" and re-resolves. NEVER updates uid (no re-key)."""
        e = normalize_email(email)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO identities (uid, email, email_verified, status, created) "
                "VALUES (?, ?, ?, 'active', ?)",
                (uid, e, 1 if email_verified else 0, time.time()))
        return uid

    def is_active(self, uid):
        row = self.get_identity(uid)
        return bool(row) and row.get("status") == "active"

    # ---- single-use magic-link nonces (replay-proof until expiry) ----
    def consume_nonce(self, jti, expires_at):
        """Atomically claim a magic-link nonce. Returns True on the FIRST claim, False if it was
        already consumed (replay) — the PRIMARY KEY makes this race-free without an explicit lock.
        Prunes expired nonces opportunistically so the table cannot grow without bound."""
        now = time.time()
        with self._connect() as conn:
            conn.execute("DELETE FROM magic_nonces WHERE expires_at < ?", (now,))
            try:
                conn.execute("INSERT INTO magic_nonces (jti, expires_at) VALUES (?, ?)",
                             (jti, expires_at))
            except sqlite3.IntegrityError:
                return False
        return True

    # ---- abuse counters (#67 D3): per-address, per-IP, global daily ----
    def record_send(self, email, ip):
        now = time.time()
        with self._connect() as conn:
            # Opportunistic prune: no counter looks back more than the daily window, so rows older
            # than two days can never affect a limit; dropping them keeps send_log self-bounded.
            conn.execute("DELETE FROM send_log WHERE ts < ?", (now - 2 * 86400,))
            conn.execute("INSERT INTO send_log (email, ip, ts) VALUES (?, ?, ?)",
                         (normalize_email(email), ip or "", now))

    def count_sends(self, since_ts, email=None, ip=None):
        """Sends at or after since_ts, optionally filtered to one address or one IP. With neither
        filter it is the global count (the daily-budget query)."""
        q = "SELECT COUNT(*) AS n FROM send_log WHERE ts >= ?"
        args = [since_ts]
        if email is not None:
            q += " AND email = ?"
            args.append(normalize_email(email))
        if ip is not None:
            q += " AND ip = ?"
            args.append(ip or "")
        with self._connect() as conn:
            return conn.execute(q, args).fetchone()["n"]

    # ---- append-only auth-event audit (#67 priority 8; identity side of the #110 split) ----
    def audit(self, event, uid=None, email=None, ip=None, detail=None):
        """Append one auth event. INSERT-only: this table is never updated or deleted from in normal
        operation, so it is a tamper-evident record of who logged in / who was issued a link / which
        accounts were created."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_audit (ts, event, uid, email, ip, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), event, uid, normalize_email(email) if email else None, ip or None,
                 detail))

    def recent_audit(self, limit=50, before=None):
        """Newest-first page of auth_audit (#144, the read path the sink lacked). `before` is the
        cursor: a ts, selecting strictly-older rows, so passing the previous page's oldest ts walks
        the log without an offset scan. Ordered by (ts, id) so the cursor and the ordering agree;
        rows sharing an identical REAL ts across a page boundary would be skipped, accepted for v1
        (time.time() collisions are freak events at this write rate)."""
        q, args = "SELECT * FROM auth_audit", []
        if before is not None:
            q += " WHERE ts < ?"
            args.append(before)
        q += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._connect() as conn:
            rows = conn.execute(q, args).fetchall()
            return [dict(r) for r in rows]

    # ---- per-session records (#223) ----
    # Two invariants shape every method here:
    #   1. An UNKNOWN jti is REJECTED, but a cookie carrying NO jti is accepted (grandfathering,
    #      owner decision D3). Those are different states and session_live() keeps them apart.
    #   2. `revoked` is set, never deleted. A deleted row reads as "unknown jti", which is also
    #      rejection, but pruning would then silently revoke live sessions at their prune time.
    #      Pruning is therefore bounded by expires_at, never by revoked.
    LAST_SEEN_THROTTLE_S = 300

    def session_create(self, jti, uid, expires_at, ip=None, user_agent=None, now=None):
        now = time.time() if now is None else now
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions "
                "(jti, uid, created, last_seen, expires_at, ip, user_agent, revoked) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (jti, uid, now, now, expires_at, ip or None, (user_agent or None)))

    def session_live(self, jti, now=None):
        """True iff this jti may still authenticate. Called on EVERY authenticated request, so it
        does one indexed primary-key lookup and nothing else."""
        if not jti:
            return False
        now = time.time() if now is None else now
        with self._connect() as conn:
            row = conn.execute(
                "SELECT revoked, expires_at FROM sessions WHERE jti=?", (jti,)).fetchone()
        return bool(row) and not row["revoked"] and row["expires_at"] > now

    def session_touch(self, jti, now=None):
        """Update last_seen, THROTTLED. Without the throttle this is a write on every request, which
        on a threaded stdlib server turns a read path into a write-lock queue."""
        now = time.time() if now is None else now
        with self._connect() as conn:
            row = conn.execute("SELECT last_seen FROM sessions WHERE jti=?", (jti,)).fetchone()
            if not row or (now - row["last_seen"]) < self.LAST_SEEN_THROTTLE_S:
                return False
            conn.execute("UPDATE sessions SET last_seen=? WHERE jti=?", (now, jti))
            return True

    def session_revoke(self, jti, uid=None):
        """Revoke ONE session. `uid`, when given, scopes the write so a caller can never revoke
        another account's session by guessing a jti."""
        with self._connect() as conn:
            if uid is None:
                cur = conn.execute("UPDATE sessions SET revoked=1 WHERE jti=?", (jti,))
            else:
                cur = conn.execute("UPDATE sessions SET revoked=1 WHERE jti=? AND uid=?", (jti, uid))
            return cur.rowcount > 0

    def session_revoke_all(self, uid, except_jti=None):
        """Sign out everywhere (optionally except the caller's own session)."""
        with self._connect() as conn:
            if except_jti:
                cur = conn.execute(
                    "UPDATE sessions SET revoked=1 WHERE uid=? AND jti<>? AND revoked=0",
                    (uid, except_jti))
            else:
                cur = conn.execute(
                    "UPDATE sessions SET revoked=1 WHERE uid=? AND revoked=0", (uid,))
            return cur.rowcount

    def sessions_for(self, uid, now=None):
        """The caller's own live sessions, newest first. Revoked and expired rows are filtered out
        rather than shown greyed: a list of things that are not sessions is not a session list."""
        now = time.time() if now is None else now
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT jti, created, last_seen, ip, user_agent FROM sessions "
                "WHERE uid=? AND revoked=0 AND expires_at>? ORDER BY created DESC",
                (uid, now)).fetchall()
            return [dict(r) for r in rows]

    def sessions_prune(self, now=None):
        """Drop EXPIRED rows only, same pattern as magic_nonces. Never prunes on `revoked`: see the
        invariant note above."""
        now = time.time() if now is None else now
        with self._connect() as conn:
            return conn.execute("DELETE FROM sessions WHERE expires_at<=?", (now,)).rowcount

    # ---- admin-managed abuse blocklist (#67 D3 / #102) ----
    def is_blocked(self, email=None, ip=None):
        """True iff the address OR the IP is blocklisted - the check MagicLinkService.issue consults
        before it sends. Normalizes the email to the same canonical form add uses."""
        e = normalize_email(email) if email else ""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM blocklist WHERE (kind='email' AND value=?) "
                "OR (kind='ip' AND value=?) LIMIT 1", (e, ip or "")).fetchone()
            return row is not None

    def block_add(self, value, kind, note=""):
        """Add (or update the note on) a blocklist entry. kind is 'email' or 'ip'; an email value is
        normalized so it matches is_blocked. Idempotent via the PK upsert. Returns the stored value."""
        v = normalize_email(value) if kind == "email" else (value or "").strip()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO blocklist (value, kind, note, added) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(value) DO UPDATE SET kind=excluded.kind, note=excluded.note",
                (v, kind, note or "", time.time()))
        return v

    def block_remove(self, value):
        """Remove a blocklist entry (by its stored value). Returns True iff a row was deleted."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM blocklist WHERE value=?", ((value or "").strip(),))
            return cur.rowcount > 0

    def block_list(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT value, kind, note, added FROM blocklist ORDER BY added DESC").fetchall()
            return [dict(r) for r in rows]
