#!/usr/bin/env python3
"""releases_page_tripwire.py (#373): fails when the newest GitHub Release is not represented on
the generated releases page.

This is the part of #373 that matters most. release.yml now creates a GitHub Release per tag,
pages.yml now generates web/site/releases/index.html from the Releases API and republishes on
`release: published` -- but a pipeline with no check is just a better-organised way to forget,
exactly as this ticket describes happening twice already (flagged at v0.4.0, not fixed; still
broken at v0.5.3). This script is that check: given a releases snapshot and the page generated
from it, decide independently whether the newest release actually made it onto the page.

Independence matters: this script does NOT import gen_releases_page's sort or its idea of
"newest" -- it recomputes both from scratch. A generator and its checker sharing one buggy
comparator is the #272-class bug (a predicate silently missing half its terms) wearing a
different hat; sharing code here would let one mistake blind both sides at once.

Exit code IS the signal: 0 clean, 1 stale (and says which tag, and why). Wired into
pages.yml as a deploy gate -- a stale page fails the workflow before it publishes -- and into
tests/releases_page_tripwire_selfcheck.py as a mutation-tested synthetic-fixture check.

Usage:
    python3 scripts/releases_page_tripwire.py <releases.json> <generated-page.html>
"""
import json
import re
import sys

VER_RE = re.compile(r'<span class="ver">([^<]*)</span>')


def _newest(releases):
    """The release the page must lead with: max published_at among non-draft releases (the JSON
    this reads is expected to already be draft-filtered, per fetch_releases, but this does not
    trust that and drops drafts again -- cheap, and this script's whole job is not trusting
    upstream assumptions). None if there is nothing to check."""
    dated = [r for r in releases if r.get("published_at") and not r.get("draft")]
    if not dated:
        return None
    return max(dated, key=lambda r: r["published_at"])


def check(releases, page_html):
    """(ok, message). `releases` is the raw list (dicts with tag_name/published_at/draft/
    html_url); `page_html` is the generated page's full text."""
    latest = _newest(releases)
    if latest is None:
        return True, "no releases to check (empty release list)"

    tag = latest["tag_name"]
    link_needle = 'releases/tag/%s"' % tag
    present = link_needle in page_html

    # Present-but-buried is still the #373 bug from a reader's point of view -- the ticket's own
    # example (v0.2.0 shown, v0.5.3 real) is a page that is wrong about what's newest, not a page
    # with a missing link. So the page must also lead with it, not merely mention it somewhere.
    first_ver = VER_RE.search(page_html)
    leads = bool(first_ver) and first_ver.group(1) == tag

    if present and leads:
        return True, "newest release %s is represented and leads the page" % tag
    if not present:
        return False, ('newest release %s has no releases/tag/%s link on the generated page '
                        '-- STALE' % (tag, tag))
    return False, ('newest release %s is present but does not lead the page (first entry is %r) '
                    '-- STALE ORDER' % (tag, first_ver.group(1) if first_ver else None))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python3 scripts/releases_page_tripwire.py <releases.json> <page.html>",
              file=sys.stderr)
        return 2

    releases_path, page_path = argv
    with open(releases_path, encoding="utf-8") as f:
        releases = json.load(f)
    with open(page_path, encoding="utf-8") as f:
        page_html = f.read()

    ok, msg = check(releases, page_html)
    print(("releases page tripwire: clean - " if ok else "releases page tripwire: STALE - ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
