#!/usr/bin/env bash
# readme_shape_selfcheck.sh — README.md stays a front door, not a manual (#257).
#
# WHAT THIS GUARDS. The README grew to 544 lines / 5,578 words by accretion: every operator runbook
# that had nowhere else to go landed there, so a reader wanting to know what mdreview IS had to
# scroll past docker build recipes and token-minting instructions. Nobody decided that; it just
# happened one section at a time. This check makes the next such section land somewhere else.
#
# It asserts three things, and the third is the one that makes the split honest: every docs/ path
# the README links to must EXIST. A move that leaves dangling links has not moved anything, it has
# deleted it and left a signpost.
#
#   bash tests/readme_shape_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

# 1. Length. 150 is the cap the ticket set: a front door someone reads in full.
lines=$(grep -c '' README.md)
[ "$lines" -le 150 ] && ok "README is ${lines} lines (cap 150)" \
  || bad "README is ${lines} lines, over the 150 cap: move a section to docs/operations/"

# 2. House style: no em dashes. Mechanically checkable, and it was 81 before this ticket.
em=$(grep -c '—' README.md || true)
[ "$em" = "0" ] && ok "no em dashes" || bad "${em} em dash(es) in README.md"

# 3. Every docs/ link resolves. This is the anti-deletion assertion.
missing=0
while read -r target; do
  [ -z "$target" ] && continue
  if [ ! -e "$target" ]; then bad "README links to a missing file: $target"; missing=1; fi
done < <(grep -oE '\]\((docs/[^)#]+)\)' README.md | sed -E 's/^\]\(//; s/\)$//' | sort -u)
[ "$missing" = "0" ] && ok "every docs/ link resolves"

# 4. The front door still answers the first question. If these go, the shrink went too far and the
#    page no longer says what the product is or how to run it.
for want in "## Getting started" "## Run" "## Config"; do
  grep -q "^$want" README.md && ok "keeps '$want'" || bad "lost '$want' — the front door must still answer it"
done

# 5. The runbooks are reachable in one hop, not merely deleted from the README.
grep -q "docs/operations/" README.md \
  && ok "links out to the operator guides" \
  || bad "no link to docs/operations/ — the moved runbooks are unreachable from the front door"

echo
[ "$fail" -eq 0 ] && echo "README shape OK" || echo "README shape FAILED"
exit "$fail"
