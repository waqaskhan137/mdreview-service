---
review_of: epics/dashboard-redesign-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-19
verdict: PASS-WITH-CONDITIONS
status: resolved
---

# G1 review — dashboard-redesign plan

**Verdict: PASS-WITH-CONDITIONS.** The plan is well-scoped, the code claims check out
(payload shape, routes, Dockerfile COPY, render-smoke flat-matcher all verified), and the two
judgment forks I was asked to rule on — A3 (notes-count, no API change) and A4 (1600px cap) —
are both **correct calls**, not creep. The one thing that must change before tickets fly: the
dark/light pane capture recipe in Verification step 4d uses the **wrong Chrome flag** and would
produce two dark screenshots while claiming to prove both panes — the exact mechanism this repo
already rejected on record. Fix the flag (one-line) and re-affirm A3/A4 in the ticket AC; then G1
passes.

## Findings

### [SHOULD] Verification 4d uses `--force-dark-mode` — invalid both-pane proof; this repo already settled the right flag

The both-pane render evidence is **load-bearing** (the plan itself elevates it to the binding
proof for a pane-adaptive page, current-state "Theme" finding + Fork 5). The capture recipe is
wrong on two counts, verified empirically on this machine:

- `--force-dark-mode` (step 4d, `dark-pane.png`) is Chrome's auto-invert filter, **not**
  `prefers-color-scheme` emulation. This is not a fresh opinion — the **theme-awareness G1 review**
  (`reviews/theme-awareness-plan-review-2026-06-18.md`, "What's sound") states it verbatim:
  "`--force-dark-mode` ... is Chrome's auto-invert, a different mechanism," and establishes
  `--blink-settings=preferredColorScheme=0/1` as the correct emulation. The current plan reaches
  for the flag that prior review explicitly rejected.
- Worse: the `light-pane.png` command (step 4d) passes **no scheme flag at all**. I reproduced
  that bare headless Chrome on this machine resolves **dark** by default
  (`getComputedStyle` body bg = `rgb(17,17,17)`, `matchMedia('(prefers-color-scheme: dark)')`
  = true). So as written, `light-pane.png` renders the **dark** pane — both "panes" come out dark
  and the both-pane proof is vacuous.

Empirical result on a pane-adaptive probe (`:root` light default + dark `@media`):
`--force-dark-mode` -> `#111` (dark); no-flag -> `#111` (dark); `preferredColorScheme=0` -> `#111`
(dark); `preferredColorScheme=1` -> `#fafaf9` (light). Only the last gives a true light pane.

**Fix (one line each):** dark pane = `--blink-settings=preferredColorScheme=0`; light pane =
`--blink-settings=preferredColorScheme=1`. Drop `--force-dark-mode`. Apply the same flag to the
dark-pane `getComputedStyle` legibility check in Fork 5. This is a verification-recipe defect, not
a design defect — the plan is otherwise right that both panes must be proven; the recipe just
wouldn't prove it.

### [NIT] A3 scope ruling is correct — let it stand (do not stop and ask)

Ruling requested. The planner reads the brief's expanded-card "full notes" as the **notes-count
label**, not per-note bodies, because `/api/reviews` carries only `notes_total`/`notes_addressed`.
**Verified in code:** `summary()` (`app.py:120-135`) emits exactly those two integer counts;
there is no note quote/body anywhere in the payload (`list_reviews()`, `app.py:138-141`). Note
bodies live only in `viewer.html` via a separate feedback fetch. The brief's hard constraint is
"**Change only layout, density, search/filter, and collapse/expand behavior**" and
"Out of scope: any change to the service, its API, the MCP wrapper." Reading "full notes" as
per-note text would force a service/API change, which the brief forbids in the same document — so
the per-note reading is self-contradictory with the brief, and the count reading is the only one
that satisfies both clauses. **The planner's reading should stand; do not stop the cycle to ask.**
The plan already records it as A3 with an explicit "if the reviewer reads it as bodies, that's a
separate epic" escape hatch, which is the right disposition. One concrete ask: the collapsed
metadata row already shows the notes badge, so the expanded card "restating the full notes label"
adds near-zero information — make sure the ticket AC doesn't treat a redundant restatement as a
must-have; "full notes" in the expanded view is satisfied by the same `noteLabel()` string and
that's fine.

### [NIT] A4 — the 1600px cap is the right call; flag stays a flag, not a blocker

Ruling requested. The brief says both `repeat(auto-fill, minmax(280px,1fr))` **and** "3-5 columns
on desktop" — genuinely in tension. I reproduced the planner's column counts exactly
(4/4/5/6/8 at 1280/1440/1680/1920/2560 with 48px total side padding, 10px gap): `minmax(280px,1fr)`
**does** overshoot to 6 at 1920px and 8 at 2560px. Capping the container at `max-width:1600px`
centered holds it at 5 on both — confirmed. I also checked the alternative (keep edge-to-edge,
raise the floor to cap the count): no single floor satisfies "<=5 cols at 2560 **and** verbatim
280px **and** doesn't starve a 1440 screen to 3 cols" — `minmax(440px)` is the first to cap 2560
at 5 but it changes the brief's verbatim value and drops 1440px to 3 columns. So the container cap
**is** the smallest change that honors both the literal value and the "3-5" intent.

