"""CustodyPolicy — the hosted AccessPolicy that IS the custody Confinement contract (#97) EXTENDED
with the owner-granted sharing exception the invariant names (#101 public, #68 named collaboration).

The custody design states Confinement as: an access to d by principal p is served iff
  p == owner(d)  OR  p holds an explicit owner-granted share on d  (OR p is an audited admin — #102,
not built here). CustodyPolicy is exactly that: owner-only for every WRITE/DELETE (owner isolation is
NOT weakened), plus reads/comments that a share grants:

  - a PUBLIC share grants VIEW to EVERY principal, including the anonymous one (the seam yields
    is_anonymous and consults the policy before demanding identity, so a public link needs no
    account). D3: public is view-only, never comment.
  - a NAMED share ("user:<uid>") grants its stated right (view | view+comment) to that one grantee.

Owner-only stays owner-only: can_write / can_delete consult ONLY ownership (via reviews.can_access,
the same durable provider:sub check OwnerPolicy uses — never re-keyed, the #97 failure class). A
"comment" grant widens can_comment (post a note / reply), NOT can_write (edit the source, resolve,
delete) — those remain the owner's. A non-shared document is therefore still indistinguishable from
absent to a non-owner: can_read returns False, the handler answers 404.

Composition, not inheritance: the owner decision is reviews.can_access; the share decision is the
injected ShareStore. Neither is a hosted import the core makes — CustodyPolicy lives in the hosted
package and is wired only by build_hosted, so the core/local tier never constructs it.
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

    def can_read(self, principal, rid):
        if self._owns(principal, rid):
            return True
        # Existence gates BEFORE the share lookup so a non-existent rid stays a clean False (-> 404),
        # never a probe that a stray share row could turn truthy.
        if not self._reviews.exists(rid):
            return False
        return self._granted_right(principal, rid) is not None

    def can_comment(self, principal, rid):
        """Post a comment / reply. The owner may; a "comment"-share grantee may; a "view"-only or
        anonymous principal may NOT (D3: no anonymous comments). Distinct from can_write."""
        if self._owns(principal, rid):
            return True
        if not self._reviews.exists(rid):
            return False
        return self._granted_right(principal, rid) == "comment"

    def can_write(self, principal, rid):
        """Owner-only. Editing the source, handing off the baton, resolving/reopening — the owner's
        alone. A share NEVER widens write; owner isolation is not weakened for a shared doc."""
        return self._owns(principal, rid)

    def can_delete(self, principal, rid):
        """Owner-only, like can_write."""
        return self._owns(principal, rid)

    def scope_list(self, principal):
        """The dashboard lists the caller's OWNED documents. Shared-in documents (shared TO the
        caller) are reached by their link, not listed here — a "shared with me" listing is a v1 TODO,
        deliberately deferred so this stays a pure owner scope and list_reviews is untouched."""
        return principal.uid

    def stamp_owner(self, principal):
        """Creation binds the document to the creating principal's durable uid (Totality)."""
        return principal.uid
