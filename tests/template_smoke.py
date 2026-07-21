#!/usr/bin/env python3
"""tests/template_smoke.py  (MR-104)

Hermetic test of the template RegistryPuller: a local HTTP server + temp manifests exercise the full
download -> per-file sha256 verify -> atomic cache -> cache-hit re-verify path, plus every containment
guard (non-HTTPS refused, private/loopback IP refused, wrong sha256 rejected, oversize aborted,
archive filename rejected). No live network and no running mdreview server. Exit 0 pass, 1 fail.

(The live end-to-end path — a real conference style downloaded from its own repo and compiled — is
exercised against the shipped registry.json in the container/G7 smoke, not here.)
"""
import hashlib
import http.server
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
os.environ.setdefault("MDREVIEW_DATA", tempfile.mkdtemp())

from mdreview.store import Store                         # noqa: E402
from latex_review.puller import RegistryPuller, TemplatePullError  # noqa: E402

STY = b"\\ProvidesPackage{houseconf}\n\\newcommand{\\houseok}{ok}\n"
STY_SHA = hashlib.sha256(STY).hexdigest()

_fails = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        _fails.append(label)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/house.sty":
            self.send_response(200)
            self.send_header("Content-Length", str(len(STY)))
            self.end_headers()
            self.wfile.write(STY)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def _manifest(files):
    p = os.path.join(tempfile.mkdtemp(), "registry.json")
    with open(p, "w") as f:
        json.dump({"house": {"files": files}}, f)
    return p


def _fresh_store():
    return Store(tempfile.mkdtemp())


def main():
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/house.sty" % port
    spec = {"url": url, "filename": "house.sty", "sha256": STY_SHA, "bytes": len(STY)}

    # ---- happy path (test relaxes require_https + allow_private for a loopback server) ----
    store = _fresh_store()
    p = RegistryPuller(_manifest([spec]), store, require_https=False, allow_private=True)
    files = p.materialize("house")
    check("download -> [(filename, bytes)] with correct content", files == [("house.sty", STY)])
    cached_path = os.path.join(store.data_dir, ".templates", "house", "house.sty")
    check("cached under <data>/.templates/house/", os.path.isfile(cached_path))
    check("second materialize serves the cached bytes", p.materialize("house") == [("house.sty", STY)])
    with open(cached_path, "wb") as f:
        f.write(b"tampered-at-rest")
    check("corrupt cache detected on hit -> re-fetched valid bytes",
          p.materialize("house") == [("house.sty", STY)])

    # ---- containment guards (each on a fresh store so the download path actually runs) ----
    def expect_error(label, files, **kw):
        pp = RegistryPuller(_manifest(files), _fresh_store(), **kw)
        try:
            pp.materialize("house")
            check(label + " (should have raised)", False)
        except TemplatePullError:
            check(label, True)

    expect_error("non-HTTPS url refused (default require_https)", [spec])
    expect_error("private/loopback IP refused (default allow_private=False)", [spec], require_https=False)
    expect_error("wrong sha256 rejected", [dict(spec, sha256="00" * 32)],
                 require_https=False, allow_private=True)
    expect_error("oversize download aborted (streamed cap)", [spec],
                 require_https=False, allow_private=True, max_bytes=8)
    expect_error("archive filename rejected", [dict(spec, filename="house.zip")],
                 require_https=False, allow_private=True)

    httpd.shutdown()
    if _fails:
        print("FAILED: %d" % len(_fails))
        return 1
    print("PASS: template puller machinery + containment guards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
