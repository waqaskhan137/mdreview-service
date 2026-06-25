#!/usr/bin/env bash
# render-smoke.sh <url> <css-selector>...
#
# Asserts that a JS-rendered page actually produced the expected DOM nodes — not just that it
# returned 200, and not by substring-matching the page source (the inline <style>/<script> text
# contains strings like "gcard"/"cmt", so a grep would false-pass even if zero elements rendered).
#
# How it works: drive headless Chrome to serialize the RENDERED DOM (`--dump-dom`) AFTER a
# render-wait (`--virtual-time-budget`, because the viewer renders via setTimeout fallbacks +
# async mermaid — see reviews/sprint-01-close-review-2026-06-08.md). Then a stdlib Python HTML
# parser COUNTS ELEMENTS matching each selector (text inside <style>/<script> is data, not
# elements, so it is correctly ignored).
#
# Contract:
#   - every selector matches >=1 element  -> exit 0
#   - any selector matches 0 elements      -> exit 1, names the missing selector
#   - no Chrome binary found               -> exit 3 (FAIL LOUD; never a silent pass)
#   - bad usage                            -> exit 2
#
# Selectors supported: `tag`, `.class`, `tag.class[.class...]`, `#id`. Target a SERVED url
# (the rebuilt container's published port), never a file:// path.
set -u

URL="${1:-}"; shift || true
if [ -z "$URL" ] || [ "$#" -eq 0 ]; then
  echo "usage: render-smoke.sh <url> <css-selector>..." >&2
  exit 2
fi

# locate a Chrome/Chromium binary; fail loud if none.
# RENDER_SMOKE_CHROME, if set, is authoritative: use exactly it, or fail (CI pins / fail-loud test).
CHROME=""
if [ -n "${RENDER_SMOKE_CHROME:-}" ]; then
  CANDIDATES=("$RENDER_SMOKE_CHROME")
else
  CANDIDATES=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "google-chrome" "google-chrome-stable" "chromium" "chromium-browser"
  )
fi
for c in "${CANDIDATES[@]}"; do
  if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then CHROME="$c"; break; fi
done
if [ -z "$CHROME" ]; then
  echo "render-smoke: no Chrome/Chromium binary found. Tried: ${CANDIDATES[*]}" >&2
  exit 3
fi

VTB="${RENDER_SMOKE_VTB:-2500}"   # virtual-time budget (ms) to wait for render
DOM="$(mktemp -t render-smoke.XXXXXX)"
trap 'rm -f "$DOM"' EXIT

if ! "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --virtual-time-budget="$VTB" --dump-dom "$URL" >"$DOM" 2>/dev/null; then
  echo "render-smoke: Chrome failed to load $URL" >&2
  exit 3
fi

# count elements per selector against the rendered DOM (stdlib parser; not a substring grep)
python3 - "$DOM" "$@" <<'PY'
import re
import sys
from html.parser import HTMLParser

dom_path = sys.argv[1]
selectors = sys.argv[2:]

# This is a FLAT matcher, not a CSS engine: only `tag`, `.class`, `tag.class[.class]`, `#id`.
# Reject anything with a combinator / attribute / pseudo / whitespace so an unsupported selector
# fails loud as bad usage (exit 2) instead of silently matching 0 and looking like a render miss.
_VALID = re.compile(r'^(#[A-Za-z_][\w-]*|[A-Za-z][\w-]*(\.[A-Za-z_][\w-]*)*|(\.[A-Za-z_][\w-]*)+)$')
bad = [s for s in selectors if not _VALID.match(s.strip())]
if bad:
    print("render-smoke: unsupported selector(s) (only tag/.class/tag.class/#id; no combinators, "
          "attributes, pseudo-classes, or spaces): " + ', '.join(repr(s) for s in bad), file=sys.stderr)
    sys.exit(2)

def parse_selector(sel):
    sel = sel.strip()
    if sel.startswith('#'):
        return ('id', sel[1:], None)
    parts = sel.split('.')
    tag = parts[0]  # '' means any tag
    classes = [p for p in parts[1:] if p]
    return ('tagclass', tag or None, classes)

parsed = [(s, parse_selector(s)) for s in selectors]
counts = {s: 0 for s in selectors}

class Counter(HTMLParser):
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        el_classes = (a.get('class') or '').split()
        el_id = a.get('id')
        for s, (kind, x, classes) in parsed:
            if kind == 'id':
                if el_id == x:
                    counts[s] += 1
            else:  # tagclass
                if (x is None or tag == x) and all(c in el_classes for c in classes):
                    counts[s] += 1

with open(dom_path, encoding='utf-8', errors='replace') as f:
    Counter().feed(f.read())

missing = [s for s in selectors if counts[s] == 0]
for s in selectors:
    mark = 'ok ' if counts[s] else 'MISSING'
    print(f"  {mark}: {s} ({counts[s]} node{'' if counts[s]==1 else 's'})")
if missing:
    print(f"render-smoke: {len(missing)} selector(s) matched no rendered element: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)
PY
