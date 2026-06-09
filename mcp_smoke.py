#!/usr/bin/env python3
"""mcp_smoke.py — dependency-free smoke for mcp_server.py (the MCP analogue of render-smoke.sh).

Stdlib only (json + subprocess + os/sys; NO jq, NO pip): drives mcp_server.py over stdio with a
handcrafted JSON-RPC sequence and asserts the protocol surface, the tools/call envelope, the
error paths, and a live create_review -> update_source round-trip.

Usage:  MDREVIEW_BASE=http://localhost:8137 python3 mcp_smoke.py
Exit 0 = all pass; nonzero = a failure (with the failing assertion named).
"""
import os
import sys
import json
import subprocess

BASE = os.environ.get("MDREVIEW_BASE", "http://localhost:8137")
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "mcp_server.py")

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "mcp_smoke", "version": "0"}}}
INITED = {"jsonrpc": "2.0", "method": "notifications/initialized"}

_fails = []


def check(label, cond):
    print(("  ok  " if cond else "  FAIL") + " " + label)
    if not cond:
        _fails.append(label)


def drive(messages):
    """Run mcp_server.py with the given JSON-RPC messages on stdin; return parsed responses."""
    proc = subprocess.run(
        [sys.executable, SERVER],
        input="".join(json.dumps(m) + "\n" for m in messages),
        capture_output=True, text=True,
        env={**os.environ, "MDREVIEW_BASE": BASE},
        timeout=60,
    )
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def main():
    print("mcp_smoke against MDREVIEW_BASE=%s" % BASE)

    # 1. protocol surface (no service needed for initialize/tools_list, but a running service is
    #    required for the round-trip below; we keep one sequence for simplicity).
    base = [INIT, INITED, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
    out = drive(base)
    check("notification gets no response (2 requests -> 2 responses)", len(out) == 2)
    init = out[0].get("result", {})
    check("initialize protocolVersion == 2025-06-18", init.get("protocolVersion") == "2025-06-18")
    check("capabilities are tools-only", init.get("capabilities") == {"tools": {}})
    check("serverInfo.name == mdreview-mcp", init.get("serverInfo", {}).get("name") == "mdreview-mcp")
    tools = out[1].get("result", {}).get("tools", [])
    names = {t.get("name") for t in tools}
    expected = {"create_review", "list_reviews", "get_review", "get_feedback",
                "get_status", "update_source", "get_history", "delete_review"}
    check("tools/list returns exactly the 8 tools", names == expected)
    check("each tool has a description + object inputSchema",
          all(t.get("description") and t.get("inputSchema", {}).get("type") == "object" for t in tools))

    # 2. happy-path envelope + round-trip (needs a running service)
    out = drive(base + [{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                         "params": {"name": "create_review",
                                    "arguments": {"markdown": "# smoke\n\nx", "title": "mcp_smoke",
                                                  "project": "mcp-smoke", "session": "ci"}}}])
    res = out[-1].get("result", {})
    envelope_ok = (res.get("content", [{}])[0].get("type") == "text" and not res.get("isError"))
    check("tools/call create_review -> text-content result, isError false", envelope_ok)
    rid = None
    if envelope_ok:
        try:
            rid = json.loads(res["content"][0]["text"]).get("id")
        except Exception:
            pass
    check("create_review result text parses as JSON with an id", bool(rid))

    if rid:
        out = drive(base + [{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                             "params": {"name": "update_source",
                                        "arguments": {"id": rid, "markdown": "# smoke\n\nrevised"}}}])
        upd = out[-1].get("result", {})
        rev = None
        try:
            rev = json.loads(upd["content"][0]["text"]).get("revision")
        except Exception:
            pass
        check("update_source round-trip -> revision >= 1", isinstance(rev, int) and rev >= 1)
        # clean up the smoke review
        drive(base + [{"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "delete_review", "arguments": {"id": rid}}}])

    # 3. tool error path: bad id -> isError:true (not a protocol error)
    out = drive(base + [{"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                         "params": {"name": "get_review", "arguments": {"id": "nope9999"}}}])
    res = out[-1].get("result", {})
    check("bad id -> isError:true result", res.get("isError") is True)

    # 4. protocol error path: unknown tool -> JSON-RPC -32602
    out = drive(base + [{"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                         "params": {"name": "frobnicate", "arguments": {}}}])
    check("unknown tool -> JSON-RPC error -32602", out[-1].get("error", {}).get("code") == -32602)

    print()
    if _fails:
        print("FAILED: %d assertion(s): %s" % (len(_fails), "; ".join(_fails)))
        sys.exit(1)
    print("PASS: all MCP smoke assertions hold")


if __name__ == "__main__":
    main()
