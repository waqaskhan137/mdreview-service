#!/usr/bin/env python3
"""mdreview.app launcher (macOS) — browser-tab launcher (P1).

Starts the bundled stdlib service on a free localhost port (written to a discovery file
for the MCP wrapper), then opens the dashboard in the default browser. The UI stays the
web app — this is only a launcher.

ponytail: no menu-bar/Quit yet. A native control surface (rumps/pywebview) is pyobjc, and
pyobjc dylibs require a VALID code signature to load on Apple Silicon (an ad-hoc bundle
crashes with a CODESIGNING fault). So the Quit affordance lands in P3, once Developer ID
signing + hardened runtime are in place. For now the server runs on a daemon thread and
the main thread parks; quit via Activity Monitor.
"""
import os
import socket
import threading
import time
import webbrowser

APP_SUPPORT = os.path.expanduser("~/Library/Application Support/mdreview")
PORT_FILE = os.path.join(APP_SUPPORT, "port")


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _web_dir():
    rp = os.environ.get("RESOURCEPATH")            # set by py2app inside the .app bundle
    if rp:
        return os.path.join(rp, "web", "app")
    here = os.path.dirname(os.path.abspath(__file__))   # dev run: repo web/app (3 dirs up)
    return os.path.normpath(os.path.join(here, "..", "..", "..", "web", "app"))


def main():
    os.makedirs(APP_SUPPORT, exist_ok=True)
    os.environ.setdefault("MDREVIEW_DATA", APP_SUPPORT)
    os.environ.setdefault("MDREVIEW_WEB_DIR", _web_dir())
    port = _free_port()
    os.environ["PORT"] = str(port)
    # MCP discovery: the stdio wrapper reads this to set MDREVIEW_BASE (P-MCP). It must still
    # verify the port is reachable — this file can be stale after a quit.
    with open(PORT_FILE, "w") as f:
        f.write(str(port))

    from mdreview.server import main as serve     # import AFTER env is set (config reads it at import)
    threading.Thread(target=serve, daemon=True).start()

    for _ in range(100):                           # wait up to ~10s for the socket to bind
        try:
            with socket.create_connection(("127.0.0.1", port), 0.1):
                break
        except OSError:
            time.sleep(0.1)
    webbrowser.open("http://127.0.0.1:%d/" % port)

    while True:                                    # keep the app alive (server is a daemon thread)
        time.sleep(3600)


if __name__ == "__main__":
    main()
