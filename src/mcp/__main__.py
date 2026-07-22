"""JSON-RPC 2.0 stdio transport + lifecycle dispatch — the `python -m mcp` entry point.

Reads newline-delimited JSON-RPC from stdin, dispatches initialize / tools/list / tools/call / ping,
and writes responses to stdout. The agent-visible schema surface lives in tools.py; the HTTP routing
in client.py. `--print-version` prints the on-disk identity (the staleness comparand) and exits.
"""
import os
import sys
import json

from .tools import (
    PROTOCOL_VERSION, SERVER_INFO, INSTRUCTIONS, TOOLS, TOOL_NAMES, _server_info,
)
from .client import http, route, ToolError, open_review, OPEN_IN_BROWSER


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


# ---- method handlers ----
def handle_tools_call(rid, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if name not in TOOL_NAMES:
        return _error(rid, -32602, "Unknown tool: %s" % name)   # protocol error
    if name == "server_info":
        # local: reports the wrapper's own identity, no HTTP — must work with no service/MDREVIEW_BASE
        return _result(rid, {"content": [{"type": "text", "text": json.dumps(_server_info())}],
                             "isError": False})
    try:
        method, path, body = route(name, args)
    except KeyError as e:
        return _error(rid, -32602, "Missing required argument: %s" % e)
    try:
        text = http(method, path, body)
        _result(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        if name == "create_review" and OPEN_IN_BROWSER:
            open_review(text)   # opt-in local-browser pop, after the result is sent
    except ToolError as e:
        _result(rid, {"content": [{"type": "text", "text": str(e)}], "isError": True})


def handle_initialize(rid, params):
    # Version negotiation: echo the client's version if we support it, else offer ours.
    client_ver = (params or {}).get("protocolVersion")
    version = client_ver if client_ver == PROTOCOL_VERSION else PROTOCOL_VERSION
    _result(rid, {
        "protocolVersion": version,
        "capabilities": {"tools": {}},      # tools only — no resources, no prompts
        "serverInfo": SERVER_INFO,
        "instructions": INSTRUCTIONS,       # the end-to-end workflow, surfaced to the agent
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
    if "--print-version" in sys.argv:
        # on-disk comparand for staleness checks: print what THIS code would serve, then exit.
        print(json.dumps({"version": SERVER_INFO["version"], "tools_hash": SERVER_INFO["tools_hash"]}))
        return
    if os.environ.get("MDREVIEW_NO_AUTO_UPDATE", "").lower() not in ("1", "true", "yes"):
        try:
            from . import update
            update.maybe_self_update()  # managed installs track their server; dev trees untouched (#90)
        except Exception:
            pass  # self-update is best-effort — never block MCP startup on it
    for msg in read_messages():
        try:
            dispatch(msg)
        except Exception as e:  # never let one bad message kill the stream
            rid = msg.get("id") if isinstance(msg, dict) else None
            if rid is not None:
                _error(rid, -32603, "Internal error: %s" % e)


if __name__ == "__main__":
    main()
