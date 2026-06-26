#!/usr/bin/env bash
# Build mdreview.app via py2app (macOS) — P0 freeze spike.
#
# Requires a FRAMEWORK Python (Homebrew or python.org); pyenv builds usually are NOT framework,
# and py2app needs one to produce a standalone .app. Override the interpreter with PYBIN=.
# All build output (venv, build/, dist/) goes under .scratch/ (gitignored) — nothing lands in the repo.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
PYBIN="${PYBIN:-/opt/homebrew/bin/python3.12}"
OUT="$REPO/.scratch/macos-build"
VENV="$OUT/venv"

"$PYBIN" -c 'import sysconfig,sys; sys.exit(0 if sysconfig.get_config_var("PYTHONFRAMEWORK") else 1)' \
  || { echo "ERROR: $PYBIN is not a framework build; py2app needs one (try PYBIN=/opt/homebrew/bin/python3.12)"; exit 1; }

mkdir -p "$OUT"
[ -d "$VENV" ] || "$PYBIN" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip py2app

cd "$OUT"                                   # build/ dist/ .eggs/ land here (gitignored), not in the repo
pkill -f "mdreview.app/Contents/MacOS" 2>/dev/null || true   # a running instance locks the bundle → py2app sign fails
rm -rf dist build
"$VENV/bin/python" "$HERE/setup.py" py2app --dist-dir "$OUT/dist" --bdist-base "$OUT/build"

# macOS 15+/26+ on Apple Silicon KILLS a bundle whose Mach-O signatures py2app invalidated when it
# rewrote install-name paths ("CODESIGNING Invalid Page" on launch). Sign inside-out so it runs.
#   local dev:  CODESIGN_IDENTITY unset -> ad-hoc ("-"), no hardened runtime (runs locally only).
#   CI/release: CODESIGN_IDENTITY="Developer ID Application: … (TEAMID)" -> hardened runtime +
#               entitlements + secure timestamp, so the result is notarizable (P3).
APP="$OUT/dist/mdreview.app"
ID="${CODESIGN_IDENTITY:--}"
ENT="$HERE/entitlements.plist"
if [ "$ID" = "-" ]; then
  SIGN=(codesign --force -s - --timestamp=none)
else
  SIGN=(codesign --force -s "$ID" --options runtime --entitlements "$ENT" --timestamp)
fi
find "$APP" -type f \( -name "*.so" -o -name "*.dylib" \) -print0 | xargs -0 -I {} "${SIGN[@]}" {}
find "$APP/Contents/Frameworks" -type f -name "Python" -print0 2>/dev/null | xargs -0 -I {} "${SIGN[@]}" {}
[ -f "$APP/Contents/MacOS/python" ] && "${SIGN[@]}" "$APP/Contents/MacOS/python"
"${SIGN[@]}" "$APP"                                  # seal the app last (no --deep: nested already signed)
codesign --verify --strict "$APP" && echo "  signed [$([ "$ID" = "-" ] && echo ad-hoc || echo "$ID")] + verified"
echo "Built: $APP"
