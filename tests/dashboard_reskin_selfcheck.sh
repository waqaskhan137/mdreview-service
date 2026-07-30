#!/usr/bin/env bash
# dashboard_reskin_selfcheck.sh — the rev-3 dashboard re-skin (#278), asserted on RENDERED and
# COMPUTED outcomes only (#265's lesson: a CSS-text regex sat green for two days over a layout
# that never worked; nothing here reads the stylesheet).
#
# Four legs, all driven through scripts/cdp-shot.mjs against throwaway local instances:
#   1. LOCAL (noAuthPlane, #224): empty state, then the full re-skinned inbox — visible heading
#      tracking the filter, "N · M projects" count line, group strings/eyebrows, MD/TEX kind
#      cells, hero block, ⌘K chip, the #285 toggle-slot fit (injected, then removed), REAL-hover
#      reveal via the --move verb (timestamp fades, open count stays), focus-visible reveal,
#      resolve/reopen with #187's three-state contract, and the delete flow end to end.
#   2. THEME: scripts/theme-check.mjs on the same instance — the emulated prefers-color-scheme
#      dark body surface must differ from light, so dark cannot be silently broken.
#   3. HOSTED (REQUIRE_AUTH=1, stub email): the rev-3 sign-in resting form (40px controls, mono
#      uppercase label, constants-sourced footnote), the 44px narrow floor on #signin-btn, the
#      anti-enumeration sent state, and the localStorage throttle lede on the 4th submit.
#   4. UNREACHABLE: /auth/session blocked at the network layer -> showUnreachable()'s screen.
#
# Every eval THROWS a named finding on failure (cdp-shot exits non-zero), so a red run says what
# broke, not just that something did.
#
#   bash tests/dashboard_reskin_selfcheck.sh     # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$here/.scratch/reskin-check-$$"
mkdir -p "$scratch"
srv=""; srv2=""
cleanup(){ [ -n "$srv" ] && kill "$srv" 2>/dev/null; [ -n "$srv2" ] && kill "$srv2" 2>/dev/null;
           rm -rf "$scratch" 2>/dev/null; return 0; }
