"""Human-confirm custody reconciliation: the ONE sanctioned way to give an unowned record an owner.

Replaces the deleted blind migrate (slice 3, #111). Custody contract (#97 epic, slice 4, #112):

  - An unowned record is `owner == ""`. can_access fails CLOSED on it (reviews.py), so it is already
    inaccessible to everyone. There is NO separate "quarantined" persisted state: quarantined simply
    MEANS owner == "" surfaced by this tool. A second marker would be a parallel source of truth that
    drifts from owner == "" and forces every reader (can_access, list_reviews, the slice-6 tripwire)
    to learn a new state, for zero behavioural gain. So: quarantined == owner == "".

  - A record's provenance (project / source_path / session) is ATTACKER-CONTROLLED free text from the
    POST body. It is displayed to a human operator as an explicitly UNTRUSTED hint and NOTHING else.
    This tool deliberately does NOT compute a candidate owner from provenance: an index mapping
    attacker-supplied strings to a concrete `provider:sub` would launder untrusted input into an
    authoritative-looking suggestion that a tired operator rubber-stamps -- i.e. the blind migrate
    with extra steps. "Suggested" here means "the human reads the hint and corroborates it", not a
    machine guess. Records with empty provenance surface with no hint at all, never auto-bound.

  - `confirm` is the sole owner-writing path. It is PER-RECORD (one rid, one owner id, both explicit
    on the command line -- that IS the human confirmation) with NO bulk/blanket form, and it REFUSES
    to overwrite a record whose owner is already set (no re-key; AC4 / #67 D1: the durable provider:sub
    is written once and never re-keyed).

Usage:
    python -m mdreview.reconcile list
    python -m mdreview.reconcile confirm <rid> <owner_id>     # owner_id = provider:sub
"""
import json
import os
import sys

from mdreview.config import DATA_DIR
from mdreview.store import Store
from mdreview.users import UserService


def valid_owner_id(owner_id):
    """True iff owner_id has the canonical provider:sub shape (both sides non-empty).

    Mirrors UserService.canonical's contract without re-deriving it: a bare sub is rejected because
    two providers can share a numeric sub.
    """
    if not owner_id or ":" not in owner_id:
        return False
    provider, sub = owner_id.split(":", 1)
    return bool(provider.strip()) and bool(sub.strip())


class Reconciler:
    """Surfaces unowned records with their untrusted provenance and binds one owner on explicit
    human confirmation. Constructed with the single Store (users read-only, for the known/unknown
    warning -- no pepper needed, it never touches tokens)."""

    def __init__(self, store):
        self.store = store
        self.users = UserService(store, "")

    def unowned(self):
        """Every record with no owner, newest first. Provenance fields are returned VERBATIM and are
        untrusted: callers must present them as hints, never act on them."""
        out = []
        for rid in os.listdir(self.store.data_dir):
            if not self.store.exists(rid):
                continue
            m = self.store.read_json(os.path.join(self.store.dir(rid), "meta.json"), {})
            if m.get("owner"):
                continue
            out.append({
                "rid": rid,
                "title": m.get("title", ""),
                "created": m.get("created", 0),
                # untrusted provenance -- display only
                "project": m.get("project", ""),
                "source_path": m.get("source_path", ""),
                "session": m.get("session", ""),
            })
        out.sort(key=lambda r: r.get("created", 0), reverse=True)
        return out

    def is_known_user(self, owner_id):
        """Whether owner_id is already a provisioned user. A False here is a warning, not a block:
        the legitimate owner may simply not have signed in yet."""
        return bool(self.users._load()["users"].get(owner_id))

    def confirm(self, rid, owner_id):
        """Bind owner_id to rid. The SOLE owner-writing path. Raises ValueError on any refusal:
        unknown rid, malformed owner id, or an already-owned record (no re-key). Re-reads meta under
        store.lock immediately before writing and bails if the owner became non-empty, so this tool
        stays the single writer of a legacy record's owner even if the server is running (the server
        sets owner only at create, never rewrites it)."""
        if not self.store.exists(rid):
            raise ValueError("no such record: %s" % rid)
        if not valid_owner_id(owner_id):
            raise ValueError("owner id must be provider:sub (both non-empty), got: %r" % owner_id)
        p = os.path.join(self.store.dir(rid), "meta.json")
        with self.store.lock:
            m = self.store.read_json(p, {})
            existing = m.get("owner", "")
            if existing:
                raise ValueError(
                    "record %s already owned by %s; refusing to re-key (no bulk, no overwrite)"
                    % (rid, existing))
            m["owner"] = owner_id
            self.store.write_text(p, json.dumps(m))


def _cmd_list(rec):
    rows = rec.unowned()
    if not rows:
        print("no unowned records: nothing to reconcile.")
        return 0
    print("%d unowned record(s). Provenance below is ATTACKER-CONTROLLED and UNTRUSTED -- a hint for"
          % len(rows))
    print("a human to corroborate, never a machine suggestion. Bind one with:")
    print("    python -m mdreview.reconcile confirm <rid> <owner_id>\n")
    for r in rows:
        print("rid:         %s" % r["rid"])
        print("  title:       %s" % (r["title"] or "(none)"))
        print("  UNTRUSTED hint  project=%r  source_path=%r  session=%r"
              % (r["project"], r["source_path"], r["session"]))
        if not (r["project"] or r["source_path"] or r["session"]):
            print("  (no provenance -- no hint; requires explicit human assignment)")
        print("")
    return 0


def _cmd_confirm(rec, rid, owner_id):
    try:
        rec.confirm(rid, owner_id)
    except ValueError as e:
        print("refused: %s" % e, file=sys.stderr)
        return 1
    warn = "" if rec.is_known_user(owner_id) else "  [WARNING: owner is not a known user -- verify the id is correct]"
    print("bound: record %s -> owner %s%s" % (rid, owner_id, warn))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rec = Reconciler(Store(DATA_DIR))
    if len(argv) == 1 and argv[0] == "list":
        return _cmd_list(rec)
    if len(argv) == 3 and argv[0] == "confirm":
        return _cmd_confirm(rec, argv[1].strip(), argv[2].strip())
    print("usage:\n"
          "  python -m mdreview.reconcile list\n"
          "  python -m mdreview.reconcile confirm <rid> <owner_id>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
