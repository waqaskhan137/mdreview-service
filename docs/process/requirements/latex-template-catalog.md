---
slug: latex-template-catalog
captured: 2026-07-21
source: owner (chat session, 2026-07-21)
related_epic: ../epics/latex-template-catalog-plan.md
---

# Requirement: LaTeX template catalog (verbatim brief)

Captured verbatim from the owner's messages in the planning session of 2026-07-21. Grooming and
scope decisions live in the epic plan, not here. Never edit the quotes below.

## Original request

> if it doesnt exist i would imagine it a feature like having a seperate endpoint which is
> responsible for latex templates pulls and then giving it to service and user option to use
> whatever template they want. /plan for it

## Binding redirects (same session, in order)

1. On placing a template picker in the web UI:

> This doesnt make any sense. User is talking to coding agent and asking to create the doc and only
> going to the web ui once it is created so giving latex templates on web ui is kind stupid

2. Bundled + pull hybrid:

> I want bundled but the ability to pull the template if doesnt exist

3. The hard rule (downloaded files never in the build):

> We ship only famouse few templates and if user wants something which we do not have in template
> we just download and keep it for them we do not incorporate it in sourcecode of our build

4. IoC requirement:

> how you will make sure this is following IoC

## Decisions given during plan review (mdreview review a4b479b1ac, 2026-07-21)

Owner answers to the four open questions:

> 1. default resgitry 2. merge to dev 3. bundle the top ones 4. the conference's own address.

Interpreted (see the epic plan "Decisions recorded"):
1. Ship `registry.json` pre-populated with the known non-CTAN conference file-sets.
2. Merge `feat/latex-review` into `dev` first, then cut this epic's tickets from `dev`.
3. Bundle the most-popular non-CTAN styles as actual files (offline); download-on-miss covers the tail.
4. Registry origin = each conference's own official source (no self-hosted mirror in v1).

> merge it and go
