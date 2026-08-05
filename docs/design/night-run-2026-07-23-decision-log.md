# Night run — decision log (2026-07-23 → morning 2026-07-24)

Autonomous overnight build of the identity/custody/sharing cluster to PRs, for owner review in
the morning. This log records every non-trivial decision I took without you, with rationale and
how to reverse it. **Nothing is merged; nothing touches prod/main/live-Kapture.**

## Owner decisions taken before sleep
- **Scope:** build ALL five features to PRs, including collaboration (which had no brief). Most
  aggressive; the security-sensitive ones (public links, admin super-access) get extra
  adversarial + security-review passes and a REVIEW-BEFORE-MERGE flag.
- **#67 native auth:** signed off → build it (magic-link primary + Google secondary + sessions +
  `provider:sub` + linking + audit, stdlib + `sqlite3`, stub email).
- **Email backend:** pluggable sender with a **stub/log** backend (no real sends tonight); a real
  provider must be wired before go-live.
- **Guardrails (confirmed):** PRs only, no merge, no prod/main/live-Kapture, no destructive or
  irreversible actions, each feature its own branch + PR into `dev`, temp files only in
  `.scratch/`, hard irreversible blocker → stop that item + log it rather than guess.

## Guardrails I operate under
1. No `git push` to main; no merges (PRs collect at your gate); no deploys; no changes to the
   running Kapture instance or its data.
2. No destructive ops (no data deletion, no force-push, no `docker compose up`, no live-volume
   touch). Throwaway smokes only, in `.scratch/`, on scratch ports (never 8139/8137).
3. Every dispatched agent is told: temp files ONLY in the project/worktree `.scratch/`, never the
   session scratchpad or /tmp.
4. Security-sensitive PRs (auth, access policy, public links, admin) are labelled and flagged here
   as **REVIEW-BEFORE-MERGE**; I will not present them as safe to merge unattended.

## Build plan (phases; dependency-ordered)
- **P1 Foundation:** verify the seam (#103 / PR #108, the base for all access); build custody
  prevention #111 (delete blind migrate, P0) + #112 (reconciliation tool).
- **P2 Auth + custody-on-seam:** build #67 identity module (magic-link/sessions/linking/audit,
  stub email); build #109 (fail-closed hosted build) + #110 (seam enforcement) on the verified seam.
- **P3 Sharing/admin/collab:** design (LLD/brief) then build #101 public link, #102 admin, #68
  collaboration on the AccessPolicy share primitive; security-review the access-control ones.
- **P4 Morning summary:** all PRs, per-PR review flags, what's partial/blocked, open questions.

## Auto-decisions (taken without you — review these)

