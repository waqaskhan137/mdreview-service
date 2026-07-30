#!/usr/bin/env bash
# viewer_polish_selfcheck.sh — the #279 viewer re-skin, verified as RENDERED OUTCOMES (#265's
# lesson: never assert that a declaration exists; assert what the browser computed).
#
# WHAT IT GUARDS (the #279 acceptance criteria that are measurable on the local tier):
#   typography  — #article p is Source Serif 4 18px/30.6px with the FACE APPLIED (fonts.check),
#                 #article h2 is sentence-case Geist, #doctitle is serif 40px/600 (AC 1-3)
#   markers     — #article li keeps its list marker and NO stylesheet is Basecoat: the viewer is
#                 deliberately off Basecoat (its preflight strips list markers) (AC 4)
#   highlight   — mark.cmt computes a background that differs from the page and carries the inset
#                 accent underline (AC 5)
#   cards       — initials chip + label + relative time; role agent -> "Agent"; on the LOCAL tier
#                 (no /auth/session route) reviewer entries read "You"; under a SYNTHESISED hosted
#                 session an entry authored by someone else must NOT read "You" (AC 6-7)
#   composer    — dashed accent border, visible ⌘↵ hint, and the click path still posts (AC 9)
#   state       — resolve moves the card out of the rail on the next poll; Reopen returns it; no
#                 in-rail "addressed" state exists (AC 10)
#   dock        — bottom-CENTRE fixed (scroll-invariant), computed translucency (alpha strictly
#                 0..1 + backdrop blur), open-count-only pill, total height <= 46px, and measured
#                 NON-INTERSECTION with #gutter.docked / #pop.docked / #resolved, which sit at
#                 bottom:70px precisely to clear it (AC 12-14, 16-17)
#   counters    — rail header, dock pill, Resolved segment and the title meta line agree after one
#                 render pass, before and after posting through the click path (AC 23)
#
# WHY MEASUREMENT STRINGS, NOT --eval ASSERTIONS: each browser step RETURNS a "KEY k=v ..." line
# and bash asserts on the parsed fields, so a regression fails with a named finding (which value,
# what it was, what it had to be) instead of a generic "eval returned falsy" crash.
#
# Runs against a throwaway local instance on an ephemeral port. Two browser launches total (the
# comment_rail lesson: many launches -> launch-contention flakes).
#   bash tests/viewer_polish_selfcheck.sh     # exit 0 = pass
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

# Fixture: front-matter title (doctitle + filename fallback — NO provenance keys on purpose, the
# AC-19 legacy case), a paragraph/h2/ul/blockquote/fenced code for the type checks, and enough
# padding paragraphs that 800px viewports genuinely scroll (the dock's scroll-invariance check).
mdfile="$tmp/fixture.md"
{
  printf -- '---\ntitle: Fixture doc\n---\n\n# Magic-link rate limiting\n\n'
  printf 'The server is the only enforcer of the send limit.\n\n## Where the limit lives\n\n'
  printf 'Three links per address per fifteen minutes, counted against the address.\n\n'
  printf -- '> A response body that varies with rate state is an enumeration oracle.\n\n'
  printf -- '- one marker\n- two markers\n\n```python\nmax_per_address = 3\n```\n\n'
  for i in $(seq 1 14); do printf 'Padding paragraph %s so an 800px viewport scrolls well past one screen.\n\n' "$i"; done
} > "$mdfile"
rid=$(python3 -c 'import sys,json,urllib.request
md=open(sys.argv[1]).read()
req=urllib.request.Request("http://127.0.0.1:"+sys.argv[2]+"/api/reviews",
  data=json.dumps({"title":"Fixture doc","markdown":md}).encode(),headers={"Content-Type":"application/json"})
print(json.load(urllib.request.urlopen(req)).get("id",""))' "$mdfile" "$port")
[ -n "$rid" ] || { echo "FAIL - could not create the fixture review"; exit 1; }
url="http://127.0.0.1:$port/review/$rid"
api="http://127.0.0.1:$port/api/reviews/$rid"

# Rendered block numbering: 1 h1, 2 p, 3 h2, 4 p(quoted target), 5 blockquote, 6 ul, 7 pre, 8.. padding.
cid=$(curl -s -X POST "$api/comments" -H 'Content-Type: application/json' \
  -d '{"anchor":{"block_num":4,"quoted_text":"Three links per address"},"text":"Is the window sliding or fixed?"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["comment_id"])')
[ -n "$cid" ] || { echo "FAIL - could not create the fixture comment"; exit 1; }
curl -s -o /dev/null -X POST "$api/comments/$cid/reply" -H 'Content-Type: application/json' \
  -d '{"text":"Sliding — rewrote the paragraph.","role":"agent"}'

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }
field(){ local s="${1#*$2=}"; echo "${s%% *}"; }
# Measurement lines are taken ONLY from cdp-shot RESULTS (the `=> "KEY ..."` tail) — grepping for
# the bare marker would also match the echoed eval EXPRESSION, whose string literals contain it.
line(){ grep -o "=> \"$2 [^\"]*" <<<"$1" | head -1 | sed 's/^=> "//'; }
lines(){ grep -o "=> \"$2 [^\"]*" <<<"$1" | sed 's/^=> "//'; }

