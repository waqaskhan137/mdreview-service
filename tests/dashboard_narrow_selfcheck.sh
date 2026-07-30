#!/usr/bin/env bash
# dashboard_narrow_selfcheck.sh — the dashboard's narrow pass (#184).
#
# BASELINE, measured in a real Chrome window at the real floor (W_min = 606px — a fresh window
# asked for 380 stops there on this display): .rw 38px, .rw-l 20px, .filt 22px, headline 32px.
# §10 rule 01 wants 44px hit targets; the fix adds them under @media (max-width:720px).
#
# REV 3 (#278) SUPERSEDED two of the geometry expectations here — a declared decision in the
# ticket, not a quiet green: the 32px-wide / 24px-narrow headline ramp became a 20px hero title
# at EVERY width (the mock's value; the ramp is gone with the display-size headline it stepped),
# and wide rows are no longer "compact, under 44px" but >= 52px min-height (the mock's row slab).
# The 44px floors and the no-horizontal-scroll assertion survive verbatim.
#
# THIS IS THE REGRESSION CHECK (G2 item 7), driven headlessly via cdp-shot --resize, the same
# split #199 recorded: the check proves the CSS logic at exact widths; STAGE 8 is separately the
# claude-in-chrome extension with a real window, and this file is not a substitute for it.
#
# Three width classes, because each catches a different way the media block can be wrong:
#   606  = W_min       -> narrow treatment ACTIVE (this is what stage 8 can reach)
#   1400 = wide        -> narrow treatment must NOT leak (wide layout byte-identical intent)
#
#   bash tests/dashboard_narrow_selfcheck.sh    # exit 0 = pass
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
[ "$up" = "1" ] || { echo "FAIL - server never came up"; exit 1; }

# Rows need to exist for .rw to be measurable; the local build shows the app (#224 noAuthPlane).
curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"narrow one","markdown":"# One\n\nA.\n"}' -o /dev/null
curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
  -d '{"title":"narrow two","markdown":"# Two\n\nB.\n"}' -o /dev/null
url="http://127.0.0.1:$port/"

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

M='(()=>{const mn=s=>{const e=[...document.querySelectorAll(s)];return e.length?Math.round(Math.min(...e.map(x=>x.getBoundingClientRect().height))):-1};return "MEAS w="+window.innerWidth+" rw="+mn(".rw")+" rwl="+mn(".rw-l")+" filt="+mn(".filt")+" title="+getComputedStyle(document.querySelector(".nu-title")).fontSize+" hscroll="+(document.documentElement.scrollWidth<=window.innerWidth);})()'

out="$(node "$here/scripts/cdp-shot.mjs" --url "$url" --wait-for ".rw" \
        --resize 606x900 --wait 400 --eval "$M" \
        --resize 1400x900 --wait 400 --eval "$M" 2>&1)"

narrow="$(grep -o 'MEAS w=606 [^"]*' <<<"$out" | head -1)"
wide="$(grep -o 'MEAS w=1400 [^"]*' <<<"$out" | head -1)"
field(){ local s="${1#*$2=}"; echo "${s%% *}"; }

if [ -z "$narrow" ]; then bad "no narrow measurement"; printf '%s\n' "$out" | tail -3; else
  for pair in "rw:44" "rwl:44" "filt:44"; do
    k=${pair%%:*}; want=${pair##*:}; got="$(field "$narrow" "$k")"
    [ -n "$got" ] && [ "$got" -ge "$want" ] 2>/dev/null \
      && ok "606px: .$k tap height ${got}px >= ${want}" \
      || bad "606px: .$k is ${got}px, needs >= ${want} (baseline was 38/20/22)"
  done
  [ "$(field "$narrow" title)" = "20px" ] && ok "606px: hero title at rev 3's 20px" \
    || bad "606px: hero title is $(field "$narrow" title), expected 20px (rev 3: no ramp, 20 everywhere)"
  [ "$(field "$narrow" hscroll)" = "true" ] && ok "606px: no horizontal scrollbar" \
    || bad "606px: horizontal scrollbar present"
fi

if [ -z "$wide" ]; then bad "no wide measurement"; else
  # Rev 3 (#278): one 20px hero title at every width, and 52px row slabs at wide.
  [ "$(field "$wide" title)" = "20px" ] && ok "1400px: hero title at rev 3's 20px" \
    || bad "1400px: hero title is $(field "$wide" title), expected 20px (rev 3: no ramp, 20 everywhere)"
  got="$(field "$wide" rw)"
  [ -n "$got" ] && [ "$got" -ge 52 ] 2>/dev/null \
    && ok "1400px: rows are rev-3 slabs (${got}px >= 52)" \
    || bad "1400px: rows are ${got}px, rev 3 wants >= 52 (mock min-height)"
fi

echo
[ "$fail" -eq 0 ] && echo "all narrow-pass cases pass" || echo "narrow-pass check FAILED"
exit "$fail"
