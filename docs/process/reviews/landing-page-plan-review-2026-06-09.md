---
review_of: epics/landing-page-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-09 (Europe/London)
verdict: PASS-WITH-FIXES
status: resolved   # round-2 re-review confirmed all F1-F7 resolved; see -r2.md
---

# G1 review — Landing page on GitHub Pages plan

## Summary

The plan is well-scoped against the brief and the house standard set by the mcp-wrapper plan:
the "sells vs documents / zero build / zero drift" spine is right, the three-ticket breakdown is
sized correctly, the `gh-pages` decoupling from the `dev`->`main` G8 flow is sound, and the
demo-as-Phase-2 split genuinely lets Phase 1 ship. The BLOCKER-FOR-HUMAN on repo-owner vs.
domain-owner is the correct call and (per the review framing) is treated as user-confirmed
same-owner, so it is not re-raised as a gate blocker here.

One factual error is load-bearing and blocks ticket creation as written: the plan asserts
`scripts/render-smoke.sh` has a "Chrome screenshot path" and uses it to produce `site/demo.png`.
It does not. The script only `--dump-dom`s and counts nodes; it never writes an image, and the
repo has no screenshot tooling at all. The Phase-1 demo-capture procedure is therefore not real
as written, and it is the only step that produces the page's reason-to-exist asset. That is F1.
Two further issues (G7 per-page render-evidence applicability to a Pages-hosted page, and the
`render-smoke` "target a SERVED url, never file://" contract vs. the plan's `http.server`
instruction) are MAJOR clarity gaps that will bite at G4/G7 if left implicit. The rest are MINOR.

Verdict: **PASS-WITH-FIXES**. F1 must be corrected (it is a false capability claim, not a
judgement call); F2 and F3 should be resolved into the relevant ticket ACs before grooming. None
require re-planning the epic shape or the ticket count.

## Findings

### F1 — BLOCKER — `render-smoke.sh` has no screenshot path; the Phase-1 demo-capture procedure is fictional

*Sections: "Rollout phases -> Phase 1", "Decisions -> Decision 2", "Recommended approach -> UI (section 2)".*

The plan states the screenshot is "Produced via `scripts/render-smoke.sh`'s Chrome screenshot
path" (Phase 1) and "produced with the existing `scripts/render-smoke.sh` Chrome path (it already
drives headless Chrome; a screenshot variant…)" (Decision 2). This is false. `render-smoke.sh`
invokes Chrome with `--headless=new … --virtual-time-budget --dump-dom "$URL"` and pipes the
serialized DOM into a stdlib HTML parser that counts elements per selector. There is no
`--screenshot` flag, no image is ever written, and the script's own header contract says
"Selectors supported … exit 0/1" — it is a DOM-assertion tool, nothing else. A repo-wide search
for screenshot tooling returns nothing.

How screenshots are actually produced in this repo: the feature-cycle skill
(`references/04-close-and-ship.md`) says to "**open it** … in a browser, screenshotting to
`reviews/sprint-NN-render-evidence-…`" — i.e. a **manual human browser capture**. The existing
`sprint-01-render-evidence/*.png` were made that way, not by the script.

Consequence: `site/demo.png` — the page's stated reason to exist — has no real automated capture
procedure. MR-019's acceptance criteria would cite a step that cannot be run.

