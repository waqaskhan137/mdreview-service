#!/usr/bin/env bash
# latex_threeway_selfcheck.sh — #332, wired into tests/ so it is discoverable the way every
# sibling rendered-outcome check is (latex_canvas_backdrop_selfcheck.sh <- latex-canvas-check.mjs,
# loading_states_selfcheck.sh <- loading-states-check.mjs). scripts/latex-threeway-check.mjs is
# self-contained (boots its own throwaway local instance, unlike latex-canvas-check.mjs which takes
# a URL an .sh wrapper must supply), so this wrapper is a thin passthrough rather than a fixture.
#
#   bash tests/latex_threeway_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
node "$here/scripts/latex-threeway-check.mjs"
