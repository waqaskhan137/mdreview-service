#!/usr/bin/env bash
# agent-user-setup.sh — idempotent installer for the restricted, READ-ONLY `agent` user on Kapture.
# Plan: docs/design/kapture-agent-user-spine.md. Run ONCE by rana on the host:
#     sudo AGENT_PUBKEY="ssh-ed25519 AAAA... kapture-agent" bash infra/deploy/agent-user-setup.sh
#
# WHY a script, not hand-edits: hand-built host state drifts from the repo (the #86 failure class this
# whole plan exists to kill). This is checked in, reviewed, idempotent (safe to re-run), logs what it
# did, and leaves `rana` untouched. check-drift.sh (once rewritten, plan §7.2) asserts the result.
#
# SAFETY: the only step that can lock anyone out is the sshd hardening. This script prints a BIG warning
# and requires CONFIRM_SSHD=1 to apply it; without that it installs everything else and tells you the
# sshd lines to review. Do the sshd step only with a root-console recovery path confirmed and a second
# rana session held open (plan §9).
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run as root (sudo)"; exit 1; }

: "${AGENT_PUBKEY:?set AGENT_PUBKEY to the kapture-agent public key line}"
# drift-check is gated OFF until check-drift.sh is rewritten for the native plane (plan §7.2). Set
# ENABLE_DRIFT=1 only after that lands, so the agent can never run the stale oauth2-era script.
ENABLE_DRIFT="${ENABLE_DRIFT:-0}"
SRC_DIR="$(cd "$(dirname "$0")/agent" && pwd)"
DEST=/usr/local/agent
say() { printf '  %s\n' "$*"; }

echo "== agent-user-setup (idempotent) =="

# 1. the user: no usable password, no sudo group, NOT in docker group --------------------------------
#
# TWO COUNTERINTUITIVE CHOICES — do NOT "harden" them back, both were verified to BREAK the boundary:
#
#  a) shell is /bin/bash, NOT /usr/sbin/nologin.  sshd runs a forced command via the user's LOGIN
#     SHELL (`$SHELL -c "<command>"`). With nologin the shell just prints "This account is currently
#     not available" and exits, so dispatch.sh NEVER RUNS — the account is unusable, not safer. The
#     security here comes from the forced command + no-pty + restrict in authorized_keys, which apply
#     to every connection with that key; the shell is only ever used to exec dispatch.sh.
#
#  b) the password is an unguessable random string, NOT `passwd -l`.  `passwd -l` writes a "!" prefix
#     into /etc/shadow, and sshd's locked-account check (auth.c / platform_locked_account) rejects the
#     login BEFORE public-key auth is considered — logging "User agent not allowed because account is
#     locked". Note `usermod -p '*'` fails the same way (LOCKED_PASSWD_STRING). A random 48-byte value
#     is not a valid crypt() hash, so NO password can ever match it, while leaving the account
#     un-flagged so pubkey auth works.
if ! id agent &>/dev/null; then
  useradd --create-home --shell /bin/bash --comment "restricted read-only agent" agent
  say "created user agent"
else
  say "user agent exists"
fi
usermod -s /bin/bash agent                       # idempotent: repair a nologin shell if one crept in
usermod -p "$(openssl rand -base64 48 2>/dev/null | tr -d ':\n' \
              || head -c 48 /dev/urandom | base64 | tr -d ':\n')" agent
case "$(passwd -S agent | awk '{print $2}')" in
  L|LK) echo "FATAL: agent account still flagged locked; sshd would refuse pubkey auth" >&2; exit 1 ;;
esac
say "agent: shell=/bin/bash, password unguessable-and-unusable, account NOT locked"
# hard assert it never gained docker/sudo/wheel (root-equivalent) — fail loudly if it did
for g in docker sudo wheel; do
  if id -nG agent | tr ' ' '\n' | grep -qx "$g"; then
    echo "FATAL: agent is in group '$g' (root-equivalent). Remove it before proceeding." >&2; exit 1
  fi
done
say "confirmed agent not in docker/sudo/wheel"