The cost is real — empty side margins on a 1920/4K monitor, which an author of "full-width
responsive grid" might dislike. But "3-5 columns" is also explicit, and density-per-row was the
point. The cap honors the stated count over the implied edge-to-edge; the reverse choice (ignore
"3-5", go truly edge-to-edge) is equally defensible and is exactly what A4 surfaces for the user.
**Proceed with the cap as the default and A4 flagged** — this is a "named risk accepted," not a
blocker. One refinement worth a line in the ticket: 1600px is a slightly arbitrary number; tie it
to the math (5 cols x ~300px + gaps + padding ~= 1600) so a later reader knows it's the 5-column
ceiling, not a guess.

### [NIT] Click-to-expand guard is sound; two edges to nail in the AC

The `e.target.closest('a, button')` + non-empty-selection guard (Fork 1) is the right approach and
correctly handles the two named cases. Verified against current code: Delete is a **delegated
`document` click handler** (`dashboard.html:130-135`) that matches `.btn.del` via its own
`closest`. The card-toggle listener is proposed on the **card grid**, a descendant of `document`,
so on a Delete click both fire — but the toggle handler's `closest('a,button')` returns the
`<button>` and bails early, so it won't toggle; and the two listeners are independent (no
`stopPropagation` needed, and the plan correctly doesn't add one that would break the delegated
delete). Two things to pin in the AC, not blockers:

- **Keyboard a11y parity:** the plan adds `role="button"`/`tabindex=0`/Enter-Space on the card.
  The Enter/Space keydown handler must apply the **same** `closest('a,button')` guard, or focusing
  the inner Open link and pressing Enter could both navigate and toggle. State it.
- **Open `<a>` navigation:** clicking Open both navigates (link default) and would bubble to the
  card grid; the guard bails on the `<a>`, so no toggle — correct. Just make the verification
  actually click Open (it does, step 5) rather than only asserting the href.

### [NIT] Preserve-functionality verification is genuinely exercised and safely scoped

Confirmed the plan does more than assert layout: step 5 clicks Open (navigates to
`/review/{id}`, viewer 200 verified against route `app.py:453-459`), clicks Delete against a
**throwaway `DEL_ID`** created in the throwaway :8138 container (then asserts it's gone from
`/api/reviews`), bumps a revision via `PUT /source` to prove the `v{n}` badge, and checks the
notes-count label. The delete-safety rail is explicit and correct (throwaway review, throwaway
container, never live :8139). This is the right shape. Minor: steps 4c/4e and the
expanded/filtered/group-collapsed shots are "captured manually in a real browser" — that's an
honest limitation of headless for click-driven states, but it means those three shots are
**unverifiable by the smoke** and rest on the implementer's diligence; call them out in the AC as
required-artifacts so G7 can check they exist, rather than trusting they were taken.

### [NIT] One ticket is the right default; the "5-6 lines = upper bound" reading is correct

One `ui` ticket (MR-031) is justified: a single-file `<style>`+`<script>` rewrite where any split
serializes on the same file with no independently shippable artifact. The 2-ticket fallback is a
sensible escape hatch and the cut line (layout/collapse | search/groups/chip) is the right seam if
the single ticket runs long. The render-smoke selectors are correctly **flat/standalone**
(`.grid` `.card` `#search` `.group-header`) — verified the matcher rejects descendant selectors at
exit 2 (`render-smoke.sh:72-77`), so footgun 11 is genuinely satisfied, not just asserted. The
"5-6 lines is an upper bound, not a floor" reading is right and the plan guards the inverse misread
explicitly; the ~60px measured collapsed height is consistent with title + one meta row.

## Resolution log

Author resolutions applied to `epics/dashboard-redesign-plan.md`, 2026-06-19 (see the plan's own
"Resolution log" for full text):

- **SHOULD — Verification 4d `--force-dark-mode`.** Fixed. Dark/light pane capture now uses
  `--blink-settings=preferredColorScheme=0` (dark) / `=1` (light); `--force-dark-mode` removed;
  same flag named in Fork 5's dark-pane `getComputedStyle` check and the Key-constraints theme
  bullet. Precedent `theme-awareness-plan-review-2026-06-18.md` cited inline.
- **NIT — A3 notes-count ruling.** Accepted as CORRECT; no design change. Expanded-card notes label
  is the existing `noteLabel()` string; AC will not treat the redundant restatement as a hard
  must-have.
- **NIT — A4 1600px cap.** Accepted as CORRECT; cap kept as default with A4 flagged. Tied `1600px`
  to the 5-column math (5×280 + 4×10 + 2×24 ≈ 1488; 6th needs ≈1778) in Fork 2, A4, and the risk row.
- **NIT — keyboard a11y guard parity.** Actioned. Fork 1 now requires the Enter/Space keydown
  handler to apply the same `closest('a, button')` + selection guard as the click handler; risk row
  added; AC carries it.
- **NIT — Open `<a>` clicked not just asserted.** Accepted; no change — Verification step 5 already
  clicks Open in the browser, as the review confirms.
- **NIT — manually-captured screenshots unverifiable by smoke.** Actioned. All eight screenshots are
  now required evidence artifacts in the ticket AC, and G7 checks each file exists under `$EV`; a
  missing required artifact fails the close review.
- **NIT — one-ticket default + "5–6 lines = upper bound."** Accepted; no change — confirmed correct
  by the review; 2-ticket fallback and floor-misread guard already in the plan.

Ticket count unchanged: one `ui` ticket, **MR-031**.
