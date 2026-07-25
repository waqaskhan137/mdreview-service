#!/usr/bin/env bash
# test-dispatch.sh — self-check for the agent boundary (dispatch.sh + agent-logs). Runs anywhere; stubs
# sudo/docker/logger and arms rm/id tripwires, drives dispatch.sh through valid + attack inputs, and
# asserts: allowed verbs dispatch to exactly one fixed wrapper; everything else is default-denied;
# command injection is inert (no shell/eval), so rm/id never execute. No root, no host, no docker needed.
#   bash infra/deploy/agent/test-dispatch.sh   # exit 0 = pass
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
bin="$tmp/bin"; marks="$tmp/marks"; mkdir -p "$bin" "$marks"

# sudo stub: drop -n, remap the pinned /usr/local/agent path to this repo copy, exec the REAL wrapper
cat >"$bin/sudo" <<EOF
#!/usr/bin/env bash
[[ "\${1:-}" == "-n" ]] && shift
cmd="\$1"; shift; cmd="\${cmd/\/usr\/local\/agent/$here}"
exec "\$cmd" "\$@"
EOF
printf '#!/usr/bin/env bash\nprintf "DOCKER:"; for a in "$@"; do printf " <%%s>" "$a"; done; echo\n' >"$bin/docker"
printf '#!/usr/bin/env bash\n: > "%s/rm_fired"\n' "$marks" >"$bin/rm"
printf '#!/usr/bin/env bash\n: > "%s/id_fired"\n' "$marks" >"$bin/id"
printf '#!/usr/bin/env bash\n:\n' >"$bin/logger"
chmod +x "$bin"/*

d() {  # run dispatch with a given SSH_ORIGINAL_COMMAND ($1 = "UNSET" to leave it unset)
  if [[ "$1" == "UNSET" ]]; then PATH="$bin:$PATH" SSH_CLIENT=x bash "$here/dispatch.sh" 2>&1 || true
  else PATH="$bin:$PATH" SSH_CLIENT=x SSH_ORIGINAL_COMMAND="$1" bash "$here/dispatch.sh" 2>&1 || true; fi
}
fail=0
ok(){ printf '  ok   %s\n' "$1"; }
bad(){ printf '  FAIL %s\n' "$1"; fail=1; }
want_deny(){ d "$1" | grep -q '^refused:' && ok "deny: ${2:-$1}" || bad "should deny: ${2:-$1}"; }
want_docker(){ [[ "$(d "$1")" == "DOCKER: $2" ]] && ok "dispatch: $1" || bad "expected [$2] for [$1], got [$(d "$1")]"; }
want_wrapreject(){ d "$1" | grep -q "$2" && ok "wrapper-reject: $1" || bad "expected wrapper reject ($2): $1"; }

echo "== default-deny =="
want_deny UNSET "bare connection"
want_deny ""    "empty"
want_deny "docker exec -it mdreview sh"
want_deny "bash -i"
want_deny "deploy prod"
want_deny "cat /home/rana/mdreview-deploy/.env"

echo "== allowed verbs dispatch to the fixed wrapper =="
want_docker "logs mdreview 50"        "<logs> <--tail> <50> <mdreview>"
want_docker "logs mdreview"           "<logs> <--tail> <200> <mdreview>"
want_docker "logs mdreview-staging 5" "<logs> <--tail> <5> <mdreview-staging>"

echo "== injection is inert (rm/id must never fire) =="
want_wrapreject "logs mdreview 50; rm -rf /" "must be an integer"
want_docker     "logs mdreview 50 && id"     "<logs> <--tail> <50> <mdreview>"   # && id are inert extra argv
want_wrapreject 'logs mdreview $(id)'        "must be an integer"
want_wrapreject "logs *"                     "not allowed"                       # set -f: no glob expansion
want_wrapreject "logs /etc/passwd 50"        "not allowed"

echo "== tripwires =="
[[ -e "$marks/rm_fired" || -e "$marks/id_fired" ]] && bad "a tripwire fired (injection succeeded)" || ok "no rm/id ever executed"

echo
[[ $fail -eq 0 ]] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
