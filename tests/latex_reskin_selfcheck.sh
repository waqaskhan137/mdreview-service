#!/usr/bin/env bash
# latex_reskin_selfcheck.sh — rendered-outcome checks for the #280 latex-viewer re-skin and the
# manual comments-off rail state (design rev 3, screens 04/05).
#
# WHY COMPUTED STYLE, NOT CSS TEXT: #265's lesson — a CSS-text regex sat green for two days over a
# broken layout. Every colour assertion here compares an element's getComputedStyle against the
# SAME page's runtime resolution of the token (a hidden probe div painted with var(--token)), so
# the checks survive token revaluation while failing when a token is declared but not applied.
#
# WHAT IT PINS, and the mutation that kills each case:
#   S1 chrome surfaces (topbar/panehead/srcpane on --bg, pdfpane backdrop on --canvas (#333), iframe
#      fills .pdfwrap, Geist Mono actually loaded)         <- revert .pdfpane to var(--canvas)
#   S2 syntax + line-marker colours (.tx-c/.tx-m accent, .tx-x subtle italic, .ln.has-c tint +
#      inset accent rule, an UNcommented neighbour has neither)  <- recolour .tx-c / tint-all bug
#   S3 splitter round-trip: .src textContent == the raw source line, mark.cmt present
#                                                          <- any highlightLatex() concat break
#   S5 comments-off hide: rail display:none, codecol absorbs >=280px, pane split + divider
#      unchanged, tint+marks survive, aria-pressed mirrors <- drop the rail-off CSS / aria sync
#   S6 poll-clobber (the AC-7 trap): an out-of-band comment lands while the rail is off; #count
#      increments AND the rail stays hidden through renderComments()+layoutCards()
#                                                          <- reimplement the toggle on body.norail
#   S7 re-show: cards re-laid out (anchored AND non-overlapping) — needs the post-show
#      layoutCards() pass because cards laid out under display:none have offsetHeight 0
#                                                          <- drop the layoutCards() on re-show
#   S8/S9 diff-mode composition (#208): diff hides all of #srcscroll; the manual state survives
#      the round trip                                      <- couple rail state to diff toggling
#   S10 dark theme (explicit [data-theme=dark], the #285 arrival path): same S1/S2 equalities
#      re-resolved, and the light/dark --bg values must actually differ (guards a vacuous pass)
#   R1-R4 responsive: <640px pane forces norail regardless of the manual flag, #cmtbtn falls back
#      to the #cmtdock, a restored wide viewport restores the MANUAL state; 880px tabbar flips
#      panes and aria-pressed
#   C1 #250 Recompile survives the re-skin: a REAL failed-at-v1 compile (broken .tex over a good
#      v0), cold load -> body.compile-failed, #recompilebtn visible+enabled+token-styled, #errsum
#      names the failed and the shown revision. Read-only: the button is never clicked, matching
#      the staging fixture contract.
#
# Needs: a Chrome/Chromium binary (scripts/cdp-shot.mjs launches it headless) and a TeX toolchain
# reachable by the server (tectonic/pdflatex) for the C1 fixture; first run may download CTAN
# packages. Runs against a THROWAWAY local instance; no host, no staging, no auth.
#   bash tests/latex_reskin_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
port="${PORT_OVERRIDE:-$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')}"
data="$here/.scratch/latex_reskin_data"
rm -rf "$data"; mkdir -p "$data"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; rm -rf "$data" 2>/dev/null; return 0; }
trap cleanup EXIT

MDREVIEW_DATA="$data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" MDREVIEW_ENABLE_LATEX=1 \
  PYTHONPATH="$here/src" python3 -m mdreview >"$data/server.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = "1" ] || { echo "FAIL - server never came up on :$port"; sed -n '1,5p' "$data/server.log"; exit 1; }
base="http://127.0.0.1:$port"

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }
field(){ local s="${1#*$2=}"; echo "${s%%|*}"; }
# Extract the Nth RESULT for a marker. cdp-shot echoes each eval's SOURCE too, so grepping the
# bare marker would match the echoed code; only lines of the form  => "S1 ..."  are results.
meas(){ local out="$1" mk="$2" n="${3:-1}"; grep -o "=> \"$mk [^\"]*" <<<"$out" | sed -n "${n}p" | sed 's/^=> "//'; }