retry_if_empty(){  # $1 = marker, rest = command (infrastructure retry ONLY — see comment_rail)
  local marker="$1"; shift
  local out; out="$("$@" 2>&1)"
  if ! grep -q "$marker" <<<"$out"; then
    printf '  note - no %s measurements; retrying the browser once (infrastructure, not an assertion)\n' "$marker" >&2
    out="$("$@" 2>&1)"
  fi
  printf '%s' "$out"
}

# ---- phase 1: wide viewport (1400x900) — typography, chrome, labels, composer, counters --------
TYPO='(async()=>{await document.fonts.ready;
const p=getComputedStyle(document.querySelector("#article p"));
const h2=getComputedStyle(document.querySelector("#article h2"));
const t=getComputedStyle(document.querySelector("#doctitle"));
const li=getComputedStyle(document.querySelector("#article li"));
const mk=getComputedStyle(document.querySelector("mark.cmt"));
const fam=s=>s.split(",")[0].replace(/"/g,"").trim().replace(/ /g,"_");
const alphaOf=c=>{const m=c.match(/^rgba\([^)]*,\s*([0-9.]+)\)/)||c.match(/\/\s*([0-9.]+)\)/);return m?m[1]:"1";};
const bga=alphaOf(mk.backgroundColor);
return "TYPO pfs="+p.fontSize+" plh="+p.lineHeight+" pfam="+fam(p.fontFamily)
 +" face="+document.fonts.check("18px \"Source Serif 4\"")
 +" h2tt="+h2.textTransform+" h2fam="+fam(h2.fontFamily)
 +" tfs="+t.fontSize+" tfw="+t.fontWeight+" tfam="+fam(t.fontFamily)
 +" li="+li.listStyleType+" bc="+[...document.styleSheets].some(s=>/basecoat/i.test(s.href||""))
 +" mkbg="+mk.backgroundColor.replace(/ /g,"")+" mka="+bga+" mksh="+(mk.boxShadow!=="none")
 +" pagebg="+getComputedStyle(document.body).backgroundColor.replace(/ /g,"");})()'
CHROME='(()=>{const chip=document.querySelector(".kindchip");
return "CHROME chip="+(chip?chip.textContent:"MISSING")
 +" fname="+document.querySelector("#filename").textContent.replace(/ /g,"_")
 +" eyebrow="+(document.querySelector("#breadcrumb").textContent||"EMPTY").replace(/ /g,"_")
 +" turn="+/Your turn/.test(document.querySelector("#docmeta").textContent)
 +" words="+/\d[\d,]* words/.test(document.querySelector("#docmeta").textContent)
 +" toggleslot="+!!document.querySelector("#sharebtn")+" acct="+!!document.querySelector("#acct");})()'
