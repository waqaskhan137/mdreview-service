---
id: MR-049
title: Viewer comment UX — reliable text-selection → comment button + markdown rendering in comment threads
status: done
layer: ui
priority: P2
sprint:                # out-of-cycle (own branch MR-049-viewer-comment-ux); not part of a sprint
epic:                  # none — user-reported bug fixes
depends_on: []
branch: MR-049-viewer-comment-ux
created: 2026-06-23
updated: 2026-06-23
---

## Goal

Two user-reported viewer bugs in the comment-authoring UX:

1. **Flaky "+ comment" button.** Highlighting text to comment often did not show the button; the
   user had to re-select multiple times. Root-caused (general-purpose investigation agent +
   confirmed in code): the `mouseup` handler resolved the target block **only** from
   `sel.anchorNode` (`viewer.html`), so a cross-block / backward / boundary-or-whitespace-started
   selection — where `anchorNode` walks up to `#article` itself — hit `.closest('.blk') === null`
   and silently hid the button. A clean re-select inside one paragraph "fixed" it.
2. **Comments render as raw plaintext ("ugly").** Thread bodies were emitted via `esc(text)`, so
   `**bold**`, `` `code` ``, lists, links, and line breaks showed literally.

## Acceptance criteria

- [x] **Selection reliability:** the comment button appears for cross-block, backward, and
      boundary-started selections. The handler resolves the block from **any** endpoint
      (`anchorNode` → `focusNode` → range start/end) and only requires the selection to intersect
      `#article`. Verified by reproducing the exact failure (`anchorNode === #article`) headlessly
      and asserting the button flips `none → block` (old code stayed `none`).
- [x] **Markdown in comments:** thread bodies render markdown (bold/italic/inline code/lists/
      links/line-breaks) via `marked`. Verified: `<strong>`, `<code>`, `<em>`, 2×`<li>`, kept
      `https://` link all present in the rendered DOM.
- [x] **XSS-safe (comments are untrusted, no-auth input):** HTML is escaped **before** `marked`
      runs (raw `<b>HTML</b>` renders as inert text, not a live element), and a post-pass strips
      `javascript:`/`data:` URLs from links/images (the `javascript:` link's `href` is removed).
      No double-escaping (a literal `&` stays `&`, not `&amp;`). All verified headlessly.
- [x] **Secondary flakiness (poll race):** the 2s live-reload poll skips a tick while a comment
      gesture is open (`#addbtn`/`#pop` visible), so a re-render can't wipe an in-progress
      selection.
- [x] **Render-smoke (G4 ui):** rebuilt the image, ran a throwaway container, drove headless
      Chrome over CDP (a 200 is not a render) + screenshot. Evidence under
      `reviews/mr049-viewer-comment-ux-evidence-2026-06-23/`.

## Notes / context

- `viewer.html` only. Changes: the `#article` `mouseup` handler (block resolution from any
  endpoint); a `mdComment()` helper (escape → `marked.parse(…,{breaks:true})` → strip dangerous
  URLs via an inert `<template>`); `threadHtml` uses it and `.gtext` becomes a `<div>`; `.gtext`
  markdown CSS; a poll-tick guard.
- Investigation: a general-purpose agent root-caused the selection bug; both causes confirmed
  against the code before fixing.
- Out-of-cycle, own branch (kept off the legacy-feedback-retire PR #11 and off MR-048).
- Evidence: `reviews/mr049-viewer-comment-ux-evidence-2026-06-23/cdp-verification.json` +
  `review-markdown-comment.png`.

## Work log

- `2026-06-23` — `viewer.html`:
  - `mouseup` handler: resolve `.blk` from `anchorNode || focusNode || range.start/end`; gate on
    `#article.contains(range.commonAncestorContainer)`. Fixes the silent no-button case.
  - `mdComment(raw)`: `esc()` first (kills raw-HTML/attribute injection), then
    `marked.parse(esc(raw),{breaks:true})`, then strip non-`http(s)`/`mailto` link hrefs and
    non-`http(s)`/`data:image` img srcs via a `<template>` (inert; no image loads). `threadHtml`
    renders `.gtext` as a `<div>` through `mdComment`.
  - `.gtext` markdown CSS (tight margins, code chip, lists, blockquote, capped heading size).
  - poll: skip the tick while `#addbtn`/`#pop` is open (secondary race).

## Validation

- `2026-06-23` — rebuilt `mdreview-viewerfix`, throwaway container :8148, seeded a 3-block review +
  a markdown/XSS-probing comment. Headless-Chrome CDP results
  (`reviews/mr049-viewer-comment-ux-evidence-2026-06-23/cdp-verification.json`):
  `has_strong/has_code/has_em=true`, `li_count=2`, `safe_link=true`, `js_link_present=false`,
  `live_raw_b=false`, `text_has_amp=true` (no double-escape), `text_has_rawtag=true` (raw HTML is
  text); and the selection repro: `anchor_is_article=true`, `addbtn_before="none"`,
  `addbtn_after="block"`. Screenshot eyeballed — comment renders bold/code/italic/bullets/links
  cleanly.

## Follow-ups

- Cosmetic (deferred): a defanged link (href stripped) still shows in accent colour; could style
  `a:not([href])` as plain text. Low value.
