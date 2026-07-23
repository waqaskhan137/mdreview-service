"""The per-document share store, on `sqlite3` (stdlib -> no new dependency). Storage only; the
sharing POLICY (owner-only base + how a share grants access) lives in custody.CustodyPolicy, exactly
as identity_store holds identity rows while the linking policy lives in identity.AccountService.

One table, one file <DATA_DIR>/shares.db (kept separate from identity.db so a custody/sharing concern
does not co-mingle with the identity concern — the audit design splits them the same way: share
grant/revoke is a CUSTODY event audited core-side, distinct from identity events in identity.db):

  shares    an owner-granted exception to the custody Confinement invariant (#97), per document.
            PK is (rid, subject). subject is either the literal "public" (share-to-all, #101) or
            "user:<uid>" where uid is the grantee's durable provider:sub (share-to-named, #68).
            grant_right is "view" or "comment" (named 'grant_right', not 'right', which is a SQL
            keyword). Absence of a row = private (the default). A row is removed to revoke, so a
            revoke is immediate at the next access.

Thread-safety mirrors IdentityStore: the core runs a ThreadingHTTPServer, so every method opens its
own short-lived sqlite3 connection (WAL + busy_timeout handle concurrency); a connection never
crosses threads. Mutating callers additionally hold the core store.lock (the module serializes writes
under it), but correctness here does not depend on that — the PK + INSERT OR REPLACE are atomic.
"""
import os
import sqlite3
import time

# Strength order so a caller holding both a public "view" and a named "comment" grant gets the
# stronger. "comment" implies "view" (you can read what you may comment on).
_RANK = {"view": 1, "comment": 2}


class ShareStore:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS shares (
                    rid         TEXT NOT NULL,
                    subject     TEXT NOT NULL,   -- "public" | "user:<provider:sub>"
                    grant_right TEXT NOT NULL,   -- "view" | "comment"
                    created     REAL NOT NULL,
                    created_by  TEXT NOT NULL,   -- owner uid that granted the share
                    PRIMARY KEY (rid, subject)
                );
                CREATE INDEX IF NOT EXISTS idx_shares_rid ON shares(rid);
                """
            )

    # ---- public (share-to-all, #101) ----
    def set_public(self, rid, grant_right, by):
        """Grant (or re-grant) a public share on rid. INSERT OR REPLACE so toggling on twice is
        idempotent and updating the right is one call. Caller holds store.lock."""
        self._upsert(rid, "public", grant_right, by)

    def remove_public(self, rid):
        """Make rid private again (revoke the public share). Idempotent. Caller holds store.lock."""
        return self.revoke(rid, "public")

    def public_right(self, rid):
        """The right a public share grants on rid, or None if it is not public."""
        return self._right(rid, "public")

    # ---- named (share-to-user, #68) ----
    def invite(self, rid, uid, grant_right, by):
        """Grant (or re-grant) a named share to grantee uid. Keyed on the durable provider:sub, so it
        follows the human across login methods. Caller holds store.lock."""
        self._upsert(rid, "user:" + uid, grant_right, by)

    def user_right(self, rid, uid):
        """The right a named share grants uid on rid, or None. The single per-principal lookup the
        policy makes for an authenticated non-owner."""
        if not uid:
            return None
        return self._right(rid, "user:" + uid)

    def list_named(self, rid):
        """Named shares on rid (subject, right, created), newest first — for the owner's share list.
        The public share is reported separately via public_right()."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT subject, grant_right, created FROM shares "
                "WHERE rid=? AND subject LIKE 'user:%' ORDER BY created DESC", (rid,)).fetchall()
        return [{"subject": r["subject"], "right": r["grant_right"], "created": r["created"]}
                for r in rows]

    # ---- revoke / cleanup ----
    def revoke(self, rid, subject):
        """Remove one share (public or a named subject). Returns True iff a row was removed. Caller
        holds store.lock."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM shares WHERE rid=? AND subject=?", (rid, subject))
            return cur.rowcount > 0

    def delete_all_for(self, rid):
        """Drop every share on rid — called when the review itself is deleted so a deleted document
        leaves no dangling grants. Caller holds store.lock."""
        with self._connect() as conn:
            conn.execute("DELETE FROM shares WHERE rid=?", (rid,))

    # ---- internals ----
    def _upsert(self, rid, subject, grant_right, by):
        if grant_right not in _RANK:
            raise ValueError("grant_right must be 'view' or 'comment'")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO shares (rid, subject, grant_right, created, created_by) "
                "VALUES (?, ?, ?, ?, ?)", (rid, subject, grant_right, time.time(), by))

    def _right(self, rid, subject):
        with self._connect() as conn:
            row = conn.execute("SELECT grant_right FROM shares WHERE rid=? AND subject=?",
                               (rid, subject)).fetchone()
            return row["grant_right"] if row else None


def stronger(a, b):
    """The stronger of two rights (or None). "comment" > "view" > None. Pure helper the policy uses to
    combine a public grant with a named grant."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _RANK[a] >= _RANK[b] else b