LAB='(()=>{const card=document.querySelector("#gutter .gcard");
const whos=[...card.querySelectorAll(".gwho")].map(x=>x.textContent).join("|");
const avs=[...card.querySelectorAll(".gav")].map(x=>x.textContent).join("|");
const ts=[...card.querySelectorAll(".gts")].map(x=>x.textContent.trim().length>0).join("|");
return "LAB whos="+whos+" avs="+avs+" ts="+ts;})()'
HOST='(()=>{const S=SESSION;
SESSION={tier:"hosted",uid:"user:someoneelse",email:"x@y.z"};renderAll();
const w1=[...document.querySelector("#gutter .gcard").querySelectorAll(".gwho")].map(x=>x.textContent).join("|");
SESSION={tier:"hosted",uid:"reviewer",email:""};renderAll();
const w2=[...document.querySelector("#gutter .gcard").querySelectorAll(".gwho")].map(x=>x.textContent).join("|");
SESSION=S;renderAll();
return "HOST other="+w1+" self="+w2;})()'
POPS='(()=>{const p=getComputedStyle(document.querySelector("#pop"));
const probe=document.createElement("i");probe.style.color="var(--accent)";document.body.appendChild(probe);
const acc=getComputedStyle(probe).color;probe.remove();
const k=document.querySelector("#pop .popkbd");
return "POPS bstyle="+p.borderTopStyle+" bacc="+(p.borderTopColor===acc)
 +" kbd="+(!!k&&k.offsetWidth>0&&/⌘/.test(k.textContent))+" addressed="+!!document.querySelector(".gcard.addressed");})()'
CNT='(()=>{const cards=document.querySelectorAll("#gutter .gcard").length;
const hdr=(document.querySelector("#gutter .gcount")||{textContent:"MISSING"}).textContent.replace(/ /g,"_");
const cnt=document.querySelector("#count").textContent.trim().replace(/ /g,"_");
const res=document.querySelector("#resbtn").textContent.trim().replace(/ /g,"_");
const meta=((document.querySelector("#opencmt")||{}).textContent||"MISSING").replace(/ /g,"_");
const gon=document.body.classList.contains("gutter-on");
const cbtn=getComputedStyle(document.querySelector("#cmtbtn")).display;
return "CNT cards="+cards+" hdr="+hdr+" cnt="+cnt+" res="+res+" meta="+meta+" gon="+gon+" cbtn="+cbtn;})()'
RC='(()=>{return "RC rcards="+document.querySelectorAll("#resolved .rcard").length
 +" shown="+(document.querySelector("#resolved").style.display==="block");})()'

# resolve fires from INSIDE the page mid-session so the live comment poll is what moves the card
RESOLVE='(async()=>{const r=await fetch("'"$api"'/comments/'"$cid"'/resolve",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});return "RES ok="+r.ok;})()'

p1="$(retry_if_empty TYPO node "$here/scripts/cdp-shot.mjs" --url "$url" \
  --resize 1400x900 --wait-for "mark.cmt" --wait 500 \
  --eval "$TYPO" --eval "$CHROME" --eval "$LAB" --eval "$HOST" --eval "$CNT" \
  --wait-for ".blk:nth-of-type(9) .num" --click ".blk:nth-of-type(9) .num" --wait 300 \
  --eval "$POPS" --type "#popnote=Counter check" --click "#popsave" --wait 800 --eval "$CNT" \
  --eval "$RESOLVE" --wait 4600 --eval "$CNT" \
  --click "#resbtn" --wait 300 --eval "$RC" \
  --click "#resolved .rcard [data-act=reopen]" --wait 800 --eval "$CNT")"

