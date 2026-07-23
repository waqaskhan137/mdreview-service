"""CustodyPolicy — the hosted AccessPolicy that IS the custody Confinement contract (#97) with ALL
THREE arms the invariant names composed into one policy: owner, owner-granted share (#101 public /
#68 named), and the audited platform-admin super-READ exception (#102).

    read served if   p == owner(d)                                    (the base, unchanged)
              OR      p holds an owner-granted share on d              (#101 public / #68 named)
              OR      p is an admin under an audited platform grant    (#102, read-only)

The narrowness of each non-owner arm is the whole point; the load-bearing invariant is that NONE of
them widens write:

  - OWNER-ONLY WRITE/DELETE (the invariant, not weakened). can_write / can_delete consult ONLY
    ownership (reviews.can_access — the durable provider:sub check, never re-keyed, the #97 failure
    class). A share NEVER widens write; the admin grant is READ-only. There is NO share path and NO
    admin path to can_write / can_delete AT ALL, by construction.
  - SHARES (#101/#68). A PUBLIC share grants VIEW to EVERY principal, incl. the anonymous one (the
    seam yields is_anonymous and consults the policy before demanding identity, so a public link
    needs no account). D3: public is VIEW-ONLY, never comment. A NAMED share ("user:<uid>") grants
    its stated right (view | view+comment) to that one grantee. A "comment" grant widens can_comment
    (post a note / reply), NOT can_write. can_comment admits the owner and a comment-share grantee
    ONLY — a view-only or anonymous principal may NOT comment (D3: no anonymous comments).
  - ADMIN SUPER-READ (#102), least-privilege + off-by-default + cookie-plane + audited. Only can_read
    is extended, and only for a principal that explicitly holds Principal.super_read (never implied by
    is_admin), on the cookie (browser) plane (an attended human act — an agent token can never
    background-read every doc), reading a doc that exists and that they do NOT own. scope_list stays
    owner-scoped, so super-read is a per-document audited act, never a firehose into the admin's
    dashboard. can_read stays a pure predicate; the handler classifies the grant via
    audit_super_access() and writes the immutable record through the core _audit() sink (server.py).

A non-shared document is still indistinguishable from absent to a plain non-owner: can_read returns
False and the handler answers 404. Composition, not inheritance: the owner decision is
reviews.can_access, the share decision is the injected ShareStore, the admin decision reads the
Principal's grant. CustodyPolicy lives in the hosted package and is wired ONLY by build_hosted, so the
core/local tier never constructs it.
"""
from mdreview.hosted.shares import stronger


class CustodyPolicy:
    def __init__(self, reviews, shares):
        self._reviews = reviews
        self._shares = shares

    def _owns(self, principal, rid):
        """True iff principal is the authenticated owner of an existing rid. Anonymous or uid-less
        principals never own (a public read must not masquerade as ownership)."""
        return (not principal.is_anonymous and principal.uid is not None
                and self._reviews.exists(rid)
                and self._reviews.can_access(rid, principal.uid))

    def _granted_right(self, principal, rid):
        """The strongest right any owner-granted share confers on principal for rid: the public share
        (applies to everyone, incl. anonymous) combined with this principal's named share. None if
        neither applies. The single share lookup the read/comment decisions share."""
        right = self._shares.public_right(rid)
        if not principal.is_anonymous and principal.uid is not None:
            right = stronger(right, self._shares.user_right(rid, principal.uid))
        return right

    def _super_read_ok(self, principal, rid):
        """True iff THIS read is served only by the platform grant (#102): an admin who holds the
        explicit super_read grant, ON THE COOKIE (browser) PLANE, reading a document that exists and
        that they do NOT own (an owner reads by the base rule, never the exception, so self-access is
        never audited as a super-read; a share grantee likewise passes _granted_right, not here).

        The cookie-plane requirement keeps super-access an ATTENDED human act (do-not-enable-
        unattended, #102): an admin's long-lived agent token can NEVER super-read every document in the
        background — only a person in a live browser session can, and every such read is audited."""
        return (bool(getattr(principal, "super_read", False))
                and bool(getattr(principal, "is_admin", False))
                and getattr(principal, "plane", "") == "cookie"
                and self._reviews.exists(rid)
                and not self._owns(principal, rid))

    def can_read(self, principal, rid):
        # Owner first (the common path, and it keeps an owner off the audited branch); then existence
        # gates BEFORE any share/admin lookup so a non-existent rid stays a clean False (-> 404), never
        # a probe a stray share row or admin grant could turn truthy; then the owner-granted share
        # (#101/#68); then the narrow, audited admin super-read (#102).
        if self._owns(principal, rid):
            return True
        if not self._reviews.exists(rid):
            return False
        if self._granted_right(principal, rid) is not None:
            return True
        return self._super_read_ok(principal, rid)

    def can_comment(self, principal, rid):
        """Post a comment / reply. The owner may; a "comment"-share grantee may; a "view"-only or
        anonymous principal may NOT (D3: no anonymous comments), and neither does the admin super-read
        grant (it is READ-only — no super-comment). Distinct from can_write."""
        if self._owns(principal, rid):
            return True
        if not self._reviews.exists(rid):
            return False
        return self._granted_right(principal, rid) == "comment"

    def can_write(self, principal, rid):
        """OWNER-ONLY (the load-bearing invariant). Editing the source, handing off the baton,
        resolving/reopening — the owner's alone. A share NEVER widens write and the admin grant is
        read-only; owner isolation is not weakened for a shared doc nor for an admin."""
        return self._owns(principal, rid)

    def can_delete(self, principal, rid):
        """OWNER-ONLY, like can_write. No share path, no admin path."""
        return self._owns(principal, rid)

    def scope_list(self, principal):
        """The dashboard lists the caller's OWNED documents only. Shared-in documents are reached by
        their link, not listed here (a "shared with me" listing is a v1 TODO), and super-read is a
        per-document audited act — NEVER a firehose that dumps every stranger's work into an admin's
        list. So the list scope stays a pure owner scope and list_reviews is untouched."""
        return principal.uid

    def stamp_owner(self, principal):
        """Creation binds the document to the creating principal's durable uid (Totality)."""
        return principal.uid

    def audit_super_access(self, principal, rid):
        """The handler's classifier for the core _audit() sink: a record dict iff this access is a
        platform-grant super-read (who = admin uid, which = rid, plus the real owner), else None (an
        owner read, a share read, or a plain denial audits nothing here). No side effects — the handler
        emits the audit and adds when/where/what (ts, ip, method+path)."""
        if not self._super_read_ok(principal, rid):
            return None
        return {"uid": principal.uid, "rid": rid, "owner": self._reviews.owner(rid)}
