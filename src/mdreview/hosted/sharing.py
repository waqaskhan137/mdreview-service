"""Owner-facing share management (#101 public link, #68 named collaboration), dispatched through the
core feature-module seam (the same `handle(h, m, path) -> bool` protocol AuthModule / latex use), so
the core router gains these routes with zero core changes. Hosted-only: build_hosted registers it;
the local/core tier never does.

Routes (owner-only, with ONE grantee exception carved out by #284 D2 — see DELETE .../shares below):
  GET    /api/reviews/{id}/shares            list the public state + named shares (owner view).
  POST   /api/reviews/{id}/public            make public (view-only; D3 — no anonymous comments).
  DELETE /api/reviews/{id}/public            make private (revoke the public share; immediate).
  POST   /api/reviews/{id}/shares  {email,right?}  invite a named grantee (right = view|comment).
  DELETE /api/reviews/{id}/shares?subject=|email=  revoke one share (immediate). Owner: any subject.
                                              #284 D2: OR a non-owning grantee revoking EXACTLY their
                                              own "user:<self>" row (dashboard "Remove from your
                                              list"), destructive, no undo. See _revoke.

Authorization (the load-bearing part):
  - /public and the GET/POST arms of /shares stay OWNER-ONLY, checked via reviews.can_access (the
    SAME durable-provider:sub owner check the policy uses) — NEVER via policy.can_read, so a
    view/comment grantee can never escalate to grant a share or make a document public. A non-owner
    (or an absent review) gets 404, indistinguishable from absent (ownership is not probeable).
  - DELETE .../shares (_revoke) is the one arm with a second authorized caller (#284 D2): a grantee
    may delete ONLY the row naming their own uid. Checked by exact string equality on the resolved
    subject ("user:" + caller uid), never by policy.can_read or any fuzzier test — so a grantee can
    never touch another grantee's row, and a stranger with no grant at all still gets the same 404
    an owner-only route gives (not owner, not your own row -> indistinguishable from absent).
  - Authenticated via the session OR the agent token (either owner plane). CSRF is enforced only when
    a real app-owned session cookie verifies (defence-in-depth behind SameSite=Lax). The transitional
    proxy plane carries no such cookie and the token plane is not a browser, so neither presents a
    CSRF token; this matches the existing /account/tokens posture and is a NAMED transition risk in
    the PR (retire with the proxy plane).

Share grant/revoke is a CUSTODY event, audited core-side via the handler's _audit (the audit split:
document-access decisions are logged where the policy lives, not in the identity service).
"""
import json
import re
from urllib.parse import parse_qs, urlparse

from mdreview.config import RID
from mdreview.hosted.sessions import SessionService

_SEC_HEADERS = (("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"))
_RIGHTS = ("view", "comment")