m="$(line "$p1" TYPO)"
if [ -z "$m" ]; then bad "typography: no measurement (browser step failed)"; else
  [ "$(field "$m" pfs)" = "18px" ] && ok "AC1: body paragraph 18px" || bad "AC1: paragraph font-size $(field "$m" pfs), expected 18px"
  plh="$(field "$m" plh)"; plhn="${plh%px}"
  awk "BEGIN{exit !($plhn>=30.0 && $plhn<=31.2)}" && ok "AC1: line-height $plh (30.6 ±0.6)" || bad "AC1: line-height $plh outside 30.0–31.2px"
  [ "$(field "$m" pfam)" = "Source_Serif_4" ] && ok "AC1: first family Source Serif 4" || bad "AC1: first family $(field "$m" pfam)"
  [ "$(field "$m" face)" = "true" ] && ok "AC1: Source Serif 4 face APPLIED (fonts.check)" || bad "AC1: fonts.check says the serif face never loaded"
  [ "$(field "$m" h2tt)" = "none" ] && ok "AC2: h2 sentence case (text-transform none)" || bad "AC2: h2 text-transform $(field "$m" h2tt) — the uppercase eyebrow is back"
  [ "$(field "$m" h2fam)" = "Geist" ] && ok "AC2: h2 first family Geist" || bad "AC2: h2 family $(field "$m" h2fam)"
  [ "$(field "$m" tfs)" = "40px" ] && [ "$(field "$m" tfw)" = "600" ] && [ "$(field "$m" tfam)" = "Source_Serif_4" ] \
    && ok "AC3: doctitle serif 40px/600" || bad "AC3: doctitle $(field "$m" tfam) $(field "$m" tfs)/$(field "$m" tfw), expected Source_Serif_4 40px/600"
  [ "$(field "$m" li)" != "none" ] && ok "AC4: list markers intact (list-style-type $(field "$m" li))" \
    || bad "AC4: li list-style-type none — Basecoat's preflight symptom"
  [ "$(field "$m" bc)" = "false" ] && ok "AC4: no Basecoat stylesheet on /review/*" || bad "AC4: a stylesheet href matches /basecoat/i"
  [ "$(field "$m" mkbg)" != "$(field "$m" pagebg)" ] && awk "BEGIN{exit !($(field "$m" mka)>0)}" \
    && ok "AC5: mark.cmt background differs from the page (alpha $(field "$m" mka))" \
    || bad "AC5: mark.cmt background $(field "$m" mkbg) vs page $(field "$m" pagebg) (alpha $(field "$m" mka))"
  [ "$(field "$m" mksh)" = "true" ] && ok "AC5: mark.cmt carries the inset accent underline" || bad "AC5: mark.cmt box-shadow is none"
fi

m="$(line "$p1" CHROME)"
if [ -z "$m" ]; then bad "chrome: no measurement"; else
  [ "$(field "$m" chip)" = "MD" ] && ok "AC19: kind chip MD" || bad "AC19: kind chip reads '$(field "$m" chip)'"
  [ "$(field "$m" fname)" = "Fixture_doc" ] && ok "AC19: breadcrumb falls back to the title on a no-provenance review" \
    || bad "AC19: breadcrumb fallback reads '$(field "$m" fname)', expected Fixture_doc"
  case "$(field "$m" eyebrow)" in *pushed*) ok "AC20: eyebrow shows pushed-<ago> (present segments only)";; *) bad "AC20: eyebrow '$(field "$m" eyebrow)' has no pushed segment";; esac
  [ "$(field "$m" turn)" = "true" ] && ok "AC20: 'Your turn' renders (turn=reviewer, not resolved)" || bad "AC20: no 'Your turn' in the title meta line"
  [ "$(field "$m" words)" = "true" ] && ok "AC20: words/min in the title meta line" || bad "AC20: no words count in the title meta line"
fi

