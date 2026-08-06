#!/usr/bin/env python3
"""releases_page_tripwire.py (#373): fails when the newest TAG is not represented on the
generated releases page.

This is the part of #373 that matters most. release.yml now creates a GitHub Release per tag,
pages.yml now generates web/site/releases/index.html from the Releases API and republishes on
`release: published`/`edited` -- but a pipeline with no check is just a better-organised way to
forget, exactly as this ticket describes happening twice already (flagged at v0.4.0, not fixed;
still broken at v0.5.3).

Ground truth is the TAG LIST, not the Releases list. That is deliberate, not incidental: broken
link #1 in #373's diagnosis is "tag -> Release" itself -- release.yml's create-Release step can
fail (token scope, a transient error), or someone can push a tag outside CI -- and a check
sourced from Releases data structurally cannot see that link break, because in that scenario the
Releases API and the generated page agree with each other while both silently ignore the newest
tag. Only the tag list catches it. Independence goes further still: this script does not import
gen_releases_page's sort or its idea of "newest" -- a generator and its checker sharing one buggy
comparator is the #272-class bug (a predicate silently missing half its terms) wearing a
different hat.

Exit code IS the signal: 0 clean, 1 stale (and says which tag, and why). Wired into pages.yml as
a deploy gate (a stale page fails the workflow before it publishes) and into
tests/releases_page_tripwire_selfcheck.py as a mutation-tested synthetic-fixture check.

Usage:
    python3 scripts/releases_page_tripwire.py <tags.txt> <generated-page.html>

<tags.txt> is one tag name per line (what `gh api repos/OWNER/NAME/tags --jq '.[].name'`
produces). Tags not matching vMAJOR.MINOR.PATCH (e.g. a baseline marker tag) are ignored: they
were never meant to appear on the page.
"""
import re
import sys

TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
VER_RE = re.compile(r'<span class="ver">([^<]*)</span>')


def newest_semver_tag(tag_names):
    """The tag the page must lead with: the max (major, minor, patch) among names matching
    vX.Y.Z. None if there is nothing to check. Non-matching tags (e.g. "v0-baseline") are
    dropped here rather than crashing on them -- this script's job is to police the page, not
    the tagging scheme."""
    parsed = []
    for name in tag_names:
        m = TAG_RE.match(name.strip())
        if m:
            parsed.append((tuple(int(x) for x in m.groups()), name.strip()))
    if not parsed:
        return None
    return max(parsed, key=lambda p: p[0])[1]


def check(tag_names, page_html):
    """(ok, message)."""
    tag = newest_semver_tag(tag_names)
    if tag is None:
        return True, "no vX.Y.Z tags to check"

    link_needle = 'releases/tag/%s"' % tag
    present = link_needle in page_html

    # Present-but-buried is still the #373 bug from a reader's point of view: the ticket's own
    # example (v0.2.0 shown, v0.5.3 real) is a page that is wrong about what's newest, not a page
    # with a missing link. So the page must also lead with it, not merely mention it somewhere.
    first_ver = VER_RE.search(page_html)
    leads = bool(first_ver) and first_ver.group(1) == tag

    if present and leads:
        return True, "newest tag %s is represented and leads the page" % tag
    if not present:
        return False, ('newest tag %s has no releases/tag/%s link on the generated page '
                        '-- possibly no GitHub Release exists for it yet -- STALE'
                        % (tag, tag))
    return False, ('newest tag %s is present but does not lead the page (first entry is %r) '
                    '-- STALE ORDER' % (tag, first_ver.group(1) if first_ver else None))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python3 scripts/releases_page_tripwire.py <tags.txt> <page.html>",
              file=sys.stderr)
        return 2

    tags_path, page_path = argv
    with open(tags_path, encoding="utf-8") as f:
        tag_names = [line for line in f.read().splitlines() if line.strip()]
    with open(page_path, encoding="utf-8") as f:
        page_html = f.read()

    ok, msg = check(tag_names, page_html)
    print(("releases page tripwire: clean - " if ok else "releases page tripwire: STALE - ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