newreview(){ # $1 = json body -> id on stdout
  printf '%s' "$1" | curl -s -X POST "$base/api/reviews" -H 'Content-Type: application/json' -d @- \
    | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))'
}
waitcompile(){ # $1 = rid ; waits for a verdict (ok|failed)
  for _ in $(seq 1 180); do
    st=$(curl -s "$base/api/latex/$1/compile" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("state",""))' 2>/dev/null)
    case "$st" in ok|failed) echo "$st"; return 0;; esac
    sleep 1
  done
  echo "timeout"
}

# ---- fixtures --------------------------------------------------------------------------------
# R1: the styling/rail review. v0 then a v1 push (same body, one line reworded) so #difftoggle
# has history for the S8/S9 composition cases. Line map (1-based): 3 = \section{Model},
# 4 = text + % comment, 5 = $math$, 6 = the c2 anchor line.
# NOTE: these are the JSON-escaped forms (\\ for a TeX backslash, \n for a newline) — they are
# embedded directly into the request bodies below.
TEX_V1='\\documentclass{article}\n\\begin{document}\n\\section{Model}\nProcesses are partially synchronous. % trailing note\nLet $t_{obs} + \\delta < t_{exp}$ hold.\nMore text line six.\n\\end{document}'
TEX_V0="${TEX_V1/More text line six./More text, first cut.}"
r1=$(newreview "{\"title\":\"reskin\",\"kind\":\"latex\",\"markdown\":\"$TEX_V0\"}")
[ -n "$r1" ] || { echo "FAIL - could not create R1"; exit 1; }
printf '%s' "{\"markdown\":\"$TEX_V1\"}" | curl -s -o /dev/null -X PUT "$base/api/reviews/$r1/source" \
  -H 'Content-Type: application/json' -H 'If-Match: "0"' -d @-
# Two open comments on nearby lines so re-shown cards MUST stack (the S7 overlap assertion is
# what makes dropping the post-show layoutCards() pass fail rather than sail through).
curl -s -o /dev/null -X POST "$base/api/reviews/$r1/comments" -H 'Content-Type: application/json' \
  -d '{"anchor":{"quoted_text":"\\section{Model}","block_num":"3","start":null,"end":null},"text":"anchor one"}'
curl -s -o /dev/null -X POST "$base/api/reviews/$r1/comments" -H 'Content-Type: application/json' \
  -d '{"anchor":{"quoted_text":"More text line six.","block_num":"6","start":null,"end":null},"text":"anchor two"}'
v1=$(waitcompile "$r1")
[ "$v1" = "ok" ] || echo "  note - R1 compile state '$v1' (styling cases proceed; PDF fill still asserted)"

# C1: the failed-compile review. v0 compiles, v1 passes the #188 write guard (documentclass +
# begin{document} present) but cannot compile -> the server keeps v0's PDF: "failed at v1,
# showing v0", the same shape as the standing staging fixture (read-only there, #250).
r2=$(newreview '{"title":"reskin failed","kind":"latex","markdown":"\\documentclass{article}\n\\begin{document}\nok v0\n\\end{document}"}')
[ -n "$r2" ] || { echo "FAIL - could not create R2"; exit 1; }
[ "$(waitcompile "$r2")" = "ok" ] || echo "  note - R2 v0 compile did not reach ok"
printf '%s' '{"markdown":"\\documentclass{article}\n\\begin{document}\n\\errmessage{broken on purpose}\n\\end{document}"}' \
  | curl -s -o /dev/null -X PUT "$base/api/reviews/$r2/source" -H 'Content-Type: application/json' -H 'If-Match: "0"' -d @-
[ "$(waitcompile "$r2")" = "failed" ] || echo "  note - R2 v1 did not reach failed; C1 will say so"

url1="$base/review/$r1"; url2="$base/review/$r2"

# In-page helpers, injected as an eval PRELUDE by each measuring expression (var, not const:
# every --eval shares one page context, and a const would throw on redeclaration):
#   T(tok)  -> the token's resolved colour on this page right now (probe div, backgroundColor)
#   C(el,p) -> computed style property of el
PRE='var $q=s=>document.querySelector(s);var T=t=>{const p=document.createElement("div");p.style.cssText="display:none;background-color:var("+t+")";document.body.appendChild(p);const v=getComputedStyle(p).backgroundColor;p.remove();return v;};var C=(s,p)=>getComputedStyle($q(s)).getPropertyValue(p);'

