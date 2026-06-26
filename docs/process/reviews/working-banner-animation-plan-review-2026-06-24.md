---
review_of: epics/working-banner-animation-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS-WITH-NITS
status: resolved
---

# G1 independent review — working-banner waiting animation (CSS-only, MR-061)

Scope: the whole single-ticket epic. This gates spawning MR-061 (the cheap slice of GH #27 — a
waiting animation on the viewer's `working`-state turn banner). Right-sized: a CSS-only change to one
already-served file, no `app.py`/Dockerfile/MCP surface. The design is sound; the two findings below
are both in the **Verification recipe**, where the plan writes the smoke against (1) a non-existent
endpoint and (2) a selector the matcher rejects. Neither touches the design — both are literal-command
fixes the ticket must make before the smoke can run, which is exactly what G1 is for.

**Verdict: PASS-WITH-NITS.** The implementation approach is correct and I verified it against the
shipped tree: `renderBanner` (`viewer.html:226-248`), the `.turnbanner` CSS (`:80-83`), the theme
vars (`:10-11`), the DOM (`:167`), the `/handoff` router arm (`app.py:604-672`), and the
`render-smoke.sh` selector grammar (regex run directly). The class-toggle pattern, the stale-vs-working
distinction, the reduced-motion off-switch, and the theme-var colour are all right. The two blocking
items are smoke-recipe defects: as written, Verification step 2 hits a 404 and step 3 fails as
bad-usage — so the gate's own "is it verifiable" question fails until they're corrected. Both are
pinned below with the exact replacement.

---

## Verification performed (read-only)

- **Attach point + state machine.** Read `renderBanner` (`viewer.html:226-248`). The working arm is
  the `else` at `:235`; it is correctly distinguished from the stale arm at `:234`
  (`(Date.now()/1000-(as.at||0))>STALE_S` → "may have stopped"). The plan's "remove at top, add only
  in the working arm" pattern is robust across all six states: `renderBanner` runs top-to-bottom every
  ~2s poll, a single `bar.classList.remove('working')` after the `:230` guard clears it, and only the
  working `else` re-adds it. No other arm can carry the class, so the `::after` ellipsis can never
  appear on a non-working banner. Confirmed.
- **No collision with `.show`/display.** `#turnbanner` already carries class `turnbanner` and gets
  `show` added at `:247` (`.turnbanner.show{display:flex}` at `:81`). Adding `working` is a third,
  orthogonal class on the same element; it does not touch the display rule. Confirmed.
- **Reduced-motion.** The plan adds `@media (prefers-reduced-motion: reduce){ … animation:none }`
  while keeping `content:"…"`, restoring today's static appearance. Present and correct.
- **Theme vars exist.** `--muted` and `--text` are defined at `:10` and re-defined under
  `@media (prefers-color-scheme: dark)` at `:11`. Driving the ellipsis colour from them (not a hex)
  reads on both panes. Confirmed.
- **DOM ids exist.** `<div id="turnbanner" class="turnbanner"><span id="turntext">…` at `:167`. Both
  `#turnbanner` and `#turntext` are real nodes the smoke can assert. Confirmed.
- **Scope.** Only `viewer.html` is edited; no new served file, so no `Dockerfile COPY` row, no
  `app.py`/MCP/`meta.json` change. Nothing from #27's progress-steps / streamed-diff half leaks in.
  Clean. No YAGNI — the animation-technique fork is correctly deferred to a 5-minute screenshot
  comparison at implementation, not pre-litigated in prose.

---

## Findings

### [blocking] B1 — The lease-claim endpoint in the smoke (`POST /…/ping`) does not exist; it's `/handoff {state:"working"}`

Verification step 2 (plan `:246-247`) claims a fresh working lease with:

```
curl -s -X POST "$BASE/api/reviews/$id/ping" -d '{"owner":"mr061-smoke","state":"working"}'
```

There is **no `/ping` route** in `app.py`. I read the full router: the only baton route is
`/handoff` (`app.py:604`), and the lease claim is the `elif state == "working"` arm *of that same
route* (`app.py:635-662`), body `{"state":"working","owner":"…"}`. The plan half-knows this — its
open-question at `:336-343` flags the route as "least-sure" and the viewer posts to `API+'/handoff'`
(`viewer.html:222`) — but the recipe body still says `/ping`, which 404s and never sets a lease, so
`/status` stays parked (`agent_status:null`) and `renderBanner` takes the **parked** arm, not working.
The smoke would then assert a banner that never animated.

**Fix (exact):** the correct two calls are

```
# hand the turn to the agent (parks agent_status:null)
curl -s -X POST "$BASE/api/reviews/$id/handoff" -d '{"to":"agent"}'
# claim a fresh working lease ON THE SAME /handoff route
curl -s -X POST "$BASE/api/reviews/$id/handoff" -d '{"state":"working","owner":"mr061-smoke"}'
```

The grant path is unconditional for an unset/equal owner (`app.py:652`), so a first claim with a fresh
`owner` succeeds and writes `agent_status={state:"working",owner,at:now}`. Drop every reference to a
`/ping` endpoint and to MCP `ping_working` as "the curl equivalent" (the MCP tool ultimately drives
this same `/handoff` arm; there is no separate ping HTTP path).

### [blocking] B2 — `render-smoke.sh` rejects `#turnbanner.working` as bad usage; assert the bare class `.working`

Verification step 3 (plan `:274`, `:279`) is built on:

```
scripts/render-smoke.sh "$BASE/review/$id" '#turnbanner.working'
```

I ran the tool's selector validator (`render-smoke.sh:72`,
`^(#[A-Za-z_][\w-]*|[A-Za-z][\w-]*(\.[A-Za-z_][\w-]*)*|(\.[A-Za-z_][\w-]*)+)$`) against this literal:
**it returns False.** The `#id` branch is `#[A-Za-z_][\w-]*` — `\w`/`-` only, **no `.` allowed** — so
`#turnbanner.working` fails the `$` anchor on the `.working` suffix and the tool exits **2 (bad
usage)**, not a real present/absent assertion. So step 3 never tests anything; it errors out both
times (the "expect exit 0" and the "expect exit 1" lines are both wrong — both would be exit 2).

