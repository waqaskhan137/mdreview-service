#!/usr/bin/env bash
# palette_fullscreen_selfcheck.sh — the ⌘K palette really is full-screen at narrow widths (#265).
#
# THIS CHECK EXISTS BECAUSE ITS PREDECESSOR LIED. keys_selfcheck.js asserted §10-02 by grepping the
# CSS text for `100vw`. It was green from the day #183 merged, while the rendered panel measured
# 574x176 at 606px and was never full-screen — the media block styled `.command-dialog`, a
# transparent wrapper, instead of `.command-dialog > .command`, the visible panel. A text assertion
# cannot see the difference. So this one measures getBoundingClientRect() and nothing else.
#
# The dialog is opened via JS here rather than a real ⌘K. That is deliberate and is NOT a
# substitute for stage 8: this file proves the LAYOUT at exact widths, and stage 8 separately
# proves a real key press opens it in a real window. Neither replaces the other.
#
#   bash tests/palette_fullscreen_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
port="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
tmp="$(mktemp -d)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; rm -rf "$tmp" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$tmp/data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$tmp/server.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = "1" ] || { echo "FAIL - server never came up"; exit 1; }
# THREE reviews on purpose: with one, the dashboard puts it in the "next up" hero and the .rw list
# stays empty, so a --wait-for on .rw times out and the check reports a layout failure that is
# really a fixture failure. Cost me a debugging round; leaving the reason here.
for i in 1 2 3; do
  curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
    -d "{\"title\":\"palette fixture $i\",\"markdown\":\"# $i\\n\\nbody.\\n\"}" -o /dev/null
done

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

# Open the palette in ONE step, then measure in a LATER one.
#
# Measuring straight after showModal() reads the panel MID-TRANSITION: Basecoat animates
# scale 0.95 -> 1 over 100ms, so a 606px panel measures 576 (0.95x) at an inset of 15px
# ((606-576)/2), which looks exactly like the inset bug this check exists to catch. It cost a
# false failure. The open and the measurement are deliberately separated by a wait.
OPEN='document.querySelector("#cmdk").showModal(), "opened"'
MEAS='(()=>{const p=document.querySelector("#cmdk .command");const r=p.getBoundingClientRect();
  return "GEO w="+window.innerWidth+" pw="+Math.round(r.width)+" ph="+Math.round(r.height)
       +" px="+Math.round(r.left)+" py="+Math.round(r.top)
       +" radius="+getComputedStyle(p).borderRadius;})()'

out="$(node "$here/scripts/cdp-shot.mjs" --url "http://127.0.0.1:$port/" --wait-for ".rw" \
        --resize 606x900  --wait 300 --eval "$OPEN" --wait 500 --eval "$MEAS" \
        --resize 1280x900 --wait 300 --eval "$OPEN" --wait 500 --eval "$MEAS" 2>&1)"

g(){ local s="${1#*$2=}"; echo "${s%% *}"; }
narrow="$(grep -o 'GEO w=606 [^"]*' <<<"$out" | head -1)"
wide="$(grep -o 'GEO w=1280 [^"]*' <<<"$out" | head -1)"

if [ -z "$narrow" ]; then bad "no narrow measurement"; printf '%s\n' "$out" | tail -3; else
  pw="$(g "$narrow" pw)"; px="$(g "$narrow" px)"; py="$(g "$narrow" py)"
  [ "$pw" = "606" ] && ok "606px: panel spans the full width (${pw}px)" \
    || bad "606px: panel is ${pw}px wide, not 606 — this is the exact #183 defect (was 574)"
  [ "$px" = "0" ] && ok "606px: panel starts at the left edge" \
    || bad "606px: panel left is ${px}, expected 0 (a 2rem inset means Basecoat still owns it)"
  [ "$py" = "0" ] && ok "606px: panel starts at the top edge" \
    || bad "606px: panel top is ${py}, expected 0 (was 300 — Basecoat's 33.3333%)"
  [ "$(g "$narrow" radius)" = "0px" ] && ok "606px: square corners, edge to edge" \
    || bad "606px: radius is $(g "$narrow" radius), expected 0px"
fi

if [ -z "$wide" ]; then bad "no wide measurement"; else
  pw="$(g "$wide" pw)"
  [ -n "$pw" ] && [ "$pw" -lt 1280 ] 2>/dev/null \
    && ok "1280px: panel stays centred and narrow (${pw}px), unchanged" \
    || bad "1280px: panel is ${pw}px — the full-screen rules leaked past the breakpoint"
fi

echo
[ "$fail" -eq 0 ] && echo "palette full-screen OK" || echo "palette full-screen FAILED"
exit "$fail"
