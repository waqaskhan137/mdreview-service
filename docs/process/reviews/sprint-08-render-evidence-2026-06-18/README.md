# sprint-08 (render-fidelity) — render evidence — 2026-06-18

Product pages touched: `viewer.html` + vendored `static/**` (marked-footnote, highlight.js,
marked-highlight, hljs-github.css). Rebuilt throwaway container on :8138 (never compose/:8139).

Fixture exercises every path: a footnote (`[^a]`) + reuse, inline math `$E=mc^2$`, a python fenced
block, a mermaid block, a GFM table, prose currency.

- `curl /healthz` → ok; `/api/reviews` → sane JSON.
- `render-smoke.sh` (flat selectors): `'pre' '.hljs' '.hljs-keyword' '#article'` all ok; and
  `'.katex' '.mermaid' 'table' 'sup'` all ok (no regression).
- MIME (GET header-dump): `highlight.min.js`=text/javascript (127496 B), `marked-highlight.umd.js`=
  text/javascript, `hljs-github.css`=text/css, `marked-footnote.umd.js`=text/javascript.

**`review-dark.png`** (preferredColorScheme=0) — the theme-sensitive proof: the python block is
token-colored (github-dark) and **legible on the dark `pre` background, no white box** (each theme's
`.hljs` base background was stripped so the pane shows through); footnote superscript + bottom
back-ref section (no "Footnotes" banner); `$E=mc^2$` rendered; mermaid is a **diagram** (not
highlighted code); table renders.

**`review-light.png`** (preferredColorScheme=1) — github-light token colors on the light pre
background; same structure.
