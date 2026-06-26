#!/usr/bin/env python3
"""mdreview.app launcher (macOS) — P0 freeze spike.

Runs the bundled stdlib mdreview service on a free localhost port with data in
~/Library/Application Support/mdreview, then opens the dashboard. py2app exports
RESOURCEPATH (the bundle's Contents/Resources), where the web/ tree is shipped.

ponytail: P0 has no menu-bar/quit lifecycle — serve_forever runs on a daemon
thread and the main thread parks. Quit via Activity Monitor for now; P1 wraps
this in a rumps menu-bar app with a real Quit + graceful shutdown.
"""
import os
import socket
import threading
import time
import webbrowser


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
    data = os.path.expanduser("~/Library/Application Support/mdreview")
    os.makedirs(data, exist_ok=True)
    os.environ.setdefault("MDREVIEW_DATA", data)
    os.environ.setdefault("MDREVIEW_WEB_DIR", _web_dir())
    port = _free_port()
    os.environ["PORT"] = str(port)

    # import AFTER env is set — mdreview.config reads PORT / MDREVIEW_DATA / MDREVIEW_WEB_DIR at import
    from mdreview.server import main as serve
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
