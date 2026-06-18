---
review_of: epics/render-fidelity-plan.md
gate: G1
reviewer: staff-critic
independent: true
timestamp: 2026-06-18
verdict: PASS
status: resolved
---

# G1 round-2 re-review — render-fidelity plan (footnotes + syntax highlighting)

**Verdict: PASS.** Narrow re-check of the round-1 conditions (4 SHOULD + 1 NIT); the load-bearing
browser-global risk was already settled by reproduction in round-1 and is not re-litigated here.
All four SHOULDs and the NIT are genuinely fixed in the revised plan, and the revision introduced
**no new blocker**. G1 passes.

## Per-finding confirmation

- **SHOULD-1 (wrong verification URL) — fixed.** Grep shows every Verification command now uses
  `$BASE/review/$ID` (seed echo L399, three render-smoke blocks L405/408/411, Chrome screenshot
  L422, default-safe regression L436). The only remaining `/r/` strings are in the resolution
  narration (L453-456), not in any runnable command. Route confirmed: `app.py:453`
  `re.fullmatch(r"/review/" + RID, path)`, `review_url` at `app.py:317` is `{base}/review/{rid}`;
  an unmatched path 404s at `app.py:470`. The plan's citations are accurate.

- **SHOULD-2 (highlight snippet threw as written) — fixed.** Step 3 (L171-186) now pins all three
  globals (`window.markedFootnote` = factory; `window.markedHighlight` = namespace object whose
  `.markedHighlight` is the factory; `window.hljs` = engine) and uses
  `const mh = window.markedHighlight && window.markedHighlight.markedHighlight; if (mh && window.hljs) marked.use(mh({…}))`
  — the `window.*` guard wraps the actual `marked.use(...)` call, so a missing/odd global
  short-circuits to falsy and skips registration silently (footgun 8). No bare `markedHighlight(...)`
  remains (grep: zero `marked.use(markedHighlight(`). Mirrored into MR-029 AC (L312-318).

- **SHOULD-3 (stray visible "Footnotes" heading) — fixed.** Step 4 (L191-204) adds a real `.sr-only`
  clip rule to the viewer `<style>`, and MR-028's CSS scope + AC (L305-311) require it with a
  screenshot AC ("no banner heading above the ordered list"). The `<h2 class="sr-only">` is hidden
  visually, kept for screen readers.

- **SHOULD-4 (peer-range deviation) — fixed.** A Risks row (L334) and MR-029's AC/Work-log note
  (L312-321) record `marked-highlight@2.1.4`'s `peerDependencies: marked ">=4 <15"` against vendored
  v18.0.4 as a verified-but-out-of-range pin, with the re-probe trigger on any `static/marked.min.js`
  bump. `marked-footnote@1.4.0` (`>=7.0.0`) noted as in-range/clean.

- **NIT (payload numbers) — actioned.** Bundle table (L130/132) and prose (M3 L96, A3 L354-355) now
  read ~127 KB / ~34 grammars; total ~136 KB (3.3+3.1+127+2.5 ≈ 135.9, consistent). The Verification
  assert is loosened to `-gt 100000` on `highlight.min.js` (L390) — a correct ~127 KB asset passes,
  a missing/empty one fails.

## Residual non-gating notes

- The bundle-size figures (~127 KB, ~34 grammars, ~136 KB total) are taken on the author's stated
  reproduction; I did not re-pack the assets this round. They are internally consistent and below the
  brief's budget, so they do not gate. The `>100000` floor is the real guard at verify time.
- `highlightAuto` on unlabelled blocks (L183) can be visually noisy on prose-in-a-fence, but that is
  a curated, accepted default-behavior choice (A3), not a defect.

## Resolution log

**2026-06-18 — round-2 re-review.** Verified the 4 SHOULDs + NIT against the revised plan by grep
and by spot-checking the `/review/{id}` route in `app.py`. All resolved as described in the plan's
"Review resolutions" section; no new blocker introduced by the revision. Verdict upgraded
PASS-WITH-CONDITIONS → **PASS**, status **resolved**. G1 may pass; the orchestrator flips the plan's
G1 gate.
