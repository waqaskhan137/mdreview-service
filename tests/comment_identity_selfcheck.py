#!/usr/bin/env python3
"""comment_identity_selfcheck.py — #368: a public review's comments must not disclose the
commenter's uid/email to a reader who is not entitled to it, verified as REAL API behaviour
against a running hosted instance (genuine magic-link logins, genuine cookies, no fixture).

THE DEFECT (reproduced live, prod + staging, before this fix).
  GET /api/reviews/{rid}/comments, called with NO cookie and NO token against a PUBLIC review,
  returned each thread entry's raw `author` — a magic-link user's full email
  ("email:waqaskhan137@gmail.com") or a proxy-plane user's stable provider sub
  ("google:100706495352040931339") — in cleartext to anyone holding the link. `created_by` and
  `status_history[0].by` carry the identical value (create() seeds all three from the same
  argument) and leaked exactly as much, through the SAME route plus every other arm that returns
  a full comment object (POST create/reply/resolve/reopen).

THE FIX UNDER TEST (CommentService.redact_identity, wired through H._visible_comments).
  Those three fields are visible to a reader only when the reader IS the entry's own author, or
  the reader is the document's owner (AccessPolicy.can_write — owner-only on every tier). Every
  other reader gets None there. thread[].name (#309's opt-in display name) and role/text/ts are
  UNCHANGED for everyone — a chosen label is not the leak. resolved_by and every
  reply/resolve/reopen thread or status_history entry are #287's plane-derived "reviewer"/"agent"
  literals, never identity, and untouched (resolve_attribution_selfcheck.py pins them).

WHO SEES WHAT (asserted below, one block each).
  - owner:            raw author/created_by/status_history[0].by for EVERY entry (their own doc,
                       and their own comment; either arm makes them entitled).
  - a "comment" grantee: raw values on entries THEY wrote; None on the owner's entry. Their own
                       POST /comments create response still carries their own raw uid (harmless —
                       you already know your own identity). Their reply POST response to the
                       OWNER's thread must NOT hand back the owner's raw identity.
  - a "view" grantee:  None on every entry (never their own; not the owner).
  - anonymous (no cookie, no token), the actual #368 scenario: None on every entry, AND the raw
                       response body — the whole JSON blob, not just the three known keys — never
                       contains an "email:" or "google:" tagged uid, the specific test email
                       addresses used below, or the owner's/grantee's raw uid strings.

Mutation coverage (see the run report, not encoded here): each of the three redacted fields is
independently load-bearing — the whole-body substring scan alone is not enough to name WHICH
field broke, so each also gets its own keyed assertion below.

Run: python3 tests/comment_identity_selfcheck.py     (exit 0 = pass)
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, ".scratch", "comment_identity_data")
OWNER_EMAIL = "owner368@example.com"
GRANTC_EMAIL = "grantee-comment-368@example.com"
GRANTV_EMAIL = "grantee-view-368@example.com"
OWNER_UID = "email:" + OWNER_EMAIL
GRANTC_UID = "email:" + GRANTC_EMAIL
GRANTV_UID = "email:" + GRANTV_EMAIL

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  [" + str(detail) + "]") if (not cond and detail != "") else ""))
    if not cond:
        fails.append(name)


def free():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # bypass a dead loopback proxy


def req(u, m="GET", d=None, h=None):
    r = urllib.request.Request(u, data=d, headers=h or {}, method=m)
    try:
        with OPENER.open(r, timeout=15) as x:
            return x.status, x.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(DATA, exist_ok=True)
port = free()
env = dict(os.environ, MDREVIEW_DATA=DATA, PORT=str(port), MDREVIEW_REQUIRE_AUTH="1",
           MDREVIEW_ALLOW_PROXY_PLANE="1", MDREVIEW_PROXY_SECRET="test-proxy-secret-368",
           MDREVIEW_SESSION_SECRET="s", MDREVIEW_TOKEN_PEPPER="p",
           MDREVIEW_OWNER_EMAIL=OWNER_EMAIL, MDREVIEW_ALLOW_STUB_EMAIL="1",
           MDREVIEW_PUBLIC_BASE="https://l.test",
           MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"),
           PYTHONPATH=os.path.join(ROOT, "src"))
log_path = os.path.join(DATA, "s.log")
log = open(log_path, "w")
srv = subprocess.Popen([sys.executable, "-m", "mdreview.hosted"], env=env, stdout=log, stderr=log)
base = "http://127.0.0.1:%d" % port


def login(email):
    """A GENUINE browser session: magic link (stub email -> server log) redeemed for Set-Cookie."""
    req(base + "/auth/magic-link", "POST", json.dumps({"email": email}).encode(),
        {"Content-Type": "application/json"})
    tok = None
    for _ in range(40):
        hits = re.findall(r"auth/redeem\?token=([A-Za-z0-9._~-]+)", open(log_path).read())
        if hits:
            tok = hits[-1]
            break
        time.sleep(0.25)

    class NR(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    op = urllib.request.build_opener(NR, urllib.request.ProxyHandler({}))
    rq = urllib.request.Request(base + "/auth/redeem", data=("token=" + (tok or "")).encode(),
                                headers={"Content-Type": "application/x-www-form-urlencoded"},
                                method="POST")
    try:
        rs = op.open(rq, timeout=15)
    except urllib.error.HTTPError as e:
        rs = e
    ck = rs.headers.get("Set-Cookie", "").split(";")[0]
    _, raw = req(base + "/auth/session", h={"Cookie": ck})
    sess = json.loads(raw)
    return ck, sess.get("csrf", "")


def hdr(ck, csrf=None):
    h = {"Content-Type": "application/json", "Cookie": ck}
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


try:
    for _ in range(60):
        try:
            req(base + "/healthz")
            break
        except Exception:
            time.sleep(0.25)

    ock, ocsrf = login(OWNER_EMAIL)
    gcck, gccsrf = login(GRANTC_EMAIL)
    gvck, gvcsrf = login(GRANTV_EMAIL)
    check("setup: three genuine sessions obtained", all([ock, gcck, gvck]))

    # ---- setup: a review, a comment-right grantee, a view-only grantee, made public ---------------
    _, raw = req(base + "/api/reviews", "POST",
                 json.dumps({"title": "identity probe", "markdown": "# x\n\nbody"}).encode(),
                 hdr(ock, ocsrf))
    rid = json.loads(raw)["id"]
    check("setup: review created", bool(rid), raw[:200])

    code, _ = req(base + f"/api/reviews/{rid}/shares", "POST",
                  json.dumps({"email": GRANTC_EMAIL, "right": "comment"}).encode(), hdr(ock, ocsrf))
    check("setup: comment-right grantee invited", code == 201, code)
    code, _ = req(base + f"/api/reviews/{rid}/shares", "POST",
                  json.dumps({"email": GRANTV_EMAIL, "right": "view"}).encode(), hdr(ock, ocsrf))
    check("setup: view-only grantee invited", code == 201, code)
    code, _ = req(base + f"/api/reviews/{rid}/public", "POST", b"{}", hdr(ock, ocsrf))
    check("setup: review made public", code == 200, code)

    # A: the owner's own comment. B: the comment-right grantee's own comment.
    _, raw = req(base + f"/api/reviews/{rid}/comments", "POST",
                 json.dumps({"anchor": {"block_num": 1}, "text": "owner's note"}).encode(),
                 hdr(ock, ocsrf))
    a = json.loads(raw)
    cidA = a["comment_id"]
    check("A: create response carries the owner's OWN raw uid (self-view is always harmless)",
          a["thread"][0].get("author") == OWNER_UID and a.get("created_by") == OWNER_UID
          and a["status_history"][0].get("by") == OWNER_UID, a)

    _, raw = req(base + f"/api/reviews/{rid}/comments", "POST",
                 json.dumps({"anchor": {"block_num": 1}, "text": "grantee's note"}).encode(),
                 hdr(gcck, gccsrf))
    b = json.loads(raw)
    cidB = b["comment_id"]
    check("B: create response carries the grantee's OWN raw uid",
          b["thread"][0].get("author") == GRANTC_UID and b.get("created_by") == GRANTC_UID
          and b["status_history"][0].get("by") == GRANTC_UID, b)

    def by_id(comments):
        return {c["comment_id"]: c for c in comments}

    # ---- owner: entitled, sees BOTH raw identities on BOTH comments --------------------------------
    print("\n1. the owner (entitled) sees full attribution on every comment")
    _, raw = req(base + f"/api/reviews/{rid}/comments", h={"Cookie": ock})
    rows = by_id(json.loads(raw)["comments"])
    check("...A (own): thread[0].author == owner's raw uid", rows[cidA]["thread"][0].get("author") == OWNER_UID)
    check("...A (own): created_by == owner's raw uid", rows[cidA].get("created_by") == OWNER_UID)
    check("...A (own): status_history[0].by == owner's raw uid", rows[cidA]["status_history"][0].get("by") == OWNER_UID)
    check("...B (grantee's): thread[0].author == grantee's raw uid (owner sees EVERYONE's)",
          rows[cidB]["thread"][0].get("author") == GRANTC_UID)
    check("...B (grantee's): created_by == grantee's raw uid", rows[cidB].get("created_by") == GRANTC_UID)
    check("...B (grantee's): status_history[0].by == grantee's raw uid", rows[cidB]["status_history"][0].get("by") == GRANTC_UID)

    # ---- comment-right grantee: raw on their OWN entry, None on the owner's -----------------------
    print("2. a comment-right grantee sees their own raw identity, and None on someone else's")
    _, raw = req(base + f"/api/reviews/{rid}/comments", h={"Cookie": gcck})
    rows = by_id(json.loads(raw)["comments"])
    check("...A (owner's, not theirs): thread[0].author is None", rows[cidA]["thread"][0].get("author") is None,
          rows[cidA]["thread"][0])
    check("...A (owner's): created_by is None", rows[cidA].get("created_by") is None)
    check("...A (owner's): status_history[0].by is None", rows[cidA]["status_history"][0].get("by") is None)
    check("...B (their own): thread[0].author == grantee's OWN raw uid",
          rows[cidB]["thread"][0].get("author") == GRANTC_UID)
    check("...B (their own): created_by == grantee's OWN raw uid", rows[cidB].get("created_by") == GRANTC_UID)

    # A reply to the OWNER's thread must not hand the owner's identity back in the 200 body — the
    # arm that does NOT go through the GET path, and the one most likely for a future refactor to
    # miss (advisor finding).
    code, raw = req(base + f"/api/reviews/{rid}/comments/{cidA}/reply", "POST",
                    json.dumps({"text": "a reply from the grantee"}).encode(), hdr(gcck, gccsrf))
    reply_body = raw.decode()
    check("...reply POST to A -> 200", code == 200, code)
    replyc = json.loads(raw)
    check("...the reply response's thread[0] (A's original entry) is STILL None, not the owner's uid",
          replyc["thread"][0].get("author") is None, replyc["thread"][0])
    check("...the raw reply response body contains no trace of the owner's email",
          OWNER_EMAIL not in reply_body and OWNER_UID not in reply_body, reply_body[:400])

    # ---- view-only grantee: None everywhere (never their own, never the owner) ---------------------
    print("3. a view-only grantee (the interesting middle case) sees None on every entry")
    _, raw = req(base + f"/api/reviews/{rid}/comments", h={"Cookie": gvck})
    rows = by_id(json.loads(raw)["comments"])
    check("...A: thread[0].author is None", rows[cidA]["thread"][0].get("author") is None)
    check("...B: thread[0].author is None", rows[cidB]["thread"][0].get("author") is None)
    check("...A: created_by is None", rows[cidA].get("created_by") is None)
    check("...B: created_by is None", rows[cidB].get("created_by") is None)
    # #309: a display NAME (opt-in, user-chosen) is deliberately NOT part of this redaction — every
    # reader keeps seeing it, unset renders as "" exactly as it always has.
    check("...role/name/text survive untouched (not an identity, never redacted)",
          rows[cidA]["thread"][0].get("role") == "reviewer" and rows[cidA]["thread"][0].get("name") == ""
          and rows[cidA]["thread"][0].get("text") == "owner's note")

    # ---- THE HEADLINE ASSERTION: anonymous, no cookie, no token ------------------------------------
    print("4. anonymous (no cookie, no token) — the actual #368 reproduction")
    code, raw = req(base + f"/api/reviews/{rid}/comments")   # zero auth headers of any kind
    body_text = raw.decode()
    check("anonymous GET .../comments on a public review -> 200 (D3: public is readable)", code == 200, code)
    anon = by_id(json.loads(raw)["comments"])
    check("...A: thread[0].author is None", anon[cidA]["thread"][0].get("author") is None, anon[cidA]["thread"][0])
    check("...A: created_by is None", anon[cidA].get("created_by") is None, anon[cidA].get("created_by"))
    check("...A: status_history[0].by is None", anon[cidA]["status_history"][0].get("by") is None,
          anon[cidA]["status_history"][0])
    check("...B: thread[0].author is None", anon[cidB]["thread"][0].get("author") is None)
    check("...B: created_by is None", anon[cidB].get("created_by") is None)
    check("...B: status_history[0].by is None", anon[cidB]["status_history"][0].get("by") is None)
    # A's thread[1] is the grantee's REPLY, not its create — #287's role literal ("reviewer"),
    # never a raw uid to begin with, so redaction correctly leaves it exactly as-is (only index 0
    # of thread[]/status_history[] is ever create()-seeded with a raw identity).
    check("...A's thread[1] (a reply, always a role literal) is untouched: \"reviewer\", not redacted",
          anon[cidA]["thread"][1].get("author") == "reviewer", anon[cidA]["thread"][1])
    # the "chosen label" decision, pinned: name is universal, unset renders "" for anonymous too —
    # this is NOT the leak (#309), asserted here so nobody "fixes" this into a second redaction.
    check("...thread[].name is STILL present and \"\" (unset) for anonymous — display names are not the leak",
          anon[cidA]["thread"][0].get("name") == "")
    # The whole-body scan: not just the three named keys, the ENTIRE raw response text, for the
    # exact strings this ticket's live reproduction showed leaking.
    check("...the raw response body contains NO \"email:\" tagged uid anywhere",
          "email:" not in body_text, body_text[:200])
    check("...the raw response body contains NO \"google:\"/proxy-shaped uid anywhere",
          "google:" not in body_text)
    check("...the raw response body contains neither test account's literal email address",
          OWNER_EMAIL not in body_text and GRANTC_EMAIL not in body_text and GRANTV_EMAIL not in body_text,
          body_text[:200])

    # Single-comment GET route independently, and the same anonymous caller
    code, raw = req(base + f"/api/reviews/{rid}/comments/{cidA}")
    single_text = raw.decode()
    single = json.loads(raw)
    check("anonymous GET single comment -> 200", code == 200, code)
    check("...single-comment route: thread[0].author is None", single["thread"][0].get("author") is None)
    check("...single-comment route: created_by is None", single.get("created_by") is None)
    check("...single-comment route body has no \"email:\"/\"google:\" substring either",
          "email:" not in single_text and "google:" not in single_text)

    # ---- resolve/reopen stay owner-only and stay fully attributed for the owner (no regression) ----
    print("5. resolve/reopen (owner-only) still return full attribution to the entitled owner")
    code, raw = req(base + f"/api/reviews/{rid}/comments/{cidB}/resolve", "POST",
                    json.dumps({"justification": "done"}).encode(), hdr(ock, ocsrf))
    resolved = json.loads(raw)
    check("owner resolve -> 200", code == 200, code)
    check("...resolved response still carries B's raw creator uid back to the owner (entitled)",
          resolved["thread"][0].get("author") == GRANTC_UID, resolved["thread"][0])
    check("...resolved_by is the role literal \"reviewer\" (#287, untouched by #368)",
          resolved.get("resolved_by") == "reviewer", resolved.get("resolved_by"))

finally:
    srv.terminate()
    srv.wait(timeout=10)
    log.close()

print()
print(("%d case(s) FAILED" % len(fails)) if fails else "all #368 comment-identity cases pass")
sys.exit(1 if fails else 0)
