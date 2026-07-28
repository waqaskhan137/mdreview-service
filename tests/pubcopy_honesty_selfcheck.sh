#!/usr/bin/env bash
# pubcopy_honesty_selfcheck.sh — the share-link Copy button must not claim success it did not have.
#
# THE DEFECT (#213), in latex-viewer.html's renderShare():
#     try{ navigator.clipboard.writeText(i.value); }catch(e){}
#     cp.textContent = "Copied";
# Two bugs, and the first is the subtle one:
#   1. writeText returns a PROMISE. The synchronous try/catch only ever caught a synchronous throw,
#      so a rejected clipboard permission — the common real failure — sailed straight past it.
#   2. "Copied" was then set unconditionally anyway.
# A UI that confidently reports success while the clipboard is untouched is worse than silence: the
# reader pastes a stale buffer elsewhere and blames that instead.
#
# WHY THE OBVIOUS FIX ALSO FAILS: copying viewer.html's markCopied does NOT satisfy this ticket. On
# failure that helper does nothing at all — no "Copied", but no error either. Silent failure is still
# a lie by omission. The failure must be VISIBLE, hence the assertion on "Copy failed".
#
# #pubcopy only renders when GET /shares returns 200, which only the HOSTED composition serves — so
# a plain local instance cannot reach this control at all. This stands up the hosted build, signs in
# through the real magic-link flow (stub email logs the link), enables the public link, then drives
# a real click with the clipboard DENIED.
#
#   bash tests/pubcopy_honesty_selfcheck.sh      # exit 0 = pass
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
port="$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')"
tmp="$(mktemp -d)"
cleanup(){ [ -n "${srv:-}" ] && kill "$srv" 2>/dev/null; rm -rf "$tmp" 2>/dev/null; return 0; }
trap cleanup EXIT

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

# PUBLIC_BASE must be an absolute https URL or the hosted build refuses to boot; it is only used to
# build magic-link URLs, which this test reads from the log rather than following.
MDREVIEW_DATA="$tmp/data" PORT="$port" MDREVIEW_WEB_DIR="$here/web/app" PYTHONPATH="$here/src" \
  MDREVIEW_REQUIRE_AUTH=1 MDREVIEW_ALLOW_PROXY_PLANE=0 MDREVIEW_PROXY_SECRET=inert-not-consumed \
  MDREVIEW_SESSION_SECRET=test-session-secret MDREVIEW_TOKEN_PEPPER=test-pepper \
  MDREVIEW_OWNER_EMAIL=owner@example.com MDREVIEW_ALLOW_STUB_EMAIL=1 MDREVIEW_ENABLE_LATEX=1 \
  MDREVIEW_PUBLIC_BASE=https://local.test \
  python3 -m mdreview.hosted >"$tmp/server.log" 2>&1 &
srv=$!
up=0
for _ in $(seq 1 60); do curl -sf -o /dev/null "http://127.0.0.1:$port/healthz" && { up=1; break; }; sleep 0.25; done
[ "$up" = "1" ] || { echo "FAIL - hosted build never came up"; sed -n '1,6p' "$tmp/server.log"; exit 1; }
base="http://127.0.0.1:$port"

curl -s -o /dev/null -X POST "$base/auth/magic-link" -H 'Content-Type: application/json' \
     -d '{"email":"owner@example.com"}'
tok="$(grep -oE 'auth/redeem\?token=[A-Za-z0-9._~-]+' "$tmp/server.log" | tail -1 | sed 's/.*token=//')"
[ -n "$tok" ] || { echo "FAIL - no magic link in the log (stub email backend expected)"; exit 1; }
curl -s -c "$tmp/jar" -o /dev/null -X POST "$base/auth/redeem" --data-urlencode "token=$tok"
cookie="$(awk '/mdr_session/{print $NF}' "$tmp/jar" | tail -1)"
[ -n "$cookie" ] || { echo "FAIL - no session cookie after redeem"; exit 1; }
ok "signed in through the real magic-link flow"

csrf="$(curl -s -b "$tmp/jar" "$base/auth/session" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("csrf",""))')"
rid="$(curl -s -b "$tmp/jar" -X POST "$base/api/reviews" -H 'Content-Type: application/json' \
        -H "X-CSRF-Token: $csrf" -d '{"title":"pubcopy","kind":"latex"}' \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("id",""))')"
[ -n "$rid" ] || { echo "FAIL - could not create the latex review"; exit 1; }
curl -s -o /dev/null -b "$tmp/jar" -X POST "$base/api/reviews/$rid/public" -H "X-CSRF-Token: $csrf"
ok "public link enabled, so #pubcopy renders"

# Deny the clipboard, then click for real. Headless Chrome has no focused document, so writeText
# rejects on its own — but the denial is made explicit so the test does not depend on that quirk.
DENY='(()=>{Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:()=>Promise.reject(new DOMException("denied","NotAllowedError")),readText:()=>Promise.reject(new DOMException("denied","NotAllowedError"))}});return true;})()'
out="$(node "$here/scripts/cdp-shot.mjs" --cookie "mdr_session=$cookie@$base" --url "$base/review/$rid" \
        --wait-for "#sharebtn" --eval "$DENY" --click "#sharebtn" --wait-for "#pubcopy" --wait 300 \
        --click "#pubcopy" --wait 700 \
        --eval '(()=>{const c=document.querySelector("#pubcopy");return "PUBCOPY text="+JSON.stringify(c.textContent);})()' 2>&1)"

# Take the RESULT side of cdp-shot's "eval: <expr>  => <result>" line. Matching the whole line
# picks up the echoed expression, which contains the marker too and always "passes".
label="$(grep 'eval:' <<<"$out" | sed 's/.*=> //' | grep 'PUBCOPY' | head -1)"
if [ -z "$label" ]; then
  bad "no measurement from the browser step"; printf '%s\n' "$out" | tail -4 | sed 's/^/        /'
else
  case "$label" in
    *Copied*) bad "button says Copied while the clipboard REJECTED — the exact defect ($label)" ;;
    *"Copy failed"*) ok "failed write is reported visibly ($label)" ;;
    *) bad "failed write produced neither an error nor Copied — silent failure is still a lie ($label)" ;;
  esac
fi

echo
[ "$fail" -eq 0 ] && echo "all pubcopy honesty cases pass" || echo "pubcopy honesty check FAILED"
exit "$fail"
