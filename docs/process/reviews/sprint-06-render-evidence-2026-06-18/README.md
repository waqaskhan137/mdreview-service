# sprint-06 (rich-rendering) — G7 render evidence — 2026-06-18

Product pages touched this sprint: `viewer.html`, `static/**` (KaTeX vendored). So G7 requires a
container rebuild + curl smoke + `render-smoke.sh` per touched page + a screenshot.

**Container:** rebuilt fresh (`docker build -t mdreview-service:rr .`) and run as a **throwaway**
on port 8138 — deliberately NOT `docker compose up` (the user's live instance serves 8139; compose
says 8137; recreating it would clobber the live container the MCP points at).

- `curl /healthz` → `{"ok": true}`
- `curl /api/reviews` → `{"reviews": []}` (sane JSON; throwaway starts empty)

**render-smoke.sh** (`render-smoke.txt`), against `/review/<id>` of a combined math+image fixture:

```
  ok : .katex (4 nodes)
  ok : img (1 node)
  ok : #article (1 node)
```

(Selector note: the harness has no descendant combinator, so `img` is used, not `#article img`.)

**Screenshot** (`review-math-image.png`) — first-paint proof, which is what render-smoke cannot give
for fonts:

- inline `$E=mc^2$` and `\(x_i\)` typeset inline;
- display `$$\int_0^1 x\,dx = \tfrac12$$` and `\[ a^2+b^2=c^2 \]` typeset as centered display blocks;
- **prose `$5 and $10` stays literal** (no false-positive math);
- the KaTeX glyphs (integral sign, fraction bar, italic math variables, superscripts) are properly
  rendered — i.e. the woff2 **fonts loaded** (the `_read_bytes`/MIME path works end to end).

The attached image (`![plot](/assets/plot.png)`, a 1×1 PNG) is the `img` node the smoke asserts;
its src is rewritten to the served `/asset/<hash>.png` URL and returns real PNG bytes — proven in
MR-023/MR-025 validation (it sits at the bottom of the doc, below this screenshot's fold).
