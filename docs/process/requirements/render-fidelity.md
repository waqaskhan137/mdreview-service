---
slug: render-fidelity
captured: 2026-06-18
source: the two remaining P2 items from the rich-rendering real-review feedback (requirements/rich-rendering.md → docs/process/backlog.md "From the rich-rendering brief — deferred P1/P2"), promoted to their own epic on the user's go-ahead this session (waqas, 2026-06-18) after theme-awareness (sprint-07) shipped
related_epic: epics/render-fidelity-plan.md
---

# Render fidelity — footnotes + syntax highlighting

Verbatim asks (the P2 items from the rich-rendering brief, as captured in the backlog). Do not
edit; append dated notes under Amendments if the requirement changes.

> **P2 — Nice-to-haves**
> - Mermaid fenced-block rendering (Jekyll posts use ```` ```mermaid ````; shows as code now).
>   *[already shipped in dev — out of scope]*
> - Parse/hide YAML front matter (the `---` block currently shows as text). *[already shipped — out
>   of scope]*
> - Confirm GFM tables, footnotes, syntax highlighting.

Backlog elaboration (the two not-yet-shipped pieces this epic takes):

> - **Footnotes (P2)** — GFM footnotes show as text; marked core needs an extension. Now cheap:
>   sprint-06 established the marked-extension pattern (`setupKatex` in `viewer.html`), so a footnote
>   extension is the same shape.
> - **Syntax highlighting (P2)** — fenced code isn't highlighted; no highlighter is bundled. Vendor a
>   small highlighter into `static/` (same stdlib-vendoring approach as KaTeX/marked/mermaid) and
>   wire it into the render path.

## Goal

The review viewer renders the last two things a Jekyll/MathJax-published post shows that mdreview
still doesn't, so a reviewer sees the draft as it will publish:

- **GFM footnotes** — `[^id]` references render as superscript links to an ordered footnotes section
  built from the `[^id]: …` definitions, with back-reference links; not as raw `[^id]` text.
- **Syntax highlighting** — fenced code blocks (```` ```python ````) render with token colors from a
  vendored highlighter, instead of plain monospace.

GFM **tables** are already confirmed working (marked GFM default); this epic only needs to not
regress them.

## What must NOT regress (already shipped)

- The **math** marked-extension (`setupKatex`) — footnotes register on the same inline tokenizer and
  must not eat math `$…$` (or be eaten by it).
- **Mermaid** — `code.language-mermaid` is converted to a diagram by `renderMermaid()`; the
  highlighter must **skip** mermaid code blocks, never highlight them as code.
- The image **mat** (theme-awareness), block numbering (`numberBlocks`), note reconciliation, and a
  document with neither footnotes nor code must render byte-identical to today.

## Decisions for the plan (not pre-made here)

- **Footnotes: vendor a marked extension vs hand-roll one.** A correct footnote tokenizer (ref +
  definition collection across the document + an ordered end section + back-refs) is more than the
  math extension was. Weigh vendoring a small, well-tested marked footnote extension into `static/`
  against hand-rolling on the established `marked.use({extensions})` pattern.
- **Highlighter engine + language set + size.** highlight.js is the standard; Prism is lighter.
  Pick the engine, the bundled language set (prune sensibly — don't ship every language), and the
  CSS theme (one that reads on both the light and dark panes, or a theme per scheme). Mermaid is
  already 3.3 MB vendored, so a few hundred KB is acceptable, but keep it lean.
- **Where highlighting runs in the render sequence** — after `marked.parse`, mind `numberBlocks()`
  reparenting and the mermaid path (`code.language-mermaid` must be excluded).

## Out of scope

- The animated-GIF landing demo (MR-021), the cut local-dir `{name,path}` asset read (S5), and the
  infra backlog items (COPY `mcp_server.py` into the image, an `mcp`-SDK wrapper variant, automated
  post-interaction render evidence) — separate backlog threads.
- Any service / API / MCP change — this is a `viewer.html` + `static/` (vendored assets) concern.
- A user-facing theme/lang picker.

## Amendments

_None yet._