class SharingModule:
    def __init__(self, reviews, shares, sessions, users):
        self.reviews = reviews
        self.shares = shares
        self.sessions = sessions
        self.users = users

    # ---- dispatch ----
    def handle(self, h, m, path):
        mo = re.fullmatch(r"/api/reviews/" + RID + r"/public", path)
        if mo:
            return self._public(h, m, mo.group(1))
        mo = re.fullmatch(r"/api/reviews/" + RID + r"/shares", path)
        if mo:
            return self._shares(h, m, mo.group(1))
        if path == "/api/account/shares" and m == "GET":
            return self._account_shares(h)
        return False

    # ---- account-wide view: what of mine is reachable by someone else (#262) ----
    def _account_shares(self, h):
        """GET /api/account/shares — every review of MINE that is public and/or has named
        grantees. The account page's "what can others reach" section.

        The gate is `list_reviews(uid=...)`, which scopes to reviews this user owns. It is NOT
        shares.created_by: created_by records who GRANTED a share, a different question from who
        OWNS the document, and conflating them would let a grantee-who-granted see a review they
        do not own.

        The per-review can_access below is deliberate defence in depth, and the two guards are
        MUTUALLY redundant: list_reviews already applies can_access internally, so removing either
        one alone changes nothing observable. Recorded because it matters for testing — no single
        mutation can make the cross-user case fail, and only removing BOTH does (verified: the
        check then reports a different user seeing another user's shares). An unlabelled pair like
        this invites a future reader to delete one "safely" and a future test to pass vacuously. Reviews with
        no public link and no grantees are omitted entirely rather than returned empty, so the
        page's list is exactly the set that needs attention."""
        p = h.server.app.identity.principal(h)
        if p.is_anonymous:
            self._json(h, 401, {"error": "authentication required"})
            return True
        items = []
        for r in self.reviews.list_reviews(uid=p.uid):
            rid = r.get("id")
            if not rid or not self.reviews.can_access(rid, p.uid):
                continue
            public = self.shares.public_right(rid)
            named = self.shares.list_named(rid)
            if not public and not named:
                continue
            items.append({
                "id": rid,
                "title": r.get("title", "") or rid,
                "public": public or None,
                "shares": [{"subject": n.get("subject", ""),
                            # Resolve server-side: list_named returns an opaque user:<provider:sub>.
                            # "" means we genuinely do not know, and the UI must say so (#267).
                            "email": self.users.email_for((n.get("subject") or "").replace("user:", "", 1)),
                            "right": n.get("right") or n.get("grant_right", "")} for n in named],
            })
        self._json(h, 200, {"items": items})
        return True

    # ---- response helper (core _send hardcodes CORS headers we don't need here) ----
    @staticmethod
    def _json(h, code, obj):
        body = json.dumps(obj).encode("utf-8")
        h.send_response(code)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(body)))
        for k, v in _SEC_HEADERS:
            h.send_header(k, v)
        h.end_headers()
        h.wfile.write(body)

    def _owner(self, h, rid, mutating):
        """Resolve the caller and require they OWN rid. Returns the Principal, or None AFTER writing
        the 401/404/403 (the caller returns True). Owner-only via reviews.can_access — not the
        shareable policy — so a share recipient cannot manage the share."""
        app = h.server.app
        p = app.identity.principal(h)
        if p.is_anonymous:
            self._json(h, 401, {"error": "authentication required"})
            return None
        if not (self.reviews.exists(rid) and self.reviews.can_access(rid, p.uid)):
            self._json(h, 404, {"error": "not found"})           # not owner -> 404, not probeable
            return None
        if mutating:
            cookie = SessionService.read_cookie(h)
            sess = self.sessions.verify(cookie) if cookie else None
            # Only the real app-owned session plane presents (and must pass) a CSRF token. No session
            # cookie => proxy/token plane => no CSRF gate here (see the module docstring's named risk).
            if sess and not self.sessions.check_csrf(sess, h.headers.get("X-CSRF-Token", "")):
                self._json(h, 403, {"error": "missing or invalid CSRF token"})
                return None
        return p

    # ---- /public toggle ----
    def _public(self, h, m, rid):
        if m == "POST":
            p = self._owner(h, rid, mutating=True)
            if p is None:
                return True
            # D3: public is VIEW-ONLY. Any requested right is ignored; a public share never comments.
            with h.server.app.store.lock:
                self.shares.set_public(rid, "view", p.uid)
            h._audit("share_public_on", uid=p.uid, rid=rid)
            self._json(h, 200, {"rid": rid, "public": True, "right": "view"})
            return True
        if m == "DELETE":
            p = self._owner(h, rid, mutating=True)
            if p is None:
                return True
            with h.server.app.store.lock:
                self.shares.remove_public(rid)
            h._audit("share_public_off", uid=p.uid, rid=rid)
            self._json(h, 200, {"rid": rid, "public": False})
            return True
        return False

    # ---- named shares ----
    def _shares(self, h, m, rid):
        if m == "GET":
            p = self._owner(h, rid, mutating=False)
            if p is None:
                return True
            self._json(h, 200, {"rid": rid, "public": self.shares.public_right(rid),
                                # Resolve email server-side, exactly as _account_shares does:
                                # list_named returns an opaque user:<provider:sub>. "" means we
                                # genuinely do not know, and the UI must say so (#267); it is
                                # never invented from the uid.
                                "shares": [{**n, "email": self.users.email_for(
                                                (n.get("subject") or "").replace("user:", "", 1))}
                                           for n in self.shares.list_named(rid)]})
            return True
        if m == "POST":
            return self._invite(h, rid)
        if m == "DELETE":
            return self._revoke(h, rid)
        return False

    def _invite(self, h, rid):
        p = self._owner(h, rid, mutating=True)
        if p is None:
            return True
        b = h._body_json()
        email = (b.get("email") or "").strip()
        right = (b.get("right") or "view").strip()
        if right not in _RIGHTS:
            self._json(h, 400, {"error": "right must be 'view' or 'comment'"})
            return True
        if not email:
            self._json(h, 400, {"error": "email required"})
            return True
        # v1 DECISION: invite an EXISTING account only. An invite to an unregistered email is refused
        # (no pending-share that binds on first login) — simpler and a smaller abuse surface. The
        # invitee signs in once (any plane provisions their account), then the invite resolves. Keyed
        # on the durable provider:sub so the share follows them across login methods.
        grantee = self.users.find_by_email(email)
        if not grantee:
            self._json(h, 404, {"error": "no account for that email; ask them to sign in once first"})
            return True
        if grantee == p.uid:
            self._json(h, 400, {"error": "you already own this document"})
            return True
        with h.server.app.store.lock:
            self.shares.invite(rid, grantee, right, p.uid)
        h._audit("share_invite", uid=p.uid, rid=rid, detail=right)
        self._json(h, 201, {"rid": rid, "subject": "user:" + grantee, "right": right})
        return True

    def _revoke(self, h, rid):
        """DELETE /api/reviews/{id}/shares — revoke one share. Two distinct authorized callers on
        the SAME route (#284 D2):
          - the OWNER may revoke ANY subject (public or named) — unchanged from before #284.
          - a NAMED GRANTEE who does NOT own the document may revoke ONLY their own row (the
            dashboard's "Remove from your list" X on the inbound "Shared with you" group) —
            subject must equal EXACTLY "user:<their own uid>". Any other subject from a non-owner
            is refused with the same 404 an owner-only route gives a stranger: ownership (or the
            mere existence of some other grant) must never be probeable, and a grantee must never
            be able to touch anyone else's share. Destructive — self-revoke deletes the row; regaining
            access needs a fresh invite from the owner (#284 D2, no undo, no hide flag).

        Identity is resolved and the anonymous case answered FIRST, before subject/email is even
        parsed, so an unauthenticated caller still gets 401 and never reaches find_by_email (the
        pre-#284 ordering, preserved)."""
        app = h.server.app
        p = app.identity.principal(h)
        if p.is_anonymous:
            self._json(h, 401, {"error": "authentication required"})
            return True
        q = parse_qs(urlparse(h.path).query)
        subject = (q.get("subject") or [""])[0].strip()
        email = (q.get("email") or [""])[0].strip()
        if not subject and email:                        # convenience: revoke by the invitee's email
            g = self.users.find_by_email(email)
            subject = "user:" + g if g else ""
        if not subject:
            self._json(h, 400, {"error": "subject or email required"})
            return True
        is_owner = self.reviews.exists(rid) and self.reviews.can_access(rid, p.uid)
        is_self = p.uid is not None and subject == "user:" + p.uid
        if not is_owner and not is_self:
            self._json(h, 404, {"error": "not found"})    # not owner, not your own row -> 404
            return True
        # Same cookie-plane CSRF gate _owner(mutating=True) applies to an owner's mutating calls;
        # a self-revoke is equally mutating and gets the identical gate.
        cookie = SessionService.read_cookie(h)
        sess = self.sessions.verify(cookie) if cookie else None
        if sess and not self.sessions.check_csrf(sess, h.headers.get("X-CSRF-Token", "")):
            self._json(h, 403, {"error": "missing or invalid CSRF token"})
            return True
        with app.store.lock:
            removed = self.shares.revoke(rid, subject)
        h._audit("share_revoke", uid=p.uid, rid=rid, detail=subject,
                  self_revoke=(is_self and not is_owner))
        self._json(h, 200 if removed else 404,
                   {"revoked": subject} if removed else {"error": "no such share"})
        return True
