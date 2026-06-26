#!/usr/bin/env python3
"""Add a "Docs" link to the landing-page nav, safely and idempotently.

web/site/index.html is a pre-generated SPA bundle whose HTML lives as a JSON-encoded
string inside <script type="__bundler/template">. Hand-editing that minified, escaped
blob is unsafe: a malformed edit breaks JSON.parse at load and renders the page blank.
This does the safe round-trip instead — decode the template JSON, insert the nav link
in the *decoded* HTML, re-encode (preserving the original ensure_ascii setting and
re-protecting any </script> so the outer tag can't close early), splice it back, and
self-check that all three bundler script blocks still parse.

Idempotent: re-running is a no-op once the link is present. Re-run it after any future
bundle regeneration to re-add the link.

    python3 src/patch_landing_docs_link.py            # patch in place
    python3 src/patch_landing_docs_link.py --check    # verify only (exit 1 if missing)
"""
import json
import pathlib
import sys

INDEX = pathlib.Path(__file__).resolve().parents[1] / "web" / "site" / "index.html"
ANCHOR = '<a class="nav-cta" href="https://github.com/waqaskhan137/mdreview-service">GitHub ↗</a>'
LINK = '<a href="/docs/">Docs</a>'
TYPES = ("__bundler/manifest", "__bundler/template", "__bundler/ext_resources")


def segment(html, typ):
    """Return (start, end) of the JSON content inside <script type="typ">...</script>."""
    open_tag = f'<script type="{typ}">'
    start = html.index(open_tag) + len(open_tag)
    end = html.index("</script>", start)
    return start, end


def main():
    check = "--check" in sys.argv
    html = INDEX.read_text()
    s, e = segment(html, "__bundler/template")
    raw = html[s:e]
    tmpl = json.loads(raw)  # the decoded HTML string (raw includes the surrounding quotes)

    present = LINK in tmpl
    if check:
        print("Docs link present" if present else "Docs link MISSING")
        sys.exit(0 if present else 1)
    if present:
        print("Docs link already present; no change.")
        return

    if tmpl.count(ANCHOR) != 1:
        sys.exit(f"abort: nav anchor not found uniquely (count={tmpl.count(ANCHOR)})")
    new_tmpl = tmpl.replace(ANCHOR, f"{LINK}\n      {ANCHOR}", 1)

    # Match the original's encoding so we don't churn every non-ASCII glyph, then re-protect
    # </script> exactly as the bundler does (escape the slash) so the HTML parser can't close
    # the template <script> early.
    ensure_ascii = not any(ord(c) > 127 for c in raw)
    new_raw = json.dumps(new_tmpl, ensure_ascii=ensure_ascii).replace("</script", "<\\/script")
    if "</script" in new_raw:
        sys.exit("abort: unescaped </script> remains in re-encoded template")

    new_html = html[:s] + new_raw + html[e:]

    # Self-check: every bundler block must still parse, and the link must be in.
    for typ in TYPES:
        a, b = segment(new_html, typ)
        json.loads(new_html[a:b])
    a, b = segment(new_html, "__bundler/template")
    assert LINK in json.loads(new_html[a:b]), "link missing after splice"

    INDEX.write_text(new_html)
    print(f"Inserted {LINK} into the nav (ensure_ascii={ensure_ascii}); all 3 blocks parse.")


if __name__ == "__main__":
    main()