Direction: pick one and write it into MR-019's ACs concretely.
(a) **Manual capture** (matches the repo's actual practice): "open the local viewer mid-review
in a browser and capture `site/demo.png`" — a documented human step, exactly like the G7
render-evidence screenshots. Cheapest; honest about what the repo does.
(b) **Headless capture as a real command**: Chrome supports
`--headless=new --screenshot=site/demo.png --window-size=… <url>` directly — invoke Chrome, do
**not** claim render-smoke does it. If this path is wanted as repeatable tooling, that is a small
new script, which itself is borderline against "zero build" and should be a conscious choice, not
smuggled in as an existing capability.
Either way, delete every claim that `render-smoke.sh` screenshots.

### F2 — MAJOR — G7 per-page render-evidence applicability to a Pages-hosted page is asserted, not grounded in the rule's literal text

*Section: "Process / gate enforcement note" (and "Risks & mitigations -> render-smoke has no container").*

The plan says the G7 per-page DOM-assertion + screenshot requirement applies to `site/index.html`
"served from its static location (not the container)" and calls this "a verification-target
clarification within the existing G7 pass-condition, **not** a new rule." But the G7
pass-condition row triggers the per-page obligation **"only if a product page (`viewer.html` /
`dashboard.html` / `static/**`) was touched this sprint."** `site/index.html` is, by this epic's
own design, none of those three and is deliberately outside `static/**`. By the rule's literal
text, this sprint touches **no** product page, so G7 would owe only the unconditional
rebuild + `curl /healthz` + `/api/reviews` smoke — which is itself trivially green here because
`app.py` is unchanged, and which proves nothing about the landing page.

This is the inverse of the mcp-wrapper plan's clean handling (it correctly concluded "no product
page touched -> per-page assertion not owed"). Here the plan *wants* the page render-verified
(rightly) but the trigger set does not name it, so the obligation is asserted by fiat. That is
exactly the "citing a gate row that does not say what you claim" defect class the mcp-wrapper
review flagged as B1 / the MR-012 lesson.

Direction: do not paper over it in prose. Either (a) put the render-smoke-against-served-`site/`
DOM assertion + a captured screenshot into **MR-019's own acceptance criteria** so it is owed at
G4 regardless of how G7's trigger reads (this is the robust fix — the gate enforcement lives in a
real ticket AC, per the MR-012 rule); or (b) make a one-line, explicit decision that the G7
trigger set is read to include `site/**` for this epic and record it as such, not as a "clarification." (a) is preferred and is consistent with how this repo resolved the same class before.

### F3 — MAJOR — `render-smoke.sh` explicitly forbids the serving method the Verification section prescribes

*Section: "Verification -> Page render-smoke (MR-019)".*

The plan's gate command serves the page with `( cd site && python3 -m http.server 8200 )` and runs
`render-smoke.sh http://localhost:8200/ …`. That URL form is fine — but the script's header
contract states: "Target a SERVED url (the rebuilt container's published port), **never a
file:// path**." The `http.server` approach satisfies "served, not file://", so the command will
work; however the plan never reconciles its instruction against the script's stated contract, and
a reader following the script's own docs (or the G4 rule in README, which says "render-smoke from
the **rebuilt image**") will reasonably believe a container is required. The page is not in the
image, so "rebuild the image" is impossible for this artifact.

There is a real gap, not just wording: README's **G4 pass-condition** says "for `ui` tickets, a
render-smoke **from the rebuilt image** passes." MR-019 is tagged `ui` but its artifact is never
in any image. The plan needs to state, as a ticket-level fact MR-019 carries, that its G4
render-smoke target is a local `python3 -m http.server` of `site/` (not a rebuilt container), so
the `ui` ticket's G4 evidence is producible and a future reader does not treat the missing
container rebuild as non-compliance. Right now that reconciliation lives only as a Risk bullet
("render-smoke has no container to hit"); it belongs in MR-019's ACs as the explicit gate target.

### F4 — MINOR — dashboard token citations are slightly off and incomplete

*Section: "Recommended approach -> UI (Design direction, Decision 5)".*

The plan copies the `:root` custom properties verbatim and cites `dashboard.html:8-9`,
`dashboard.html:11,20`. The palette is on line 8 and the dark-mode block on line 9 (correct), the
system font stack is on the `body` rule (line 11, correct), and `max-width:920px` is on `.wrap`
(line 12, correct). But the quoted `:root` set **omits `--noteline:#d4a017`**, which is present in
both the light and dark `:root` in the real file — and `--noteline` is exactly the
strike-through/annotation accent the demo screenshot will show, so dropping it risks a palette
mismatch between the page chrome and the screenshot it frames. Also, citing `dashboard.html:20`
for the monospace stack is imprecise (the mono stack appears on several rules; line 20 is
`.session>h3`). Direction: copy the **full** `:root` set including `--noteline`, and drop the
narrow line cite for the mono stack in favour of "the `ui-monospace,SFMono-Regular,Menlo,monospace`
stack used throughout `dashboard.html`."

