#!/usr/bin/env python3
"""session_records_selfcheck.py — per-session records (#223).

This is the auth path: every authenticated request runs through verify(). The cases below are the
ones where a mistake is either a silent security hole or a mass logout, which is why they are
asserted rather than eyeballed:

  - a REVOKED jti must stop authenticating. That is the whole feature; if it does not hold,
    "sign out this device" is a lie that looks like it worked.
  - an UNKNOWN jti must be rejected. Otherwise a forged-but-unsigned... (the MAC already stops that)
    or a pruned row would silently re-admit a session.
  - a cookie with NO jti must STILL WORK (owner decision D3, grandfathering). Getting this wrong
    logs every existing user out on deploy, which is the exact thing #221 exists to prevent.
  - revocation must be uid-scoped, so one account cannot end another's session by guessing.
  - fail-CLOSED on the pair (jti present, records wired): the check must not be skippable.

Run: python3 tests/session_records_selfcheck.py   (exit 0 = pass, 1 = a case failed)
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from mdreview.hosted.identity_store import IdentityStore      # noqa: E402
from mdreview.hosted.sessions import SessionService           # noqa: E402

failed = []


def check(name, cond, detail=""):
    if cond:
        print("ok   - " + name)
    else:
        print("FAIL - " + name + (("  (" + detail + ")") if detail else ""))
        failed.append(name)


tmp = tempfile.mkdtemp(prefix="mdr223-")
try:
    store = IdentityStore(os.path.join(tmp, "identity.db"))
    svc = SessionService("test-secret-not-a-real-key", ttl_s=3600, records=store)

    # 1. Happy path: mint writes a row, and the cookie verifies.
    cookie, csrf = svc.mint("u1", "a@example.com", ip="1.2.3.4", user_agent="UA/1")
    s = svc.verify(cookie)
    check("a minted session verifies", s is not None and s.uid == "u1")
    check("the payload carries a jti", bool(s and s.jti))
    check("the row is listed for its owner", len(store.sessions_for("u1")) == 1)
    check("ip and user-agent are recorded for the device list",
          store.sessions_for("u1")[0]["ip"] == "1.2.3.4" and
          store.sessions_for("u1")[0]["user_agent"] == "UA/1")

    # 2. THE FEATURE. Revoke it and the very same cookie must stop working.
    store.session_revoke(s.jti, uid="u1")
    check("a REVOKED session no longer verifies", svc.verify(cookie) is None)
    check("a revoked session disappears from the list", store.sessions_for("u1") == [])

    # 3. A revoked row is kept, not deleted: it must stay rejected, not become "unknown".
    check("the revoked row is retained (rejection is durable)",
          store.session_live(s.jti) is False)

    # 4. GRANDFATHERING (D3). A pre-#223 cookie has no jti and must still authenticate, or the
    #    deploy logs everyone out.
    stateless = SessionService("test-secret-not-a-real-key", ttl_s=3600)   # no records
    old_cookie, _ = stateless.mint("u2", "b@example.com")
    import base64 as _b64, json as _json
    p = old_cookie.split(".")[0]
    payload = _json.loads(_b64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    # Simulate a genuinely pre-#223 cookie: signed, but with no jti key at all.
    del payload["jti"]
    raw = _json.dumps(payload, separators=(",", ":")).encode()
    pb = _b64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    legacy = pb + "." + svc._mac(pb)
    ls = svc.verify(legacy)
    check("a cookie with NO jti is GRANDFATHERED, not rejected", ls is not None)
    check("a grandfathered session reports an empty jti", ls is not None and ls.jti == "")

    # 5. An unknown jti (row never existed, or was pruned after expiry) is rejected.
    cookie2, _ = svc.mint("u3", "c@example.com")
    s2 = svc.verify(cookie2)
    store.sessions_prune(now=time.time() + 999999)      # expire everything
    check("an unknown jti is rejected", svc.verify(cookie2) is None)

    # 6. Revocation is uid-scoped: u4 cannot end u5's session even holding the jti.
    c4, _ = svc.mint("u4", "d@example.com")
    c5, _ = svc.mint("u5", "e@example.com")
    j5 = svc.verify(c5).jti
    check("cross-account revoke is refused", store.session_revoke(j5, uid="u4") is False)
    check("the victim's session still works", svc.verify(c5) is not None)
    check("the owner CAN revoke it", store.session_revoke(j5, uid="u5") is True)
    check("and then it stops working", svc.verify(c5) is None)

    # 7. Sign out everywhere else keeps the caller's own session alive.
    a, _ = svc.mint("u6", "f@example.com")
    b, _ = svc.mint("u6", "f@example.com")
    c, _ = svc.mint("u6", "f@example.com")
    keep = svc.verify(a).jti
    n = store.session_revoke_all("u6", except_jti=keep)
    check("sign out others revokes exactly the others", n == 2, "revoked=%d" % n)
    check("the current session survives", svc.verify(a) is not None)
    check("the other sessions are dead", svc.verify(b) is None and svc.verify(c) is None)

    # 8. last_seen is throttled, or the read path becomes a write path on every request.
    g, _ = svc.mint("u7", "g@example.com")
    jg = svc.verify(g).jti
    check("an immediate touch is throttled away", store.session_touch(jg) is False)
    check("a touch past the window writes",
          store.session_touch(jg, now=time.time() + store.LAST_SEEN_THROTTLE_S + 1) is True)

    # 9. Expiry still applies independently of revocation.
    short = SessionService("test-secret-not-a-real-key", ttl_s=1, records=store)
    e, _ = short.mint("u8", "h@example.com")
    check("an expired session is rejected even though its row is live",
          short.verify(e, now=time.time() + 5) is None)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n" + (str(len(failed)) + " case(s) failed" if failed else "all session-record cases pass"))
sys.exit(1 if failed else 0)
