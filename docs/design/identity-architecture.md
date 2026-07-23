# Core + injected access seam — one architecture for local vs hosted

> Status: **APPROVED** (owner, 2026-07-23) after G1 passed (staff-critic, 2 rounds). The frame the
> identity/custody/sharing cluster slots into: #67 identity, #97 custody, #101 public, #68
> collaboration, #102 admin.
>
> **Owner decision on OQ1 (2026-07-23): BUILD-MINIMAL, not reuse.** The hosted identity core is
> built in-house on the Python stdlib, with **`sqlite3` (stdlib) as the user/session/audit store**
> — no FastAPI, no Postgres, no new dependency, and no separate identity service to run/patch/back
> up. mdreview stays single-service and stdlib-only on both tiers. The fikar service was studied as
> a reference (its email+password model, JWT scaffolding, invite/email primitives) but is **not
> adopted**. Everything else in this design is implementation-agnostic and stands: the injected
> seam, the three caller planes, the durable-`provider:sub` invariant, the audit split, the
> byte-identical rollout. Where the doc below says "the copied/hosted identity service," read "the
> in-house hosted identity module (stdlib + sqlite3)"; whether it is in-process or a small separate
> stdlib process, and whether an internal signed-token boundary is used at all, are LLD/ticket
> details.

## 1. Problem and the key observation