### F5 — MINOR — README "where it lives" edit is a small drift surface the plan half-acknowledges but does not constrain

*Sections: "Rollout phases -> Phase 1 (Record the canonical URL)", "Decision 3".*

Recording the canonical URL in the README is correct and folded into MR-020 (good — no separate
docs-sweep needed). But the brief's "No drift surface" rule is about the README being the source
of truth; here the **README gains a new fact (the live URL) that only becomes true after the
one-time human Pages/DNS/HTTPS steps succeed.** If MR-020 records the URL in the README before the
human steps verify, the README asserts a live URL that 404s. Direction: sequence MR-020's ACs so
the README URL edit is gated on the `dig`/`curl -sI … 200`/render-smoke live checks passing —
i.e. "record the URL in README **after** the publish-verification block is green," not as a
parallel step. The plan lists both under Phase 1 without ordering them.

### F6 — MINOR — Phase 2 (MR-021, GIF) sizing and "this sprint?" question is left implicit

*Sections: "Rollout phases -> Phase 2", "Preferred execution order (MR-021)", "Ticket breakdown".*

The plan correctly makes Phase 2 separable and says MR-021 is "independently shippable later, not
required to declare Phase 1 live." Good. But it still lists MR-021 in the same ticket-breakdown
table as MR-019/MR-020 without saying whether it is **committed to this sprint** or parked to the
backlog. Per G6 (sprint open), every committed ticket must be `ready`; MR-021 cannot be `ready`
because its capture tooling/decision (GIF vs `<video>`) is an open question (Q in Assumptions) and
the asset does not exist. Putting a not-ready ticket in the sprint's committed list would fail G6.
Direction: state explicitly that MR-021 is **backlog / next-sprint**, not committed to sprint-05;
the epic's sprint commits MR-019 + MR-020 only. This keeps the sprint's committed set all-`ready`
and avoids a guaranteed carry-over.

### F7 — NIT — `gh-pages` publish step is "a documented git command sequence" but the sequence is never shown

*Sections: "Decision 1", "Decision 3 (the per-cycle act of updating)".*