m="$(line "$p1" LAB)"
if [ -z "$m" ]; then bad "card labels: no measurement"; else
  [ "$(field "$m" whos)" = "You|Agent" ] && ok "AC6: local tier labels You|Agent" || bad "AC6: card labels '$(field "$m" whos)', expected You|Agent"
  [ "$(field "$m" ts)" = "true|true" ] && ok "AC7: every entry shows a relative time from thread[].ts" || bad "AC7: timestamps '$(field "$m" ts)'"
  case "$(field "$m" avs)" in *\|ag) ok "AC6: agent entry carries the ag initials chip";; *) bad "AC6: chips '$(field "$m" avs)'";; esac
fi

m="$(line "$p1" HOST)"
if [ -z "$m" ]; then bad "hosted-label guard: no measurement"; else
  [ "$(field "$m" other)" = "Reviewer|Agent" ] && ok "AC6: hosted session — another grantee's entry is NOT labelled You" \
    || bad "AC6: with a foreign uid the labels read '$(field "$m" other)' — someone else's words labelled as yours"
  [ "$(field "$m" self)" = "You|Agent" ] && ok "AC6: hosted session — your own entry IS labelled You" \
    || bad "AC6: with the author's own uid the labels read '$(field "$m" self)'"
fi

m="$(line "$p1" POPS)"
if [ -z "$m" ]; then bad "composer: no measurement"; else
  [ "$(field "$m" bstyle)" = "dashed" ] && [ "$(field "$m" bacc)" = "true" ] && ok "AC9: composer border is dashed accent" \
    || bad "AC9: composer border style=$(field "$m" bstyle) accent=$(field "$m" bacc)"
  [ "$(field "$m" kbd)" = "true" ] && ok "AC9: ⌘↵ hint visible in the composer" || bad "AC9: no visible ⌘↵ hint"
  [ "$(field "$m" addressed)" = "false" ] && ok "AC10: no .gcard.addressed state exists" || bad "AC10: an addressed card appeared — that state was removed by design"
fi

# counters: snapshot 1 (2 open) -> post -> snapshot 2 (3 open) -> resolve -> snapshot 3 (2 open,
# Resolved 1) -> reopen -> snapshot 4 (3 open, Resolved 0)
snaps="$(lines "$p1" CNT)"
s1="$(sed -n 1p <<<"$snaps")"; s2="$(sed -n 2p <<<"$snaps")"; s3="$(sed -n 3p <<<"$snaps")"; s4="$(sed -n 4p <<<"$snaps")"
agree(){ # $1 snapshot, $2 open, $3 done, $4 label
  local s="$1" o="$2" d="$3" l="$4"
  if [ -z "$s" ]; then bad "$l: no counter measurement"; return; fi
  [ "$(field "$s" cards)" = "$o" ] && [ "$(field "$s" hdr)" = "${o}_open_·_${d}_done" ] \
    && [ "$(field "$s" cnt)" = "${o}_open" ] && [ "$(field "$s" res)" = "Resolved_${d}" ] \
    && case "$(field "$s" meta)" in ${o}_open_comment*) true;; *) false;; esac \
    && ok "AC23: $l — rail ${o}·${d}, dock ${o}, meta agree in one pass" \
    || bad "AC23: $l — cards=$(field "$s" cards) hdr=$(field "$s" hdr) dock=$(field "$s" cnt) res=$(field "$s" res) meta=$(field "$s" meta), expected ${o} open / ${d} done everywhere"
}
agree "$s1" 1 0 "before posting"
agree "$s2" 2 0 "after posting via the click path"
agree "$s3" 1 1 "after the agent resolve reached the poll"
agree "$s4" 2 0 "after Reopen returned the card (AC10)"
if [ -n "$s1" ]; then
  [ "$(field "$s1" gon)" = "true" ] && [ "$(field "$s1" cbtn)" = "none" ] \
    && ok "AC15: body.gutter-on hides #cmtbtn in the wide layout" \
    || bad "AC15: wide layout — gutter-on=$(field "$s1" gon) cmtbtn display=$(field "$s1" cbtn)"