retry_if_empty(){ # $1 = marker, rest = command (same infrastructure-only retry as comment_rail)
  local marker="$1"; shift
  local out; out="$("$@" 2>&1)"
  if ! grep -q "$marker" <<<"$out"; then
    printf '  note - no %s measurements; retrying the browser once (infrastructure, not an assertion)\n' "$marker" >&2
    out="$("$@" 2>&1)"
  fi
  printf '%s' "$out"
}

# ---- run A: styling, round-trip, rail hide / clobber / re-show, diff composition, dark -------
S1=$PRE'(()=>{const w=$q(".pdfwrap").getBoundingClientRect(),f=$q("#pdfframe").getBoundingClientRect();return "S1 top="+(C(".topbar","background-color")===T("--bg"))+"|ph="+(C(".panehead","background-color")===T("--bg"))+"|src="+(C(".srcpane","background-color")===T("--bg"))+"|pdf="+(C(".pdfpane","background-color")===T("--canvas"))+"|ifr="+($q("#pdfframe").tagName==="IFRAME"&&!!$q("#pdfframe").contentWindow)+"|fill="+(Math.abs(w.width-f.width)<=2&&Math.abs(w.height-f.height)<=2)+"|mono="+document.fonts.check("13px \"Geist Mono\"")+"|";})()'
S2=$PRE'(()=>{const acc=T("--accent"),sub=T("--text-subtle"),am=T("--accent-muted");const P=t=>{const p=document.createElement("div");p.style.cssText="display:none;color:var("+t+")";document.body.appendChild(p);const v=getComputedStyle(p).color;p.remove();return v;};const c=$q(".tx-c"),m=$q(".tx-m"),x=$q(".tx-x");const hc=$q(".ln.has-c"),nb=$q(".ln:not(.has-c)");const hcs=getComputedStyle(hc),nbs=getComputedStyle(nb);return "S2 c="+(getComputedStyle(c).color===P("--accent"))+"|m="+(getComputedStyle(m).color===P("--accent"))+"|x="+(getComputedStyle(x).color===P("--text-subtle")&&getComputedStyle(x).fontStyle==="italic")+"|hc="+(hcs.backgroundColor===am&&hcs.boxShadow.includes("inset"))+"|nb="+(nbs.backgroundColor!==am&&!nbs.boxShadow.includes("inset"))+"|";})()'
S3=$PRE'(()=>{const ln=$q(".ln[data-num=\"3\"]");return "S3 b64="+btoa(ln.querySelector(".src").textContent)+"|mark="+(!!ln.querySelector("mark.cmt"))+"|";})()'
S4=$PRE'(()=>{return "S4 railW="+Math.round($q(".railcol").getBoundingClientRect().width)+"|codeW="+Math.round($q("#codecol").getBoundingClientRect().width)+"|paneB="+C(".srcpane","flex-basis")+"|divX="+Math.round($q("#vdiv").getBoundingClientRect().left)+"|aria="+$q("#cmtbtn").getAttribute("aria-pressed")+"|count="+$q("#count").textContent+"|";})()'
S5=$PRE'(()=>{const am=T("--accent-muted");return "S5 raild="+C(".railcol","display")+"|codeW="+Math.round($q("#codecol").getBoundingClientRect().width)+"|paneB="+C(".srcpane","flex-basis")+"|divX="+Math.round($q("#vdiv").getBoundingClientRect().left)+"|aria="+$q("#cmtbtn").getAttribute("aria-pressed")+"|hc="+(getComputedStyle($q(".ln.has-c")).backgroundColor===am)+"|marks="+document.querySelectorAll("mark.cmt").length+"|"; })()'
# The clobber comment is deliberately hostile: block_num is a JSON NUMBER with no matching line,
# the shape API/MCP authors actually send. Without the String() guard in escapeHtml (the #279
# escape bug, shared by this file), renderComments() dies mid-pass on it and #count never updates.
POST='(fetch("/api/reviews/"+location.pathname.split("/").pop()+"/comments",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({anchor:{quoted_text:null,block_num:999,start:null,end:null},text:"clobber probe"})}),true)'
S6=$PRE'(()=>{return "S6 count="+$q("#count").textContent+"|raild="+C(".railcol","display")+"|noRail="+document.body.classList.contains("norail")+"|railOff="+document.body.classList.contains("rail-off")+"|";})()'
S7=$PRE'(()=>{const cards=[...document.querySelectorAll("#railcol .gcard")].sort((a,b)=>a.offsetTop-b.offsetTop);const anch=cards.length>=3&&cards.every(c=>!c._anchor||c.offsetTop>=c._anchor.offsetTop);const stack=cards.length>=3&&cards.slice(1).every((c,i)=>c.offsetTop>=cards[i].offsetTop+cards[i].offsetHeight);return "S7 raild="+C(".railcol","display")+"|aria="+$q("#cmtbtn").getAttribute("aria-pressed")+"|n="+cards.length+"|anch="+anch+"|stack="+stack+"|";})()'
S8=$PRE'(()=>{return "S8 srch="+$q("#srcscroll").hidden+"|diffh="+$q("#texdiffpane").hidden+"|";})()'
S9=$PRE'(()=>{return "S9 srch="+$q("#srcscroll").hidden+"|raild="+C(".railcol","display")+"|";})()'
S10=$PRE'(()=>{document.documentElement.dataset.theme="light";const lightBg=T("--bg");document.documentElement.dataset.theme="dark";const P=t=>{const p=document.createElement("div");p.style.cssText="display:none;color:var("+t+")";document.body.appendChild(p);const v=getComputedStyle(p).color;p.remove();return v;};return "S10 flip="+(T("--bg")!==lightBg)+"|top="+(C(".topbar","background-color")===T("--bg"))+"|pdf="+(C(".pdfpane","background-color")===T("--canvas"))+"|c="+(getComputedStyle($q(".tx-c")).color===P("--accent"))+"|hc="+(getComputedStyle($q(".ln.has-c")).backgroundColor===T("--accent-muted"))+"|raild="+C(".railcol","display")+"|";})()'

