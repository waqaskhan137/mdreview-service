# Spine: document custody — a document belongs to the account that created it

> Status: SPINE, awaiting owner approval (routed through mdreview once the MCP reconnects).
> Written after the #97 custody breach so the ownership rules survive the people who know them.
> 5-line spine; no expansion until approved.

1. **What.** The design for how a hosted document stays bound to its creator: stamped at birth,
   enforced on every access, never silently re-assigned.
2. **How.** Identity is the canonical `provider:sub` uid (email-linked per #67 D1); the owner is
   resolved and stamped at CREATE time from the authenticated principal (Bearer token or
   session), and creation **fails closed** when no principal exists, so an un-owned document is
   impossible, not merely repairable.
3. **Enforcement.** Every read / list / write / delete passes an owner check at the service
   layer (not the proxy), so the loopback and direct-to-app paths enforce identically;
   un-owned records on an auth-enabled instance trip an alarm and queue for HUMAN assignment by
   provenance. Blanket adoption (the #97 back-fill failure) is forbidden by design.
4. **Covers.** Creation stamping, access enforcement, the auth-off failure class and its
   tripwires, migration / back-fill rules, and how ownership meets the coming magic-link
   identity (#67).
5. **Out of scope.** The local tier (keep-it-yours: no accounts, everything open on localhost,
   by design); sharing / visibility / invites (#68 builds ON this as explicit exceptions);
   resource quotas (#96).
