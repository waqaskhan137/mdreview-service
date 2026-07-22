"""The installed wrapper tracks the server it talks to (issue #90).

On startup the wrapper asks MDREVIEW_BASE which wrapper it serves and, if the installed copy differs,
replaces the installed copy in place so the NEXT session runs the served version. It does not compare
"newer": sha256 only tells you "different", so the rule is deliberately "match whatever MDREVIEW_BASE
serves". That is the fix for the recurring local/hosted staleness (an agent running a stale wrapper
against a fresh server) — the wrapper never diverges from its own server again.

Guardrails:
  * Managed installs only. install.sh drops a `.managed` marker next to src/; a repo/dev checkout has
    none, so a working tree is never overwritten. (The marker sits at the install root, outside src/,
    so it is never part of the served set and cannot leak into the repo.)
  * Fail-safe. Any error (network, bad payload, unwritable dir, checksum mismatch) logs one line to
    stderr and continues on the current wrapper. Startup is never blocked and files are only touched
    after the download fully verifies.
  * Opt-out. MDREVIEW_NO_AUTO_UPDATE=1 skips the whole thing (checked by the caller).
  * Path allowlist. Only mcp_server.py and mcp/<name>.py are ever written; anything else in the
    server's payload aborts the update (defense-in-depth against a malformed/hostile response).
stdlib only.
"""
import json
import os
import re
import shutil
import sys
import urllib.request

from . import bundle
from .client import BASE, TOKEN, _opener

_TIMEOUT = 4  # ponytail: short + fail-open; a slow/hung server must not stall MCP startup.
_VALID_PKG_FILE = re.compile(r"^[A-Za-z0-9_]+\.py$")


def _log(msg):
    sys.stderr.write("[mdreview] " + msg + "\n")


def _managed_root():
    """The src/ root if this is an installer-managed tree, else None (dev/repo checkout: leave it).

    The sole gate is install.sh's `.managed` marker (at the install root or beside src/). A working
    tree has none, so it is never touched — no path-based heuristics that could misfire on a repo
    living under a git-tracked $HOME."""
    src = bundle._src_root()
    marked = any(os.path.isfile(os.path.join(base, ".managed"))
                 for base in (os.path.dirname(src), src))
    return src if marked else None


def _get(path):
    req = urllib.request.Request(BASE + path, method="GET")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with _opener.open(req, timeout=_TIMEOUT) as r:
        return r.read().decode("utf-8")


def _allowed(rel):
    """True iff rel is a legit wrapper path: the entry script or mcp/<name>.py — no traversal, no
    absolute paths, no nesting. Guards os.path.join from writing outside the wrapper set."""
    parts = rel.split("/")
    if parts == [bundle._ENTRY]:
        return True
    return len(parts) == 2 and parts[0] == bundle._PKG and bool(_VALID_PKG_FILE.match(parts[1]))


def _apply(src, files):
    """Make the installed wrapper set exactly equal `files`: replace each file atomically (temp in the
    same dir + os.replace) keeping one .bak, and soft-delete any wrapper file the server no longer
    serves (rename to .bak) so a client that is a superset converges in one round, not forever."""
    for rel, text in files.items():
        dst = os.path.join(src, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isfile(dst):
            shutil.copy2(dst, dst + ".bak")
        tmp = dst + ".new"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, dst)  # atomic: readers see old-or-new, never partial
    served = set(files)
    for rel, _ in bundle.wrapper_files(src):
        if rel not in served:
            path = os.path.join(src, *rel.split("/"))
            try:
                os.replace(path, path + ".bak")
            except OSError:
                pass


def maybe_self_update():
    """Best-effort: bring the installed wrapper in line with MDREVIEW_BASE. Never raises."""
    src = _managed_root()
    if src is None:
        return
    try:
        local = bundle.wrapper_version()
        served_ver = json.loads(_get("/install/version")).get("wrapper_version")
        if not served_ver or served_ver == local:
            return
        payload = json.loads(_get("/install/wrapper"))
        files = payload.get("files") or {}
        for rel in files:
            if not _allowed(rel):
                _log("auto-update skipped: server sent an unexpected path %r" % rel)
                return
        got = bundle.wrapper_version(sorted(files.items()))
        if got != payload.get("wrapper_version") or got != served_ver:
            _log("auto-update skipped: checksum mismatch (download not applied)")
            return
        _apply(src, files)
        _log("wrapper updated %s -> %s; takes effect next session" % (local[:12], served_ver[:12]))
    except Exception as e:
        _log("auto-update skipped (%s); continuing on the current wrapper" % e)