runA="$(retry_if_empty '=> "S1 ' node "$here/scripts/cdp-shot.mjs" --url "$url1" \
  --resize 1500x900 --wait-for ".ln[data-num='3']" --wait-for "#railcol .gcard" --wait 700 \
  --eval "$S1" --eval "$S2" --eval "$S3" --eval "$S4" \
  --click "#cmtbtn" --wait 300 --eval "$S5" \
  --eval "$POST" --wait 5500 --eval "$S6" \
  --click "#cmtbtn" --wait 400 --eval "$S7" \
  --click "#cmtbtn" --wait 200 --click "#difftoggle" --wait 700 --eval "$S8" \
  --click "#difftoggle" --wait 300 --eval "$S9" \
  --eval "$S10")"
[ -n "${RESKIN_DEBUG:-}" ] && printf '%s\n' "$runA" > "$here/.scratch/reskin-runA.log"

m1="$(meas "$runA" S1)"
if [ -z "$m1" ]; then bad "S1: no measurement (browser step failed)"; echo "$runA" | tail -5; else
  case "$m1" in *"top=true|ph=true|src=true|pdf=true|ifr=true|fill=true|mono=true"*) ok "S1: chrome surfaces on --bg, PDF backdrop on --canvas, iframe fills .pdfwrap, Geist Mono loaded";;
    *) bad "S1: $m1";; esac
fi
m2="$(meas "$runA" S2)"
if [ -z "$m2" ]; then bad "S2: no measurement"; else
  case "$m2" in *"c=true|m=true|x=true|hc=true|nb=true"*) ok "S2: .tx-c/.tx-m accent, .tx-x subtle italic, .ln.has-c tint+rule, neighbour clean";;
    *) bad "S2: $m2";; esac
fi
m3="$(meas "$runA" S3)"
if [ -z "$m3" ]; then bad "S3: no measurement"; else
  got="$(field "$m3" b64 | python3 -c 'import sys,base64;print(base64.b64decode(sys.stdin.read().strip()).decode())')"
  want="$(curl -s "$base/api/reviews/$r1/source" | sed -n '3p')"
  [ "$got" = "$want" ] && ok "S3: .src textContent round-trips the raw source line ('$want')" \
    || bad "S3: textContent '$got' != raw line '$want' (highlightLatex concat contract broken)"
  [ "$(field "$m3" mark)" = "true" ] && ok "S3: mark.cmt present inside the commented line" \
    || bad "S3: no mark.cmt inside L3 (offset mapping failed)"
