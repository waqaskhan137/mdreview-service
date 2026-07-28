#!/usr/bin/env bash
# drift_staging_selfcheck.sh — self-check for the image-reference comparison in
# infra/deploy/check-drift-staging.sh (#214). Runs anywhere: stubs `docker` on PATH, uses
# HOST= (local mode, no ssh hop) and MDR_DEPLOY_DIR pointing at a temp dir with a fake compose
# file. No host, no ssh, no docker, no network.
#
#   bash tests/drift_staging_selfcheck.sh    # exit 0 = pass
#
# WHY THIS DRIVES THE REAL SCRIPT rather than asserting on its text:
# the check being added could pass VACUOUSLY. On a healthy host the container runs exactly what
# compose pins, so ANY comparison — including a broken one that always returns ok, or one that
# compares a variable to itself — reports "ok" on first run and looks correct. The only way to
# know the comparison works is to feed it a DELIBERATE MISMATCH and require it to fail.
#
# Modelled on infra/deploy/agent/test-dispatch.sh, which stubs the same way.
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
script="$here/infra/deploy/check-drift-staging.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; dir="$tmp/deploy"; mkdir -p "$bin" "$dir"

PINNED="ghcr.io/ranawaqas-ai/mdreview-service-latex:dev"
WRONG="ghcr.io/ranawaqas-ai/mdreview-service:dev"     # CI pushes this too, so the mix-up is real

cat >"$dir/docker-compose.staging.yml" <<EOF
services:
  mdreview-staging:
    image: $PINNED
EOF

# docker stub: only `inspect ... --format {{.Config.Image}}` needs to be interesting. Everything
# else returns empty, which makes the OTHER checks report drift — expected and irrelevant here.
# We assert on the image-ref line specifically, not on the script's overall exit alone.
make_docker() {
  cat >"$bin/docker" <<EOF
#!/usr/bin/env bash
for a in "\$@"; do
  case "\$a" in
    *Config.Image*) echo "$1"; exit 0 ;;
  esac
done
exit 1
EOF
  chmod +x "$bin/docker"
}

run_check() {  # $1 = image ref the stubbed docker will report
  make_docker "$1"
  PATH="$bin:$PATH" HOST= MDR_DEPLOY_DIR="$dir" bash "$script" 2>&1
}

fail=0
ok(){   printf '  ok   - %s\n' "$1"; }
bad(){  printf '  FAIL - %s\n' "$1"; fail=1; }

# 1. MATCH: the container runs exactly what compose pins -> no image-ref drift line.
out_match="$(run_check "$PINNED")"
if grep -q "image ref matches compose" <<<"$out_match"; then
  ok "matching ref reports ok"
else
  bad "matching ref did not report ok"; printf '%s\n' "$out_match" | sed 's/^/        /'
fi
if grep -q "image ref MISMATCH" <<<"$out_match"; then
  bad "matching ref wrongly reported a MISMATCH"
else
  ok "matching ref produces no mismatch line"
fi

# 2. MISMATCH: the container runs the OTHER repository -> drift, naming BOTH sides.
out_wrong="$(run_check "$WRONG")"
if grep -q "image ref MISMATCH" <<<"$out_wrong"; then
  ok "mismatched ref is caught"
else
  bad "MISMATCH NOT CAUGHT — this is the whole point of the check"
  printf '%s\n' "$out_wrong" | sed 's/^/        /'
fi
grep -q "$PINNED" <<<"$out_wrong" && ok "drift line names the expected ref" \
  || bad "drift line does not name what compose pins"
grep -q "$WRONG" <<<"$out_wrong" && ok "drift line names the running ref" \
  || bad "drift line does not name what is actually running"

# 3. The mismatch must make the script EXIT NON-ZERO, or CI would never notice.
make_docker "$WRONG"
PATH="$bin:$PATH" HOST= MDR_DEPLOY_DIR="$dir" bash "$script" >/dev/null 2>&1
[ $? -ne 0 ] && ok "mismatch exits non-zero" || bad "mismatch exited 0 — drift would be invisible"

# 4. UNREADABLE IS NOT MATCHING (#216's rule applied here): if the ref cannot be read, that is
#    drift, not silence. A checker that treats an empty read as agreement is the #189 failure.
printf '#!/usr/bin/env bash\nexit 1\n' >"$bin/docker"; chmod +x "$bin/docker"
out_empty="$(PATH="$bin:$PATH" HOST= MDR_DEPLOY_DIR="$dir" bash "$script" 2>&1)"
grep -q "could not read the image ref" <<<"$out_empty" && ok "unreadable ref reports drift, not ok" \
  || bad "unreadable ref did not report drift"

echo
[ "$fail" -eq 0 ] && echo "all image-ref drift cases pass" || echo "image-ref drift check FAILED"
exit "$fail"
