---
review_of: sprints/sprint-21.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-24
verdict: PASS
status: resolved
---

# Sprint-21 G7 close review — MR-061 (animated working-state turn banner)

Independent staff-critic close review of sprint-21 (epic `working-banner-animation`,
single ticket MR-061). I did not implement this. I verified the shipped change against
the ticket ACs by reading `viewer.html` and the merge diff, and I **independently
re-ran the render-smoke from a freshly rebuilt throwaway image** (scratch port 8767,
disposable container `mr061critic`, image `mdreview-mr061-critic`) — not a file diff,
not the implementer's container.

## Verdict: PASS

The change is exactly the three edits the ticket specifies, scoped to `viewer.html`,
and every AC is satisfied by my own re-run (positive smoke, negative smoke, both CDP
probe arms). No blocking findings; no nits worth holding the gate.

## What I verified

### Code correctness (read `viewer.html` + isolated the feature commit `36263dd`)
The feature commit is `viewer.html` only, **8 insertions / 1 deletion**, matching the
work log. The three edits:

- **CSS (`viewer.html:87-89`).** `#turnbanner.working #turntext::after{content:"…";
  color:var(--muted);animation:turnworking 1.25s ease-in-out infinite;}` +
  `@keyframes turnworking{0%,100%{opacity:.3}50%{opacity:1}}` +
  `@media (prefers-reduced-motion:reduce){...animation:none;opacity:1}`. Colour is the
  theme var `--muted` (not a hex); loop ~1.25s; reduced-motion off-switch present. ✓
- **`remove('working')` at top of `renderBanner` (`viewer.html:237`)**, immediately
  after `if(!bar)return;`. Guarantees no stale class survives a re-render. ✓
- **`add('working')` ONLY in the genuine working arm (`viewer.html:242`)**, the `else`
  branch of the freshness check (`turn==='agent'` AND `as` present AND lease fresh).
  NOT in the `!as` "waiting to pick up" arm, NOT in the `>STALE_S` "may have stopped"
  arm, NOT in the reviewer `else` (your-turn / done / blocked). The literal trailing
  "…" was dropped from that one message so `::after` is the sole ellipsis (no "……"). ✓

### Scope / regression
`app.py`, `Dockerfile`, `mcp_server.py`, `requirements.txt`, `meta.json` — **none
touched** by the feature commit or the merge (`git show` confirmed empty for those
paths). The merge `e668ed0` brought in only `viewer.html` + the MR-061 ticket doc. The
other five banner states are byte-for-byte unchanged in the diff. Live (8139) and
compose (8137) containers are untouched — I tested a rebuilt throwaway only, and the
live `mdreview` container on 8139 is still serving (app.py byte-unchanged → same image).

### Independent render-smoke (rebuilt image, scratch port 8767)
I rebuilt the image from the current `dev` tree, confirmed the **baked** `viewer.html`
contains `turnworking` (proves the rebuild carries the edit, not a stale layer), forced
the working state via `POST /handoff {to:agent}` then
`POST /handoff {state:working,owner:critic-owner}`, and ran:

| Check | My result |
|---|---|
| Baked `viewer.html` contains `turnworking` | PASS (2 matches) |
| `/healthz` → `{"ok": true}` | PASS |
| Working render: `#turnbanner` / `#turntext` / `.working` present | PASS (1/1/1, exit 0) |
| Negative: after `{to:reviewer,by:reviewer}` reclaim, `.working` ABSENT | PASS (0 nodes, exit 1) |
| `#turntext` textContent = `"Agent is working on your feedback"` (no literal "…") | PASS |
| Default `animationName` (CDP, no emulation) | `turnworking` |
| `::after` content default | `"…"` |
| `prefers-reduced-motion: reduce` → `animationName` | `none` |
| `::after` content under reduce (static ellipsis retained) | `"…"` |
| `#turnbanner.working` still present under reduce (off-switch, not state change) | 1 |

The negative smoke is the load-bearing one: it proves the class is scoped to the
working arm AND that the top-of-function `remove` clears it when the turn flips back —
i.e. no stale-class regression.

### Evidence compliance
`reviews/sprint-21-render-evidence-2026-06-24/` exists with `SMOKE.md` +
`banner-light.png` + `banner-dark.png` (real 1100x800 PNGs). I opened `banner-dark.png`:
it shows the working banner "Agent is working on your feedback…" with the ellipsis
legible on the dark pane, in the genuine working state. The evidence matches my
independent re-run. A product-page change owes render evidence; it is present and real.

## Findings

_None blocking._

- **(worth-considering)** The `STALE_S=180` JS constant comments that it MIRRORS
  `app.py LEASE_TTL_S` as a "single source of truth … move together". MR-061 doesn't
  touch either, so this is not a sprint-21 defect — flagging only because a future
  banner change in this function should keep that mirror in mind. No action for G7.
- **(nit)** `SMOKE.md` and the ticket validation note both say "8766"; I used 8767 per
  the task. Cosmetic; the recipe is identical and reproducible on any scratch port.

## Resolution log

- 2026-06-24 — Independent G7 review opened. Read `viewer.html` (CSS ~:84-89,
  `renderBanner` :232-255) and isolated feature commit `36263dd` (viewer.html only,
  8+/1-). Rebuilt throwaway image `mdreview-mr061-critic`, ran disposable container
  `mr061critic` on scratch port 8767. Re-ran positive render-smoke (exit 0, `.working`
  present), negative render-smoke (exit 1, `.working` absent after reclaim), and a CDP
  reduced-motion probe (default `animationName=turnworking`, reduce → `none`, `::after`
  content `"…"` retained both ways). All ACs met. Verified scope (no app.py/Dockerfile/
  MCP/meta change) and evidence dir (real PNGs, on-state). Torn down container + image;
  `.scratch/` contents cleaned; live 8139 / compose 8137 untouched. **Verdict: PASS.**

## Resolution log

- 2026-06-24 — Independent G7 review (1-ticket ui sprint). Verdict PASS, no blockers. The critic
  independently rebuilt a throwaway image and re-ran the render-smoke: `#turnbanner`/`#turntext`/
  `.working` present in the working state (exit 0); `.working` ABSENT after a reclaim (exit 1 — proves
  the working-only scope + the top-of-function remove clears it, no stale-class regression); CDP
  reduced-motion probe `animationName` = `none` under reduce, `turnworking` without. Scope clean
  (viewer.html only). Two no-change notes (STALE_S mirror for future banner edits; port cosmetic).
  Review status: resolved; sprint-21 closed at G7; the working-banner-animation epic marked done.