fi
m4="$(meas "$runA" S4)"
railW="$(field "$m4" railW)"; codeW0="$(field "$m4" codeW)"; paneB0="$(field "$m4" paneB)"; divX0="$(field "$m4" divX)"
if [ -z "$m4" ]; then bad "S4: no baseline measurement"; else
  [ "$railW" -ge 290 ] 2>/dev/null && [ "$railW" -le 300 ] && ok "S4: rail baseline ~296px (${railW}px), 2 open" \
    || bad "S4: rail baseline ${railW}px, expected ~296 — $m4"
  [ "$(field "$m4" aria)" = "true" ] && ok "S4: aria-pressed=true with the rail shown" || bad "S4: aria-pressed != true — $m4"
fi
m5="$(meas "$runA" S5)"
if [ -z "$m5" ]; then bad "S5: no measurement"; else
  [ "$(field "$m5" raild)" = "none" ] && ok "S5: one #cmtbtn click hides the rail (display:none)" || bad "S5: rail display '$(field "$m5" raild)' — $m5"
  codeW1="$(field "$m5" codeW)"
  [ $((codeW1 - codeW0)) -ge 280 ] 2>/dev/null && ok "S5: #codecol absorbed the freed width (+$((codeW1-codeW0))px)" \
    || bad "S5: codecol ${codeW0}->${codeW1}px, expected +>=280"
  { [ "$(field "$m5" paneB)" = "$paneB0" ] && [ "$(field "$m5" divX)" = "$divX0" ]; } && ok "S5: pane split and divider unchanged" \
    || bad "S5: pane/divider moved (basis $paneB0->$(field "$m5" paneB), divX $divX0->$(field "$m5" divX))"
  [ "$(field "$m5" hc)" = "true" ] && [ "$(field "$m5" marks)" -ge 1 ] 2>/dev/null && ok "S5: has-c tint and mark.cmt survive with the rail off" \
    || bad "S5: line markers lost with the rail off — $m5"
  [ "$(field "$m5" aria)" = "false" ] && ok "S5: aria-pressed=false with the rail off" || bad "S5: aria-pressed != false — $m5"
fi
m6="$(meas "$runA" S6)"
if [ -z "$m6" ]; then bad "S6: no measurement"; else
  [ "$(field "$m6" count)" = "3 open" ] && ok "S6: the out-of-band comment landed through the poll (3 open)" \
    || bad "S6: count '$(field "$m6" count)', expected '3 open' (poll never repainted, or renderComments died on the numeric anchor — the #279 escape bug)"
  { [ "$(field "$m6" raild)" = "none" ] && [ "$(field "$m6" railOff)" = "true" ] && [ "$(field "$m6" noRail)" = "false" ]; } \
    && ok "S6: rail STAYED hidden through the poll repaint (rail-off held; norail untouched) — the AC-7 clobber trap" \
    || bad "S6: rail reappeared after the poll repaint (the naive body.norail implementation) — $m6"
fi
m7="$(meas "$runA" S7)"
if [ -z "$m7" ]; then bad "S7: no measurement"; else
  [ "$(field "$m7" raild)" != "none" ] && ok "S7: second click restores the rail" || bad "S7: rail still hidden — $m7"
  { [ "$(field "$m7" anch)" = "true" ] && [ "$(field "$m7" stack)" = "true" ]; } \
    && ok "S7: cards re-laid out after re-show (anchored, non-overlapping)" \
    || bad "S7: stale card layout after re-show (missing post-show layoutCards) — $m7"
  [ "$(field "$m7" aria)" = "true" ] && ok "S7: aria-pressed back to true" || bad "S7: aria-pressed — $m7"
fi
m8="$(meas "$runA" S8)"
[ -n "$m8" ] && case "$m8" in *"srch=true|diffh=false"*) ok "S8: diff mode hides all of #srcscroll (rail with it), diff pane shows";;
  *) bad "S8: $m8";; esac
[ -z "$m8" ] && bad "S8: no measurement"
m9="$(meas "$runA" S9)"
[ -n "$m9" ] && case "$m9" in *"srch=false|raild=none"*) ok "S9: source view returns with the manual rail state STILL off";;
  *) bad "S9: $m9";; esac
[ -z "$m9" ] && bad "S9: no measurement"
m10="$(meas "$runA" S10)"
[ -n "$m10" ] && case "$m10" in *"flip=true|top=true|pdf=true|c=true|hc=true|raild=none"*) ok "S10: dark theme re-resolves every equality (and really flipped); rail state survives";;
  *) bad "S10: $m10";; esac
