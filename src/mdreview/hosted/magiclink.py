"""Magic-link login (#67 D4) + its abuse controls (#67 D3) + the pluggable email backend (#67 D6).

Flow: an email address -> a signed, short-lived, SINGLE-USE token -> emailed as a link -> the user
POSTs it back to confirm -> the token is verified and its nonce consumed (so it cannot be replayed
until it expires). Two independent guards make single-use hold: the HMAC proves the token is ours
and unmodified; the consumed-nonce store (IdentityStore.consume_nonce) proves it has not been
redeemed before. Redemption is a POST (the route enforces this), so an email-scanner's GET prefetch
of the link cannot burn the token.

Abuse controls (membership is open, so the send path is a spam/enumeration surface): a per-address
limit, a per-IP limit, and a global daily budget, all counted in sqlite. The send endpoint returns
a CONSTANT response whether or not the address exists or a limit was hit (enumeration-safe); throttle
decisions are recorded server-side only.

The signing key is DOMAIN-SEPARATED from the session key (a derived subkey), so a session cookie can
never be replayed as a magic-link token or vice-versa even though both descend from the one hosted
secret.
"""
import hashlib
import hmac
import json
import secrets
import smtplib
import time
from email.message import EmailMessage
from urllib.parse import quote

from mdreview.hosted.identity_store import normalize_email
from mdreview.hosted.sessions import b64url_decode, b64url_encode


class EmailSender:
    """The pluggable email backend seam. Real providers (SES, SMTP, ...) implement send() later."""

    def send(self, to, subject, body):
        raise NotImplementedError


class StubEmailSender(EmailSender):
    """The owner-chosen backend for tonight: LOG the message (no real send). The magic link lands on
    stdout so an operator can complete a login from the logs during bring-up. Never used once a real
    provider is wired."""

    def __init__(self, sink=None):
        self._sink = sink or (lambda line: print(line, flush=True))

    def send(self, to, subject, body):
        self._sink("EMAIL-STUB to=%s subject=%r body=%r" % (to, subject, body))


class SmtpEmailSender(EmailSender):
    """A real SMTP backend (stdlib smtplib) — the production magic-link delivery path, selected when
    MDREVIEW_SMTP_HOST is configured. One short-lived connection per send (magic-link volume is low).
    Port 465 => implicit TLS (SMTP_SSL); otherwise STARTTLS is issued before auth (unless explicitly
    disabled) so credentials never cross in the clear. No third-party SDK: single algorithm, stdlib."""

    def __init__(self, host, port=587, username="", password="", from_addr="", use_starttls=True,
                 timeout=15):
        self._host = host
        self._port = int(port)
        self._username = username or ""
        self._password = password or ""
        self._from = from_addr
        self._use_starttls = use_starttls
        self._timeout = timeout

    def _deliver(self, client, msg):
        if self._username:
            client.login(self._username, self._password)
        client.send_message(msg)

    def send(self, to, subject, body):
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if self._port == 465:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout) as client:
                self._deliver(client, msg)
        else:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as client:
                if self._use_starttls:
                    client.starttls()
                self._deliver(client, msg)


class MagicLinkService:
    def __init__(self, secret, store, sender, link_base,
                 ttl_s=900, max_per_address=3, address_window_s=900,
                 max_per_ip=10, ip_window_s=3600, global_daily_budget=500):
        if not secret:
            raise ValueError("MagicLinkService requires a non-empty secret")
        if not link_base:
            # Fail closed: without a verified canonical base we cannot build a trustworthy link, so
            # we refuse to construct rather than emit links pointing at an attacker-influenced host.
            raise ValueError("MagicLinkService requires a verified canonical link_base")
        # Domain-separated subkey so magic-link MACs live in a disjoint space from session MACs.
        self._key = hmac.new(secret.encode("utf-8"), b"mdreview.magic-link.v1",
                             hashlib.sha256).digest()
        self._store = store
        self._sender = sender
        self._link_base = link_base.rstrip("/")
        self.ttl_s = int(ttl_s)
        self.max_per_address = int(max_per_address)
        self.address_window_s = int(address_window_s)
        self.max_per_ip = int(max_per_ip)
        self.ip_window_s = int(ip_window_s)
        self.global_daily_budget = int(global_daily_budget)

    # ---- token crypto ----
    def _mac(self, payload_b64):
        return b64url_encode(hmac.new(self._key, payload_b64.encode("ascii"),
                                       hashlib.sha256).digest())

    def _mint_token(self, email, now):
        jti = secrets.token_hex(16)
        payload = {"email": email, "jti": jti, "exp": now + self.ttl_s}
        payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        return payload_b64 + "." + self._mac(payload_b64)

    # ---- send path (rate-limited, enumeration-safe) ----
    def _within_limits(self, email, ip, now):
        if self._store.count_sends(now - self.address_window_s, email=email) >= self.max_per_address:
            return False, "address"
        if ip and self._store.count_sends(now - self.ip_window_s, ip=ip) >= self.max_per_ip:
            return False, "ip"
        if self._store.count_sends(now - 86400) >= self.global_daily_budget:
            return False, "global"
        return True, ""

    def issue(self, email, ip):
        """Mint + email a magic link IF the abuse limits allow. Returns a status string for audit /
        tests ('sent' | 'throttled:<which>' | 'invalid'); the ROUTE maps every outcome to one
        constant client response, so this return value never leaks to the caller. Records the send
        and audits issuance on success, and audits the throttle on a limit hit."""
        e = normalize_email(email)
        if not e or "@" not in e:
            return "invalid"
        now = time.time()
        ok, which = self._within_limits(e, ip, now)
        if not ok:
            self._store.audit("magiclink_throttled", email=e, ip=ip, detail=which)
            return "throttled:" + which
        token = self._mint_token(e, now)
        link = "%s/auth/redeem?token=%s" % (self._link_base, quote(token, safe=""))
        self._sender.send(e, "Your mdreview sign-in link",
                          "Confirm your sign-in: %s (valid %d minutes, one use)."
                          % (link, self.ttl_s // 60))
        self._store.record_send(e, ip)
        self._store.audit("magiclink_issued", email=e, ip=ip)
        return "sent"

    # ---- redeem path (verify + single-use) ----
    def redeem(self, token):
        """Verify a magic-link token and CONSUME its nonce. Returns the verified email on the first
        redemption, or None on a bad MAC, expiry, or replay. Single-use is enforced by consume_nonce
        (the nonce PK rejects a second redemption atomically)."""
        if not token or "." not in token:
            return None
        payload_b64, _, sig = token.partition(".")
        if not payload_b64 or not sig:
            return None
        if not hmac.compare_digest(sig, self._mac(payload_b64)):
            return None
        try:
            payload = json.loads(b64url_decode(payload_b64))
        except (ValueError, json.JSONDecodeError):
            return None
        email = normalize_email(payload.get("email"))
        jti = payload.get("jti")
        exp = payload.get("exp", 0)
        if not email or not jti or not isinstance(exp, (int, float)) or exp <= time.time():
            return None
        if not self._store.consume_nonce(jti, exp):
            return None                                   # already redeemed (replay) -> reject
        return email
