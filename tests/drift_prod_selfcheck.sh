#!/usr/bin/env bash
# drift_prod_selfcheck.sh — self-check for infra/deploy/check-drift.sh (#360), which #360 schedules
# via infra/deploy/systemd/mdreview-driftcheck.{service,timer} but does NOT rewrite: check-drift.sh's
# five invariants are unchanged, only their cadence and visibility are new. Runs anywhere: stubs
# `docker` and `ssh` on PATH, sets HOST= (local mode -- the exact invocation the new systemd unit
# uses) and HOME=<fixture> so the script's hardcoded `~/mdreview-deploy/...` reads resolve into a
# synthetic fixture, never the real host.
#
#   bash tests/drift_prod_selfcheck.sh    # exit 0 = pass
#
# WHY THIS DRIVES THE REAL SCRIPT rather than asserting on its text (same rationale as
# tests/drift_staging_selfcheck.sh / tests/custody_tripwire_selfcheck.py): a comparison that always
# says "ok" passes vacuously on a clean fixture. The only way to know it actually compares anything is
# to plant a divergence and require it to fail — then mutate the comparison itself and require THIS
# selfcheck to notice the detector went silent, by reusing the SAME positive assertion post-mutation
# (the #361 technique) rather than writing a new one that could itself be vacuous.
set -uo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
script="$here/infra/deploy/check-drift.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; mkdir -p "$bin"

fail=0
ok(){  printf '  ok   - %s\n' "$1"; }
bad(){ printf '  FAIL - %s\n' "$1"; fail=1; }

# --- ssh stub: proves HOST= truly engages check-drift.sh's local-mode branch. check-drift.sh reads
# `HOST="${HOST-kapture}"` -- the bare `-` only substitutes the ssh default when HOST is UNSET, so
# HOST= (set-but-empty, exactly what mdreview-driftcheck.service's Environment=HOST= sets) must leave
# HOST empty and `run()` must take the `bash -c` branch, never ssh. Get this wrong (e.g. `${HOST:-...}`)
# and the systemd unit ssh's from the host to itself with no key for that hop -- it fails EVERY run
# for a reason that has nothing to do with drift, which is exactly the "nobody reads it" failure #360
# exists to kill. Asserted first, before any fixture content matters.
cat >"$bin/ssh" <<'EOF'
#!/usr/bin/env bash
echo "SSH-CALLED $*" >>"${SSH_MARKER:?}"
exit 1
EOF
chmod +x "$bin/ssh"

# --- docker stub: check-drift.sh only ever calls `docker inspect <container> --format '...Mounts...'`
# or `...Config.Env...`. Anything else is unexpected in this test and fails loudly (exit 3) rather
# than silently defaulting to empty output, which check-drift.sh's own mounts check would read as
# "ok" -- an unreadable stub must never masquerade as a match (the #216 rule).
cat >"$bin/docker" <<'EOF'
#!/usr/bin/env bash
container=""; mode=""
for a in "$@"; do
  case "$a" in
    mdreview|mdreview-oauth2-proxy) container="$a" ;;
  esac
  case "$a" in
    *Config.Env*) mode=env ;;
    *Mounts*)     mode=mounts ;;
  esac
done
f="${DOCKER_FIXTURE_DIR:?DOCKER_FIXTURE_DIR not set}/${mode}-${container}.txt"
if [ -f "$f" ]; then cat "$f"; exit 0; fi
echo "docker stub: no fixture for mode=$mode container=$container (looked for $f)" >&2
exit 3
EOF
chmod +x "$bin/docker"