[ -z "$m10" ] && bad "S10: no measurement"

# ---- run B: responsive floor + tabbar --------------------------------------------------------
R1=$PRE'(()=>{return "RB1 noRail="+document.body.classList.contains("norail")+"|raild="+C(".railcol","display")+"|";})()'
R2=$PRE'(()=>{return "RB2 noRail="+document.body.classList.contains("norail")+"|raild="+C(".railcol","display")+"|dock="+$q("#cmtdock").classList.contains("show")+"|aria="+$q("#cmtbtn").getAttribute("aria-pressed")+"|";})()'
R3=$PRE'(()=>{return "RB3 noRail="+document.body.classList.contains("norail")+"|raild="+C(".railcol","display")+"|railOff="+document.body.classList.contains("rail-off")+"|";})()'
R4=$PRE'(()=>{return "RB4 tab="+C(".tabbar","display")+"|srcd="+C(".srcpane","display")+"|ariaPdf="+$q("#tab-pdf").getAttribute("aria-pressed")+"|";})()'
R5=$PRE'(()=>{return "RB5 srcd="+C(".srcpane","display")+"|ariaSrc="+$q("#tab-src").getAttribute("aria-pressed")+"|";})()'
runB="$(retry_if_empty '=> "RB1 ' node "$here/scripts/cdp-shot.mjs" --url "$url1" \
  --resize 1500x900 --wait-for ".ln[data-num='3']" --wait 500 --eval "$R1" \
  --click "#cmtbtn" --wait 200 \
  --resize 1000x800 --wait 500 --eval "$R2" \
  --click "#cmtbtn" --wait 200 --eval "$R2" \
  --click "#cmtbtn" --wait 200 \
  --resize 1500x900 --wait 500 --eval "$R3" \
  --resize 800x900 --wait 500 --click "#tab-pdf" --wait 300 --eval "$R4" \
  --click "#tab-src" --wait 300 --eval "$R5")"

b1="$(meas "$runB" RB1)"
[ -n "$b1" ] && case "$b1" in *"noRail=false"*) ok "RB1: wide viewport, responsive norail off, rail visible";; *) bad "RB1: $b1";; esac
[ -z "$b1" ] && bad "RB1: no measurement"
b2a="$(meas "$runB" RB2)"; b2b="$(meas "$runB" RB2 2)"
if [ -n "$b2a" ] && [ -n "$b2b" ]; then
  { [ "$(field "$b2a" noRail)" = "true" ] && [ "$(field "$b2a" raild)" = "none" ]; } \
    && ok "RB2: <640px pane forces the rail hidden (responsive norail)" || bad "RB2: $b2a"
  { [ "$(field "$b2a" dock)" = "false" ] && [ "$(field "$b2b" dock)" = "true" ] && [ "$(field "$b2b" aria)" = "true" ]; } \
    && ok "RB2: narrow #cmtbtn toggles #cmtdock exactly as before (aria follows the dock)" \
    || bad "RB2: narrow dock toggle broken — $b2a / $b2b"
else bad "RB2: missing measurements"; fi
b3="$(meas "$runB" RB3)"
[ -n "$b3" ] && case "$b3" in *"noRail=false|raild=none|railOff=true"*) ok "RB3: restored wide viewport restores the MANUAL state (still off)";;
  *) bad "RB3: manual state lost across the responsive round trip — $b3";; esac
[ -z "$b3" ] && bad "RB3: no measurement"
b4="$(meas "$runB" RB4)"
[ -n "$b4" ] && case "$b4" in *"tab=flex|srcd=none|ariaPdf=true"*) ok "RB4: 880px tabbar shows; PDF tab hides the source pane, aria flips";;
  *) bad "RB4: $b4";; esac
[ -z "$b4" ] && bad "RB4: no measurement"
b5="$(meas "$runB" RB5)"
[ -n "$b5" ] && case "$b5" in *"srcd=flex|ariaSrc=true"*) ok "RB5: Source tab restores the source pane";; *) bad "RB5: $b5";; esac
[ -z "$b5" ] && bad "RB5: no measurement"