### D1 — #67/#97 shared boot-guard ownership
The fail-closed boot guard + principal resolution (shared by #67 D2 and custody slice #109) is
built ONCE, owned by the #67 identity module (the `IdentityProvider` + hosted composition root);
custody #109 consumes it rather than re-implementing. Rationale: one implementation, no drift.
Reversible: yes (internal refactor). Review: low-risk.

### D2 — #96 resource-quota exposure
Accepted as a named risk for the overnight run; quotas NOT built. Magic-link D3 abuse controls
(per-address/per-IP rate limits) partially mitigate signup abuse; per-account review/asset quotas
deferred to a separate ticket. Reversible: yes. Review: it's a live exposure you already flagged.

### D3 — Public link (#101) default policy
Built with the safe defaults, pending your ruling: **view-only** (no anonymous comments —
smaller abuse surface), **anyone-with-link**, **noindex by default** (public = "anyone I send the
link to", not search-indexed). Revocable per-document; default private. Reversible: yes (config/policy).
Review: **REVIEW-BEFORE-MERGE** (access-control).

### D4 — Admin (#102) scope
Admin-v1 = **user-management** (list/disable/ban, blocklist, token revoke) built. **Audited
document super-access** is the highest-risk piece: built WITH the append-only audit + a dedicated
security-review pass, but flagged hard as **REVIEW-BEFORE-MERGE / do-not-enable-unattended**.
Reversible: yes (capability off by default). Review: highest-risk PR of the run.

### D5 — Collaboration (#68) brief
No owner brief existed; I authored an inferred brief from product.md's direction (per-document
share by email → view/comment, on the same owner-granted-share ACL as public link). Treat the
brief itself as a proposal for your review, not a settled requirement. Reversible: yes. Review:
confirm the brief matches your intent before merging the build.

<!-- Run-time decisions get appended below as they occur. -->

## Run-time decisions
_(appended during the night)_

### Phase 1 — foundation (DONE)
- **#103 seam (PR #108): VERIFIED sound.** Oracle passes; agent independently proved byte-identical
  both tiers + 401(unauth)/404(non-owner), AND that the read-order inversion is fail-closed by the
  `can_access` predicate for legacy `owner==''` records (the load-bearing point). Coverage caveat
  (flagged, low risk): the oracle does not exercise `/account` + `/account/tokens` routes — their
  rewrite is mechanical but unproven. **REVIEW-BEFORE-MERGE.**
- **#111 delete blind migrate: PR #117.** Agent chose FULL delete of `migrate.py` (vs tombstone) —
  a disarmed entrypoint invites re-arming; recoverable from git history. Nothing imported it.
  **REVIEW-BEFORE-MERGE (custody P0).**
- **#112 reconciliation tool: PR #118.** New `src/mdreview/reconcile.py`. Key security decisions
  (good): **display-only provenance** — the tool computes NO owner candidate from the
  attacker-controlled provenance fields (a provenance→owner index would be "blind migrate with
  extra steps"); **quarantined == `owner==''`** surfaced by the tool, no separate marker (avoids a
  drift-prone parallel truth); per-record confirm only, no bulk, no re-key. **REVIEW-BEFORE-MERGE.**
- **Design specs branch:** committed identity-architecture + custody designs to `origin/docs/cluster-designs`
  so build agents can read them (PR-able in the morning).
- **Stacking decision:** #67/#109/#110 build on the unmerged #103 seam, so their branches base on
  `refactor/103-access-identity-seam` (PR base = that branch, stacked). Morning: merge #103 to dev
  first, then the stacked PRs rebase onto dev. Noted in each PR.

### Phase 2 — auth + custody-on-seam (DONE)
- **#67 hosted identity core: DRAFT PR #120** (stacked on #103). New `src/mdreview/hosted/` package:
  sqlite identity store (provider:sub, UNIQUE-email linking, adopts existing google:<sub> owners →
  migration no-op), signed session cookie, three-plane HostedIdentity, single-use magic-link
  (signed + sqlite consumed-nonce, POST-confirm), abuse controls, stub email, fail-closed hosted
  build (covers #109 core), auth audit. 34 core + 28 e2e self-checks pass; seam oracle still
  byte-identical. **REVIEW-BEFORE-MERGE.** Draft because incomplete (see TODOs).
  - **⚠ DESIGN DEVIATION (review): symmetric HMAC session secret, NOT the design's asymmetric
    JWKS.** Sound reasoning: JWKS was premised on the separate-service reuse option (rejected);
    build-minimal in-process has no external assertion to verify, so a symmetric secret is correct +
    simpler + no alg-confusion. Legitimate, but reverses the G1-reviewed MF3 crypto decision — your call to bless.
  - **⚠ PROD-CONFIG CHANGE (review before any redeploy):** SESSION_SECRET wired into
    `infra/deploy/docker-compose.prod.yml` (fail-fast) so the current prod compose keeps booting
    under the new guard. In the PR, not applied to the live host.
  - **Two stores (G1-WC2):** `users.json` (account/token map) + sqlite `identity.db`
    (linking/nonces/audit), native users in both under the same provider:sub. Cross-store backup
    integrity is a noted risk.
  - **Defaults (env-overridable):** rate 3/addr/15min, 10/IP/hr, 500/day; session TTL 12h;
    magic-link TTL 15min.
  - **TODO (deliberately deferred, for morning):** CSRF enforcement on core state-changing POSTs
    (sequenced with proxy-plane retirement; SameSite=Lax is the in-place defense) — a real security
    TODO; login UI/page (only /auth/* API exists); Google-secondary bridged into the session;
    proxy-plane retirement flag.
- **#110 seam enforcement: PR #119** (stacked on #103). Audited all child-resource routes (comments/
  assets/history/feedback/PDF) — all already gated; ADDED a central custody choke point in H.route
  so a future child arm is gated even if its author forgets (structural guarantee); ownership-stamp
  audit routed to core `_audit()`. Self-check proves non-owner 404 / anon 401 on every child incl.
  latex PDF. Behavior delta (judged an improvement): an un-armed review-scoped path now 404s
  non-owner / 401s anon (less probeable). **REVIEW-BEFORE-MERGE.**
- **#109 status:** its fail-closed-build CORE is delivered inside PR #120; the remaining #109/#115
  piece (the regression test asserting the prod-default image refuses to serve) is still to build.

### Phase 3 — sharing + admin (DONE)
- **#101 public + #68 collaboration: PR #122** (stacked on #67). Built as ONE owner-granted-share
  ACL primitive (public = share-to-all, named = collaboration) extending CustodyPolicy — the
  Confinement exception, not a bypass. Public read = D3 defaults (view-only, anyone-with-link,
  noindex). Owner-only management (a grantee can't escalate). Added `can_comment` to the seam.
  Self-checks pass (public readable-not-writable by anon; named share view/comment per grant;
  revoke immediate; non-shared still 404; grantee no-escalation). **REVIEW-BEFORE-MERGE.**
  - Decisions: invite EXISTING accounts only for v1 (no pending-invite); public exposes the whole
    read surface (viewer+source+comments+feedback+history+assets) per the confinement-unit rule;
    `scope_list` stays owner-only (shared-in docs reached by link, not listed — "shared with me" is
    a TODO); email→account via `find_by_email` (works for federated owners too).
  - TODO: in-viewer share UI (v1 API-only); pending invites for unregistered emails; shared-with-me
    dashboard; latex-viewer noindex header; CSRF-branch not exercised by self-checks.
- **#102 admin: PR #121** (stacked on #67). (A) user-management: list/ban/grant-admin/grant-super_read/
  revoke-tokens/revoke-sessions/blocklist, all audited. (B) audited super-access: `can_read` ONLY,
  OFF by default (not implied by is_admin), cookie-plane-only (attended), audited via `_audit()`;
  NO super-write/delete by construction. Blocklist wired into magic-link issue. Self-checks pass
  (21 assertions incl. the audit row is written). **REVIEW-BEFORE-MERGE / do-not-enable-unattended.**
  - Decisions: `is_owner ⇒ admin` bootstrap (zero-config, always ≥1 admin, owner can't self-de-admin).
  - TODO: proxy plane has no session-revoke epoch (transitional); no admin UI; no audit-review route.

### All five features now exist as PRs (stacked): #103←#67←{#101/#68, #102}; custody prevention #117/#118/#119.

### Phase 4 — adversarial security review (DONE): 21 findings (0 critical, 3 high, 6 med, 8 low, 4 info)
**Best news: core Confinement HOLDS — no cross-user document read/write/comment hole found; the #97
breach class is NOT reintroduced.** Session HMAC, magic-link single-use (race-safe), domain-key
separation, POST-only redemption, enumeration-safe send, and fail-closed boot all traced SOUND.
**Deployment reality (important): the auth plane is BUILT but NOT LIVE** — the committed compose sets
no SESSION_SECRET and nginx has no pre-auth `/auth/` location, so nothing I built is exposed on prod.
These are review-ready PRs, NOT shipped features.

**HIGH — fix before the auth plane goes live:**
- **H1 Owner-bootstrap takeover.** `is_owner = not data["users"]` (users.py:51) → under open membership
  the FIRST magic-link registrant on an empty users.json becomes owner+admin. Fix: pin owner to a
  configured `MDREVIEW_OWNER_EMAIL` (verified), refuse admin-bootstrap otherwise. **Must-fix pre-deploy.**
- **H2 Stub email → tokens in logs.** `build_hosted` hard-wires StubEmailSender (your chosen tonight
  backend), so login links print to stdout = account takeover via logs IF deployed. Fix: select the
  sender from config + **fail closed** if no real sender. **Do NOT deploy the hosted build as-is.**

**MEDIUM — merge-integration + custody:**
- **M1 #101 vs #102 CustodyPolicy collision (merge-critical).** Both branches edit `hosted/custody.py`
  separately; a naive merge silently DROPS a control. Requires ONE explicit integration commit
  composing all three arms (owner-only writes + public/named shares + audited admin super-read).
- **M2 Blind migrate still on the feature branches.** #111's deletion is a separate branch; #111+#112
  must merge in the SAME cluster as the features or the blind stamp lingers. Merge-ordering note.
- **M3 Google-plane linking gap (#97-adjacent).** The proxy (Google) plane doesn't route through the
  email-link lookup, so native-first-then-Google fragments one human into two owner uids. Fix: route
  proxy provisioning through the verified-email link.
- **M4 No per-user quota (#96)** — already an accepted named risk (D2).
- **M5 Proxy-plane share/admin mutations are CSRF-unprotected** (the deferred-CSRF gap on the proxy plane).

**LOW/INFO (8+4):** CSRF deferred on core POSTs (defense-in-depth; SameSite=Lax holds for cross-site,
escalates only under a same-site XSS foothold on a sibling subdomain); noindex on only 2 of the read
routes; share-invite account enumeration; login-CSRF on /auth/redeem; global-budget login-DoS lever;
no server-side session revocation (logout client-only); super_read self-grantable (least-privilege is
audit-only). All fixable hardening; none is a live isolation break.

**DECISION: I did NOT blind-fix the security findings overnight** — fixing security code unsupervised
risks regressions, and you asked for PRs to review. All findings are recorded here + as PR comments;
you review + decide fixes. The clear must-fixes-before-deploy are H1, H2, and the M1 integration.

### Waves 8-9 — auth security fixes + sharing/admin integration (DONE, merged to dev)
Fixed #120's two HIGH findings and composed #121/#122, then ran an adversarial security RE-REVIEW → **verdict CLEAN** (h1_closed, h2_closed, isolation_intact, no_control_dropped, no critical/high).
- **#128** (secured auth, supersedes #120): H1 owner pinned to `MDREVIEW_OWNER_EMAIL` (no first-registrant takeover; hosted refuses boot if unset); H2 email backend config-selected + fail-closed (stub only behind explicit `MDREVIEW_ALLOW_STUB_EMAIL=1` with a loud dev-only warning).
- **#129** (integrated sharing+admin, supersedes #121/#122): ONE CustodyPolicy — reads widen to public/named shares + audited off-by-default cookie-plane admin super-read; **writes/deletes stay OWNER-ONLY** (no share/admin path widens them); the composition explicitly hardened so the #110 choke can't drop the comment control and the owner-pin can't clobber admin grants.
- **Re-review informational carry-forwards (NOT blockers):**
  1. **Features are DORMANT in prod.** The verdict covers the hosted BUILD (`python -m mdreview.hosted`); prod runs the slim `python -m mdreview` (OwnerPolicy). Merging to dev / main does NOT activate magic-link/sharing/admin — that needs a deliberate entrypoint switch + `MDREVIEW_OWNER_EMAIL` + an email sender, and it fails closed without them.
  2. **LaTeX custody out of scope:** if a hosted rollout sets `ENABLE_LATEX=1`, verify `/api/latex/{rid}` enforces the same custody separately (not covered by the #110 choke).
  3. **Transitional proxy plane** is on by default (PROXY_SECRET-trusted); keep nginx the sole setter of `X-Mdreview-Proxy`, and retire the plane once the native session plane is proven.
- **dev final: whole cluster compiles + access-seam oracle PASS + migrate.py deleted.** Only #83 (dev→main, G8) remains — owner's call.
