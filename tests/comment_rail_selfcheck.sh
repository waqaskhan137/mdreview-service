#!/usr/bin/env bash
# comment_rail_selfcheck.sh — regression check for the comment-rail width band (#199).
#
# The rail used to dock below ~1312px innerWidth, which covers 1280x800 and every laptop narrower:
# the reader lost the side-by-side view at exactly the widths most people use. The fix narrows the
# reading column in that band so the rail still fits beside the text.
#
# WHY GEOMETRY, NOT `.gcard` PRESENCE:
# cards render whether the rail is beside the text or docked over it, so counting them passes in
# both states. The observable that distinguishes them is `body.gutter-on` plus the measured left
# edge of #gutter against the measured right edge of #article.
#
# WHY IT CHECKS #pop TOO:
# layoutComments() and positionPop() carried the SAME threshold literal. A fix applied to one ships
# a viewer whose rail sits beside the text while its composer docks. That parity criterion was
# dropped once during grooming and restored; this is what stops it being dropped again.
#
# WHY ONE BROWSER LAUNCH PER PHASE:
# an earlier version launched Chrome five times per run and was FLAKY — roughly 2 runs in 10 died
# on "wait-for timed out (10s)" before any assertion, from launch contention rather than a defect.
# A check that fails at random trains people to ignore it. Two launches, many steps each.
#
# Runs against a throwaway local instance on an ephemeral port. No host, no staging, no auth.
#   bash tests/comment_rail_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
port="${PORT_OVERRIDE:-$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')}"
tmp="$(mktemp -d)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; rm -rf "$tmp" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$tmp/data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$tmp/server.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = "1" ] || { echo "FAIL - server never came up on :$port"; sed -n '1,5p' "$tmp/server.log"; exit 1; }

rid=$(curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"rail","markdown":"# Rail\n\nAlpha.\n\nBeta.\n\nGamma.\n"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))')
[ -n "$rid" ] || { echo "FAIL - could not create the fixture review"; exit 1; }
url="http://127.0.0.1:$port/review/$rid"

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

field(){ local s="${1#*$2=}"; echo "${s%% *}"; }

# Retry ONLY on an infrastructure failure — Chrome producing ZERO measurements, e.g. the known
# "wait-for timed out" launch race. A failed ASSERTION is never retried: that would turn a real
# regression into a coin flip. The distinction is the point, and the retry announces itself so a
# flaky environment stays visible instead of being silently smoothed over.
retry_if_empty(){  # $1 = marker, rest = command
  local marker="$1"; shift
  local out; out="$("$@" 2>&1)"
  if ! grep -q "$marker" <<<"$out"; then
    printf '  note - no %s measurements; retrying the browser once (infrastructure, not an assertion)\n' "$marker" >&2
    out="$("$@" 2>&1)"
  fi
  printf '%s' "$out"
}

# --resize drives CDP Emulation.setDeviceMetricsOverride: a REAL relayout that changes
# window.innerWidth. An OS window resize does not, which is why it is used here.
G='(()=>{const A=document.querySelector("#article"),G=document.querySelector("#gutter");const a=A.getBoundingClientRect(),g=G.getBoundingClientRect();return "MEAS w="+window.innerWidth+" on="+document.body.classList.contains("gutter-on")+" aRight="+Math.round(a.right)+" gLeft="+Math.round(g.left)+" gW="+Math.round(g.width)+" col="+Math.round(document.querySelector(".wrap").getBoundingClientRect().width);})()'

geo="$(retry_if_empty MEAS node "$here/scripts/cdp-shot.mjs" --url "$url" --wait-for "#article" \
        --resize 1180x900 --wait 400 --eval "$G" \
        --resize 1280x900 --wait 400 --eval "$G" \
        --resize 1400x900 --wait 400 --eval "$G")"


for w in 1180 1280; do
  m="$(grep -o "MEAS w=$w [^\"]*" <<<"$geo" | head -1)"
  if [ -z "$m" ]; then bad "${w}px: no measurement (browser step failed)"; continue; fi
  on="$(field "$m" on)"; ar="$(field "$m" aRight)"; gl="$(field "$m" gLeft)"
  [ "$on" = "true" ] && ok "${w}px: gutter-on" || bad "${w}px: rail DOCKED (this is the bug) — $m"
  if [ -n "$ar" ] && [ -n "$gl" ] && [ "$gl" -gt "$ar" ] 2>/dev/null; then
    ok "${w}px: rail beside the text (gutter.left $gl > article.right $ar)"
  else
    bad "${w}px: rail overlaps the text — $m"
  fi
done

# Wide layouts must be untouched: same column and same rail width as before the change.
m="$(grep -o "MEAS w=1400 [^\"]*" <<<"$geo" | head -1)"
if [ -z "$m" ]; then bad "1400px: no measurement"; else
  col="$(field "$m" col)"; gw="$(field "$m" gW)"
  [ "$col" = "720" ] && ok "1400px: reading column unchanged at 720px" \
    || bad "1400px: column ${col}px, expected 720 — wide layouts must not be penalised"
  [ "$gw" = "284" ] && ok "1400px: rail still 284px" || bad "1400px: rail ${gw}px, expected 284"
fi

# Composer parity. Settle on the EXACT selector after the resize: viewer.html renders through
# marked plus setTimeout fallbacks, so the block being clicked may not exist yet (hard rule 5).
P='(()=>{const p=document.querySelector("#pop");return "POP w="+window.innerWidth+" docked="+p.classList.contains("docked")+" width="+Math.round(p.getBoundingClientRect().width);})()'
pop="$(retry_if_empty POP node "$here/scripts/cdp-shot.mjs" --url "$url" --wait-for ".blk .num" \
        --resize 1180x900 --wait 400 --wait-for ".blk:nth-of-type(2) .num" \
        --click ".blk:nth-of-type(2) .num" --wait 400 --eval "$P" \
        --resize 1280x900 --wait 400 --eval "$P")"

for w in 1180 1280; do
  m="$(grep -o "POP w=$w [^\"]*" <<<"$pop" | head -1)"
  if [ -z "$m" ]; then bad "${w}px: composer not measured (browser step failed)"; continue; fi
  case "$m" in
    *"docked=false"*"width=284"*) ok "${w}px: composer floats beside the text at 284px" ;;
    *) bad "${w}px: composer DOCKED or resized while the rail is beside the text — $m" ;;
  esac
done

echo
[ "$fail" -eq 0 ] && echo "all comment-rail cases pass" || echo "comment-rail check FAILED"
exit "$fail"