# ---- run C: #250 Recompile after a REAL failed compile (cold load, read-only) ----------------
# #286 restructured the failure card: #errsum is gone, replaced by #errhead (the D2 headline) and
# #errline (the mono line retaining #205's failed/shown revision detail plus the first l.NNN log
# line). Everything else C1 pins (recompilebtn styling, diff pill) is untouched by that ticket.
C1=$PRE'(()=>{const rb=$q("#recompilebtn"),s=getComputedStyle(rb);const rc=(()=>{const p=document.createElement("div");p.style.cssText="display:none;border-radius:var(--r-control)";document.body.appendChild(p);const v=getComputedStyle(p).borderRadius;p.remove();return v;})();return "C1 failed="+document.body.classList.contains("compile-failed")+"|vis="+(s.display!=="none")+"|en="+(!rb.disabled)+"|rad="+(s.borderRadius===rc)+"|bg="+(s.backgroundColor===T("--surface"))+"|bord="+(s.borderTopColor===(()=>{const p=document.createElement("div");p.style.cssText="display:none;color:var(--border)";document.body.appendChild(p);const v=getComputedStyle(p).color;p.remove();return v;})())+"|dt="+(getComputedStyle($q("#difftoggle")).display!=="none")+"|head="+btoa(unescape(encodeURIComponent($q("#errhead").textContent)))+"|line="+btoa(unescape(encodeURIComponent($q("#errline").textContent)))+"|";})()'
runC="$(retry_if_empty '=> "C1 ' node "$here/scripts/cdp-shot.mjs" --url "$url2" \
  --resize 1500x900 --wait-for ".ln" --wait 1500 --eval "$C1")"
c1="$(meas "$runC" C1)"
if [ -z "$c1" ]; then bad "C1: no measurement"; else
  case "$c1" in *"failed=true|vis=true|en=true|rad=true|bg=true|bord=true|dt=true"*)
      ok "C1: cold-load failed compile -> #recompilebtn visible, enabled, token-styled; diff pill visible (history exists)";;
    *) bad "C1: $c1";; esac
  head="$(field "$c1" head | python3 -c 'import sys,base64;print(base64.b64decode(sys.stdin.read().strip()).decode("utf-8"))' 2>/dev/null)"
  line="$(field "$c1" line | python3 -c 'import sys,base64;print(base64.b64decode(sys.stdin.read().strip()).decode("utf-8"))' 2>/dev/null)"
  [ "$head" = "Compile failed — the last good PDF is still shown." ] \
    && ok "C1: #errhead reads the #286/D2 headline ('$head')" \
    || bad "C1: #errhead '$head', expected the D2 headline verbatim"
  case "$line" in "v1 failed"*"showing v0"*) ok "C1: #errline retains #205's failed/shown revisions ('$line')";;
    *) bad "C1: #errline '$line', expected 'v1 failed ... showing v0 ...'";; esac
fi

# ---- run D: fresh review (no agent push): the Diff pill stays hidden -------------------------
# theme.css's shared .difftoggle{display:inline-flex} is an author rule and beats the UA's
# [hidden]{display:none}; without the page's .difftoggle[hidden] gate the pill renders on every
# fresh review (#279 found it on the viewer; the shared rule bites this page identically).
r3=$(newreview '{"title":"reskin fresh","kind":"latex","markdown":"\\documentclass{article}\n\\begin{document}\nfresh, no history\n\\end{document}"}')
[ -n "$r3" ] || { echo "FAIL - could not create R3"; exit 1; }
D1=$PRE'(()=>{const d=$q("#difftoggle");return "D1 hid="+d.hidden+"|disp="+getComputedStyle(d).display+"|";})()'
runD="$(retry_if_empty '=> "D1 ' node "$here/scripts/cdp-shot.mjs" --url "$base/review/$r3" \
  --resize 1500x900 --wait-for ".ln" --wait 800 --eval "$D1")"
d1="$(meas "$runD" D1)"
if [ -z "$d1" ]; then bad "D1: no measurement"; else
  case "$d1" in *"hid=true|disp=none"*) ok "D1: fresh review, Diff pill hidden AND computed display:none (the [hidden] gate holds against theme.css)";;
    *) bad "D1: Diff pill visible on a fresh review (hidden attribute defeated by theme.css's .difftoggle display rule) — $d1";; esac
fi

echo
[ "$fail" -eq 0 ] && echo "all #280 re-skin cases pass" || echo "#280 re-skin check FAILED"
exit "$fail"
