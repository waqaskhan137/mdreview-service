#!/usr/bin/env bash
# latex_resolve_selfcheck.sh — #342 "LaTeX viewer has no Resolved surface, so it cannot safely
# take the Resolve action". scripts/latex-resolve-check.mjs is self-contained (boots its own
# throwaway local instance, same shape as latex-threeway-check.mjs <- latex_threeway_selfcheck.sh),
# so this wrapper is a thin passthrough rather than a fixture, wired into tests/ so it is
# discoverable the way every sibling rendered-outcome check is.
#
#   bash tests/latex_resolve_selfcheck.sh    # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
node "$here/scripts/latex-resolve-check.mjs"