# --- fixture builder ---------------------------------------------------------------------------------
# build_fixture DIR MODE lays out DIR/home/mdreview-deploy/... (for `~` reads under HOME=DIR/home) and
# DIR/docker/*.txt (read by the docker stub via DOCKER_FIXTURE_DIR=DIR/docker). MODE=clean satisfies
# all five invariants; drift-auth / drift-oauth each break exactly one, via two structurally different
# mechanisms (a docker-inspect env read vs a config-file read), so "fires on divergence" isn't proven
# for only one code path.
build_fixture() {
  local dir="$1" mode="$2"
  rm -rf "$dir"
  mkdir -p "$dir/home/mdreview-deploy/oauth2-proxy" "$dir/docker"

  cat >"$dir/docker/mounts-mdreview.txt" <<'M'
/home/rana/mdreview-deploy
/var/lib/docker/volumes/mdreview-data/_data
M
  cp "$dir/docker/mounts-mdreview.txt" "$dir/docker/mounts-mdreview-oauth2-proxy.txt"

  cat >"$dir/docker/env-mdreview.txt" <<'E'
MDREVIEW_REQUIRE_AUTH=1
MDREVIEW_PUBLIC_BASE=https://app.mdreview.space
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
E

  cat >"$dir/home/mdreview-deploy/oauth2-proxy/oauth2-proxy.cfg" <<'C'
provider = "oidc"
whitelist_domains = [ "app.mdreview.space" ]
redirect_url = "https://app.mdreview.space/oauth2/callback"
C

  cat >"$dir/home/mdreview-deploy/oauth2-proxy/invited-emails.txt" <<'A'
# invited users
alice@example.com
bob@example.com
A

  case "$mode" in
    clean) : ;;
    drift-auth)
      # The #360 incident's exact shape: a setting the repo's compose declares is silently absent
      # from what the container is actually running.
      grep -v REQUIRE_AUTH "$dir/docker/env-mdreview.txt" >"$dir/docker/env-mdreview.txt.tmp"
      mv "$dir/docker/env-mdreview.txt.tmp" "$dir/docker/env-mdreview.txt"
      ;;
    drift-oauth)
      printf 'provider = "oidc"\nredirect_url = "https://app.mdreview.space/oauth2/callback"\n' \
        >"$dir/home/mdreview-deploy/oauth2-proxy/oauth2-proxy.cfg"
      ;;
    *) echo "build_fixture: unknown mode $mode" >&2; exit 9 ;;
  esac
}

# run_check FIXTURE_DIR -> prints check-drift.sh's stdout+stderr; caller reads $? for its exit code.
run_check() {
  local fixture="$1"
  rm -f "$tmp/ssh-called"
  PATH="$bin:$PATH" HOST= HOME="$fixture/home" DOCKER_FIXTURE_DIR="$fixture/docker" \
    SSH_MARKER="$tmp/ssh-called" bash "$script" 2>&1
}

# Reused verbatim in the mutation test (step 4) and the healed-fixture test (step 5) -- the same
# positive assertion, not a fresh one, is what proves this selfcheck would notice either the detector
# going silent or a genuinely-fixed host going quiet again.
fires_on_auth_drift() {  # $1=stdout $2=exit-code
  local out="$1" rc="$2"
  [ "$rc" -ne 0 ] && grep -qF "DRIFT: REQUIRE_AUTH not =1" <<<"$out"
}

echo "== 0. HOST= truly avoids ssh (the load-bearing assumption behind mdreview-driftcheck.service) =="
build_fixture "$tmp/clean" clean
out0="$(run_check "$tmp/clean")"; rc0=$?
if [ -s "$tmp/ssh-called" ]; then
  bad "HOST= invoked ssh -- Environment=HOST= in the systemd unit would ssh the host to itself and fail every run"
  sed 's/^/        /' "$tmp/ssh-called"
else
  ok "HOST= stays local (no ssh hop) -- Environment=HOST= in the systemd unit is correct"
fi

echo
echo "== 1. clean fixture: all 5 invariants pass, zero DRIFT lines, exit 0 (stays quiet on an identical pair) =="
if [ "$rc0" -eq 0 ]; then ok "clean fixture exits 0"; else bad "clean fixture exited $rc0 (expected 0)"; fi
if grep -q "DRIFT" <<<"$out0"; then
  bad "clean fixture reported DRIFT"; echo "$out0" | sed 's/^/        /'
else
  ok "clean fixture reports no DRIFT lines"
fi
for line in "no stray ~/mdreview-src deploy dir" \
            "mdreview mounts from mdreview-deploy" \
            "mdreview-oauth2-proxy mounts from mdreview-deploy" \
            "REQUIRE_AUTH=1" "PUBLIC_BASE canonical" \
            "oauth whitelist_domains set" "oauth redirect_url canonical" \
            "allowlist has 2 members"; do
  if grep -qF "$line" <<<"$out0"; then ok "clean fixture: '$line'"
  else bad "clean fixture missing expected ok line: '$line'"; fi
