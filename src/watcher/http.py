"""The watcher's HTTP helper: branch on status, do NOT raise on 409.

Unlike the mcp package's http() (which raises on any non-2xx), this returns (status, parsed_body) so
a 409 from a lease claim is a normal skip signal the loop branches on, not an exception. Only a real
transport failure (URLError) propagates — the loop backs off on it.
"""
import json
import urllib.error
import urllib.request

from .config import BASE


def _http(method, path, body=None, timeout=None):
    """Return (status, parsed_body). Catches HTTPError and returns its (.code, body) so a 409 from
    the lease claim is a normal skip signal, not an exception. Raises only on a real transport
    failure (URLError), which the loop backs off on."""
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.code, _parse(r.read())
    except urllib.error.HTTPError as e:
        # HTTPError carries .code and is itself a readable response — a 409 is a normal signal here.
        return e.code, _parse(e.read())


def _parse(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
