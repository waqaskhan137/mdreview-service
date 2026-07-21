"""Download-on-miss for non-CTAN conference styles (MR-104).

`RegistryPuller` materializes a template's companion file-set from a pinned manifest
(`registry.json`): a normalized id maps to an explicit list of individually-pinned files
(`{url, filename, sha256, bytes}`). It only ever fetches the exact URLs in the manifest (never an
agent-supplied or arbitrary URL), so the manifest IS the allowlist. Downloaded files are cached
under the root-only `<data>/.templates/<id>/` and reused; nothing is written to the repo/image.

Containment (the compile is already the real boundary: --untrusted, uid-dropped, no /data reads,
shell-escape off):
  - HTTPS only (a test may relax via require_https=False);
  - resolve the host and validate every resolved IP is public (reject private/loopback/link-local/
    reserved/multicast), then pin the connection to a validated IP with SNI+cert against the
    hostname (closes DNS-rebind/TOCTOU); redirects are rejected (the manifest must give final URLs);
  - streamed byte-size cap (abort mid-download, never buffer past the cap);
  - a per-connect/read timeout AND a total wall-clock fetch budget, so a slow/hung host fails the
    compile (like the tectonic TimeoutExpired path) instead of wedging the single compile worker;
  - per-file sha256 verified on download AND on every cache hit (a truncated/tampered cache file is
    never trusted); atomic write into the cache;
  - single files only: a `.zip`/`.tar`/`.gz` filename is rejected.
"""
import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
from urllib.parse import urlparse


class TemplatePullError(Exception):
    """A registry download/verification failed. Raised into _prepare_job so _compile records a
    failed status with the reason (never crashes the worker)."""


_ARCHIVE_EXT = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar")


class RegistryPuller:
    def __init__(self, manifest_path, store, *, require_https=True, allow_private=False,
                 max_bytes=2 * 1024 * 1024, io_timeout=15.0, total_budget=45.0):
        self._store = store
        self._require_https = require_https
        self._allow_private = allow_private
        self._max_bytes = int(max_bytes)
        self._io_timeout = float(io_timeout)
        self._total_budget = float(total_budget)
        self._manifest = self._load(manifest_path)

    @staticmethod
    def _load(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, ValueError):
            return {}

    def ids(self):
        return set(self._manifest)

    # ---- resolution entry point (called by TemplateService at compile time) ----
    def materialize(self, template_id):
        """Return [(filename, bytes)] for the id: served from the /data cache when every file is
        present and sha256-valid, else downloaded, verified, and cached. Raises TemplatePullError."""
        entry = self._manifest.get(template_id)
        if not entry:
            return []
        specs = entry.get("files") or []
        out = []
        deadline = time.monotonic() + self._total_budget
        for spec in specs:
            filename = os.path.basename((spec.get("filename") or "").replace("\\", "/").rstrip("/"))
            sha = (spec.get("sha256") or "").lower()
            if not filename or not sha:
                raise TemplatePullError("registry entry %r has a malformed file spec" % template_id)
            if filename.lower().endswith(_ARCHIVE_EXT):
                raise TemplatePullError("archive files are not allowed: %s" % filename)
            data = self._cached(template_id, filename, sha)
            if data is None:
                data = self._download(spec.get("url") or "", sha, deadline)
                self._cache_write(template_id, filename, data)
            out.append((filename, data))
        return out

    # ---- cache (root-only <data>/.templates/<id>/) ----
    def _cache_dir(self, template_id):
        return os.path.join(self._store.data_dir, ".templates", template_id)

    def _cached(self, template_id, filename, sha):
        p = os.path.join(self._cache_dir(template_id), filename)
        try:
            with open(p, "rb") as f:
                data = f.read()
        except (FileNotFoundError, NotADirectoryError):
            return None
        return data if _sha256(data) == sha else None   # re-verify on hit; stale -> re-fetch

    def _cache_write(self, template_id, filename, data):
        d = self._cache_dir(template_id)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, filename)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)          # atomic; a partial download is never read

    # ---- the contained download ----
    def _download(self, url, expected_sha, deadline):
        u = urlparse(url)
        if self._require_https and u.scheme != "https":
            raise TemplatePullError("non-HTTPS url refused: %s" % url)
        if u.scheme not in ("http", "https"):
            raise TemplatePullError("unsupported url scheme: %s" % url)
        host, port = u.hostname, (u.port or (443 if u.scheme == "https" else 80))
        if not host:
            raise TemplatePullError("url has no host: %s" % url)
        ip = self._validated_ip(host, port)
        if time.monotonic() > deadline:
            raise TemplatePullError("fetch budget exhausted before connect")

        conn = self._pinned_connection(u.scheme, host, ip, port, deadline)
        try:
            path = u.path + (("?" + u.query) if u.query else "")
            conn.request("GET", path or "/", headers={"Host": host, "Accept": "*/*",
                                                       "User-Agent": "mdreview-latex-templates"})
            resp = conn.getresponse()
            if resp.status in (301, 302, 303, 307, 308):
                raise TemplatePullError("redirect refused (manifest must use a final url): %s" % url)
            if resp.status != 200:
                raise TemplatePullError("http %d fetching %s" % (resp.status, url))
            data = self._read_capped(resp, deadline)
        finally:
            conn.close()
        if _sha256(data) != expected_sha:
            raise TemplatePullError("sha256 mismatch for %s" % url)
        return data

    def _validated_ip(self, host, port):
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise TemplatePullError("cannot resolve %s: %s" % (host, e))
        chosen = None
        for info in infos:
            ip = info[4][0]
            addr = ipaddress.ip_address(ip)
            blocked = (addr.is_private or addr.is_loopback or addr.is_link_local
                       or addr.is_reserved or addr.is_multicast or addr.is_unspecified)
            if blocked and not self._allow_private:
                raise TemplatePullError("refusing non-public address %s for %s" % (ip, host))
            if chosen is None:
                chosen = ip
        if chosen is None:
            raise TemplatePullError("no address for %s" % host)
        return chosen

    def _pinned_connection(self, scheme, host, ip, port, deadline):
        remaining = max(0.1, min(self._io_timeout, deadline - time.monotonic()))
        sock = socket.create_connection((ip, port), timeout=remaining)   # connect to the validated IP
        if scheme == "https":
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)           # SNI + cert vs the hostname
        conn = http.client.HTTPConnection(host, port, timeout=remaining) if scheme == "http" \
            else http.client.HTTPSConnection(host, port, timeout=remaining)
        conn.sock = sock                                                 # pin: reuse the validated socket
        return conn

    def _read_capped(self, resp, deadline):
        buf = bytearray()
        while True:
            if time.monotonic() > deadline:
                raise TemplatePullError("fetch budget exhausted mid-download")
            chunk = resp.read(65536)
            if not chunk:
                break
            buf += chunk
            if len(buf) > self._max_bytes:
                raise TemplatePullError("download exceeds the %d-byte cap" % self._max_bytes)
        return bytes(buf)


def _sha256(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()
