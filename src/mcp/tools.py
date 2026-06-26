"""The agent-visible surface: tool schemas, the workflow INSTRUCTIONS, and this server's identity.

Static metadata only (no I/O): tools/list serves TOOLS, initialize serves SERVER_INFO + INSTRUCTIONS,
and _tools_hash() fingerprints the whole surface so a stale running server is detectable. The HTTP
side (mapping a tool call onto an endpoint) lives in client.py; the JSON-RPC plumbing in __main__.py.
"""
import json
import hashlib

PROTOCOL_VERSION = "2025-06-18"   # MCP spec revision this server targets
SERVER_INFO = {"name": "mdreview-mcp", "version": "0.1.0"}

# Surfaced to the agent on `initialize` (MCP `instructions`) so the whole workflow reaches it, not
# just per-tool blurbs.
INSTRUCTIONS = (
    "mdreview is human-in-the-loop markdown review. Loop: create_review(markdown) -> hand the "
    "returned review_url to a human -> poll get_status (cheap) and read get_feedback / list_comments "
    "when it changes -> apply the edits and update_source(id, markdown) (the human's page "
    "live-reloads). get_source reads the current draft (e.g. when resuming a review you didn't keep "
    "in memory). Comments are the primary feedback surface: call list_comments(status=\"open\") "
    "FIRST, reply_to_comment to discuss, resolve_comment only when actually addressed (justification "
    "optional but recommended — the reviewer can reopen; you never reopen, that's their UI action). "
    "Watch comments_updated on get_status for thread changes. AUTHOR TO THE VIEWER'S RENDERER: it "
    "renders Mermaid diagrams (```mermaid), LaTeX math ($…$/$$…$$), GFM footnotes, language-labelled "
    "syntax-highlighted code, and images (attach_asset) — so a flow / decision tree / state machine / "
    "architecture belongs in a ```mermaid diagram, NOT ASCII art or a plain ``` fence (which renders as "
    "monospace text, not a picture). Operate only on reviews you created; the service has no auth (roles are attribution, not "
    "security). If a tool you expect is missing or misbehaves, the running server may be stale: "
    "server_info reports its tools_hash, but you CANNOT conclude 'stale' from inside MCP — a human/CI "
    "compares that hash to the repo's `python3 mcp_server.py --print-version` and reconnects the client "
    "on a mismatch (the server signals staleness; it cannot reload itself)."
)

_ID = {"type": "string", "description": "the opaque review id"}
_DOCID = {"type": "string", "description": "the review id the comments belong to (the document_id)"}
_CID = {"type": "string", "description": "the comment id (cXXXXXXXXXX)"}

