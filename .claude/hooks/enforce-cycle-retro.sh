#!/usr/bin/env bash
# Stop hook: enforce the /feature-cycle Phase 10 retrospective.
#
# The orchestrator drops a marker file the moment a cycle reaches a terminal state
# (entering Phase 9 / ship, or declaring a park). Phase 10 (the cycle-retrospective
# meta agent) deletes the marker after it runs. While the marker exists, this hook
# blocks Stop so the run cannot finish without the retrospective.
#
# Hardened for a solo repo (differs from the source process): if `jq` is missing we
# FAIL OPEN (allow Stop) rather than trap the session. The manual unstick is always:
#   rm .claude/.feature-cycle-pending-retro
#
# Stdin is the Stop-hook JSON payload (unused). Output:
#   - marker present + jq available -> {"decision":"block","reason":...}  (model must run retro)
#   - marker absent                 -> no output, exit 0  (stop allowed)
#   - jq missing                    -> no output, exit 0  (fail open, do not trap)

DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
MARKER="$DIR/.claude/.feature-cycle-pending-retro"

[ -f "$MARKER" ] || exit 0

if ! command -v jq >/dev/null 2>&1; then
  # Fail open: cannot emit structured block without jq; do not trap the session.
  echo "enforce-cycle-retro: jq not found; allowing Stop. Run the retro and: rm \"$MARKER\"" >&2
  exit 0
fi

slug="$(cat "$MARKER" 2>/dev/null)"
reason="feature-cycle Phase 10 (cycle retrospective) has not run for this cycle (${slug:-unknown}). \
Before stopping: spawn the cycle-retrospective agent to meta-review THIS run, write \
reviews/<slug>-cycle-retro-<YYYY-MM-DD>.md, report its top suggestions to the user, then remove \
the marker:  rm \"$MARKER\"  . If the retrospective genuinely cannot run, delete the marker \
manually and state why."

jq -nc --arg r "$reason" '{decision:"block", reason:$r}'
exit 0
