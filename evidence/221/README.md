# #221 stage-8 evidence — staging.mdreview.space, 2026-07-28

Captured with `node scripts/cdp-shot.mjs` against **staging**, signed in as the owner
(`waqaskhan137@gmail.com`), using a real session cookie obtained through the actual magic-link
redeem flow. Not a local instance, not a simulated response.

| Shot | Surface | What it proves |
|---|---|---|
| `dashboard-signed-in.png` | `/` with a valid session | `#app` visible, account menu shows the signed-in email. `account.js` `mount()` works with the new `{sess, reachable}` return. |
| `admin-signed-in.png` | `/admin` with a valid session | The admin console renders. **This is the first time `admin.html`'s changed `boot()` ran in a browser at all** — `/admin` 404s on the local build, so it could not be checked before staging. |
| `dashboard-unreachable.png` | `/` with a **valid session** and `/auth/session` blocked | "Can't reach mdreview", **no** magic-link email input, and "Reconnecting…" in the account menu. This is the fixed defect: the same conditions previously rendered the sign-in form at a user who was still signed in. |
| `admin-unreachable.png` | `/admin`, same conditions | "Could not reach the service." instead of "Sign in to continue". |

## Why the failure shots required a tooling change

The connection state is unreachable while the endpoint is healthy, so it cannot be screenshotted by
navigating to a URL. `scripts/cdp-shot.mjs` gained two steps for this:

- `--cookie name=value@origin` — set a session cookie before navigating. Authenticated surfaces are
  otherwise unreachable headlessly, since magic links arrive by email and there is no login UI to
  drive. The value is never printed: a session cookie in a log is a live credential.
- `--block <pattern>` — block a URL pattern so a specific request genuinely fails, without taking
  the server down for anyone else.

Both are reusable: #223's stage 8 needs **two** concurrent signed-in sessions to prove that revoking
one device actually signs it out.

## What this evidence does NOT cover

- `account.html` was not separately captured. Its `account.js` path is the same one exercised on the
  dashboard and admin shots.
- The TTL half is verified separately, not by screenshot: a cookie from the real redeem flow decodes
  to `exp - iat = 2592000` (30 days), and `docker exec mdreview-staging printenv
  MDREVIEW_SESSION_TTL_S` returns `2592000`.
- **Prod is untouched** (decision D1). None of this is evidence about prod.