# The 20 tools (mostly 1:1 with the HTTP API; hand_back + ping_working both map onto POST /handoff).
# Static metadata served by tools/list.
TOOLS = [
    {
        "name": "create_review",
        "description": "Create a review from markdown; returns the id and the review/feedback urls. "
                       "AUTHOR TO THE VIEWER'S RENDERER, don't dumb the markdown down: it renders GFM + "
                       "**Mermaid diagrams** (```mermaid fenced blocks), **LaTeX math** ($…$ inline, "
                       "$$…$$ display), **GFM footnotes**, **syntax-highlighted** fenced code (label the "
                       "language), and **images** (attach via attach_asset). So a flow / decision-tree / "
                       "state machine / architecture should be a ```mermaid diagram — NOT ASCII art or a "
                       "plain ``` code block (a plain fence renders as monospace text, not a picture). "
                       "Optional project/session/source_path tag its provenance for the dashboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "markdown": {"type": "string", "description": "the document to review"},
                "title": {"type": "string"},
                "project": {"type": "string"},
                "session": {"type": "string"},
                "source_path": {"type": "string"},
            },
            "required": ["markdown"],
        },
    },
    {
        "name": "list_reviews",
        "description": "List every review with its status (awaiting/feedback/resolved), note counts, and revision.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_review",
        "description": "Get one review's metadata.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "get_source",
        "description": "Get a review's current source markdown — the draft you edit. Read it before "
                       "applying feedback when you didn't keep the draft in memory (e.g. a resumed session).",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "get_feedback",
        "description": "Get a review's human feedback: structured notes (now including a projection of "
                       "the comments) plus the rendered markdown block. For the full threads use list_comments.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "get_status",
        "description": "Cheap poll: a review's source_updated, feedback_updated, and comments_updated "
                       "timestamps. Watch comments_updated for new/changed comment threads.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "update_source",
        "description": "Push a revised draft (applied edits). Snapshots a history round and live-reloads "
                       "the human's page. Same authoring rule as create_review: use the viewer's "
                       "renderer — a flow/decision-tree/architecture belongs in a ```mermaid block, "
                       "math in $…$/$$…$$, code in a language-labelled fence — not ASCII art or a plain "
                       "```  fence.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": _ID, "markdown": {"type": "string", "description": "the new draft"}},
            "required": ["id", "markdown"],
        },
    },
    {
        "name": "get_history",
        "description": "List a review's past rounds; with `round`, fetch one past draft plus the feedback it received.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": _ID, "round": {"type": "integer", "description": "round number; omit for the list"}},
            "required": ["id"],
        },
    },
    {
        "name": "delete_review",
        "description": "Delete a review and its data.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "attach_asset",
        "description": "Attach an image to a review so the viewer serves and renders it. "
                       "PREFER `path`: pass a local file path and this server reads + encodes the "
                       "bytes itself, so you never emit base64 through your context (the right way for "
                       "anything bigger than a tiny icon — a 38KB SVG is ~50K chars of base64 you "
                       "should NOT hand-carry). Use `content_b64` only if the file isn't on this "
                       "machine. Pass `name` as the exact src the draft uses (e.g. \"/assets/x.png\" "
                       "or \"fig/y.svg\"); attach once — it survives every update_source revision. "
                       "Returns the stored name and the served url.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": _ID,
                "name": {"type": "string", "description": "the draft <img> src this asset backs (the match key)"},
                "path": {"type": "string", "description": "local file path the server reads + base64-encodes (preferred)"},
                "content_b64": {"type": "string", "description": "the file bytes, base64-encoded (use only if no local path)"},
            },
            "required": ["id", "name"],
        },
    },
    {
        "name": "list_assets",
        "description": "List a review's attached assets (name, stored name, served url, bytes, ctype).",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "create_comment",
        "description": "Author a NEW comment on a document, anchored to a quoted phrase — use this to "
                       "leave review feedback at a specific spot (you act as a reviewer). Pass "
                       "`quoted_text` = the exact phrase from the source to anchor to (the viewer "
                       "highlights it wherever it occurs) and `text` = your comment. Omit `quoted_text` "
                       "for a document-level (unanchored) note. Attributed to `role` (default `agent`). "
                       "After this, the reviewer (or you) can reply/resolve it like any thread.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": _DOCID,
                "quoted_text": {"type": "string", "description": "exact phrase to anchor + highlight (omit for a doc-level note)"},
                "text": {"type": "string", "description": "the comment body"},
                "role": {"type": "string", "enum": ["agent", "reviewer"],
                         "description": "attribution; default agent"},
            },
            "required": ["document_id", "text"],
        },
    },
    {
        "name": "list_comments",
        "description": "List comments on a document. Call this FIRST to see what the reviewer raised "
                       "and what needs attention; only address what the reviewer actually flagged. "
                       "`status` filters: open (default) | resolved | reopened | all. Reply to a "
                       "comment to discuss it, resolve it only once you've genuinely addressed it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": _DOCID,
                "status": {"type": "string", "enum": ["open", "resolved", "reopened", "all"],
                           "description": "filter; default open"},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "get_comment",
        "description": "Fetch one comment thread in full — every reply plus the status_history "
                       "(the open -> resolved -> reopened transitions).",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": _DOCID, "comment_id": _CID},
            "required": ["document_id", "comment_id"],
        },
    },
    {
        "name": "reply_to_comment",
        "description": "Add a reply to a comment WITHOUT resolving it. Use this when a comment is a "
                       "question or needs discussion, or to respond before you decide — resolve only "
                       "once the issue is actually addressed.",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": _DOCID, "comment_id": _CID,
                           "text": {"type": "string", "description": "your reply"}},
            "required": ["document_id", "comment_id", "text"],
        },
    },
    {
        "name": "resolve_comment",
        "description": "Mark a comment resolved once you've actually addressed it. `justification` is "
                       "OPTIONAL — provide a short note (appended to the thread, attributed to you, the "
                       "agent) to explain what you did, or omit to resolve silently; a clear note is "
                       "recommended because the reviewer can REOPEN the thread, so it reduces "
                       "back-and-forth. On resolve the comment leaves the active document and moves to "
                       "the Resolved panel. You never reopen — after a reviewer reopens, you'll see the "
                       "comment again via list_comments (status reopened/open) and can reply or resolve "
                       "again.",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": _DOCID, "comment_id": _CID,
                           "justification": {"type": "string",
                                             "description": "optional note explaining the resolution"}},
            "required": ["document_id", "comment_id"],
        },
    },
    {
        "name": "delete_comment",
        "description": "HARD-delete a comment (and its whole thread) — for cleaning up a junk/mistaken "
                       "comment. This is different from resolve_comment: resolve just hides a real "
                       "comment in the Resolved panel; delete removes it entirely and irreversibly. "
                       "Use it only on a comment you created by mistake, never to dismiss the "
                       "reviewer's feedback (resolve that).",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": _DOCID, "comment_id": _CID},
            "required": ["document_id", "comment_id"],
        },
    },
    {
        "name": "hand_back",
        "description": "Hand the turn baton back to the reviewer after you've acted on their feedback. "
                       "Sets turn=reviewer on the review so the viewer's banner flips to 'Agent updated "
                       "the draft … your turn' (state=done) — or 'Agent needs you' (state=blocked) when "
                       "you replied with a question instead of finishing. Call it when you're done "
                       "(after update_source + reply/resolve on the comments you addressed) or when "
                       "blocked. This is the AGENT's half of the loop; the human's 'Send to agent' and "
                       "'Take back the turn' are viewer actions. For blocked, pair this with a comment "
                       "reply asking the question — never reopen (reopen is the reviewer's UI action).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": _DOCID,
                "message": {"type": "string",
                            "description": "one-line summary shown in the reviewer's banner (e.g. 'addressed 3 comments, 1 question')"},
                "state": {"type": "string", "enum": ["done", "blocked"],
                          "description": "done (default) when finished; blocked when you need the reviewer"},
            },
            "required": ["document_id", "message"],
        },
    },
    {
        "name": "ping_working",
        "description": "Claim or renew your lease on a review while you hold the turn. Find work by "
                       "polling list_reviews / get_status for reviews you own with turn=='agent'; on "
                       "one, call ping_working right away and then periodically while you work, so the "
                       "viewer shows 'Agent is working…' instead of a stale 'Agent may have stopped' "
                       "hint. `owner` is YOUR opaque session id; a review already leased by a DIFFERENT "
                       "owner returns an error (HTTP 409) — back off and skip it (another agent holds "
                       "it). Does NOT change whose turn it is.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": _DOCID,
                "owner": {"type": "string",
                          "description": "your opaque agent/session id; identifies who holds the lease"},
                "message": {"type": "string", "description": "optional short status shown in the banner"},
            },
            "required": ["document_id", "owner"],
        },
    },
    {
        "name": "server_info",
        "description": "Report THIS running MCP server's identity: name, version, protocol_version, "
                       "tools_hash, tool_count, tool_names — so you can see what the *running* process "
                       "exposes. This SURFACES the running server's identity; it does NOT by itself tell "
                       "you the server is stale. To check staleness a human/CI compares this tools_hash "
                       "to the repo's `python3 mcp_server.py --print-version`; on a mismatch, RECONNECT "
                       "the MCP client (the server can signal, it cannot reload itself). An MCP-only "
                       "agent cannot self-detect staleness — it has the running hash but no on-disk "
                       "comparand over MCP.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _tools_hash():
    """sha256 (12 hex) over the agent-visible surface: the TOOLS schema + INSTRUCTIONS. Changes
    automatically whenever a tool or the workflow text changes, so it can't silently drift from a
    hand-bumped `version` string. One canonical input — every surface that reports a hash uses this."""
    canon = json.dumps(TOOLS, sort_keys=True) + INSTRUCTIONS
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


SERVER_INFO["tools_hash"] = _tools_hash()   # surfaced in initialize's serverInfo + the server_info tool

TOOL_NAMES = {t["name"] for t in TOOLS}


def _server_info():
    """The running wrapper's own identity (no HTTP call — reports THIS process, not the service)."""
    return {
        "name": SERVER_INFO["name"],
        "version": SERVER_INFO["version"],
        "protocol_version": PROTOCOL_VERSION,
        "tools_hash": SERVER_INFO["tools_hash"],
        "tool_count": len(TOOLS),
        "tool_names": sorted(t["name"] for t in TOOLS),
    }
