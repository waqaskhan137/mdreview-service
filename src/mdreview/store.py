"""The single persistence seam: the on-disk Store (MR-081).

Store owns DATA_DIR, the ONE threading.Condition that serialises every state write (MR-054: one
Condition over one lock; the /wait long-poll parks on store.wait() which releases the lock, and a
writer calls store.notify_all() under that same lock after its write), and the typed read/write
helpers + content-type table. Every service is constructed with this single Store injected; no
service builds its own lock or re-acquires it.
"""
import json
import os
import threading


class Store:
    # Content types for files served out of web/static and for attached asset bytes (the type is
    # inferred from the attached name's extension). Anything unlisted -> application/octet-stream.
    _CTYPES = {
        ".js": "text/javascript",
        ".css": "text/css",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
    }

    def __init__(self, data_dir):
        self.data_dir = data_dir
        # The ONE Condition. A Condition is itself a context manager (acquires/releases its internal
        # lock), so `with store.lock:` behaves exactly as the old `with _lock:`. Never a second lock,
        # never re-created per service: exactly one, owned here and injected everywhere (MR-054).
        self._cond = threading.Condition()

    # ---- lock + long-poll pass-throughs (MR-054 semantics preserved verbatim) ----
    @property
    def lock(self):
        return self._cond

    def notify_all(self):
        self._cond.notify_all()

    def wait(self, timeout):
        return self._cond.wait(timeout)

    # ---- paths ----
    def dir(self, rid):
        return os.path.join(self.data_dir, rid)

    def exists(self, rid):
        return os.path.isfile(os.path.join(self.dir(rid), "meta.json"))

    # ---- typed reads / writes ----
    def read_text(self, path, default=""):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return default

    def read_bytes(self, path, default=b""):
        """Binary read for assets served verbatim (fonts, images, css).

        read_text decodes utf-8 and raises on the first font/image byte; binary-served routes
        (/static/*, the asset GET) must use this instead.
        """
        try:
            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            return default

    def read_json(self, path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def write_text(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # ---- misc helpers ----
    def ctype_for(self, name):
        return self._CTYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")

    @staticmethod
    def to_float(s, default):
        """Parse a query-string number, falling back to default on None/garbage (MR-054)."""
        try:
            return float(s)
        except (TypeError, ValueError):
            return default