done

echo
echo "== 2. planted divergence (REQUIRE_AUTH absent): fires, and ONLY that check -- no false-positive cascade =="
build_fixture "$tmp/drift-auth" drift-auth
out2="$(run_check "$tmp/drift-auth")"; rc2=$?
if fires_on_auth_drift "$out2" "$rc2"; then
  ok "fires: exit non-zero and names REQUIRE_AUTH"
else
  bad "did NOT fire on planted REQUIRE_AUTH drift"; echo "$out2" | sed 's/^/        /'
fi
for line in "no stray ~/mdreview-src deploy dir" "mdreview mounts from mdreview-deploy" \
            "oauth whitelist_domains set" "allowlist has 2 members"; do
  if grep -qF "$line" <<<"$out2"; then ok "drift-auth fixture: unrelated check still ok ('$line')"
  else bad "drift-auth fixture: unrelated check '$line' wrongly not-ok (false-positive cascade)"; fi
done

echo
echo "== 3. planted divergence (oauth2-proxy.cfg missing whitelist_domains): fires via a DIFFERENT code path (file read, not docker inspect) =="
build_fixture "$tmp/drift-oauth" drift-oauth
out3="$(run_check "$tmp/drift-oauth")"; rc3=$?
if [ "$rc3" -ne 0 ] && grep -qF "DRIFT: oauth whitelist_domains missing" <<<"$out3"; then
  ok "fires: exit non-zero and names oauth whitelist_domains"
else
  bad "did NOT fire on planted oauth whitelist_domains drift"; echo "$out3" | sed 's/^/        /'
fi
if grep -qF "REQUIRE_AUTH=1" <<<"$out3"; then ok "drift-oauth fixture: REQUIRE_AUTH still ok (unrelated check unaffected)"
else bad "drift-oauth fixture: REQUIRE_AUTH wrongly not-ok"; fi

echo
echo "== 4. mutation test: neuter check-drift.sh's REQUIRE_AUTH comparison, prove THIS selfcheck notices the detector going silent =="
ANCHOR='grep -qx "MDREVIEW_REQUIRE_AUTH=1"'
if ! grep -qF "$ANCHOR" "$script"; then
  bad "mutation harness: expected anchor not found in check-drift.sh (script changed -- update this selfcheck's anchor)"
else
  mutated="$tmp/mutated-check-drift.sh"
  sed "s/${ANCHOR//\//\\/}/grep -q \"\"/" "$script" >"$mutated"
  chmod +x "$mutated"
  real_script="$script"; script="$mutated"
  out4="$(run_check "$tmp/drift-auth")"; rc4=$?
  script="$real_script"
  if fires_on_auth_drift "$out4" "$rc4"; then
    bad "MUTATION NOT CAUGHT -- neutered comparison still reported drift (this selfcheck's patch is wrong, not a real result)"
    echo "$out4" | sed 's/^/        /'
  else
    ok "MUTATION CAUGHT: the SAME 'fires on planted drift' assertion used in step 2 now evaluates false against the neutered detector -- this selfcheck would notice check-drift.sh's comparison going silent"
  fi
fi

echo
echo "== 5. fixture healed in place: the SAME assertion correctly flips back to quiet (it isn't a tautology that always reports drift) =="
printf 'MDREVIEW_REQUIRE_AUTH=1\nMDREVIEW_PUBLIC_BASE=https://app.mdreview.space\n' >"$tmp/drift-auth/docker/env-mdreview.txt"
out5="$(run_check "$tmp/drift-auth")"; rc5=$?
if fires_on_auth_drift "$out5" "$rc5"; then
  bad "healed fixture still reads as drifted -- the assertion is not actually discriminating"
  echo "$out5" | sed 's/^/        /'
else
  ok "healed fixture is quiet again (exit $rc5, no REQUIRE_AUTH DRIFT line) -- same assertion, real signal"
fi

echo
[ "$fail" -eq 0 ] && echo "drift-prod selfcheck: all clear" || echo "drift-prod selfcheck FAILED"
exit "$fail"
