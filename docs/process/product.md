# Product goal

> **Status: DRAFT**, distilled from the landing page + README positioning on 2026-07-22, revised
> per owner review feedback (mdreview review `3d177a514f`, rev 2). Not yet explicitly approved:
> treat as provisional, use it but say so. Update it deliberately; it is strategy, not a
> scratchpad.

**North star.** An agent's work never ships past a review the human has not signed off on, and
earning that sign-off is a tight loop: the agent drafts (markdown or LaTeX), the human reviews
in the browser with threaded comments, the agent actions the feedback and pushes a new draft,
repeat until approval. Positioning: "Human-in-the-loop markdown review for AI agents. Coding was
never the bottleneck. Thinking was."

**Target users, in order.**

1. The owner: daily driver for plan and doc review with Claude Code.
2. Agent-using developers self-hosting locally: no account, no auth, keep-it-yours.
3. Invited hosted users at app.mdreview.space: Google sign-in, invite-only today.

**Product principles** (what "good" means when weighing work):

- The loop is the product. Anything that makes draft, comment, action, re-draft faster or
  clearer beats anything that does not.
- Smooth beats featureful. Polished and hiccup-free end to end (sign-up, install, review) wins
  over a new capability; a hiccup in the first five minutes costs more than a missing feature.
- Keep-it-yours. Local-first and self-hostable stays first-class; hosted never overrules,
  degrades, or phones home from a local instance.
- Simplicity is a feature. Stdlib-only service, buildless frontend, one container; a new
  dependency has to pay rent.
- Agent-native. MCP is a first-class surface: whatever a human can do in the viewer, an agent
  can do over MCP, except approve.
- The sign-off is sacred. Nothing may fake, skip, or dilute the human's approval.

**The model: local and hosted, distinct on purpose.** Local is free, full-featured for solo use,
and stays that way; it is the product's promise, not a crippled demo of hosted. Hosted is the
power tier you sign up for when you want more: collaboration, invites, your docs in the cloud,
and it may in future charge a minimal fee to maintain the platform. The two are kept distinct;
neither is a funnel that degrades the other.

**Strategic direction (as of 2026-07).** From solo tool toward a small multi-user product,
smoothness first:

1. Frictionless entry. Native simple login becomes the primary auth with Google sign-in
   secondary (#67): depending on Google's OAuth approval process means wait-and-approve friction
   the product must not be gated on. Onboarding and packaging stay in scope (#37, #38).
2. Collaboration (hosted). Per-document public/private visibility and inviting other users by
   email to view and comment (#68).
3. Also in play: local-hosted sync (#66) and the rebrand decision (#43).

These enter a sprint only through the gates.

**Non-goals.** A general-purpose docs platform or Google-Docs clone; realtime co-editing
(deferred, issue #16); heavyweight frameworks or build steps; monetizing or gating the local
tool.

**Scoring hook.** In RICE and WSJF, "Impact" and "user value" mean movement toward this north
star for the target users above, in their listed order.