trap cleanup EXIT
pickport(){ python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()'; }
waitup(){ for _ in $(seq 1 40); do curl -sf -o /dev/null "http://127.0.0.1:$1/healthz" && return 0; sleep 0.25; done; return 1; }

fail=0
leg(){ printf '\n== %s ==\n' "$1"; }
bad(){ printf 'FAIL - %s\n' "$1"; fail=1; }

# ---------------------------------------------------------------- leg 1: local, noAuthPlane
port="$(pickport)"
MDREVIEW_DATA="$scratch/data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" python3 -m mdreview >"$scratch/server.log" 2>&1 &
srv=$!
waitup "$port" || { bad "local server never came up"; exit 1; }
url="http://127.0.0.1:$port/"

leg "empty state (no reviews at all)"
node "$here/scripts/cdp-shot.mjs" --url "$url" --wait-for ".dash-empty" --wait 200 \
  --eval '(()=>{const e=document.querySelector(".dash-empty");if(!e.textContent.includes("Connect your agent"))throw Error("empty copy: "+JSON.stringify(e.textContent.slice(0,80)));const s=document.querySelector("#sub");if(s.textContent!=="No reviews yet.")throw Error("sub on empty: "+JSON.stringify(s.textContent));return "EMPTY ok"})()' \
  || bad "empty-state leg"

# Fixtures. Order matters: activity = created, the hero is the most recently active yours row,
# so the plain markdown rows go LAST and "Alpha yours" is the hero. Two projects (p1/p2) feed
# the count line; the comment on Alpha feeds the hero say line; the resolved pair covers #187's
# human-vs-derived split; the two handoffs cover both agent states.
mk(){ curl -s -X POST "http://127.0.0.1:$port/api/reviews" -H 'Content-Type: application/json' \
       -d "$1" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'; }
rid_der="$(mk '{"title":"Zeta derived","project":"p2","markdown":"# z\n\nbody\n"}')"
cid="$(curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_der/comments" \
        -H 'Content-Type: application/json' -d '{"anchor":{"block_num":1},"text":"note"}' \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["comment_id"])')"
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_der/comments/$cid/resolve" \
  -H 'Content-Type: application/json' -d '{}' -o /dev/null      # all addressed -> DERIVED resolved
rid_hum="$(mk '{"title":"Yota resolved","project":"p1","markdown":"# y\n\nbody\n"}')"
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_hum/resolve" \
  -H 'Content-Type: application/json' -d '{"resolved":true}' -o /dev/null   # HUMAN resolved
rid_a1="$(mk '{"title":"Delta agent","project":"p2","markdown":"# d\n\nbody\n"}')"
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_a1/handoff" \
  -H 'Content-Type: application/json' -d '{"to":"agent"}' -o /dev/null      # waiting for agent
rid_a2="$(mk '{"title":"Epsilon working","project":"p1","markdown":"# e\n\nbody\n"}')"
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_a2/handoff" \
  -H 'Content-Type: application/json' -d '{"to":"agent"}' -o /dev/null
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_a2/handoff" \
  -H 'Content-Type: application/json' -d '{"state":"working","owner":"smoke"}' -o /dev/null  # agent working
mk '{"title":"Gamma latex","project":"p2","kind":"latex","markdown":"\\documentclass{article}\\begin{document}x\\end{document}"}' >/dev/null
mk '{"title":"Beta yours","project":"p1","markdown":"# b\n\nbody\n"}' >/dev/null
rid_hero="$(mk '{"title":"Alpha yours","project":"p1","markdown":"# a\n\nbody\n"}')"
curl -s -X POST "http://127.0.0.1:$port/api/reviews/$rid_hero/comments" \
  -H 'Content-Type: application/json' -d '{"anchor":{"block_num":1},"text":"open note"}' -o /dev/null

leg "the re-skinned inbox (heading, groups, rows, hover, flows) at 1440x900"
node "$here/scripts/cdp-shot.mjs" --url "$url" --wait-for ".rw" --resize 1440x900 --wait 300 \
  --eval '(()=>{const a=document.querySelector("#app"),s=document.querySelector("#signin");if(a.style.display==="none")throw Error("noAuthPlane: #app hidden");if(getComputedStyle(s).display!=="none")throw Error("noAuthPlane: #signin visible");return "APP ok"})()' \
  --eval '(()=>{const h=document.querySelector("#h1"),r=h.getBoundingClientRect(),cs=getComputedStyle(h);if(r.width<50||r.height<20)throw Error("h1 not genuinely visible: rect "+Math.round(r.width)+"x"+Math.round(r.height)+" (a .vh clip measures 1x1)");if(cs.visibility!=="visible")throw Error("h1 visibility "+cs.visibility);if(h.textContent!=="Documents")throw Error("h1 at rest reads "+JSON.stringify(h.textContent));return "H1 ok"})()' \
  --eval '(()=>{const h=document.querySelector("#h1").getBoundingClientRect(),s=document.querySelector("#sub"),r=s.getBoundingClientRect();if(s.textContent!=="7 · 2 projects")throw Error("count line: "+JSON.stringify(s.textContent)+" (wanted 7 · 2 projects)");if(Math.min(h.bottom,r.bottom)-Math.max(h.top,r.top)<=0)throw Error("count line not beside the heading");return "SUB ok"})()' \
  --click '.filt[data-filter="needs"]' --wait 150 \
  --eval '(()=>{const t=document.querySelector("#h1").textContent;if(t!=="Yours")throw Error("h1 after needs click: "+JSON.stringify(t));const s=document.querySelector("#sub").textContent;if(s!=="3 · 2 projects")throw Error("count after needs click: "+JSON.stringify(s));return "FILT-NEEDS ok"})()' \
  --click '.filt[data-filter="needs"]' --wait 150 \
  --eval '(()=>{if(document.querySelector("#h1").textContent!=="Documents")throw Error("h1 did not return to Documents");return "FILT-CLEAR ok"})()' \
  --click '.filt[data-filter="working"]' --wait 150 \
  --eval '(()=>{const t=document.querySelector("#h1").textContent;if(t!=="With the agent")throw Error("h1 after working click: "+JSON.stringify(t));return "FILT-WORKING ok"})()' \
  --click '.filt[data-filter="working"]' --wait 150 \
  --click '.filt[data-filter="resolved"]' --wait 150 \
  --eval '(()=>{const t=document.querySelector("#h1").textContent;if(t!=="Resolved")throw Error("h1 after resolved click: "+JSON.stringify(t));return "FILT-RESOLVED ok"})()' \
  --click '.filt[data-filter="resolved"]' --wait 150 \
  --eval '(()=>{const sel=document.querySelector("#projsel");sel.value="p1";sel.dispatchEvent(new Event("change"));const t=document.querySelector("#h1").textContent;if(t!=="Documents · p1")throw Error("h1 with project: "+JSON.stringify(t));const gy=document.querySelector(".grp-yours .grp-h");if(!gy||gy.textContent!=="Waiting on you")throw Error("no-hero eyebrow (project view): "+(gy?JSON.stringify(gy.textContent):"missing"));sel.value="";sel.dispatchEvent(new Event("change"));if(document.querySelector("#h1").textContent!=="Documents")throw Error("h1 did not drop the project suffix");return "PROJ ok"})()' \
  --type '#search=Beta' --wait 150 \
  --eval '(()=>{const n=document.querySelectorAll("#list .rw").length;if(n!==1)throw Error("search Beta shows "+n+" rows, wanted 1 (live filtering broken?)");const s=document.querySelector("#sub").textContent;if(s!=="1 · 2 projects")throw Error("count under search: "+JSON.stringify(s));return "SEARCH ok"})()' \
  --type '#search=zzzz' --wait 150 \
  --eval '(()=>{const n=document.querySelector("#noresults");if(getComputedStyle(n).display==="none")throw Error("noresults hidden on zero matches");if(n.textContent!=="No reviews match your search.")throw Error("noresults wording: "+JSON.stringify(n.textContent));return "NORESULTS ok"})()' \
  --type '#search=' --wait 150 \
  --eval '(()=>{const gy=document.querySelector(".grp-yours .grp-h");if(!gy)throw Error("no .grp-yours eyebrow");if(gy.textContent!=="2 more waiting on you")throw Error("yours eyebrow: "+JSON.stringify(gy.textContent));const all=[...document.querySelectorAll(".grp-h")].map(e=>e.textContent);if(!all.includes("With the agent"))throw Error("With the agent eyebrow missing: "+JSON.stringify(all));const cs=getComputedStyle(gy);if(!/Geist Mono/.test(cs.fontFamily))throw Error("eyebrow family: "+cs.fontFamily);if(cs.textTransform!=="uppercase")throw Error("eyebrow text-transform: "+cs.textTransform);return "GROUPS ok"})()' \
  --eval '(()=>{const b=document.querySelector("#browseall");if(b.textContent!=="Browse all 2 resolved")throw Error("resolved control: "+JSON.stringify(b.textContent));b.click();const n=document.querySelectorAll("#list .w-resolved").length;if(document.querySelector("#browseall").textContent!=="Hide resolved")throw Error("open-state label: "+JSON.stringify(document.querySelector("#browseall").textContent));if(n!==2)throw Error("resolved rows shown: "+n+", wanted 2");document.querySelector("#browseall").click();if(document.querySelectorAll("#list .w-resolved").length!==0)throw Error("resolved rows survived the hide click");return "BROWSEALL ok"})()' \
  --eval '(()=>{const t=document.querySelector(".nu-title");if(!t)throw Error("no hero in the resting view");if(t.textContent!=="Alpha yours")throw Error("hero title: "+JSON.stringify(t.textContent));if(getComputedStyle(t).fontSize!=="20px")throw Error("hero title size: "+getComputedStyle(t).fontSize);const s=document.querySelector(".nu-say").textContent;if(!s.startsWith("1 open comment"))throw Error("hero say line: "+JSON.stringify(s));const cta=document.querySelector(".nu-go");if(cta.textContent!=="Read the comments")throw Error("hero CTA: "+JSON.stringify(cta.textContent));const bg=getComputedStyle(document.querySelector("#nextup")).backgroundColor;if(bg==="rgba(0, 0, 0, 0)"||bg==="transparent")throw Error("hero block not tinted (bg "+bg+")");return "HERO ok"})()' \
  --eval '(()=>{const ks=[...document.querySelectorAll("#list .rw")].map(r=>{const k=r.querySelector(".rw-k");return k?k.textContent:"(none)"});const badk=ks.filter(k=>k!=="MD"&&k!=="TEX");if(badk.length)throw Error("kind cells off-contract: "+JSON.stringify(badk));const tex=ks.filter(k=>k==="TEX").length;if(tex!==1)throw Error("expected exactly 1 TEX row, got "+tex+" of "+JSON.stringify(ks));if(!ks.includes("MD"))throw Error("no MD kind cells rendered");return "KINDS ok ("+ks.join(",")+")"})()' \
  --eval '(()=>{const a2=document.querySelector(".rw[data-title=\"Epsilon working\"] .rw-s");if(!a2)throw Error("working row lacks .rw-s");if(a2.textContent!=="agent working"||!a2.classList.contains("live"))throw Error("working status span: "+JSON.stringify(a2.textContent)+" live="+a2.classList.contains("live"));const a1=document.querySelector(".rw[data-title=\"Delta agent\"] .rw-s");if(a1.textContent!=="waiting for agent")throw Error("waiting status span: "+JSON.stringify(a1.textContent));return "STATES ok"})()' \
  --eval '(()=>{const box=document.querySelector(".searchbox"),c=box&&box.querySelector(".kbd-hint");if(!c)throw Error("no ⌘K chip inside the search control");const b=box.getBoundingClientRect(),r=c.getBoundingClientRect();if(r.width<=0||r.height<=0)throw Error("chip has zero rect");if(c.textContent!=="⌘K")throw Error("chip text: "+JSON.stringify(c.textContent));if(r.left<b.left||r.right>b.right+1)throw Error("chip rendered outside the search control");return "CHIP ok"})()' \
  --eval '(()=>{const top=document.querySelector(".app-top"),acct=document.querySelector("#acct"),sb=document.querySelector(".searchbox");const preA=acct.getBoundingClientRect(),preH=top.getBoundingClientRect().height;const d=document.createElement("div");d.setAttribute("data-theme-icon","");d.style.cssText="width:30px;height:30px;flex:0 0 auto;border:1px solid var(--border);border-radius:var(--r-control);background:var(--surface)";sb.after(d);const sr=d.getBoundingClientRect(),postA=acct.getBoundingClientRect(),postH=top.getBoundingClientRect().height;const err=[];if(Math.round(sr.width)!==30||Math.round(sr.height)!==30)err.push("slot measures "+sr.width+"x"+sr.height);if(postH!==preH)err.push("top line grew "+preH+" -> "+postH+" (wrapped)");if(Math.abs(postA.top-preA.top)>0.5)err.push("#acct left its line");if(sr.left<sb.getBoundingClientRect().right-1)err.push("slot not after the search control");if(postA.width>0&&sr.right>postA.left+1)err.push("slot overlaps #acct");d.remove();const finA=acct.getBoundingClientRect();if(Math.abs(finA.top-preA.top)>0.5||Math.abs(finA.left-preA.left)>0.5)err.push("removing the slot moved #acct");if(err.length)throw Error("SLOT: "+err.join(" | "));return "SLOT ok"})()' \
  --move '.rw[data-title="Beta yours"]' --wait 350 \
  --eval '(()=>{const rw=document.querySelector(".rw[data-title=\"Beta yours\"]");if(!rw.matches(":hover"))throw Error("row is not :hover after a real pointer move");const o=e=>getComputedStyle(e).opacity;const del=rw.querySelector(".del"),res=rw.querySelector(".res"),m=rw.querySelector(".rw-m"),s=rw.querySelector(".rw-s");const err=[];if(o(del)!=="1")err.push(".del opacity "+o(del));if(!res)err.push("unresolved yours row offers no .res");else if(o(res)!=="1")err.push(".res opacity "+o(res));if(o(m)!=="0")err.push("timestamp opacity "+o(m)+" (must fade)");if(o(s)!=="1")err.push("open-count opacity "+o(s)+" (must stay)");const other=document.querySelector(".rw[data-title=\"Delta agent\"]");if(o(other.querySelector(".del"))!=="0")err.push("unhovered .del revealed");if(o(other.querySelector(".rw-m"))!=="1")err.push("unhovered timestamp faded");if(err.length)throw Error("HOVER: "+err.join(" | "));return "HOVER ok"})()' \
  --move '#h1' --wait 350 \
  --eval '(()=>{const del=document.querySelector(".rw[data-title=\"Beta yours\"] .del");const o=getComputedStyle(del).opacity;if(o!=="0")throw Error("un-hover left .del at opacity "+o);return "UNHOVER ok"})()' \
  --eval '(()=>{const del=document.querySelector(".rw[data-title=\"Beta yours\"] .del");del.focus({focusVisible:true});if(!del.matches(":focus-visible"))throw Error("focus({focusVisible:true}) did not produce :focus-visible");return "FOCUSED"})()' \
  --wait 300 \
  --eval '(()=>{const del=document.querySelector(".rw[data-title=\"Beta yours\"] .del");const o=getComputedStyle(del).opacity;del.blur();if(o!=="1")throw Error(".del:focus-visible opacity "+o+" (keyboard reveal broken)");return "FOCUS ok"})()' \
  --move '.rw[data-title="Beta yours"]' --wait 300 --click '.rw[data-title="Beta yours"] .res' --wait 900 \
  --eval '(()=>{const b=document.querySelector("#browseall");if(!b||b.textContent!=="Browse all 3 resolved")throw Error("after resolving Beta: "+(b?JSON.stringify(b.textContent):"no control"));if(document.querySelector(".rw[data-title=\"Beta yours\"]"))throw Error("resolved row still listed as open");return "RESOLVE ok"})()' \
  --click '#browseall' --wait 200 \
  --eval '(()=>{const h=document.querySelector(".rw[data-title=\"Yota resolved\"] .res");if(!h)throw Error("human-resolved row lacks its reopen control (#187)");if(h.dataset.to!=="0")throw Error("reopen control data-to="+h.dataset.to);const d=document.querySelector(".rw[data-title=\"Zeta derived\"]");if(!d)throw Error("derived-resolved row not rendered");if(d.querySelector(".res"))throw Error("derived-resolved row must offer NO control (#187)");return "THREESTATE ok"})()' \
  --move '.rw[data-title="Yota resolved"]' --wait 300 --click '.rw[data-title="Yota resolved"] .res' --wait 900 \
  --eval '(()=>{const rw=document.querySelector(".rw[data-title=\"Yota resolved\"]");if(!rw||!rw.className.includes("w-yours"))throw Error("reopened row did not move back to yours");const res=document.querySelectorAll("#list .w-resolved").length;if(res!==2)throw Error("resolved rows after reopen: "+res+", wanted 2");return "REOPEN ok"})()' \
  --move '.rw[data-title="Delta agent"]' --wait 300 --click '.rw[data-title="Delta agent"] .del' --wait 200 \
  --eval '(()=>{const bar=document.querySelector("#confirmbar");if(getComputedStyle(bar).display!=="flex")throw Error("confirmbar did not appear");if(!bar.querySelector(".msg").textContent.includes("Delta agent"))throw Error("confirm names the wrong review: "+JSON.stringify(bar.querySelector(".msg").textContent));return "CONFIRM ok"})()' \
  --click '#cfy' --wait 900 \
  --eval '(()=>{if(document.querySelector(".rw[data-title=\"Delta agent\"]"))throw Error("row survived a confirmed delete");if(getComputedStyle(document.querySelector("#confirmbar")).display!=="none")throw Error("confirmbar still open after confirm");return "DELETE ok"})()' \
  || bad "main inbox leg"

leg "themes (emulated prefers-color-scheme; dark must differ)"
node "$here/scripts/theme-check.mjs" "$url" >/dev/null 2>&1 \
  && printf 'ok   - dark and light body surfaces differ\n' \
  || bad "theme leg (run scripts/theme-check.mjs $url for the table)"

kill "$srv" 2>/dev/null; wait "$srv" 2>/dev/null; srv=""

# ---------------------------------------------------------------- leg 3: hosted, sign-in
port2="$(pickport)"
MDREVIEW_DATA="$scratch/data2" PORT="$port2" MDREVIEW_WEB_DIR="$here/web/app" \
  PYTHONPATH="$here/src" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=0 \
  MDREVIEW_PROXY_SECRET=inert-not-consumed-with-plane-off \
  MDREVIEW_SESSION_SECRET=selfcheck-session MDREVIEW_TOKEN_PEPPER=selfcheck-pepper \
  MDREVIEW_OWNER_EMAIL=owner@example.com MDREVIEW_ALLOW_STUB_EMAIL=1 \
  MDREVIEW_PUBLIC_BASE=https://selfcheck.invalid \
  python3 -m mdreview.hosted >"$scratch/server2.log" 2>&1 &
srv2=$!
waitup "$port2" || { bad "hosted server never came up (see $scratch/server2.log)"; exit 1; }
url2="http://127.0.0.1:$port2/"

leg "sign-in resting form + throttle (4 submits, localStorage window)"
node "$here/scripts/cdp-shot.mjs" --url "$url2" --wait-for "#signin-btn" --wait 300 \
  --eval '(()=>{const err=[];if(getComputedStyle(document.querySelector("#signin")).display!=="flex")err.push("#signin not shown");if(document.querySelector("#app").style.display!=="none")err.push("#app visible under sign-in");const h=document.querySelector("#signin-card h1");if(h.textContent!=="Sign in")err.push("h1: "+JSON.stringify(h.textContent));const l=document.querySelector("#signin-card .lede");if(!/^We.ll email you a one-time link\. No password, and the same link signs you up\.$/.test(l.textContent))err.push("lede: "+JSON.stringify(l.textContent));const lab=document.querySelector(".signin-field label"),cs=getComputedStyle(lab);if(!/Geist Mono/.test(cs.fontFamily))err.push("label family "+cs.fontFamily);if(cs.textTransform!=="uppercase")err.push("label transform "+cs.textTransform);const ih=document.querySelector("#signin-email").getBoundingClientRect().height;if(Math.round(ih)!==40)err.push("input height "+ih);const bh=document.querySelector("#signin-btn").getBoundingClientRect().height;if(Math.round(bh)!==40)err.push("button height "+bh);const n=document.querySelector("#signin-note");if(n.textContent!=="Links last 15 minutes · 3 per address")err.push("footnote: "+JSON.stringify(n.textContent));if(err.length)throw Error("SIGNIN: "+err.join(" | "));return "SIGNIN ok"})()' \
  --resize 606x900 --wait 300 \
  --eval '(()=>{const bh=document.querySelector("#signin-btn").getBoundingClientRect().height;if(bh<44)throw Error("#signin-btn "+bh+"px at 606, #184 floor is 44");return "BTN44 ok"})()' \
  --resize 1280x900 --wait 200 \
  --type '#signin-email=smoke@example.com' --click '#signin-btn' --wait 600 \
  --eval '(()=>{const h=document.querySelector("#signin-card h1");if(h.textContent!=="Check your email")throw Error("sent state h1: "+JSON.stringify(h.textContent));if(!document.querySelector("#signin-card .lede").textContent.includes("a link is on its way"))throw Error("sent lede off-copy");return "SENT-1 ok"})()' \
  --url "$url2" --wait-for "#signin-btn" --type '#signin-email=smoke@example.com' --click '#signin-btn' --wait 600 \
  --eval '(()=>{if(!document.querySelector("#signin-card .lede").textContent.includes("a link is on its way"))throw Error("submit 2 not the constant confirmation");return "SENT-2 ok"})()' \
  --url "$url2" --wait-for "#signin-btn" --type '#signin-email=smoke@example.com' --click '#signin-btn' --wait 600 \
  --eval '(()=>{if(!document.querySelector("#signin-card .lede").textContent.includes("a link is on its way"))throw Error("submit 3 not the constant confirmation");return "SENT-3 ok"})()' \
  --url "$url2" --wait-for "#signin-btn" --type '#signin-email=smoke@example.com' --click '#signin-btn' --wait 600 \
  --eval '(()=>{const l=document.querySelector("#signin-card .lede").textContent;if(!l.includes("already requested 3 links"))throw Error("4th submit did not show the cooldown lede: "+JSON.stringify(l.slice(0,90)));return "THROTTLE ok"})()' \
  || bad "sign-in leg"

leg "unreachable (auth plane blocked at the network layer)"
node "$here/scripts/cdp-shot.mjs" --block "*/auth/session" --url "$url2" --wait 2500 \
  --eval '(()=>{const h=document.querySelector("#signin-card h1");if(!h||!/^Can.t reach mdreview$/.test(h.textContent))throw Error("unreachable screen h1: "+(h?JSON.stringify(h.textContent):"none"));return "UNREACHABLE ok"})()' \
  || bad "unreachable leg"

echo
[ "$fail" -eq 0 ] && echo "dashboard re-skin selfcheck OK" || echo "dashboard re-skin selfcheck FAILED"
exit "$fail"
