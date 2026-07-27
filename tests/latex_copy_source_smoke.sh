#!/usr/bin/env bash
# tests/latex_copy_source_smoke.sh (#189) — does the source-pane Copy control put the RAW .tex on
# the clipboard?
#
# A render smoke asserting `#copysrc` exists would not check the acceptance criterion. The AC is the
# clipboard, so this drives a real browser: click the control, read the clipboard back, and compare
# it byte-for-byte to what GET /api/reviews/<id>/source returns. The comparison matters because the
# rendered DOM interleaves gutter line numbers into the source text — an implementation that copied
# `.ln` textContent would look right on screen and fail here.
#
# Needs `--clipboard` (grantPermissions + focus emulation): headless Chrome rejects even writeText
# with "Document is not focused" otherwise.
#
# Stands up its own throwaway instance on an unused port with its own data dir, and kills it by PID
# file — never by process name, which would kill a sibling agent's server on another port.
#
# exit 0 = round trip matched; 1 = mismatch or a failed step; 2 = missing prerequisite.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8193}"
RUN="$ROOT/.scratch/copysmoke-$PORT"
PIDFILE="$RUN/server.pid"

command -v node >/dev/null 2>&1 || { echo "FAIL node is required"; exit 2; }
python3 -c "import sys; sys.exit(0)" 2>/dev/null || { echo "FAIL python3 is required"; exit 2; }

cleanup() {
  # ponytail: PID file, never `pkill -f mdreview` — that matches every agent's instance.
  [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null
  rm -rf "$RUN"
}
trap cleanup EXIT

rm -rf "$RUN"; mkdir -p "$RUN/data"

PORT="$PORT" MDREVIEW_DATA="$RUN/data" MDREVIEW_ENABLE_LATEX=1 \
  MDREVIEW_WEB_DIR="$ROOT/web/app" PYTHONPATH="$ROOT/src" \
  python3 -m mdreview > "$RUN/server.log" 2>&1 &
echo $! > "$PIDFILE"

for _ in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$PORT/healthz" || true)
  [ "$code" = "200" ] && break
  sleep 0.25
done
[ "${code:-}" = "200" ] || { echo "FAIL server never came up on $PORT; log:"; tail -20 "$RUN/server.log"; exit 1; }

# A source with a tab, a trailing space and a blank line: anything that normalises whitespace on the
# way to the clipboard fails the comparison instead of passing by luck.
RID=$(curl -s -XPOST "http://127.0.0.1:$PORT/api/reviews" -H 'Content-Type: application/json' \
  --data-binary '{"kind":"latex","markdown":"\\documentclass{article}\n\\begin{document}\n\tIndented \\emph{body} \n\n\\end{document}"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])') || { echo "FAIL could not create the review"; exit 1; }
[ -n "$RID" ] || { echo "FAIL empty review id"; exit 1; }

curl -s "http://127.0.0.1:$PORT/api/reviews/$RID/source" > "$RUN/expected.tex"
[ -s "$RUN/expected.tex" ] || { echo "FAIL /source returned nothing"; exit 1; }

# The clipboard text is compared against /source INSIDE the page, so the assertion is the AC itself.
node "$ROOT/scripts/cdp-shot.mjs" \
  --clipboard "http://127.0.0.1:$PORT" \
  --url "http://127.0.0.1:$PORT/review/$RID" \
  --wait-for "#copysrc" \
  --eval "document.querySelector('#copysrc').getAttribute('aria-label').length>0" \
  --click "#copysrc" \
  --wait 400 \
  --eval "fetch('/api/reviews/$RID/source',{cache:'no-store'}).then(r=>r.text()).then(async src=>{const clip=await navigator.clipboard.readText(); if(clip!==src){console.log('CLIP_MISMATCH len',clip.length,'vs',src.length); return false;} return true;})" \
  || { echo "FAIL the clipboard did not match GET /source"; exit 1; }

echo "  ok   #copysrc renders in the source pane header and is labelled"
echo "  ok   clicking it puts the raw .tex on the clipboard, byte-identical to GET /source"
echo "latex copy-source smoke: all clear"