The decision to publish `site/` -> `gh-pages` root manually is sound and correctly rejects the
Actions-workflow alternative for "zero build." But the actual mechanic ("a documented git command
sequence in the ticket, not a build") is deferred entirely to MR-020 with no shape given. The
non-obvious part — getting only `site/` contents to `gh-pages` **root** (not under `site/`) while
keeping `dev` clean — has a few standard forms (`git subtree split`, a `git worktree` on
`gh-pages`, or a throwaway-branch `git checkout`); each has a footgun (subtree history bloat,
worktree path collisions). Not a blocker for G1, but MR-020's AC should pin one concrete sequence
so it is repeatable, since the plan elsewhere prides itself on concrete commands.

## Resolution log

- **F1 (BLOCKER) — render-smoke screenshot path is fictional.** RESOLVED 2026-06-09 (author).
  Removed every claim that `scripts/render-smoke.sh` produces a screenshot. In *Rollout phases ->
  Phase 1* the demo-capture bullet now states explicitly that render-smoke `--dump-dom`s and counts
  nodes only and "cannot produce this," and offers two real procedures: **(a)** a documented manual
  browser capture (default, matching how `sprint-01-render-evidence/*.png` were made per the
  feature-cycle `references/04-close-and-ship.md`), and **(b)** a direct
  `"$CHROME" --headless=new --screenshot=site/demo.png --window-size=1280,800 …` command invoked
  *directly* (not via render-smoke), reusing the binary render-smoke locates (`RENDER_SMOKE_CHROME`
  / the `CANDIDATES` list at `scripts/render-smoke.sh:32-41`). *Decision 2* now says render-smoke is
  "not a screenshot tool … so it is *not* used to produce the demo asset." The capture is wired into
  MR-019's ACs (item 2 in *Verification -> Page render-smoke (MR-019)*). MR-019 picks (a) or (b); (a)
  is default.

- **F2 (MAJOR) — G7 per-page trigger does not cover `site/index.html`.** RESOLVED 2026-06-09
  (author). Rewrote *Process / gate enforcement note* to **stop asserting** the G7 trigger covers
  the page: it now states plainly that the G7 row fires only for `viewer.html`/`dashboard.html`/
  `static/**`, that `site/index.html` is none of those, and that the plan does **not** claim the
  trigger covers `site/**` (avoiding the MR-012/B1 defect). The render obligation is instead placed
  in **MR-019's own acceptance criteria** (item 1+2 of *Verification -> Page render-smoke (MR-019)*):
  a served-`site/` render-smoke DOM assertion **plus** a committed screenshot, owed at **G4**
  regardless of how G7's trigger reads.

- **F3 (MAJOR) — README G4 "rebuilt image" vs. a page never in any image.** RESOLVED 2026-06-09
  (author). Promoted the `python3 -m http.server` approach from a Risk bullet into **MR-019's named
  G4 validation target** in *Verification -> Page render-smoke (MR-019)*: the gate command is
  `python3 -m http.server 8200 --directory site` then `scripts/render-smoke.sh http://localhost:8200/
  <selectors>`, and MR-019 carries as a ticket-level fact that the absent container rebuild is
  compliant for this artifact (the README "rebuilt image" wording does not apply to a Pages-hosted
  page). The Risk bullet now points at this AC rather than owning the reconciliation.

- **F4 (MINOR) — token set incomplete; mono-stack cite imprecise.** RESOLVED 2026-06-09 (author).
  Added `--noteline:#d4a017` to the copied `:root` set in *Recommended approach -> UI* and *Decision
  5*, noting it is the strike-through/annotation accent the demo screenshot shows. Verified against
  `dashboard.html:8` (light) and `dashboard.html:9` (dark). Replaced the imprecise `dashboard.html:20`
  mono cite (line 20 is `.session>h3`) with "the `ui-monospace,SFMono-Regular,Menlo,monospace` stack
  used throughout `dashboard.html`"; kept precise cites for the palette (`:8`), dark block (`:9`),
  and system font stack (`:11`).

- **F5 (MINOR) — README URL recorded before publish verified.** RESOLVED 2026-06-09 (author).
  Re-sequenced *Rollout phases -> Phase 1*: the one-time human Pages/DNS/HTTPS steps now come first,
  and the README canonical-URL edit is listed **last and explicitly gated** on the
  publish-verification block (`dig` -> `<owner>.github.io`, `curl -sI … 200`, live render-smoke)
  being green, so the README never asserts a URL that 404s. MR-020's ACs are told to order it
  "after publish-verification is green," not in parallel.

- **F6 (MINOR) — MR-021 cannot be `ready`; sprint scope unstated.** RESOLVED 2026-06-09 (author).
  Stated explicitly in *Rollout phases -> Phase 2*, *Preferred execution order*, and the *Ticket
  breakdown* (new "Sprint" column) that **MR-021 is backlog / next cycle, NOT committed to this
  sprint** — it cannot be `ready` (no GIF asset; GIF-vs-`<video>` open), and committing it would
  fail G6. The epic's sprint commits **MR-019 + MR-020 only**.

- **F7 (NIT) — publish sequence never shown.** RESOLVED 2026-06-09 (author). Pinned **one** concrete
  sequence in *Decision 3*: a dedicated **`git worktree` on an orphan `gh-pages` branch**
  (`git worktree add --orphan -b gh-pages ../mdreview-gh-pages`, then
  `rsync -a --delete --exclude '.git' site/ ../mdreview-gh-pages/`, commit, `git push origin
  gh-pages`). Explicitly rejected `git subtree split` (history bloat) and an in-place throwaway
  `git checkout` (working-tree collision). The exact commands are written into the plan so MR-020
  inherits them verbatim; `rsync --delete` makes re-publishes idempotent and `site/CNAME` lands at
  the branch root.
