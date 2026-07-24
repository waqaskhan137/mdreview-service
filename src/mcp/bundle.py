"""Wrapper self-identity: the set of files the MCP wrapper is made of, and a content hash of it.

Shared by both ends of the self-update (issue #90) so they agree byte-for-byte: the server
advertises/serves exactly this set (GET /install/*), and the installed wrapper hashes its own copy
to notice it has drifted from the server it talks to. stdlib only.

The wrapper = the entry script `mcp_server.py` + the whole `mcp/` package (this file included). A
change to any of them changes wrapper_version(), which is the whole point: unlike tools_hash (which
fingerprints only the agent-visible tool surface), this catches client.py/__main__.py churn too.
"""
import hashlib
import os

_ENTRY = "mcp_server.py"
_PKG = "mcp"


def _src_root():
    """The src/ dir holding mcp_server.py and the mcp/ package (this module lives in mcp/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wrapper_files(root=None):
    """Sorted [(relpath, text)] of every wrapper file: mcp_server.py + mcp/*.py. Deterministic."""
    root = root or _src_root()
    rels = [_ENTRY]
    rels += [_PKG + "/" + n for n in os.listdir(os.path.join(root, _PKG)) if n.endswith(".py")]
    out = []
    for rel in sorted(rels):
        p = os.path.join(root, *rel.split("/"))
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                out.append((rel, f.read()))
    return out


def wrapper_version(files=None):
    """sha256 over the (path, content) set — a stable id of exactly this wrapper. Same set -> same id.

    Pass `files` (a sorted [(rel, text)] list, e.g. from a downloaded payload) to hash that set the
    identical way the server hashed its own; omit it to hash the on-disk wrapper."""
    files = wrapper_files() if files is None else files
    h = hashlib.sha256()
    for rel, text in files:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(text.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def wrapper_payload():
    """{wrapper_version, files:{relpath: content}} — what the server serves and the client rehashes."""
    files = wrapper_files()
    return {"wrapper_version": wrapper_version(files), "files": {rel: text for rel, text in files}}
