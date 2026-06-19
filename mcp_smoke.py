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
import urllib.request

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
    check("initialize surfaces the workflow as instructions",
          bool(init.get("instructions")) and "list_comments" in init.get("instructions", ""))
    tools = out[1].get("result", {}).get("tools", [])
    names = {t.get("name") for t in tools}
    expected = {"create_review", "list_reviews", "get_review", "get_source", "get_feedback",
                "get_status", "update_source", "get_history", "delete_review",
                "attach_asset", "list_assets",
                "list_comments", "get_comment", "reply_to_comment", "resolve_comment",
                "server_info"}
    check("tools/list returns exactly the 16 tools", names == expected)
    check("each tool has a description + object inputSchema",
          all(t.get("description") and t.get("inputSchema", {}).get("type") == "object" for t in tools))
    # the comment tools must encode the agent workflow in their descriptions (the brief's expectations)
    desc = {t["name"]: t.get("description", "").lower() for t in tools}
    check("list_comments description says call it FIRST",
          "first" in desc.get("list_comments", ""))
    check("reply_to_comment description says reply WITHOUT resolving",
          "without" in desc.get("reply_to_comment", ""))
    check("resolve_comment description says justification optional + reviewer can reopen",
          "optional" in desc.get("resolve_comment", "") and "reopen" in desc.get("resolve_comment", ""))

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

        # get_source returns the draft we just pushed (text content, not JSON)
        out = drive(base + [{"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                             "params": {"name": "get_source", "arguments": {"id": rid}}}])
        src = out[-1].get("result", {}).get("content", [{}])[0].get("text", "")
        check("get_source -> the current draft markdown", "revised" in src)

        # attach_asset -> list_assets round-trip (a 1x1 png by base64)
        pix = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQ"
               "DwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
        out = drive(base + [{"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                             "params": {"name": "attach_asset",
                                        "arguments": {"id": rid, "name": "/assets/pixel.png",
                                                      "content_b64": pix}}}])
        att = out[-1].get("result", {})
        stored = None
        try:
            stored = json.loads(att["content"][0]["text"]).get("stored")
        except Exception:
            pass
        check("attach_asset -> stored sha1+ext, isError false",
              bool(stored) and not att.get("isError"))

        # attach_asset by PATH: the wrapper reads + encodes the file locally (no base64 in context)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(__import__("base64").b64decode(pix)); tmp_png = tf.name
        out = drive(base + [{"jsonrpc": "2.0", "id": 11, "method": "tools/call",
                             "params": {"name": "attach_asset",
                                        "arguments": {"id": rid, "name": "/assets/by-path.png",
                                                      "path": tmp_png}}}])
        ap = out[-1].get("result", {})
        path_stored = None
        try:
            path_stored = json.loads(ap["content"][0]["text"]).get("stored")
        except Exception:
            pass
        os.unlink(tmp_png)
        check("attach_asset by path -> wrapper reads the file, stored returned, isError false",
              bool(path_stored) and not ap.get("isError"))
        out = drive(base + [{"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                             "params": {"name": "list_assets", "arguments": {"id": rid}}}])
        listed = []
        try:
            listed = json.loads(out[-1]["result"]["content"][0]["text"]).get("assets", [])
        except Exception:
            pass
        check("list_assets -> includes the attached asset's stored name",
              any(a.get("stored") == stored for a in listed))

        # comment round-trip: seed a comment over HTTP (create is reviewer-side), then exercise the
        # four agent tools (list -> get -> reply -> resolve) and the open/resolved filter.
        cid = None
        try:
            req = urllib.request.Request(
                "%s/api/reviews/%s/comments" % (BASE, rid),
                data=json.dumps({"anchor": {"quoted_text": "smoke", "block_num": "1"},
                                 "text": "please clarify"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                cid = json.loads(r.read().decode("utf-8")).get("comment_id")
        except Exception:
            pass
        check("seeded a comment via HTTP (comment_id present)", bool(cid))

        if cid:
            def call_tool(call_id, tool, arguments):
                o = drive(base + [{"jsonrpc": "2.0", "id": call_id, "method": "tools/call",
                                   "params": {"name": tool, "arguments": arguments}}])
                r = o[-1].get("result", {})
                try:
                    return json.loads(r["content"][0]["text"]), r.get("isError")
                except Exception:
                    return None, r.get("isError")

            lst, err = call_tool(20, "list_comments", {"document_id": rid})  # default open
            check("list_comments(open) -> the seeded comment is listed, isError false",
                  not err and isinstance(lst, dict)
                  and any(c.get("comment_id") == cid for c in lst.get("comments", [])))
            one, err = call_tool(21, "get_comment", {"document_id": rid, "comment_id": cid})
            check("get_comment -> full thread (>=1 entry) + status_history",
                  not err and isinstance(one, dict) and len(one.get("thread", [])) >= 1
                  and len(one.get("status_history", [])) >= 1)
            rep, err = call_tool(22, "reply_to_comment",
                                 {"document_id": rid, "comment_id": cid, "text": "looking into it"})
            check("reply_to_comment -> thread grows, status still open",
                  not err and isinstance(rep, dict) and len(rep.get("thread", [])) == 2
                  and rep.get("status") == "open")
            res, err = call_tool(23, "resolve_comment", {"document_id": rid, "comment_id": cid})
            check("resolve_comment -> status resolved, resolved_by agent",
                  not err and isinstance(res, dict)
                  and res.get("status") == "resolved" and res.get("resolved_by") == "agent")
            op, _ = call_tool(24, "list_comments", {"document_id": rid, "status": "open"})
            rv, _ = call_tool(25, "list_comments", {"document_id": rid, "status": "resolved"})
            check("after resolve: excluded from open, included in resolved",
                  isinstance(op, dict) and isinstance(rv, dict)
                  and not any(c.get("comment_id") == cid for c in op.get("comments", []))
                  and any(c.get("comment_id") == cid for c in rv.get("comments", [])))

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
