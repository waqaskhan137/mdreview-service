#!/bin/sh
# mdreview hosted-instance installer.
#
#   curl -fsSL https://mdreview.space/install.sh | sh
#
# Fetches the stdlib-only MCP wrapper into ~/.mdreview and registers it with Claude Code
# (user scope) so `create_review` etc. work against the hosted instance. You need an API
# token first: sign in at https://app.mdreview.space, "Connect your agent", mint one. Pass it
# as MDREVIEW_TOKEN, or the script prompts for it when run in a terminal:
#
#   curl -fsSL https://mdreview.space/install.sh | MDREVIEW_TOKEN=mdr_xxx sh
#
set -eu

BASE="${MDREVIEW_BASE:-https://app.mdreview.space}"
TARBALL="https://github.com/waqaskhan137/mdreview-service/archive/refs/heads/main.tar.gz"
DEST="$HOME/.mdreview/mdreview-service"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

# 1. Prerequisites. python3 runs the wrapper; the claude CLI owns the config edit (no hand-rolled JSON).
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3, then re-run."
command -v curl    >/dev/null 2>&1 || die "curl not found."
command -v tar     >/dev/null 2>&1 || die "tar not found."
command -v claude  >/dev/null 2>&1 || die "the 'claude' CLI (Claude Code) is not on PATH. Install Claude Code first."
PY="$(python3 -c 'import sys; print(sys.executable)')"
[ -n "$PY" ] || die "could not resolve the python3 interpreter path."

# 2. Token. Env var wins; otherwise prompt from the terminal (stdin is the piped script, so read
#    /dev/tty). Probe openability in a subshell first: `[ -r /dev/tty ]` can pass in CI/piped shells
#    where the device still won't open, and a failed open must fall through to the hint, not a raw error.
if [ -n "${MDREVIEW_TOKEN:-}" ]; then
  TOKEN="$MDREVIEW_TOKEN"
elif ( : < /dev/tty ) 2>/dev/null; then
  printf 'Paste your mdreview API token (from %s, "Connect your agent"): ' "$BASE" > /dev/tty 2>/dev/null || true
  stty -echo < /dev/tty 2>/dev/null || true
  IFS= read -r TOKEN < /dev/tty 2>/dev/null || TOKEN=""
  stty echo < /dev/tty 2>/dev/null || true
  printf '\n' > /dev/tty 2>/dev/null || true
  [ -n "$TOKEN" ] || die "no token entered. Re-run with MDREVIEW_TOKEN=mdr_xxx set."
else
  die "no token. Re-run as:  curl -fsSL https://mdreview.space/install.sh | MDREVIEW_TOKEN=mdr_xxx sh"
fi
case "$TOKEN" in
  mdr_*_*) : ;;
  *) die "that does not look like a token (expected mdr_<id>_<secret>). Mint one at $BASE." ;;
esac

# 3. Fetch the wrapper (stdlib only, no pip install) into ~/.mdreview. Download to a file first so a
#    failed curl gives a precise error instead of feeding an empty stream to tar.
say "Downloading the mdreview MCP wrapper..."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$TARBALL" -o "$TMP/repo.tgz" || die "download failed ($TARBALL)."
tar -xzf "$TMP/repo.tgz" -C "$TMP" || die "extract failed."
set -- "$TMP"/mdreview-service-*
SRC="$1"
[ -f "$SRC/src/mcp_server.py" ] || die "unexpected archive layout (no src/mcp_server.py)."
mkdir -p "$HOME/.mdreview"
rm -rf "$DEST"
mv "$SRC" "$DEST"
WRAPPER="$DEST/src/mcp_server.py"

# 4. Smoke: confirm the wrapper imports under this python before wiring it in.
"$PY" "$WRAPPER" --print-version >/dev/null 2>&1 || die "the wrapper failed to run under $PY."

# 5. Register with Claude Code at user scope. Idempotent: drop any prior entry, re-add.
# ponytail: token is passed via -e, so it is briefly visible in `ps` on a shared box; fine for a
# single-user machine. Upgrade path if that matters: a stdin-fed secret, which claude mcp add lacks today.
claude mcp remove mdreview -s user >/dev/null 2>&1 || true
claude mcp add mdreview -s user \
  -e "MDREVIEW_BASE=$BASE" \
  -e "MDREVIEW_TOKEN=$TOKEN" \
  -- "$PY" "$WRAPPER"

say ""
say "Done. mdreview is registered (user scope) against $BASE."
say "Fully quit and reopen Claude Code, then verify with the mdreview tools: server_info, then list_reviews."
