---
review_of: sprints/sprint-08.md
gate: G7
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS-WITH-CONDITIONS
status: resolved
---

# G7 sprint-close review — sprint-08 (render-fidelity)

**Verdict: PASS-WITH-CONDITIONS.** Both features ship and are reproduced end-to-end in a freshly
built throwaway container (:8141): footnotes, syntax highlighting, mermaid-skip, sync `marked.parse`,
default-safe degradation, and no regression to math/mermaid/tables/block-numbering all verified from
the served viewer, not the Work log. The vendored JS is genuine pinned upstream. **One real defect:**
the hand-curated `hljs-github.css` has a botched base-rule strip (`pre codecode/*!…*/`) that silently
kills the `.hljs-doctag` token color in **both** themes — black-on-dark on the dark pane, reachable in
common languages (JS/Java JSDoc, Python docstring tags). Narrow, but it contradicts the AC's "legible
on each pane" and the docs' "reads on light and dark panes." Fix the one selector and the sprint
closes clean; the feature is otherwise sound.

## Reproduction

`docker build -t mdreview-rf2 .` + `docker run … -p 8141:8080` (throwaway, never compose/:8139).
`py_compile app.py` OK; `docker build` OK; `/healthz`→`{"ok":true}`; `/api/reviews`→sane JSON.
Fixture exercised every path (footnote + reuse, inline math, currency, python fence, JS-JSDoc fence,
mermaid, GFM table). DOM dumped via headless Chrome `--dump-dom`; token colors measured via
`getComputedStyle` light (`preferredColorScheme=1`) and dark (`=0`); `scripts/render-smoke.sh` run
with flat selectors. Container torn down (`docker rm -f g7rf`).

## Per-ticket AC check

### MR-028 — footnotes — **MET**

- Vendored `static/marked-footnote.umd.js` (2982 B, genuine UMD, `window.markedFootnote` factory) —
  committed, scripted after `marked.min.js` (`viewer.html:155`). **Met.**
- Registered default-safe in `setupMarked()` via `var mf=window.markedFootnote; if(typeof mf==='function') marked.use(mf());`
  (`viewer.html:225-226`), `_markedReady`-guarded, called once in `boot()`. **Met.**
- `.sr-only` clip rule added (`viewer.html:41`); served DOM has `<h2 … class="sr-only">` present but
  visually hidden — no "FOOTNOTES" banner (screenshot + DOM confirm). **Met.**
- `.footnotes` styling using `--rule`/`--muted` (`viewer.html:42-44`). **Met.**
- Section numbered as a `.blk` (A4) — renders as block 6 in both PNGs. **Met.**
- No regression / sync parse: served DOM shows `<sup>`×3, `data-footnotes`×1, 2 back-ref `↩`/`↩²`,
  `$E=mc^2$` as `.katex`, `$5 and $10` literal, no raw `[^a]` leak, article renders (so parse is sync).
  **Met.**
- Gating render evidence: `render-smoke.sh … 'sup' '.footnotes' '#article'` → all ok; MIME
  `marked-footnote.umd.js`=`text/javascript`. **Met (reproduced).**

### MR-029 — syntax highlighting — **MET with one defect (SHOULD-1)**

- Vendored 4 files: `highlight.min.js` (v11.11.1 common, 127496 B, `var hljs`, python/js/bash/json/
  yaml/go/rust/java/sql present, **mermaid grammar absent**), `marked-highlight.umd.js` (3131 B,
  namespace UMD), `hljs-github.css` (2837 B). **Met.**
- Registered with the exact namespace-factory shape `window.markedHighlight.markedHighlight`, guard on
  resolved factory **and** `window.hljs`, sync callback, mermaid→raw (`viewer.html:231-240`). Served
  DOM: `.hljs-keyword`×2, `.hljs-string`×3, `.hljs-comment`×1; `marked.parse` stays sync (article
  renders). **Met.**
- Mermaid not regressed: served DOM has `language-mermaid` raw + an `<svg>`/`.mermaid` diagram with no
  `.hljs-*` tokens inside it. **Met.**
- Dual-scheme theme, `.hljs` base background stripped so the pane mat shows through (no white box):
  dark PNG + computed colors confirm kw/str/comment/number legible on the dark pre, no box. **Met for
  these tokens — but see SHOULD-1: `.hljs-doctag` is broken in both themes.**
- Peer-dep deviation recorded (MR-029 Work log + AC): `marked-highlight@2.1.4` peer `marked ">=4 <15"`
  vs vendored v18.0.4, verified-but-out-of-range, re-probe-on-`marked.min.js`-bump trigger. **Met.**
- Gating render evidence: `render-smoke.sh … 'pre' '.hljs' '.hljs-keyword'` → all ok; `'.katex'
  '.mermaid' 'table'` → all ok; MIME `highlight.min.js`/`marked-highlight.umd.js`=`text/javascript`,
  `hljs-github.css`=`text/css`; body 127496 B (`>100000`); both-pane PNGs present and correct.
  **Met (reproduced).**

