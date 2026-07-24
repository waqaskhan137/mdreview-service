"""Hosted-only identity core (#67 native auth + #109 fail-closed-build core). Stdlib only.

The mdreview CORE (src/mdreview/*.py, src/mdreview/access.py) imports NOTHING from this package: the
seam (#103) defines IdentityProvider + AccessPolicy, and this package supplies the hosted
implementations, wired ONLY by the hosted composition root (`python -m mdreview.hosted`). The local
tier never touches it, so "keep it yours" stays stdlib + one-container by construction.

Owner decision (2026-07-23, identity-architecture.md): BUILD-MINIMAL on the stdlib, with `sqlite3`
(also stdlib) as the user/session/audit store. No FastAPI, no Postgres, no new dependency, no
separate identity service to run. Consequently the login primitives here are mdreview's OWN,
signed with a symmetric key (MDREVIEW_SESSION_SECRET, HMAC-SHA256): there is no external service to
verify a JWKS/asymmetric assertion from, so the design's JWKS language (which was contingent on the
now-rejected reuse-a-service option) does not apply to the session cookie or the magic-link tokens.

Modules:
  identity_store  the sqlite3 store: identities (durable provider:sub, verified email, linking),
                  single-use magic-link nonces, send counters (abuse control), auth-event audit.
  sessions        the app-owned signed session cookie (HttpOnly/Secure/SameSite=Lax + CSRF).
  magiclink       email -> signed short-lived single-use token; EmailSender + StubEmailSender.
  identity        HostedIdentity: the three caller planes (mdr_ token -> session -> proxy header),
                  and AccountService: verified-email -> the ONE durable provider:sub (linking).
  authroutes      AuthModule: the /auth/* routes, dispatched via the core's feature-module seam.
  compose         the hosted composition root: build-time selection of the owner-only policy +
                  the fail-closed boot guard (refuses to serve without the session secret).
"""