This contradicts the plan's own Key Constraints (`:158-161`), which correctly says render-smoke is a
flat matcher — but then mis-applies it. The tool **does** support compound `tag.class` and bare
`.class` on a single element (`.working` and `div.working` both validate); what it rejects is
specifically `#id.class` and descendant combinators (a space).

**Fix (exact):** assert the bare class, which is an unambiguous proxy because only `#turnbanner` ever
carries it:

```
# working state -> the marker class is present
scripts/render-smoke.sh "$BASE/review/$id" '#turnbanner' '#turntext' '.working'   # expect exit 0
# flip to reviewer's turn, re-assert ABSENCE of the marker
curl -s -X POST "$BASE/api/reviews/$id/handoff" -d '{"to":"reviewer","by":"reviewer"}'
scripts/render-smoke.sh "$BASE/review/$id" '.working'                              # expect exit 1
```

A1/A3 still hold verbatim; only the selector token changes. (If a future class name collision worried
you, `span.working` or `div.working` would also validate and scope to a tag — but `.working` is fine
here.)

### [worth-considering] W1 — Reduced-motion probe (step 5) needs a concrete getComputedStyle, not just prose

Step 5 (`:307-322`) correctly notes `--dump-dom` won't show pseudo `animation-name` reliably and says
"prefer a small evaluate," but leaves the actual probe unwritten. The ticket should pin one line so the
A4 check is reproducible, e.g. drive CDP `Runtime.evaluate` with
`getComputedStyle(document.querySelector('#turntext'),'::after').animationName` and assert it resolves
to `none` under reduced-motion and to your keyframe name otherwise. Without a written probe this AC
risks being eyeballed-only. Not blocking — the mechanism is named, just not concretised.

### [nit] N1 — `--force-prefers-reduced-motion` flag availability

Step 5 uses `--force-prefers-reduced-motion`; the plan already hedges with a CDP
`Emulation.setEmulatedMedia` fallback (`:319-321`), which is the portable path. Lead with the CDP
emulation rather than the flag so the recipe doesn't depend on a flag a given Chrome build may not
expose. Cosmetic.

---

## What's good (load-bearing)

- The "single `remove` at top, `add` only in the working arm" pattern is the correct way to keep the
  class hygienic across the 2s re-render, and the plan correctly identifies it as load-bearing (the
  alternative — adding in working, removing in each other arm — is the bug-prone version).
- Choosing an animated `::after` ellipsis over a spinner span is the right call: zero new DOM,
  `renderBanner` only toggles a class, and the smoke surface stays a single real node. The plan
  defends this explicitly and keeps the spinner as a documented reversible fallback.
- Deferring the keyframe technique (content-step vs clip/width vs opacity) to a screenshot comparison,
  rather than arguing it in the plan, is correctly right-sized for a CSS tweak.

---

## Resolution log

- **B1 (lease endpoint)** — OPEN. Smoke step 2 must use `POST /api/reviews/{id}/handoff` with
  `{"state":"working","owner":"…"}` (the `state=="working"` arm at `app.py:635`), not a `/ping` route
  (which does not exist). Confirmed against the full router.
- **B2 (`#turnbanner.working` rejected)** — OPEN. Smoke step 3 must assert the bare class `.working`
  (validates; tool exits 0/1 correctly); `#turnbanner.working` exits 2 (bad usage) — confirmed by
  running `render-smoke.sh`'s `_VALID` regex against the literal. The plan's Verification contradicts
  its own Key Constraints here.
- **W1 (reduced-motion probe)** — OPEN. Write the concrete `getComputedStyle(...,'::after')
  .animationName` assertion into the ticket.
- **N1 (reduced-motion flag)** — OPEN. Prefer the CDP `setEmulatedMedia` path over the Chrome flag.

Both blocking items are recipe-literal corrections inside MR-061's Verification; the design,
acceptance criteria, and scope are sound. Fix B1/B2 in the groomed ticket and the gate clears.

## Resolution log

- 2026-06-24 — Independent G1 review (1-ticket CSS-only ui change). Verdict PASS-WITH-NITS; the DESIGN
  is sound (working-vs-stale arm distinction, class-remove-at-top + add-in-working-arm, `.show`
  non-collision, `--muted`/`--text` theme vars, the `::after` ellipsis approach — all confirmed). Both
  "blocking" items were in the render-smoke RECIPE, not the implementation.
- 2026-06-24 — Planner revised (author preserved). Folded: **B1** — force-working step corrected to
  `POST /handoff {to:agent}` then `POST /handoff {state:working,owner}` (no `/ping` route exists;
  verified app.py:635-662); **B2** — every `#turnbanner.working` render-smoke assertion → bare
  `.working` (render-smoke.sh:72 rejects the compound id+class); **W1** — reduced-motion check is now a
  concrete `getComputedStyle($("#turntext"),'::after').animationName === 'none'` probe; **N1** — CDP
  `Emulation.setEmulatedMedia` over a Chrome flag. No second G1 round needed (smoke-recipe fixes, not
  design). **G1 PASS.**
