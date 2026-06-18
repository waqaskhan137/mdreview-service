---
review_of: sprints/sprint-07.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS
status: resolved
---

# G7 sprint-close review — sprint-07 (theme-awareness / MR-027), independent

The shipped change is a single, correctly-scoped CSS rule plus a 3-line CLAUDE.md note. I
rebuilt the container from the `Dockerfile`, ran `/healthz` + `/api/reviews`, drove
`render-smoke.sh`, and captured my own light/dark screenshots from a throwaway on :8141 — the
mat renders, is image-only, and the documented non-goal shows exactly as claimed. The committed
evidence reproduces; no service/route/MCP change is attributable to MR-027. **PASS.**

## MR-027 acceptance-criteria check (reproduced, not trusted)

| AC | Status | Evidence |
|----|--------|----------|
| **The mat** — `#article img, .histdoc img` gets `background:#fafaf9` + `padding:8px` + `border-radius:8px`, keeps `max-width:100%`, extends the old rule | **MET** | `viewer.html:36`; the prior `#article img{max-width:100%}` is gone, replaced in place |
| **Image-only scope (no regression)** — selector matches only `<img>`; never `.mermaid svg`/`.katex`; forbidding comment present | **MET** | `viewer.html:29-36` (comment) + `:36` (rule). In my dark/light shots Mermaid keeps its JS theme (dark-bordered / lavender) with NO mat |
| **History modal covered** — `.histdoc img` gets the same mat | **MET (by CSS semantics + render-path)** | Same declaration block as `#article img` (`:36`); `showRound()` writes `marked.parse(source)` into `.histdoc` (`:485-491`). See finding [SHOULD-1] on the missing modal screenshot |
| **No `color-scheme`** added to `:root`/`html`/`body`/`<meta>` | **MET** | grep: only pre-existing `@media (prefers-color-scheme)` (`:10`) + `matchMedia` (`:161`); no `<meta name="color-scheme">` |
| **No service/DOM change** — `app.py`/routes/storage/`meta.json`/`mcp_server.py` untouched; no JS image-wrapping | **MET** | MR-027 impl commit `f541bbf` touches only `viewer.html` (9 lines), `CLAUDE.md` (3), ticket, TRACKER, evidence. `python3 -m py_compile app.py` OK |
| **Default-safe** — no-`<img>` doc unchanged | **MET** | `review-noimg-dark.png` (clean prose render, rule matched nothing); rule is `img`-only |
| **Gating render evidence (both panes)** — render-smoke all ok; light AND dark shots showing fix + non-goal + Mermaid | **MET** | Committed `render-smoke.txt` (img 3 / #article 1 / .mermaid 1); `review-theme-dark.png` + `review-theme-light.png` differ in pane theme and show A/B legible on mat (fix), C washed out (non-goal), Mermaid themed. Reproduced independently on :8141 — matches |
| **Docs note inside ticket** | **MET** | `CLAUDE.md` 3-line note; no separate docs-sweep ticket |
| **Local validation** (py_compile / docker build / smoke + shots) | **MET** | Reproduced: py_compile OK, `docker build` OK, container `/healthz` OK, smoke ran |

## Findings

### [SHOULD-1] The `.histdoc img` arm has no screenshot; the round-2 G1 review asked for one "if cheap"
`docs/process/tickets/MR-027-image-theme-mat.md:34` and the plan accept the history-modal arm on
*inspection + rule presence* only, and the round-2 G1 review left a residual note that a manually-
opened-modal shot "should ideally" be included at G7 if cheap
(`theme-awareness-plan-review-2026-06-18-r2.md:70`). It was not produced. I reproduced the arm via
CDP (created a history round with `PUT /source`, opened the modal) but the headless-command target
would not execute page JS in scope, so I could not capture the modal shot either.

This is **not a blocker**, and I am confident the arm works: the mat is a *single declaration block*
shared by both selectors (`viewer.html:36`) — if `#article img` is matted (screenshot-proven), then
`.histdoc img` is matted by CSS semantics, the only question being whether a `.histdoc img` node ever
exists, which `showRound()` (`viewer.html:485-491`, `marked.parse(source)` into `.histdoc`)
guarantees for any historical draft containing an image. The evidence is genuinely weaker than the
`#article` arm but the residual risk is cosmetic (a mat behind a history-modal image) and the path is
short and inspected. Acceptable to close on; worth a one-line modal shot next time the modal is open
for any reason.

### [NIT] The sprint board's stat-check premise is stale, not wrong
The G7 instruction to confirm `git diff main...dev --stat` shows "only `viewer.html` + `CLAUDE.md`
(+ process files)" does **not** hold as written: that diff also carries all of sprint-06
(rich-rendering — `app.py` +132, `mcp_server.py`, `static/` KaTeX, MR-022–026), because local `main`
is behind and sprint-06 (PR #5) sits on `dev` ahead of it. The correct scope check is the MR-027
implementation commit `f541bbf`, which **is** clean (only `viewer.html`/`CLAUDE.md` + ticket/TRACKER/
evidence). No stray app/service change is attributable to this sprint. Flagging so the close note
records *why* the stat is noisy, and so the PR for sprint-07 is understood to also land sprint-06's
already-reviewed work onto this `main` — not a defect, but the merge should be intentional.

### [NIT] `viewer.html:33` mentions `color-scheme` inside the explanatory comment
The forbidding comment uses the word `color-scheme` ("the pane's color-scheme can't reach an
`<img>`-loaded SVG"). This is correct and intentional prose, not a CSS declaration — noted only so a
future grep for the property doesn't mistake it for a re-introduction. No action.

## What's sound (load-bearing)
- The mat mechanism is real and theme-correct, reproduced independently on a rebuilt :8141 container:
  light-authored A and dark-stroke-on-transparent B are legible on the white mat on a dark pane (the
  fix); white-on-transparent C is washed out (the named non-goal); Mermaid keeps its per-pane JS theme
  with no mat (no regression); the no-image doc is unchanged.
- The non-goal is honestly carried in the ticket, plan (Non-goals, Risks, design-fork 238→5), and the
  CLAUDE.md note, and is *shown* on the dark screenshot for sign-off rather than hidden.
- Blast radius is one HTML file + a docs line; gutter notes route through `esc()` (`viewer.html:439-440`)
  so they can never emit a matted `<img>` — scoping holds.

## Recommendation
Close sprint-07. Set `sprints/sprint-07.md` `close_review:` to this file and flip `status: closed`;
record the `.histdoc` modal-shot gap (SHOULD-1) as the one carry-note. No blocker.

## Resolution log

- **2026-06-18 — SHOULD-1 (no `.histdoc` history-modal screenshot): accepted, carried as a note.**
  The mat is a single shared declaration block (`#article img, .histdoc img{…}`); `#article img` is
  screenshot-proven matted, so `.histdoc img` is matted by CSS semantics, and `showRound()`
  (`viewer.html:~485`) guarantees the modal node exists. A headless click-through to open the modal
  is beyond the render-smoke harness (the critic's own CDP attempt couldn't run page JS in scope);
  building that harness for a cosmetic arm is disproportionate. Residual risk is cosmetic only.
  **Carry-note:** add a one-line manually-opened-history-modal screenshot if/when a future cycle
  touches `.histdoc`.
- **2026-06-18 — NIT-1 (stale `git diff main...dev` scope): informational, no action.** The local
  `main` ref was behind `origin/main`; `origin/main` already carries sprint-06 (PR #5 merged), so the
  theme-awareness PR diffs only the post-PR-#5 work. The MR-027 impl commit `f541bbf` is clean
  (`viewer.html` + `CLAUDE.md` only). No stray app/service change.
- **2026-06-18 — NIT-2 (`color-scheme` word in the comment): informational, no action.** It is
  explanatory prose, not a CSS declaration.
- **2026-06-18 — Verdict PASS, 0 blockers. Sprint-07 closed at G7.**
