#!/usr/bin/env python3
"""Bring the landing page current with the hosted launch, safely and idempotently.

web/site/index.html is a pre-generated SPA bundle whose HTML lives as a JSON-encoded string
inside <script type="__bundler/template">. Hand-editing that minified, escaped blob is unsafe
(a malformed edit breaks JSON.parse at load and renders the page blank), so this does the same
safe round-trip as patch_landing_docs_link.py: decode the template JSON, edit the *decoded*
HTML, re-encode (preserving ensure_ascii and re-protecting </script>), splice back, and
self-check that all three bundler blocks still parse.

Three content fixes, all idempotent (re-running once applied is a no-op):
  1. Stale domain  mdreview.waqasrana.space -> mdreview.space (the site's own canonical link).
  2. MCP tool count 18 -> 20 (two spots) to match src/mcp/tools.py.
  3. The "Run it" block becomes an "Install" block that leads with the hosted one-command
     installer and keeps self-host below it, plus an "Install" nav link.

Re-run after any future bundle regeneration to re-apply.

    python3 src/patch_landing_hosted_install.py            # patch in place
    python3 src/patch_landing_hosted_install.py --check    # verify only (exit 1 if not applied)
"""
import json
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[1] / "web" / "site" / "index.html"
TYPES = ("__bundler/manifest", "__bundler/template", "__bundler/ext_resources")

ARROW = "\u2192"   # the -> glyph the bundle uses in terminal comments
MDASH = "\u2014"   # long dash (U+2014) in the original copy; escape, not a literal glyph

NEW_TERM = (
    '<pre class="code"><span class="c"># one command (needs the claude CLI)</span>\n'
    'curl -fsSL https://mdreview.space/install.sh | sh\n'
    '<span class="c"># connects Claude Code to app.mdreview.space</span></pre>'
)

# (label, old, new, sentinel-that-means-already-applied)
REPLACEMENTS = [
    ("footer domain",
     '<span>canonical: <a href="https://mdreview.waqasrana.space/">mdreview.waqasrana.space</a></span>',
     '<span>canonical: <a href="https://mdreview.space/">mdreview.space</a></span>',
     'mdreview.space/">mdreview.space</a></span>'),
    ("mcp eyebrow count", "18 tools</p>", "20 tools</p>", "20 tools</p>"),
    ("mcp strong count", "18 first-class tools", "20 first-class tools", "20 first-class tools"),
    ("hero pill count", "18 MCP tools</span>", "20 MCP tools</span>", "20 MCP tools</span>"),
    ("meta desc count", '18 MCP tools.">', '20 MCP tools.">', '20 MCP tools.">'),
    ("run eyebrow", '<p class="eyebrow">Run it</p>', '<p class="eyebrow">Install</p>',
     '<p class="eyebrow">Install</p>'),
    ("run terminal",
     '<pre class="code">docker compose up -d --build\n<span class="c"># %s http://localhost:8137</span></pre>' % ARROW,
     NEW_TERM, "install.sh | sh"),
    ("run after blurb",
     '<p class="after">Stdlib Python only %s <strong style="color:var(--text)">no pip installs</strong>, '
     'tiny image, renderers vendored. Config and variants in the '
     '<a href="https://github.com/waqaskhan137/mdreview-service#run">README</a>.</p>' % MDASH,
     '<p class="after">Needs the <code>claude</code> CLI and a token from '
     '<a href="https://app.mdreview.space">app.mdreview.space</a>. Prefer your own instance? Self-host '
     'with <code>docker compose up</code>, stdlib Python only, no pip installs; details in the '
     '<a href="https://github.com/waqaskhan137/mdreview-service#getting-started-hosted-or-self-hosted">README</a>.</p>',
     'Prefer your own instance?'),
    ("nav install link",
     '<a href="#mcp">MCP</a>',
     '<a href="#mcp">MCP</a>\n      <a href="#run">Install</a>',
     '<a href="#run">Install</a>'),
]


def segment(html, typ):
    open_tag = f'<script type="{typ}">'
    start = html.index(open_tag) + len(open_tag)
    end = html.index("</script>", start)
    return start, end


def main():
    check = "--check" in sys.argv
    html = INDEX.read_text()
    s, e = segment(html, "__bundler/template")
    raw = html[s:e]
    tmpl = json.loads(raw)

    applied = [lbl for lbl, _o, _n, sen in REPLACEMENTS if sen in tmpl]
    if check:
        done = len(applied) == len(REPLACEMENTS)
        print("all applied" if done else "MISSING: " + ", ".join(
            lbl for lbl, _o, _n, sen in REPLACEMENTS if sen not in tmpl))
        sys.exit(0 if done else 1)

    changed = False
    for lbl, old, new, sen in REPLACEMENTS:
        if sen in tmpl:
            continue  # already applied
        if tmpl.count(old) != 1:
            sys.exit(f"abort: anchor for '{lbl}' not found uniquely (count={tmpl.count(old)})")
        tmpl = tmpl.replace(old, new, 1)
        changed = True
        print(f"  applied: {lbl}")
    if not changed:
        print("all fixes already present; no change.")
        return

    ensure_ascii = not any(ord(c) > 127 for c in raw)
    new_raw = json.dumps(tmpl, ensure_ascii=ensure_ascii).replace("</script", "<\\/script")
    if "</script" in new_raw:
        sys.exit("abort: unescaped </script> remains in re-encoded template")
    new_html = html[:s] + new_raw + html[e:]

    # Self-check: every bundler block still parses, and every sentinel is present.
    for typ in TYPES:
        a, b = segment(new_html, typ)
        json.loads(new_html[a:b])
    a, b = segment(new_html, "__bundler/template")
    final = json.loads(new_html[a:b])
    for lbl, _o, _n, sen in REPLACEMENTS:
        assert sen in final, f"sentinel missing after splice: {lbl}"
    assert "mdreview.waqasrana.space" not in final, "stale domain still present"

    INDEX.write_text(new_html)
    print(f"Patched (ensure_ascii={ensure_ascii}); all 3 bundler blocks parse, stale domain gone.")


if __name__ == "__main__":
    main()
