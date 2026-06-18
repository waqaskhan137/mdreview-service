---
review_of: sprints/sprint-06.md
epic: rich-rendering
gate: cycle-retro
reviewer: cycle-retrospective
independent: true
timestamp: 2026-06-18
status: open   # suggestions only — orchestrator/user decides what becomes a ticket
---

# Rich-rendering cycle retrospective (sprint-06)

**Verdict: smooth run.** 5/5 committed tickets shipped same-day in dependency order, G1 closed in
two rounds, G7 passed first pass (0 blockers, 0 shoulds, 2 NITs), zero carry-overs, scope held
2 P0s start→finish. The only friction was two foreseeable-on-paper gaps that surfaced at G4 instead
of G1 — both cheap to prevent next cycle.

## What went well (load-bearing)

- **The G1 critic earned its keep on the catchable risks.** B1 (the UTF-8 `_read` would 500 on
  the first `.woff2`/image byte — reproduced in the review against real font bytes) and S4 (key
  the served URL on the `%2F`-free `sha1+ext` stored name so a reverse proxy can't mangle it) were
  both load-bearing and both came from staff-critic round 1. These were catchable on paper because
  they are *data-shape* claims — what a function returns, what a proxy does to a byte sequence —
  verifiable by reading `app.py` without a browser.
- **Scope discipline held.** The user scoped to 2 P0s up front; the critic recommended cutting the
  `{name,path}` local-read form (S5) and the planner took it, dropping MR-024 to backlog. No
  tickets grew beyond plan; no debt was smuggled in (history-aware assets stayed an explicit
  Non-goal). Five tickets in, five out.
- **The G4 deviation was diagnosed, not waved through.** MR-022's mechanism switch was documented
  in the Work log with both failure reasons, and the G7 critic independently reproduced them.

## Top suggestions (prioritized)

### 1. Add two repo footguns to the planner's footgun list. `[agent]`
The cycle hit two verification commands the plan specified that don't work on *this* server, both
caught only at implementation:
- `curl -sI` (HEAD) → **501**, because `app.py` implements only `do_GET`/`do_POST`, no `do_HEAD`
  (verified: `app.py:272,275`). The plan's woff2/MIME gating checks all used `curl -sI`; the
  implementer had to switch to a GET header-dump (`curl -sD -`). See MR-022 Follow-ups.
- `scripts/render-smoke.sh '#article img'` → **rejected**: the harness validator allows only
  `tag` / `.class` / `tag.class` / `#id`, **no descendant combinator** (verified:
  `scripts/render-smoke.sh` `_VALID` reject path). The plan and several ACs specified `#article
  img`; it became the bare `img` selector.

Both are stable properties of this repo, not one-offs — they will recur in every future `ui` plan.
The planner already carries a numbered footgun list (`.claude/agents/mdreview-planner.md`,
entries 1–9, e.g. footgun 9 the Dockerfile-COPY rule). **Suggest adding: (a) "HEAD is 501 — MIME
checks use `curl -sD - <GET>`, never `curl -sI`"; (b) "render-smoke selectors are
tag/.class/#id only — no `#parent child`."** This is the single highest-value, lowest-cost fix:
it stops the planner shipping broken verification commands into ACs every cycle.

### 2. Give the planner/critic a "validate the render *mechanism* against the library's real behavior" check for client-side rendering. `[agent]`
The defining discovery (MR-022) was that the G1-approved plan's mechanism — KaTeX `auto-render`
as a **post-markdown pass** — could not meet the brief, for two reasons the implementer verified
at G4: marked strips the backslashes off `\(…\)`/`\[…\]` *before* any post-pass sees them, and
auto-render's bare-`$` scanner pairs prose dollars (`$5 and $10`). The fix was a marked
**extension** (tokenize math during the parse), same engine.

This is the one risk G1 *couldn't* fully catch on paper — it needed marked's actual tokenizer
behavior to surface — and "the browser surfaced it at G4" is largely the system working as
intended. But the *class* is foreseeable: **any "render X client-side after marked has already
parsed the markdown" design inherits marked's mutations of the source.** A planner footgun on
footgun-6 (JS-rendered surfaces) of the shape *"if a feature post-processes marked's output,
state which markdown constructs marked has already consumed/transformed (backslash escapes, code
spans) and whether the post-pass can still see them"* would have surfaced the `\(…\)`-stripping
on paper. The prose-`$` pairing was genuinely a runtime find. Tag this `[agent]` (planner
footgun), not `[process]` — the gate is fine; the prompt lacked the prompt.

### 3. Trim the stray `path` field the critic flagged at G1-r2; it survived into… nothing — confirm it didn't. `[skill]`
The G1-r2 review left one residual non-gating note: the back-compat bullet still listed `path`
among "new POST fields (`content_b64`/`path`/`name`)" after the `path` form was cut (S5), to be
trimmed when MR-023 was written. G7 confirms no `path` field shipped, so this caused no defect —
but it is a case of a known-stale instruction riding from plan → ticket on the implementer's
memory rather than being struck at the source. **Suggest the skill's groom step (`02-groom-and-open`)
explicitly reconcile a plan's "Review resolutions / cut features" against the ticket text it
generates, so a cut feature's vestigial wording can't reach the implementer.** Low value (it
worked this time), included only because it's a recurring *shape* (cut-but-not-fully-excised).

### 4. Record the `do_HEAD`-absence as a tiny backlog ticket, or decide it's wontfix. `[feature]`
`do_HEAD` being unimplemented (HEAD → 501 text/html) is a real, if minor, service gap that this
cycle tripped over twice (the MIME checks). It's noted in MR-022 Follow-ups but has no backlog
home. **Suggest either a one-line backlog ticket (add `do_HEAD` → 200 + headers, no body) or an
explicit "wontfix: clients use GET" note in `backlog.md`,** so the next planner doesn't
rediscover it. Pairs with suggestion 1 (footgun) — the footgun is the cheap fix; this is the
optional real fix.

## What I deliberately did NOT flag

- **G1 taking two rounds is not friction** — round 1 found a real blocker (B1) plus 5 shoulds and
  the author resolved all of them; round 2 was a clean confirmation pass. That is the gate working,
  not churn. The rounds found *different* issues, not the same class repeatedly.
- **The throwaway-container-vs-live-:8139 dance** ran cleanly (every validation used a rebuilt
  `:8138` container, per the standing memory note); no incident to fix.
- **The G7 NITs** (nosniff on name-derived ctype; the render-smoke selector) were correctly
  triaged — NIT 1 hardened, NIT 2 accepted as a pre-existing harness limit. No standing change owed.

## Metrics

| Metric | Value |
|--------|-------|
| G1 rounds | 2 (r1 PASS-WITH-CONDITIONS: 1 blocker + 5 should + 3 nit; r2 PASS) |
| G7 rounds | 1 (PASS: 0 blocker, 0 should, 2 nit) |
| Tickets shipped vs carried | 5 shipped / 0 carried |
| Parks / BLOCKED | 0 |
| Wrong load-bearing assumptions | 0 of 6 (assumption 1, KaTeX-engine, held — only the *integration mechanism*, a plan design choice not flagged as an assumption, was overturned at G4) |
| Plan/AC commands wrong about this repo | 2 (`curl -sI` HEAD→501; `#article img` combinator), both caught at implementation |
