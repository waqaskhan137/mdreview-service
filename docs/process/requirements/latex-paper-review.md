---
slug: latex-paper-review
captured: 2026-07-21
source: owner (chat session, 2026-07-21)
related_epic: ../epics/latex-paper-review-plan.md
---

# Requirement: LaTeX paper review mode (verbatim brief)

Captured verbatim from the owner's messages in the planning session of 2026-07-21. Grooming and
scope decisions live in the epic plan, not here. Never edit the quotes below.

## Original request

> I want you to plan the mdreview model which is for research paper review And ideally it should
> take inpiration from overleafe because alot of researchers know the ui one side latex and other
> otherside preview. And we can have out comment feature same as it is now and user should be able
> to download the pdf as well.

## Binding redirects (same session, in order)

1. Modularity / IoC:

> i want it to be modular and a feature if user wants to enable it, it should have its own module
> inside src/ and should be following IoC The objective is to keep the current app features intact
> but only add this feature with minimum modifications to the existing app.

2. Branching:

> This feature should have its own feature branch and can not move to the dev until it is approved
> by me.

3. Feedback flow (rejecting the turn-baton UI for this mode):

> it is intended that user once commented on the doc how much they wanted and then come to cli and
> ask the coding agent to collect the feedback.

4. Live preview (rejecting the attached-PDF / staleness-badge design):

> no, the latex version should be live view in pdf and I do not want to complicate it

5. On the normal-mode turn banner shown in the comparison mockup:

> this is not required as it is taken that user after commenting they will say colelct feedback
> from coding cli to colelct so, drop this

## Decisions given during plan review (mdreview review 9215476104, 2026-07-21)

> First consolidate the dev and then take base branch from dev. I can not accept the process
> breakage.

> acceptable. [figures: bare-filename-only asset references in v1]

> rollout will be later only when I test it locall and approve the changes.

> do that [add the two compile hardenings: scrubbed subprocess env + unprivileged compile uid]

> approved