### MR-030 — docs — **MET (one downstream inaccuracy, see SHOULD-1)**

- README / CLAUDE / AGENTS updated with footnotes + syntax-highlighting + dual-scheme note alongside
  math/Mermaid; no API-table duplication. **Met.**
- No overclaim on the common-build/best-effort-auto-detect caveat and cosmetic id-dup (CLAUDE.md
  "Rich content" bullet). **Met.** Caveat: README:15 "reads on light and dark panes" is true for every
  token *except* `.hljs-doctag` — that's a consequence of the CSS defect, not an independent doc error;
  it resolves when SHOULD-1 is fixed.

## Findings

### [SHOULD] 1 — `hljs-github.css` botched base-rule strip kills `.hljs-doctag` color in both themes
`static/hljs-github.css:5` and `:15` each begin `pre codecode/*!  Theme: … */.hljs-doctag,…`. The
upstream `pre code{…}` base rule was deleted but left the dangling text `pre codecode` glued (across
the license comment, which CSS treats as whitespace) onto the first token selector. The first
comma-group's leading selector parses as the never-matching `pre codecode.hljs-doctag`; the rest of
the comma-list (`.hljs-keyword`, `.hljs-type`, …) still applies, which is why everything *looks* fine
in the PNGs. Measured `getComputedStyle().color` on a `.hljs-doctag` span: **`rgb(0,0,0)` in both
light and dark** (every other token correct: light kw `rgb(215,58,73)`, dark kw `rgb(255,123,114)`,
etc.). On the dark pane that is black text on the `#1f1f1f` pre mat — effectively invisible. Reachable
in common languages: a JS `/** @param … */` fence emits `hljs-doctag` (reproduced, count 1); same for
Javadoc and Python docstring tags. Fix: delete the stray `pre codecode` on both lines so each block
starts at `.hljs-doctag,`. One-character-class blast radius, but a real legibility regression on the
theme this epic exists to get right. Re-screenshot a JSDoc fence on the dark pane after the fix.

### [NIT] 2 — `marked.parse` sync-with-all-three was asserted but its only true guard is "the article rendered"
The viewer calls `marked.parse(md)` synchronously; if any extension registered async, the article
would silently fail. The served container renders the full article (footnotes + highlight + math),
which is the real proof and it holds — noting only that there's no standalone assertion, so a future
async regression would surface as a blank article, not a clear error. No action this sprint.

### [NIT] 3 — `section.footnotes` is a commentable `.blk` (A4 default)
Confirmed intentional and consistent (block 6 in both PNGs). The MR-028 follow-up to exclude it is
correctly left as optional. No action.

## What's good
The browser-global wiring — the exact risk that broke a prior epic — is correct and reproduced:
`window.markedFootnote` (factory) and `window.markedHighlight.markedHighlight` (namespace factory)
both compose with global `marked` v18, `marked.parse` stays a string, mermaid stays a diagram, and
default-safe guards degrade cleanly (plain doc: 0 `.hljs`, 0 footnotes, article still renders). The
vendored JS is genuine pinned upstream; only the one hand-edited CSS file regressed. Diff scope is
exactly `viewer.html` + 4 `static/` files + 3 docs — no `app.py`/`Dockerfile` drift. Commit trailers
and ticket IDs present on all three feature commits.

## Should the sprint close?
Close after SHOULD-1 (one-line CSS fix + a dark-pane JSDoc re-shot). The defect is narrow and the
rest of the epic is reproduced-clean, so a maintainer may also elect to close now and carry SHOULD-1
as a fast-follow — but since the dark-pane invisibility contradicts the epic's headline claim, fixing
it before close is the honest call. No BLOCKER; do not re-plan.

## Resolution log

- **2026-06-18 — SHOULD-1 (orphaned `pre codecode` → `.hljs-doctag` invisible on dark): FIXED.**
  Regenerated `static/hljs-github.css` removing the **full** upstream base-rule selectors
  (`[…]\.hljs\{…\}`, i.e. `pre code.hljs{}` / `code.hljs{}` / `.hljs{}`), not just the `.hljs{…}`
  fragment. Verified in the rebuilt container: served CSS sets `.hljs-doctag` `color:#d73a49` (light)
  / `#ff7b72` (dark); a JSDoc `/** @param */` fence renders `@param` red + legible on the dark pane
  (`review-doctag-dark.png`); render-smoke still green. Commit "fix(ui): hljs theme — remove full
  .hljs base-rule selectors (MR-029, G7 SHOULD-1)".
- **2026-06-18 — NIT 2 (no standalone sync-parse assertion): accepted, no action.** The real guard
  ("the full article renders") holds and is render-smoked; a future async regression would surface as
  a blank article. Noted, not gated.
- **2026-06-18 — NIT 3 (`section.footnotes` is a commentable `.blk`): accepted (A4 default).** The
  MR-028 follow-up to exclude it stays optional.
- **2026-06-18 — Verdict PASS-WITH-CONDITIONS; SHOULD-1 resolved, NITs dispositioned. Sprint-08
  closed at G7.**
