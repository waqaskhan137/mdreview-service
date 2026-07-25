#!/usr/bin/env bash
# dispatch.sh — the SSH forced-command target for the restricted `agent` user on Kapture.
#
# Design: docs/design/kapture-agent-user-spine.md (READ-ONLY model). This is Layer A's landing point.
# The agent's authorized_keys pins command="/usr/local/agent/dispatch.sh",no-pty,restrict — so the
# agent NEVER gets a shell; whatever it typed arrives in $SSH_ORIGINAL_COMMAND and we parse ONE verb.
#
# This file is root-owned (root:root 0755) in a root-owned dir (/usr/local/agent 0755). If the agent
# could write it, the whole boundary is gone. It is the ONLY thing the agent key can execute.
#
# Every invocation is audit-logged BEFORE dispatch (accept or reject), to a root-owned append-only log
# AND journald, so a lost key / odd command is never silent.
set -euo pipefail
set -f                      # no globbing: `logs *` must not expand
IFS=' '

WRAP=/usr/local/agent                       # root-owned wrappers live here

# --- audit -------------------------------------------------------------------------------------------
# Sink is JOURNALD (via logger), on purpose. dispatch.sh runs AS the agent, so a plain root-owned file
# it must write is a contradiction (the agent either can't write it, or could tamper with it). logger
# hands the record to journald, which stores it root-side, tamper-evident, and outside the deploy dir
# (survives its loss). Read it with:  journalctl -t agent-dispatch
# (Optional: route this tag to /var/log/agent-dispatch.log via rsyslog — a ROOT writer, never the agent
#  — see agent-user-setup.sh. Not required; journald is the record.)
audit() {  # $1 = decision (accept:<verb> | reject)
  local ts; ts="$(date -u +%FT%TZ)"
  logger -t agent-dispatch -- \
    "$ts client=${SSH_CLIENT:-?} decision=$1 raw=[${SSH_ORIGINAL_COMMAND:-}]" || true
}

# --- parse exactly one verb + args --------------------------------------------------------------------
# ${SSH_ORIGINAL_COMMAND:-} : a bare `ssh kapture-agent` leaves it UNSET; under `set -u` that would
# abort here, BEFORE we log+deny — i.e. an unlogged refusal. The :- makes the empty case flow through
# to default-deny (which logs).
read -r -a parts <<<"${SSH_ORIGINAL_COMMAND:-}"
verb="${parts[0]:-}"

deny() { audit "reject"; echo "refused: not an allowed command" >&2; exit 1; }

case "$verb" in
  logs)        audit "accept:logs";  exec sudo -n "$WRAP/agent-logs"   "${parts[@]:1}" ;;
  ps|status)   audit "accept:status";exec sudo -n "$WRAP/agent-status" ;;
  health)      audit "accept:health";exec sudo -n "$WRAP/agent-status" health ;;
  drift-check) audit "accept:drift"; exec sudo -n "$WRAP/agent-drift" ;;
  *)           deny ;;
esac
