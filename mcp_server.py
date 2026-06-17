#!/usr/bin/env python3
"""mdreview-mcp: a thin stdio MCP server wrapping the mdreview-service HTTP API.

Stdlib only (no pip): newline-delimited JSON-RPC 2.0 over stdin/stdout. It holds a BASE
URL (MDREVIEW_BASE, default http://localhost:8137) and maps each MCP tool 1:1 onto an
existing HTTP endpoint. It adds NO state and does not change the HTTP service.

Protocol grounded against the MCP spec rev 2025-06-18 (lifecycle + tools).

  initialize                -> {protocolVersion, capabilities:{tools:{}}, serverInfo}
  notifications/initialized -> (no response)
  tools/list                -> {tools:[...10 schemas]}
  tools/call                -> {content:[{type:text,text}], isError?}   (dispatch: MR-016)

Run:  MDREVIEW_BASE=http://localhost:8137 python3 mcp_server.py
"""
import os
import sys
import json
import urllib.request
import urllib.error

PROTOCOL_VERSION = "2025-06-18"   # MCP spec revision this server targets
SERVER_INFO = {"name": "mdreview-mcp", "version": "0.1.0"}
BASE = os.environ.get("MDREVIEW_BASE", "http://localhost:8137").rstrip("/")

_ID = {"type": "string", "description": "the opaque review id"}

# The 10 tools, 1:1 with the HTTP API. Static metadata served by tools/list.
TOOLS = [
    {
        "name": "create_review",
        "description": "Create a review from markdown; returns the id and the review/feedback urls. "
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
        "name": "get_feedback",
        "description": "Get a review's human feedback: structured notes plus the rendered markdown block.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "get_status",
        "description": "Cheap poll: a review's source_updated and feedback_updated timestamps.",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
    {
        "name": "update_source",
        "description": "Push a revised draft (applied edits). Snapshots a history round and live-reloads the human's page.",
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
        "description": "Attach an image (base64) to a review so the viewer serves and renders it. "
                       "Pass `name` as the exact src the draft uses (e.g. \"/assets/x.png\" or "
                       "\"fig/y.svg\"); attach once — it survives every update_source revision, so "
                       "you never resend the bytes. Returns the stored name and the served url.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": _ID,
                "name": {"type": "string", "description": "the draft <img> src this asset backs (the match key)"},
                "content_b64": {"type": "string", "description": "the file bytes, base64-encoded"},
            },
            "required": ["id", "name", "content_b64"],
        },
    },
    {
        "name": "list_assets",
        "description": "List a review's attached assets (name, stored name, served url, bytes, ctype).",
        "inputSchema": {"type": "object", "properties": {"id": _ID}, "required": ["id"]},
    },
]


# ---- JSON-RPC stdio framing (isolated so a spec change is a one-function fix) ----
def write_message(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def read_messages():
    """Yield parsed JSON-RPC messages from stdin, one per line; stop cleanly on EOF."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            # Malformed line with no id we can answer; skip rather than crash the stream.
            continue


def _result(rid, result):
    write_message({"jsonrpc": "2.0", "id": rid, "result": result})


def _error(rid, code, message):
    write_message({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})


TOOL_NAMES = {t["name"] for t in TOOLS}


# ---- HTTP client (tools/call dispatch -> the existing mdreview HTTP API) ----
class ToolError(Exception):
    """A tool ran and failed (bad id, service down, non-2xx) -> isError result, not a protocol error."""


def http(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise ToolError("HTTP %s from %s %s: %s" % (e.code, method, path, detail))
    except urllib.error.URLError as e:
        raise ToolError("cannot reach mdreview at %s (%s)" % (BASE, e.reason))


def route(name, args):
    """Map a tool name + args onto (http_method, path, body). KeyError -> missing required arg."""
    if name == "create_review":
        body = {k: args[k] for k in ("markdown", "title", "project", "session", "source_path") if k in args}
        body.setdefault("markdown", args["markdown"])  # KeyError if absent -> -32602
        return "POST", "/api/reviews", body
    if name == "list_reviews":
        return "GET", "/api/reviews", None
    if name == "get_review":
        return "GET", "/api/reviews/%s" % args["id"], None
    if name == "get_feedback":
        return "GET", "/api/reviews/%s/feedback" % args["id"], None
    if name == "get_status":
        return "GET", "/api/reviews/%s/status" % args["id"], None
    if name == "update_source":
        return "PUT", "/api/reviews/%s/source" % args["id"], {"markdown": args["markdown"]}
    if name == "get_history":
        if args.get("round") is not None:
            return "GET", "/api/reviews/%s/history/%s" % (args["id"], args["round"]), None
        return "GET", "/api/reviews/%s/history" % args["id"], None
    if name == "delete_review":
        return "DELETE", "/api/reviews/%s" % args["id"], None
    if name == "attach_asset":
        return "POST", "/api/reviews/%s/assets" % args["id"], {
            "name": args["name"], "content_b64": args["content_b64"]}
    if name == "list_assets":
        return "GET", "/api/reviews/%s/assets" % args["id"], None
    return None  # unreachable (caller checks TOOL_NAMES first)


def handle_tools_call(rid, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if name not in TOOL_NAMES:
        return _error(rid, -32602, "Unknown tool: %s" % name)   # protocol error
    try:
        method, path, body = route(name, args)
    except KeyError as e:
        return _error(rid, -32602, "Missing required argument: %s" % e)
    try:
        text = http(method, path, body)
        _result(rid, {"content": [{"type": "text", "text": text}], "isError": False})
    except ToolError as e:
        _result(rid, {"content": [{"type": "text", "text": str(e)}], "isError": True})


# ---- method handlers ----
def handle_initialize(rid, params):
    # Version negotiation: echo the client's version if we support it, else offer ours.
    client_ver = (params or {}).get("protocolVersion")
    version = client_ver if client_ver == PROTOCOL_VERSION else PROTOCOL_VERSION
    _result(rid, {
        "protocolVersion": version,
        "capabilities": {"tools": {}},      # tools only — no resources, no prompts
        "serverInfo": SERVER_INFO,
    })


def handle_tools_list(rid, params):
    _result(rid, {"tools": TOOLS})


def dispatch(msg):
    method = msg.get("method")
    rid = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) get no response. notifications/initialized is the handshake ack.
    if rid is None:
        return

    if method == "initialize":
        return handle_initialize(rid, params)
    if method == "tools/list":
        return handle_tools_list(rid, params)
    if method == "tools/call":
        return handle_tools_call(rid, params)
    if method == "ping":
        return _result(rid, {})
    _error(rid, -32601, "Method not found: %s" % method)


def main():
    for msg in read_messages():
        try:
            dispatch(msg)
        except Exception as e:  # never let one bad message kill the stream
            rid = msg.get("id") if isinstance(msg, dict) else None
            if rid is not None:
                _error(rid, -32603, "Internal error: %s" % e)


if __name__ == "__main__":
    main()