fi
m="$(line "$p1" RC)"
if [ -z "$m" ]; then bad "resolved panel: no measurement"; else
  [ "$(field "$m" shown)" = "true" ] && [ "$(field "$m" rcards)" = "1" ] && ok "AC10/15: #resbtn opened the panel with the resolved thread" \
    || bad "AC10/15: resolved panel shown=$(field "$m" shown) rcards=$(field "$m" rcards)"
fi

# ---- phase 2: narrow viewport (900x800) — dock geometry, translucency, collisions --------------
DOCK='(()=>{const d=document.querySelector("#dock").getBoundingClientRect();
const bar=getComputedStyle(document.querySelector("#dockbar"));
const bg=bar.backgroundColor;
const m=bg.match(/^rgba\([^)]*,\s*([0-9.]+)\)/)||bg.match(/\/\s*([0-9.]+)\)/);const a=m?m[1]:"1";
const bf=(bar.backdropFilter&&bar.backdropFilter!=="none")?bar.backdropFilter:(bar.webkitBackdropFilter||"none");
const anim=[...document.querySelectorAll("#dock,#dock *")].every(n=>getComputedStyle(n).animationName==="none");
const wrapPB=parseFloat(getComputedStyle(document.querySelector(".wrap")).paddingBottom);
return "DOCK dx="+Math.abs((d.left+d.width/2)-innerWidth/2).toFixed(1)+" bot="+Math.round(innerHeight-d.bottom)
 +" h="+Math.round(d.height)+" alpha="+a+" blur="+/blur\(/.test(bf)+" anim="+anim
 +" cnt="+document.querySelector("#count").textContent.trim().replace(/ /g,"_")
 +" need="+Math.round(d.height+(innerHeight-d.bottom)+24)+" wrapPB="+Math.round(wrapPB)
 +" y="+Math.round(scrollY)+" top="+Math.round(d.top);})()'
COL='(sel=>{const d=document.querySelector("#dock").getBoundingClientRect();
const el=document.querySelector(sel);const r=el.getBoundingClientRect();
const vis=r.width>0&&r.height>0&&getComputedStyle(el).display!=="none";
const hit=!(d.right<=r.left||r.right<=d.left||d.bottom<=r.top||r.bottom<=d.top);
return "COL vis="+vis+" hit="+hit+" dock="+[d.left,d.top,d.right,d.bottom].map(Math.round).join(",")
 +" panel="+[r.left,r.top,r.right,r.bottom].map(Math.round).join(",");})'

p2="$(retry_if_empty DOCK node "$here/scripts/cdp-shot.mjs" --resize 900x800 --url "$url" \
  --wait-for ".blk .num" --wait 500 \
  --eval "$DOCK" \
  --eval '(()=>{scrollBy(0,600);return "SCROLLED";})()' --wait 250 --eval "$DOCK" \
  --click "#cmtbtn" --wait 300 --eval "${COL}('#gutter.docked')" --click "#cmtbtn" --wait 200 \
  --click "#resbtn" --wait 300 --eval "${COL}('#resolved')" --click "#resbtn" --wait 200 \
  --eval '(()=>{scrollTo(0,0);return "TOPPED";})()' --wait 250 \
  --wait-for ".blk:nth-of-type(2) .num" --click ".blk:nth-of-type(2) .num" --wait 300 \
  --eval "${COL}('#pop.docked')" --click "#popcancel" --wait 200 \
  --click "#histbtn" --wait 300 \
  --eval '(()=>{return "HIST shown="+(getComputedStyle(document.querySelector("#histmodal")).display==="flex");})()' \
  --click "#histclose")"

