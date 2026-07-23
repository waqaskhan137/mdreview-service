"""CustodyPolicy (#102): the owner-only Confinement base (#97) PLUS the audited, platform-granted
admin super-READ exception. This IS the Confinement invariant's third arm, built INTO the custody
model rather than bolted around it:

    served if  p == owner(d)                              (the base, unchanged)
          OR   p holds an owner-granted share on d         (#101/#68, not built here)
          OR   p is an admin under an audited platform grant  (this file, read-only)

The exception is deliberately narrow, and the narrowness is the whole point of shipping it as a
feature instead of leaving it as the #97 breach it re-creates on purpose:

  - LEAST-PRIVILEGE. Only can_read is extended. can_write / can_delete are inherited unchanged from
    OwnerPolicy, so there is NO admin super-write / super-delete path AT ALL, by construction - an
    admin can never mutate a document they do not own. scope_list is inherited too: super-read is a
    per-document, audited act, never a firehose that dumps every stranger's work into the admin's
    dashboard list.
  - OFF BY DEFAULT. The grant is Principal.super_read, which is False unless a hosted user record
    explicitly holds it (UserService.set_super_read). is_admin alone does NOT grant it.
  - AUDITED. can_read stays a pure predicate (no side effects - the handler may probe it). The
    handler learns a grant was a super-read via audit_super_access() and writes the immutable record
    through the core _audit() sink (server.py). Un-audited god-mode is exactly what this forbids.
"""
from mdreview.access import OwnerPolicy


class CustodyPolicy(OwnerPolicy):
    def _super_read_ok(self, principal, rid):
        """True iff THIS read is served only by the platform grant: an admin who holds the explicit
        super_read grant, ON THE COOKIE (browser) PLANE, reading a document that exists and that they
        do NOT own (an owner reads by the base rule, never the exception, so self-access is never
        audited as a super-read).

        The cookie-plane requirement keeps super-access an ATTENDED human act (do-not-enable-
        unattended, #102): an admin's long-lived agent token can NEVER super-read every document in
        the background - only a person in a live browser session can, and every such read is audited.
        This is the safest-reversible default; it can be loosened to other planes later if a genuine
        need appears."""
        return (bool(getattr(principal, "super_read", False))
                and bool(getattr(principal, "is_admin", False))
                and getattr(principal, "plane", "") == "cookie"
                and self._reviews.exists(rid)
                and not self._owns(principal, rid))

    def can_read(self, principal, rid):
        # Owner first (the common path, and it keeps an owner off the audited branch); then the
        # narrow, audited admin exception.
        return self._owns(principal, rid) or self._super_read_ok(principal, rid)

    # can_write / can_delete / scope_list / stamp_owner: inherited from OwnerPolicy unchanged. There
    # is intentionally NO admin branch on the mutating verbs - super-access is READ-only.

    def audit_super_access(self, principal, rid):
        """The handler's classifier for the core _audit() sink: a record dict iff this access is a
        platform-grant super-read (who = admin uid, which = rid, plus the real owner), else None. No
        side effects - the handler emits the audit and adds when/where/what (ts, ip, method+path)."""
        if not self._super_read_ok(principal, rid):
            return None
        return {"uid": principal.uid, "rid": rid, "owner": self._reviews.owner(rid)}
