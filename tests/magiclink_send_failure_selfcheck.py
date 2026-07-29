#!/usr/bin/env python3
"""magiclink_send_failure_selfcheck.py — #302: an SMTP rejection must not break anti-enumeration.

WHAT THIS GUARDS. POST /auth/magic-link deliberately returns ONE constant 200 body for every
outcome (unknown address, throttled, blocked), so a caller cannot enumerate addresses. Before
#302, an SMTP rejection (smtplib.SMTPRecipientsRefused out of the real sender) escaped
`AuthModule._magic_link`, killed the request thread, and surfaced as an nginx 502 — which made a
rejected recipient distinguishable from an accepted one, the exact signal the constant response
exists to deny. The fix catches smtplib.SMTPException and socket errors (OSError), records the
failure server-side (stderr log + audit row), and returns the byte-identical constant response.

Checked here, per logic path:
  1. accepted recipient      -> 200 constant body, sent.
  2. SMTP-rejected recipient -> NO exception; status+headers+body BYTE-IDENTICAL to case 1;
                                the failure is audited (magiclink_send_failed) and logged.
  3. socket-level failure    -> same byte-identical 200 (OSError family: refused/timeout/DNS).
  4. an UNEXPECTED bug (ValueError) still propagates — the catch is scoped, not a bare except,
     so this check fails if someone ever widens it into an exception silencer.

Run: python3 tests/magiclink_send_failure_selfcheck.py   (exit 0 = pass)
"""
import contextlib
import io
import os
import smtplib
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from mdreview.hosted.authroutes import AuthModule          # noqa: E402
from mdreview.hosted.magiclink import MagicLinkService     # noqa: E402

failed = []


def check(name, cond, why=""):
    print(("ok   - " if cond else "FAIL - ") + name + (("  <- " + why) if not cond and why else ""))
    if not cond:
        failed.append(name)


# ---- fakes: just the seams _magic_link touches ----
class FakeIdentityStore:
    """The slice of IdentityStore that MagicLinkService.issue + the route's failure path use."""

    def __init__(self):
        self.audits = []
        self.sends = []

    def count_sends(self, since, email=None, ip=None):
        return 0                                            # never throttled in this check

    def is_blocked(self, email, ip):
        return False

    def record_send(self, email, ip):
        self.sends.append(email)

    def audit(self, event, uid=None, email=None, ip=None, detail=None):
        self.audits.append((event, email, ip, detail))


class FakeStore:
    lock = threading.Lock()


class Sender:
    def __init__(self, exc=None):
        self.exc = exc
        self.sent = []

    def send(self, to, subject, body):
        if self.exc is not None:
            raise self.exc
        self.sent.append(to)


class FakeHandler:
    """The BaseHTTPRequestHandler surface _magic_link uses, capturing the full wire response."""

    def __init__(self, email):
        self._email = email
        self.headers = {"X-Real-IP": "203.0.113.9"}
        self.client_address = ("203.0.113.9", 4242)
        self.status = None
        self.sent_headers = []
        self.wfile = io.BytesIO()

    def _body_json(self):
        return {"email": self._email}

    def send_response(self, code):
        self.status = code

    def send_header(self, k, v):
        self.sent_headers.append((k, v))

    def end_headers(self):
        pass


def post_magic_link(sender, email):
    """Run POST /auth/magic-link through the module; return (handler, id_store, stderr_text)."""
    ids = FakeIdentityStore()
    magic = MagicLinkService("test-secret", ids, sender, "https://staging.test")
    mod = AuthModule(FakeStore(), None, None, magic, None, ids)
    h = FakeHandler(email)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        handled = mod.handle(h, "POST", "/auth/magic-link")
    return h, ids, err.getvalue(), handled


# ---- 1. the accepted baseline ----
ok_sender = Sender()
h_ok, ids_ok, _, handled_ok = post_magic_link(ok_sender, "owner@staging.test")
accepted_wire = (h_ok.status, tuple(h_ok.sent_headers), h_ok.wfile.getvalue())
check("accepted recipient -> handled, 200, mail sent",
      handled_ok and h_ok.status == 200 and ok_sender.sent == ["owner@staging.test"])
check("accepted audit trail says issued",
      ("magiclink_issued", "owner@staging.test", "203.0.113.9", None) in ids_ok.audits)

# ---- 2. the SMTP-rejected recipient (the staging 502, #302) ----
refused = smtplib.SMTPRecipientsRefused(
    {"nobody@example.com": (550, b"5.1.5 Recipient address reserved by RFC 2606")})
h_rej, ids_rej, err_rej, handled_rej = post_magic_link(Sender(exc=refused), "nobody@example.com")
rejected_wire = (h_rej.status, tuple(h_rej.sent_headers), h_rej.wfile.getvalue())
check("SMTP rejection does not escape the route (no 502)", handled_rej and h_rej.status == 200)
check("rejected response is BYTE-IDENTICAL to the accepted one (anti-enumeration)",
      rejected_wire == accepted_wire,
      "any observable difference re-opens the enumeration signal")
check("rejection is audited server-side as magiclink_send_failed",
      any(ev == "magiclink_send_failed" and em == "nobody@example.com"
          and det == "SMTPRecipientsRefused" for ev, em, ip, det in ids_rej.audits))
check("rejection is logged server-side (stderr)",
      "magic-link send failed" in err_rej and "SMTPRecipientsRefused" in err_rej)

# ---- 3. socket-level failure (OSError family) ----
h_sock, ids_sock, _, handled_sock = post_magic_link(
    Sender(exc=ConnectionRefusedError(61, "Connection refused")), "owner@staging.test")
sock_wire = (h_sock.status, tuple(h_sock.sent_headers), h_sock.wfile.getvalue())
check("socket failure -> same byte-identical 200",
      handled_sock and sock_wire == accepted_wire)
check("socket failure audited",
      any(ev == "magiclink_send_failed" and det == "ConnectionRefusedError"
          for ev, em, ip, det in ids_sock.audits))

# ---- 4. an unexpected bug must still propagate (the catch is scoped) ----
try:
    post_magic_link(Sender(exc=ValueError("a real bug")), "owner@staging.test")
    propagated = False
except ValueError:
    propagated = True
check("a non-SMTP, non-socket exception still propagates (no bare except)", propagated,
      "widening the catch would hide real bugs behind the constant 200")

print("\n" + ("%d case(s) failed" % len(failed) if failed else "all magic-link failure cases pass"))
sys.exit(1 if failed else 0)
