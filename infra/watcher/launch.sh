#!/bin/bash
# Watcher launch wrapper (MR-069 / #30). Spawned by watch.py once per Sent review; interpolates the
# child-env contract ($REVIEW_ID / $MDREVIEW_BASE / $MDREVIEW_OWNER, set by watch.py) into the agent
# prompt. The `claude` agent uses ONLY the mdreview MCP tools (--strict-mcp-config pins the tool
# surface to exactly the mdreview server; --allowedTools scopes it; --permission-mode dontAsk denies
# any stray tool cleanly headless). Subscription auth comes from CLAUDE_CODE_OAUTH_TOKEN in the
# environment (mint once with `claude setup-token` — a subscription token, NEVER an API key).
#
# MR-063 RECIPE GOTCHA: `-p "$PROMPT"` MUST be the FINAL argv token. `--allowedTools` is variadic and
# will swallow a trailing bare prompt, so keep -p (and its single prompt arg) last with no flag after.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT="You are an automated agent that just picked up mdreview review $REVIEW_ID at $MDREVIEW_BASE as owner $MDREVIEW_OWNER. Do exactly this using ONLY the mdreview MCP tools: 1. call ping_working with document_id=$REVIEW_ID and owner=$MDREVIEW_OWNER. 2. call list_comments with document_id=$REVIEW_ID status=open. 3. call get_source with document_id=$REVIEW_ID. 4. For EACH open comment, make the exact change the reviewer asks for in the markdown, then call update_source with document_id=$REVIEW_ID and the full new markdown. 5. call resolve_comment for each comment you addressed with a short justification. 6. call hand_back with document_id=$REVIEW_ID and a one-line summary. Keep all unrelated content intact."
exec claude --mcp-config "$DIR/agent-mcp.json" --strict-mcp-config --permission-mode dontAsk --allowedTools "mcp__mdreview__*" -p "$PROMPT"
