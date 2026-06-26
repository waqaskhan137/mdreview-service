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
rm -rf dist build
"$VENV/bin/python" "$HERE/setup.py" py2app --dist-dir "$OUT/dist" --bdist-base "$OUT/build"
echo "Built: $OUT/dist/mdreview.app"