d1="$(lines "$p2" DOCK | sed -n 1p)"; d2="$(lines "$p2" DOCK | sed -n 2p)"
if [ -z "$d1" ]; then bad "dock: no measurement (browser step failed)"; else
  awk "BEGIN{exit !($(field "$d1" dx)<=1)}" && ok "AC12: dock centred (|centre−w/2| = $(field "$d1" dx)px ≤ 1)" \
    || bad "AC12: dock centre is $(field "$d1" dx)px off innerWidth/2"
  b="$(field "$d1" bot)"; [ "$b" -ge 20 ] && [ "$b" -le 32 ] && ok "AC12: dock bottom ${b}px from the viewport edge (20–32)" \
    || bad "AC12: dock bottom offset ${b}px outside 20–32"
  [ "$(field "$d1" h)" -le 46 ] && ok "AC16: dock height $(field "$d1" h)px ≤ 46px (the bottom:70px panels' clearance budget)" \
    || bad "AC16: dock height $(field "$d1" h)px BLOWS the 46px budget — the panel clearance must be re-derived"
  a="$(field "$d1" alpha)"
  awk "BEGIN{exit !($a>0 && $a<1)}" && ok "AC13: computed background alpha $a (strictly 0..1)" \
    || bad "AC13: computed background alpha $a is not translucent"
  [ "$(field "$d1" blur)" = "true" ] && ok "AC13: computed backdrop-filter carries blur()" || bad "AC13: no computed backdrop blur"
  [ "$(field "$d1" anim)" = "true" ] && ok "AC17: every #dock node computes animation-name none" || bad "AC17: a #dock node animates"
  case "$(field "$d1" cnt)" in
    *resolved*) bad "AC14: #count still carries the ' · M resolved' suffix: $(field "$d1" cnt)";;
    [0-9]*_open) ok "AC14: #count is the open count only ($(field "$d1" cnt))";;
    *) bad "AC14: #count reads '$(field "$d1" cnt)', expected 'N_open'";;
  esac
  [ "$(field "$d1" wrapPB)" -ge "$(field "$d1" need)" ] && ok "AC16: .wrap bottom padding $(field "$d1" wrapPB)px ≥ dock+offset+24 ($(field "$d1" need)px)" \
    || bad "AC16: .wrap bottom padding $(field "$d1" wrapPB)px < required $(field "$d1" need)px — the dock covers the last line"
fi
if [ -n "$d1" ] && [ -n "$d2" ]; then
  [ "$(field "$d2" y)" -ge 400 ] || bad "AC12: the page never scrolled (fixture too short?) — scroll-invariance unproven"
  [ "$(field "$d1" top)" = "$(field "$d2" top)" ] && [ "$(field "$d2" dx)" = "$(field "$d1" dx)" ] \
    && ok "AC12: dock rect unchanged after scrollBy(0,600) (top $(field "$d1" top)px)" \
    || bad "AC12: dock moved on scroll — top $(field "$d1" top) -> $(field "$d2" top)"
else bad "AC12: missing post-scroll dock measurement"; fi

cols="$(lines "$p2" COL)"
c1="$(sed -n 1p <<<"$cols")"; c2="$(sed -n 2p <<<"$cols")"; c3="$(sed -n 3p <<<"$cols")"
colcheck(){ # $1 snapshot, $2 name
  local s="$1" n="$2"
  if [ -z "$s" ]; then bad "AC16: $n never measured"; return; fi
  [ "$(field "$s" vis)" = "true" ] || { bad "AC16: $n did not open (nothing to measure)"; return; }
  [ "$(field "$s" hit)" = "false" ] && ok "AC16: $n does not intersect the dock (dock $(field "$s" dock) vs panel $(field "$s" panel))" \
    || bad "AC16: $n INTERSECTS the dock — dock $(field "$s" dock) vs panel $(field "$s" panel)"
}
colcheck "$c1" "#gutter.docked"
colcheck "$c2" "#resolved"
colcheck "$c3" "#pop.docked"
m="$(line "$p2" HIST)"
if [ -z "$m" ]; then bad "AC15: history modal never measured"; else
  [ "$(field "$m" shown)" = "true" ] && ok "AC15: #histbtn opens #histmodal" || bad "AC15: #histbtn did not open #histmodal"
fi

echo
[ "$fail" -eq 0 ] && echo "all viewer-polish cases pass" || echo "viewer-polish check FAILED"
exit "$fail"
