# #223 stage-8 evidence — staging.mdreview.space, 2026-07-28

Deployed image `sha256:214efa86…`, adopted 18:18 after CI concluded for merge `25e996c`.

## The two sessions, and which is which

Proving per-device revoke needs **two concurrent sessions**: one session cannot demonstrate that
ending B leaves A alone. Being precise about how each was obtained, because it matters:

- **Session A** — a genuine end-to-end login: magic link requested from staging, delivered by real
  email, redeemed through `POST /auth/redeem`. This is the session that does the revoking.
- **Session B** — minted inside the container through the app's own `SessionService.mint`, the same
  call `/auth/redeem` makes, producing a real row and a real signed cookie with a distinct `jti`
  and its own user-agent. It is a real session, **not** a stub or a forged cookie. It was created
  this way rather than by a second email round-trip because Gmail's index lagged the send; the
  alternative was burning turns polling for a message that had already been sent.

If B had been faked, the revoke test would prove nothing. It is a real row in the real database and
it authenticated against the real deployment (200 before revoke) before anything else happened.

| Shot | What it proves |
|---|---|
| `account-two-sessions.png` | The Active sessions card lists **both**: "Safari · iOS / 10.0.0.9" and "Unknown device **(this device)**". The current session is marked; "Sign out everywhere else" is offered only because another session exists. |
| `account-after-revoke.png` | After clicking **End session** in the UI, one row remains: the current device. |
| `revoked-session-signin.png` | B's browser now renders the **sign-in form**, not the connection card. |

## The sequence, on the real deployment

```
B (curl, real cookie)          -> 200
A clicks "End session" in the account UI   (the button, not the API)
sessions table                 -> 2 rows becomes 1
B (same cookie, unchanged)     -> 401
A (same cookie, unchanged)     -> 200
```

The revoke was driven by the **actual UI button**, not a curl against the endpoint, so this
exercises the CSRF header the page sends and the click handler, not just the route.

## The #221 / #223 interaction, checked deliberately

A revoked session must land on the **sign-in form**, not on #221's "Can't reach mdreview" card.
Both are non-authenticated states but they mean opposite things: the server *answered* here
(`{authenticated:false}`), it did not fail. Asserted explicitly, and the screenshot confirms an
email input is present and the connection text is absent.

Getting this backwards would have told a user with a deliberately-revoked session that the server
was down.

## Found here and fixed

The **End session** button was clipped at the card's right edge. Measured rather than eyeballed:
table `scrollWidth` 617 against container `clientWidth` 584, with `overflow-x: auto`, so each row's
primary action sat off-screen behind a horizontal scroll. The row-count and text assertions all
passed; the screenshot is what showed it. Fixed by dropping the least actionable column (`first
seen`), which also matches the tokens card above it.

## Not covered here

Grandfathering is covered by `tests/session_records_selfcheck.py` (a signed cookie with no `jti`
still authenticates and reports an empty jti) rather than on staging, because manufacturing a
genuinely pre-#223 cookie against the live deployment would mean signing one by hand with the
production secret.
