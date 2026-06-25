#!/usr/bin/env python3
"""PreToolUse hook: lock the repo root.

Blocks any Write/Edit/NotebookEdit that would ADD a new file or directory at the
repo root. The root is default-DENY: only the allowlisted entries (plus the
gitignored .scratch/ escape hatch) are writable at the top level; everything else
must live in a subdirectory. See CLAUDE.md -> "The repo root is LOCKED".

Editing an existing allowlisted root file (README.md, CLAUDE.md, ...) and writing
anywhere inside an allowlisted dir (src/, web/, ...) are allowed. Creating a new
root file, or a file inside a brand-new root directory, is denied.

Fails OPEN on any parse/IO error or for paths outside the project root, so it can
never trap a session or interfere with cross-project writes.
"""
import sys, json, os

ALLOWED_DIRS = {"src", "web", "tests", "docs", "infra",
                ".claude", ".github", ".git", ".scratch"}
ALLOWED_FILES = {"README.md", "CLAUDE.md", "LICENSE", "Makefile", ".gitignore"}


def allow():
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    allow()

if data.get("tool_name") not in ("Write", "Edit", "NotebookEdit"):
    allow()

ti = data.get("tool_input") or {}
fp = ti.get("file_path") or ti.get("notebook_path")
if not fp:
    allow()

root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
try:
    rel = os.path.relpath(os.path.abspath(fp), os.path.abspath(root))
except Exception:
    allow()

# Outside the project root -> not our concern (the cross-project hook governs that).
if rel == os.curdir or rel.startswith(os.pardir):
    allow()

parts = rel.split(os.sep)
if len(parts) > 1:
    # Writing inside a subdirectory: its top-level component must be allowlisted.
    if parts[0] in ALLOWED_DIRS:
        allow()
else:
    # Writing a file directly at the root.
    if rel in ALLOWED_FILES:
        allow()

reason = (
    "BLOCKED by the root-lock hook: '%s' would add a NEW entry to the LOCKED repo root.\n"
    "The root is default-DENY (see CLAUDE.md -> \"The repo root is LOCKED\"). Approved root =\n"
    "  src/ web/ tests/ docs/ infra/ .claude/ .github/  +  README.md CLAUDE.md LICENSE Makefile .gitignore\n"
    "Put it in a subdirectory instead: service code -> src/, frontend -> web/app/, tests -> tests/,\n"
    "docs/notes/plans -> docs/, Dockerfiles/compose/env -> infra/, throwaway/scratch -> .scratch/ (gitignored).\n"
    "If a NEW root entry is genuinely required, do NOT create it: STOP and ask the human (what it is,\n"
    "why it cannot live in a subdir, what breaks without it at root). Default answer: no."
) % rel

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": reason,
}}))
sys.exit(0)