mdreview runs in two tiers with opposite needs. **Local** is keep-it-yours: no accounts, no auth,
stdlib-only, one tiny container. **Hosted** (now open to the world) needs identity, per-user
custody, sharing, and admin. Five open issues (#67/#97/#101/#68/#102) all circle the same axis:
who is the caller, and what may they see. Built ad hoc, they would scatter access checks across
the codebase, the exact drift that produced the #97 custody breach.

**The seam already exists, implicitly.** In `src/mdreview/server.py` today:

- `_principal()` (`:114`) returns a `local` plane when `REQUIRE_AUTH` is off (everything open),
  else resolves a `token` (Bearer `mdr_`) or `cookie` (oauth2-proxy vouched header) principal.
- `_authz(rid)` (`:155`) gates every review on `reviews.can_access(rid, uid)` (owner-only,
  fail-closed on a missing owner, `reviews.py:35`).
- `list_reviews(uid)` (`reviews.py:74`) scopes to owned reviews when `uid` is set, returns all
  when `uid is None` (local).

This design **formalizes that implicit seam into one injected interface** and makes the cluster
fall out of it, rather than inventing new architecture.

## 2. The seam

Two small interfaces, injected on the existing `Services` composition root and reached by the
handler via `self.server.app` (the pattern already in place):

- **`IdentityProvider.principal(request) -> Principal`** — resolve the caller. A `Principal`
  carries a stable `uid`, `email`, `is_admin`, and an `is_anonymous` flag (for public reads,
  section 4c). The `uid` is the **durable owner key** (see the invariant below).
- **`AccessPolicy`** — decide access given a `Principal` and a resource:
  `can_read / can_write / can_delete(principal, review) -> bool`, `scope_list(principal) -> uid|None`,
  and `stamp_owner(principal) -> uid` at creation. This IS the custody Confinement contract (#97).

The core defines these interfaces and **never imports hosted code**, so local stays stdlib and
one-container by construction. Composition by injection (the repo rule: composition over
inheritance, an interface only at a seam that genuinely varies) — no base class, no `Hosted`
subclass of a `Core` server.

> **Durable-owner-key invariant (resolves G1-MF1).** The owner key is and stays
> **`provider:sub`** (e.g. `google:100706495352040931339`), the key already stamped on every
> existing review. The identity plane switch does **NOT re-key** anything. Instead the hosted
> identity service **links** a user's native/magic-link and Google logins to one durable
> `provider:sub`, and every principal it issues **carries that same `sub`** (#67 D2 account
> linking). Migration of existing owners is therefore a **no-op**: their reviews already match.
> A re-key is explicitly forbidden — it is the #97 blanket-reassignment failure class.

```mermaid
flowchart TB
  subgraph core["mdreview core (stdlib, shared)"]
    H["MdreviewServer / handler"]
    R["reviews · comments · store · _audit()"]
    IP["IdentityProvider (interface)"]
    AP["AccessPolicy (interface)"]
    H --> IP
    H --> AP
    H --> R
  end
  subgraph local["Local injection"]
    LI["OperatorIdentity (single operator)"]
    OP["OpenPolicy (allow all)"]
  end
  subgraph hosted["Hosted injection (hosted-only module, non-stdlib OK)"]
    HI["HostedIdentity: mdr_ token · session cookie · anon"]
    CP["CustodyPolicy (owner + shares + audited admin)"]
  end
  IP -. local .-> LI
  AP -. local .-> OP
  IP -. hosted .-> HI
  AP -. hosted .-> CP
  HI -->|verifies login assertion (JWKS)| IDP["mdreview's copy of the\nidentity service (hosted-only sidecar)"]
```

## 3. Local injection (the null adapter)

`OperatorIdentity` returns one fixed operator `Principal`; `OpenPolicy` allows every operation and
`scope_list -> None`. This is exactly today's `REQUIRE_AUTH`-off behavior, made explicit as a
null-object adapter. Local pulls no hosted code, no FastAPI, no Postgres, no JWT library; the
container and the stdlib-only contract are unchanged.

## 4. Hosted injection — the three real planes (resolves G1-MF2, MF3)

`HostedIdentity.principal(request)` resolves in a fixed order; the design names all three planes
explicitly rather than "verify a JWT":

**(a) Agent plane — mdreview-native `mdr_` HMAC tokens (unchanged, PRIMARY interface).** The MCP
wrapper authenticates with `mdr_<id>_<secret>`, minted at `/account/tokens`, resolved by
`UserService.mint_token`/`resolve`. **These stay mdreview-native HMAC**; they do not become
identity-service JWTs. They key to the user's durable `provider:sub`. This preserves the project's
main door with zero migration.

**(b) Browser plane — an mdreview-owned session cookie (the real native-auth work).** Navigations
(`/review/{id}`, `/account`, dashboard) carry no `Authorization` header; oauth2-proxy solved this
with a cookie today. Replacing it means **mdreview owns the session**: at login (magic-link or
Google, via the identity service) mdreview mints its **own** signed session cookie
(HttpOnly, Secure, SameSite=Lax, fixed lifetime + refresh, explicit logout, CSRF token for
state-changing posts, login redirect). `HostedIdentity` resolves the cookie to a `Principal`
carrying the durable `sub`. This is #67 D2's "one app-owned session," specified here as a
first-class rollout step, not a footnote.

**(c) Anonymous plane — for public reads (#101).** A request with no `mdr_` token and no session
cookie yields `Principal(is_anonymous=True)`. It is **not** rejected up front; `AccessPolicy`
decides (a public document serves an anonymous principal; anything else 404s). This inverts
today's `_require_user`-before-`can_access` order for read paths (section 7 handles the refactor).

**Crypto (resolves G1-MF3).** The login assertion mdreview receives from the identity service is
an **asymmetrically signed** token (RS256/ES256/EdDSA) verified against the service's **JWKS**,
using a **vetted JWT library in the hosted adapter** (hosted already runs non-stdlib code; the
stdlib-only rule binds only local, which never verifies a token). No shared symmetric secret, no
hand-rolled verifier. The verifier pins `alg`, rejects `alg:none`/RS-HS confusion, and validates
`exp`/`nbf`/`aud`/`iss`. The HS256/stdlib-hmac path from the prior draft is dropped. (Note: this
JWKS-verified assertion is distinct from the native `mdr_` HMAC tokens in plane (a), which are
mdreview's own and unrelated to the identity service's signing.)

## 5. The reused identity service (mdreview's own copy)

mdreview takes its **own copy** of the fikar-derived FastAPI + Postgres identity service, fully
**decoupled from the running Kapture instance (never touched)**. It runs **hosted-only**, as a
sidecar `HostedIdentity` verifies login assertions from.

**Verified against the fikar source (2026-07-23): it is email + password only** — users are keyed
by email (`get_by_email`), created with a bcrypt password; there is **no social/OAuth, no
`provider:sub` model, and no account linking**. That materially changes the Keep/Add split below
and is the crux of open question 1.

- **Keep (the actual reuse):** the FastAPI + Postgres + JWT scaffolding, register/login, refresh
  rotation, the account/user CRUD (covers #102 user-management), invitations, email, and JWKS
  (asymmetric per MF3).
- **Add (larger than the spine assumed):** **magic-link login** (the invite token+email+expiry
  primitive helps, but **open self-serve magic-link is a different abuse surface** than an
  admin-issued invite, so it must ship #67 D3 caps/blocklist); **Google secondary** sign-in (absent
  today); a **`provider:sub` identity model + account linking by verified email** (absent today, and
  **required by the MF1 no-re-key invariant** — this is an Add, not a Keep); a **one-time seed** of
  the existing `email ↔ google:<sub>` map from mdreview's `users.json` into the service (the
  critic's caveat: review keys are a no-op, the linking records are not); and **identity/auth-event
  audit** service-side.
- **Drop:** password-primary (against our magic-link direction) and the org / RBAC / hierarchy
  machinery.
- **Trim decision is the owner's, and it decides the whole reuse rationale (G1-WC1).** Running only
  *users + auth + admin + audit* — the recommended minimal set — **is** the build-minimal service;
  inheriting FastAPI + Postgres + ORM to run ~4 tables re-imports the ops weight section 8 admits
  bit us all week. The owner must confirm knowingly: the delta between "strip fikar to four tables"
  and "four tables in stdlib + SQLite" may be *negative* once patch/backup/restore of a second
  datastore is counted. **Open question 2 gates whether reuse beats build-minimal at all.**
- **Owned code**, so no AGPL / paywall concern a third-party IdP (Zitadel/Authentik) carried.

## 6. Where audit lives (resolves G1-MF4) and the cluster mapping

Audit is **split by where the decision is made**:

- **Identity/auth events** (login, magic-link issuance, account CRUD, admin user actions): audited
  **service-side**, in the identity service.
- **Document custody/admin-access events** (an admin reads a doc they don't own; an ownership
  stamp; a share grant/revoke): audited **core-side**, where `CustodyPolicy` makes the call, via
  the existing core `_audit()` sink (`server.py:133`). The identity service never sees document
  access, so this cannot live there without breaking the seam.

| Issue | Where it lives in this architecture |
|---|---|
| #67 identity | `HostedIdentity` (mdr_ + session + anon) + the copied service (magic-link primary / Google secondary / account linking) |
| #97 custody | `AccessPolicy` = Confinement; `stamp_owner` fail-closed = Totality; **custody audit core-side** |
| #101 public | anonymous principal + a share entry `CustodyPolicy` consults (share-to-all); read path decides policy-before-identity |
| #68 collaboration | share entries (share-to-named); invites reuse the service's invitation flow |
| #102 admin | `Principal.is_admin` + the **audited** super-access branch in `CustodyPolicy`; user-mgmt from the service |

## 7. Rollout (behavior-preserving, staged; step 2 broken out per G1-WC5)

1. **Extract the seam (internal refactor, no behavior change).** Move `_principal`/`_authz`/
   `can_access`/`list_reviews` behind `IdentityProvider` + `AccessPolicy` on `Services`; inject
   `OperatorIdentity`+`OpenPolicy` when `REQUIRE_AUTH` off, and today's oauth2-proxy-header resolver
   + owner check when on. **Also invert the read-path order** so `can_read` is consulted before
   identity is demanded (needed for the anonymous plane later; do it now so step 1 doesn't lock in
   require-auth-first). Gate: **byte-identical** API for both tiers (golden-transcript oracle, as
   the oop-refactor did). NB: hosted `REQUIRE_AUTH` is currently ON (restored in #86), so the
   hosted transcript pins the real production path.
2. **Stand up the hosted identity service + native auth.** Sub-steps, each independently shippable:
   (2a) mdreview's identity-service copy deployed hosted-only, issuing JWKS-signed assertions with
   account linking so the `sub` equals the existing `provider:sub`; (2b) mdreview's own session
   cookie mechanism + login/logout/redirect (plane b); (2c) magic-link primary + #67 D3 abuse
   controls + Google secondary bridged into the session; (2d) `mdr_` agent tokens confirmed working
   unchanged; (2e) retire the oauth2-proxy vouched-header plane only after (2a-2d) are proven, so
   the two identity planes never both decide custody.
3. **Sharing + admin** (#101/#68/#102) as `AccessPolicy` extensions and service capabilities.

Local stays byte-identical throughout; the live hosted instance keeps working at every step.

## 8. Risks

- **Refactor regressions.** Step 1 must be byte-identical for both tiers, proven by the golden
  transcript, or it silently changes access behavior. Mitigated by the oracle.
- **Two identity planes during transition** (oauth2-proxy header + mdreview session). Retire the
  header plane only when the session plane is proven (2e); resolution order fixed and tested.
- **Two persistence systems, one invariant (G1-WC2).** Owner keys live in `meta.json` on the data
  volume; identity lives in Postgres. A backup/restore recovering one but not the other re-creates
  the #97 mismatch (a review keyed to a uid whose user record is gone). Back them up together;
  add the owner-key referential check to the #86 drift tripwire.
- **Ops weight (G1-WC1).** The copied service is FastAPI + Postgres — a real hosted-only service to
  run, patch, back up (the category that bit us). This is the crux of open question 2; if the
  answer is "four tables," build-minimal-stdlib may win outright.
- **Stable-subject discipline.** Key ownership on the immutable `provider:sub`; never a mutable id
  (the #97 failure class, and the Authentik `X-authentik-uid`-changed-on-upgrade risk the research
  flagged). Email is mutable and must NOT be the key.
- **Hand-rolled crypto avoided** by MF3 (vetted library, asymmetric, hosted-side).
- **License hygiene.** Confirm the fikar service's own code + deps are clear to copy into
  mdreview's repo/licensing before importing.

## 9. Out of scope

Local ever getting accounts/auth (keep-it-yours, by construction). Any class hierarchy or plugin
framework — one injected seam only. A per-object ReBAC engine (OpenFGA/SpiceDB) — later, if sharing
outgrows a flat owner+share list. The running Kapture fikar instance. Real-time co-editing (#16).

## 10. Open questions (owner)

1. ~~Reuse vs build-minimal~~ — **RESOLVED 2026-07-23: build-minimal** (stdlib + `sqlite3`,
   in-house, one service). See the owner-decision banner at the top. The fikar service is a studied
   reference, not adopted.
2. **Magic-link + Google:** confirm magic-link primary with #67 D3 abuse controls, and Google
   secondary bridged into mdreview's session (not a separate plane).
3. **Datastore:** if reuse — a separate Postgres for mdreview's identity copy, or co-locate with the
   fikar instance's infra (decoupled logically, shared host)?
4. ~~Ownership-key migration~~ — **resolved** by the durable-owner-key invariant (section 2): keep
   `provider:sub`, the JWT carries it via account linking, migration is a no-op.
