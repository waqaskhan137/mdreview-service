---
review_of: epics/render-fidelity-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS-WITH-CONDITIONS
status: resolved
---

# G1 independent review — render-fidelity plan (footnotes + syntax highlighting)

**Verdict: PASS-WITH-CONDITIONS.** The load-bearing risk — that the three JS deps load as
browser `<script>` globals and compose with the vendored `window.marked` v18.0.4 — is **resolved
by reproduction, not opinion: it works.** All three attach usable globals, `marked.use(...)`
composes them, `marked.parse` returns a **string** (the sync call at `viewer.html:270` holds),
footnotes emit `<section class="footnotes" data-footnotes>` + `<sup>` refs, highlight.js emits
`.hljs-keyword` tokens, and mermaid stays raw. No BLOCKER. Three SHOULDs must land in the tickets
before they're cut (the verification URL is wrong everywhere, the highlight snippet as literally
written throws, and the emitted `sr-only` footnote heading has no CSS in this viewer). Fix those
in the ticket AC and G1 passes.

## Reproduction (what I actually ran)

Packed the exact pinned versions (`npm pack marked-footnote@1.4.0 marked-highlight@2.1.4
@highlightjs/cdn-assets@11`), staged them next to the **real vendored
`static/marked.min.js` (v18.0.4)**, served over HTTP, and dumped the rendered DOM from headless
Chrome (`/Applications/Google Chrome.app/...`) — i.e. the viewer's exact `<script src>` + global
path, not node `require`. Result (verbatim):

```
typeof window.markedFootnote                    function
typeof window.markedHighlight (obj)             object
typeof window.markedHighlight.markedHighlight   function
typeof window.hljs                              object
bare markedHighlight callable?                  false      <-- see SHOULD-2
typeof parse return                             string     <-- sync call holds
parse is Promise                                false
has <sup> ref                                   true
has data-footnotes                              true
footnotes container tag   <section class="footnotes" data-footnotes>
has hljs-keyword                                true
mermaid raw language-mermaid                    true
footnote markup slice  ...<section class="footnotes" data-footnotes>
                       <h2 id="footnote-label" class="sr-only">Footnotes</h2><ol><li id="footnote-a">...
```

This settles scrutiny points 1, 3, and the markup half of 4. The browser-global gap that broke
the math feature last epic **does not recur here** — both adapters ship real UMD builds
(`marked-footnote/dist/index.umd.js` attaches `window.markedFootnote` directly;
`marked-highlight/lib/index.umd.js` attaches `window.markedHighlight` as a namespace object whose
`.markedHighlight` is the factory), and `@highlightjs/cdn-assets@11.11.1/highlight.min.js` is the
**common** build (`var hljs=...`, 34 grammars incl. python/js/bash/json/yaml/go/rust/java/sql;
`mermaid` correctly absent), 127 KB on disk.

## Findings

### [SHOULD] 1 — Every verification command targets the wrong URL (`/r/{id}` → 404)