# 2. wrappers + dispatcher: root:root, in a root-owned dir -------------------------------------------
install -d -o root -g root -m 0755 "$DEST"
for f in dispatch.sh agent-logs agent-status agent-drift; do
  install -o root -g root -m 0755 "$SRC_DIR/$f" "$DEST/$f"
done
say "installed $DEST/{dispatch.sh,agent-logs,agent-status,agent-drift} root:root 0755 (dir 0755)"

# 3. audit sink: journald (dispatch.sh logs via `logger -t agent-dispatch`) --------------------------
# No file to create: the record lives in journald (root-owned, tamper-evident, the agent can only
# append via logger, never rewrite). Read it with `journalctl -t agent-dispatch`. If you want a plain
# file too, route the tag with rsyslog (a ROOT writer): e.g. a /etc/rsyslog.d/ rule matching
# programname 'agent-dispatch' -> /var/log/agent-dispatch.log. Intentionally NOT done here (keeps the
# agent off the file entirely); journald is the audit of record.
say "audit sink = journald (journalctl -t agent-dispatch); no agent-writable file"

# 4. sudoers: exact-command, validated before install -------------------------------------------------
# When drift is disabled, install a copy WITHOUT the agent-drift line so the verb truly can't run.
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
if [[ "$ENABLE_DRIFT" == "1" ]]; then
  cp "$SRC_DIR/agent.sudoers" "$tmp"
else
  grep -v 'agent-drift' "$SRC_DIR/agent.sudoers" >"$tmp"
  say "drift-check DISABLED (ENABLE_DRIFT=1 to enable once check-drift.sh is native-plane)"
fi
visudo -cf "$tmp" >/dev/null || { echo "FATAL: sudoers failed visudo -c" >&2; exit 1; }
install -o root -g root -m 0440 "$tmp" /etc/sudoers.d/agent
say "installed /etc/sudoers.d/agent 0440 (visudo-validated)"

# 5. authorized_keys: forced command, no shell, no forwarding ----------------------------------------
install -d -o agent -g agent -m 0700 /home/agent/.ssh
AK=/home/agent/.ssh/authorized_keys
OPTS='command="/usr/local/agent/dispatch.sh",no-port-forwarding,no-agent-forwarding,no-pty,no-X11-forwarding,restrict'
printf '%s %s\n' "$OPTS" "$AGENT_PUBKEY" >"$AK"
chown agent:agent "$AK"; chmod 0600 "$AK"
say "wrote $AK with forced-command (no pty, no forwarding)"

# 6. sshd hardening — GATED (the only lockout-capable step) -------------------------------------------
SSHD_DROPIN=/etc/ssh/sshd_config.d/50-agent-hardening.conf
read -r -d '' SSHD_BODY <<'EOF' || true
# Installed by agent-user-setup.sh (plan §7.3). Blocks the env-injection vector for the agent user:
# its home is agent-writable, so ~/.ssh/environment must NOT be honoured, and MDR_*/LD_* must not pass.
PermitUserEnvironment no
AcceptEnv LANG LC_*
EOF
if [[ "${CONFIRM_SSHD:-0}" == "1" ]]; then
  echo "$SSHD_BODY" >"$SSHD_DROPIN"; chmod 0644 "$SSHD_DROPIN"
  if sshd -t; then systemctl reload ssh 2>/dev/null || systemctl reload sshd; say "sshd hardening applied + reloaded"
  else echo "FATAL: sshd -t failed; removing drop-in, NOT reloading" >&2; rm -f "$SSHD_DROPIN"; exit 1; fi
else
  echo
  echo "!! sshd hardening NOT applied (CONFIRM_SSHD!=1). This is the ONLY lockout-capable step."
  echo "!! Confirm a root-console recovery path + hold a second rana session, THEN re-run with"
  echo "!! CONFIRM_SSHD=1. It would install $SSHD_DROPIN with:"
  echo "$SSHD_BODY" | sed 's/^/     /'
fi

echo "== done. Verify per plan §9: bare connection refused+logged, docker exec refused, sudo -l shows only the wrappers. =="
