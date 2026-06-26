---
review_of: epics/viewer-transparency-plan.md
gate: G1
reviewer: staff-critic
independent: true
verdict: GO-WITH-NITS
status: resolved
date: 2026-06-24
---

# G1 review — viewer-transparency plan

Independent staff-critic review of the `viewer-transparency` epic plan (GH #27). Reviewer is not the
author (the `mdreview-planner` authored and revised; the orchestrator implements). One round.

## Verdict: GO-WITH-NITS — no blocking findings.

The load-bearing design fork is resolved correctly and evidence-backed: every "verified against" cell
in the A/B/C table checks out against the real code, so the YAGNI deferral of (C) is trustworthy. The
critic confirmed all cited lines: `/status` body (`app.py:589-598`), hand_back re-bump of `turn_updated`
(`:629`), reviewer→agent flip bump (`:636`), lease claim writing `state:"working"`+`message`
(`:660-664`), `source_updated` (`:558`), `comments_updated` (`:751/771/790`), the `renderBanner` arms
(`viewer.html:241-281`), the spinner+reduced-motion (`:87-89`), `watch.py:504` (stdout uncaptured),
the crash signal (`watch.py:405-407`). `claude --output-format stream-json` confirmed real (so (C) is
deferred on YAGNI, not infeasibility).

**Key judgments:**
- **Tier-1 (derive the step timeline from existing `/status` signals, UI-only) is enough to ship as
  the headline; (C) the raw tool-call stream is a fair follow-on, not load-bearing.** The owner's
  trigger (a healthy 2.5-min run looks frozen) is fully resolved by step-level stages + the live timer.
  **Owner confirmed step-level** (not the literal tool-call stream) — (C) stays deferred.
- **The client-side timer is sound.** `turn_updated` is the Send/flip time, present in `/status`;
  re-bumped on hand_back (`:629`) so the final duration is captured client-side (shows *no number*
  rather than a wrong one after a post-`done` reload). The 1s tick is fetch-free; leak risk addressed.
- **Cutting MR-074 is correct** — the `ping_working` `message` already round-trips
  (`mcp_server.py` → `app.py:661` → `/status:597`); only the viewer display is missing, which is MR-073.

## Findings + resolution

| # | Sev | Finding | Resolution (planner revision, 2026-06-24) |
|---|-----|---------|-------------------------------------------|
| 1 | worth-fixing | The "resolving" label over-claims: `comments_updated` bumps on `reply\|reopen\|create\|delete` too, so a reply-then-`blocked` turn would falsely light "resolving". | **Folded.** The comment step is now signal-honest **"Updating comments"**; the word **"Resolved"** shows ONLY on terminal `done`. New node-CDP assertion for the reply-then-`blocked` path: "Resolved" must never appear that turn. |
| 2 | worth-fixing | No derivable signal for the brief's "reading comments" step (dropped by omission). | **Folded.** "Reading" is made an explicit non-derivable **resting label of the claimed step** ("Connected — reading your comments"); the plan states it is not independently derivable (no fake signal invented). |

**Open question (now closed):** owner chose **step-level** over the literal tool-call stream — (C)
stays deferred; no scope expansion. All findings resolved; G1 cleared.