The route is `/review/{id}` (`app.py:453`, `re.fullmatch(r"/review/" + RID, path)`); there is **no
`/r/{id}` route** — an unmatched path falls through to the `404 {"error":"no route"}` at
`app.py:470`. The plan's Verification section uses `"$BASE/r/$ID"` in **every** render-smoke and
in the Chrome screenshot command (the "Render-smoke", "Both-pane screenshot", and "Default-safe
regression" blocks). As written, G4/G7 would smoke a 404 page: `render-smoke.sh` would report all
selectors missing and the screenshot would be the not-found text — a false BLOCK on a feature
that's actually fine, or worse, masked by someone "fixing" the URL ad hoc without updating the
plan. Fix: replace `/r/$ID` → `/review/$ID` throughout Verification before MR-028/029 inherit it.
(The CLAUDE.md contract and `review_url` in `app.py:317` both use `/review/`, so this is a plan
typo, not a route question.)

### [SHOULD] 2 — The recommended highlight snippet as literally written throws

Step 3's literal code is `marked.use(markedHighlight({ langPrefix:'hljs language-', ... }))`. The
UMD wrapper is `factory(global.markedHighlight = {})` with `exports.markedHighlight = markedHighlight`
— so `window.markedHighlight` is an **object**, and bare `markedHighlight(...)` is
`{}( ... )` → **TypeError: markedHighlight is not a function** (reproduced: "bare markedHighlight
callable? false"). The plan's parenthetical ("global is `markedHighlight.markedHighlight` —
destructure or reference accordingly") is correct and the `window.markedHighlight && window.hljs`
guard means a missing asset degrades safely — but the *guard passes and then the call throws*,
which is exactly the not-default-safe failure footgun 8 is meant to prevent. Pin the real call in
the ticket AC: `const mh = window.markedHighlight.markedHighlight; marked.use(mh({...}))` (or
`const { markedHighlight: mh } = window.markedHighlight;`). Don't leave it as "reference
accordingly" — that's the one line most likely to be copied verbatim.

### [SHOULD] 3 — `marked-footnote` emits a `class="sr-only"` heading the viewer has no CSS for

The emitted section leads with `<h2 id="footnote-label" class="sr-only">Footnotes</h2>`.
`viewer.html` has **no `.sr-only` rule** (grep: zero hits). Without one, a full-size "Footnotes"
`<h2>` renders visibly above the list — and via the article `#article h2` rule
(`viewer.html:20`: uppercase, accent-colored) it'll render as a styled "FOOTNOTES" banner, not the
intended visually-hidden label. Step 4 commits to footnotes CSS (a muted `<hr>` + ordered list)
but never mentions `.sr-only`. Add the standard clip rule to the footnotes CSS in MR-028's AC, or
the feature ships a stray heading. (Minor knock-on: that `<h2>` is *inside* the footnotes
`<section>`, so it does not perturb `numberBlocks` heading tracking — the section is one top-level
`.blk` child and the nested h2 is never iterated, so A4 holds. The only issue is its visibility.)

### [SHOULD] 4 — `marked-highlight@2.1.4` declares `peerDependencies: marked ">=4 <15"`; vendored marked is v18

From its `package.json`. The probe shows v18 works **today** despite the declared ceiling, so this
is not a blocker — but "outside the supported range and works in my probe" is a latent risk, not a
guarantee: a future `marked.min.js` bump could land on an API the adapter assumed gone, with no
peer-range warning because nothing runs `npm install`. `marked-footnote@1.4.0` is clean
(`marked ">=7.0.0"`, open-ended). Record this explicitly in MR-029 as an accepted, verified-by-reproduction
deviation, with the trigger "re-run the headless compose probe on any `marked.min.js` upgrade."
The probe I ran is the canonical check; cite it.

### [NIT] 5 — Bundle/grammar numbers are slightly off (harmless)

`highlight.min.js` is **127 KB** on disk, not ~119 KB (min size; the plan's table says ~119 KB and
the byte-count assert in Verification expects "~119000" — make it `> 100000` so a correct asset
doesn't read as suspicious). Common build is **34** registered grammars, not 36 (alias counting);
the language coverage claim is otherwise accurate. No action needed beyond loosening the wc-c
expectation comment.

## Assessment of the plan's own measurements

- **M2/M3 (sync return, coexistence, mermaid skip):** confirmed in-browser, not just node. The
  string-return claim — the single thing that must hold for `viewer.html:270` — holds with all
  three extensions registered. Good.
- **M4 (dual-scheme theme):** sane by inspection. Pane dark bg is `--bg:#111` + `#article pre`
  overlay `rgba(127,127,127,.1)` ≈ `#1f1f1f`; github-dark tokens (`#ff7b72` kw, `#79c0ff`
  literals, `#a5d6ff` strings, `#8b949e` comments) are authored for `#0d1117` and stay high-contrast
  on a slightly lighter mat; the weakest is the grey comment, still legible. Stripping `.hljs{background}`
  to let the pane mat show through is the right call. The both-pane screenshot is already a G7
  requirement — keep it; it's the real proof.
- **Footnote markup selectors (point 4):** both `.footnotes` **and** `[data-footnotes]` are
  emitted, so the plan's `.footnotes` flat selector is valid and not assumed. Good.

## Items judged fine, not flagged

- **History modal (`viewer.html:489`) gets both for free** via the global `marked.use` — correct,
  and the cosmetic id-duplication (A5) is genuinely cosmetic (transient overlay, same-page
  anchors). Don't gate it.
- **Footnotes-as-numbered-`.blk` (A4)** — reasonable and consistent; no special-casing needed.
- **No `app.py`/`Dockerfile` change** — verified: `/static/` route (`app.py:461`) + `_ctype_for`
  (`.js`→`text/javascript`, `.css`→`text/css`) + `COPY static/` already cover four new `static/`
  files. Footgun 9 genuinely satisfied.
- **Ticket sizing** (MR-028 footnotes / MR-029 highlighting / MR-030 docs): right granularity.
  MR-028 is the smaller, lower-risk slice; MR-029 carries the 127 KB payload + theme. Sequential
  ordering (both edit `setupMarked()` + `<head>`) is correctly justified as merge-conflict
  avoidance, not a real dependency. Folding MR-030 into MR-029's docs requirement is fine under the
  same-sprint docs-sweep rule; if kept separate, it is **not** carry-over-eligible (G7) — call that
  out in the sprint so deferred docs don't cross sprint-08's boundary.

## Conditions for PASS (all addressable in ticket AC, no re-plan)

1. Replace `/r/$ID` → `/review/$ID` in every Verification command (SHOULD-1).
2. Pin the real highlight call (`window.markedHighlight.markedHighlight`) in MR-029 AC (SHOULD-2).
3. Add a `.sr-only` clip rule to the footnotes CSS in MR-028 AC (SHOULD-3).
4. Record the `marked-highlight <15` peer-range deviation + re-probe trigger in MR-029 (SHOULD-4).

None require redesign; the architecture is sound and reproduced end-to-end.

## Resolution log

**2026-06-18 — author revision** (by `mdreview-planner`, plan stays author-owned for G1
independence). All four SHOULDs and the NIT applied to `epics/render-fidelity-plan.md`; ticket count
unchanged (MR-028/MR-029/MR-030). See the plan's "Review resolutions" section for the full entry.

- **SHOULD-1 — resolved.** `/r/$ID` → `/review/$ID` in every Verification command (seed echo, 3
  render-smoke blocks, Chrome screenshot, default-safe regression). Grep-confirmed no `/r/` remains.
- **SHOULD-2 — resolved.** Step 3 (`setupMarked()`) now pins the three global shapes and gives a
  verbatim snippet whose `window.*` guard wraps the actual call
  (`const mh = window.markedHighlight && window.markedHighlight.markedHighlight; if (mh && window.hljs) marked.use(mh({…}))`).
  Mirrored into MR-029 AC. No bare `markedHighlight(...)` anywhere.
- **SHOULD-3 — resolved.** Step 4 adds the standard `.sr-only` clip rule to the viewer `<style>`;
  added to MR-028's CSS scope + AC (label hidden visually, present for screen readers).
- **SHOULD-4 — resolved.** New Risks row + MR-029 scope/Work-log note record the
  `marked-highlight@2.1.4` `<15` peer-range deviation as verified-but-out-of-range, with the
  re-probe-on-marked-bump trigger.
- **NIT — actioned.** Bundle table/prose corrected to ~127 KB / ~136 KB total and ~34 grammars; the
  Verification non-empty assert loosened to a `> 100000` floor.

Verdict and frontmatter unchanged (orchestrator flips the plan's G1 gate post-re-review).
