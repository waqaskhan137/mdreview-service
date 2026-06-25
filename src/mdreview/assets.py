"""Content-hash asset storage (MR-083).

Per review, raw bytes live under <data>/<rid>/assets/<stored> and a manifest at assets.json (both
siblings of source.md/history/, untouched by snapshot_round, so assets survive every PUT /source).
The stored name is sha1(bytes)[:16] + the sanitized original extension: it can never contain '/',
'..' or NUL, so it is path-traversal-proof by construction and dedupes identical bytes. The
human-supplied name is kept only as a manifest match field; it never appears in a filesystem path
or a served URL. Mutating methods assume the caller holds store.lock.
"""
import hashlib
import json
import os
import re
import time


class AssetService:
    _EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")

    def __init__(self, store):
        self.store = store

    def _dir(self, rid):
        return os.path.join(self.store.dir(rid), "assets")

    def _manifest(self, rid):
        return os.path.join(self.store.dir(rid), "assets.json")

    def list(self, rid):
        return self.store.read_json(self._manifest(rid), [])

    def _stored_name(self, name, data):
        mo = self._EXT_RE.search(name or "")
        ext = mo.group(0).lower() if mo else ""
        return hashlib.sha1(data).hexdigest()[:16] + ext

    def attach(self, rid, name, data):
        """Store bytes under a content-hash name and upsert the manifest. Caller holds store.lock."""
        ad = self._dir(rid)
        os.makedirs(ad, exist_ok=True)
        stored = self._stored_name(name, data)
        with open(os.path.join(ad, stored), "wb") as f:
            f.write(data)
        entry = {"name": name, "stored": stored, "bytes": len(data),
                 "ctype": self.store.ctype_for(name), "ts": time.time()}
        manifest = [e for e in self.store.read_json(self._manifest(rid), []) if e.get("name") != name]
        manifest.append(entry)
        self.store.write_text(self._manifest(rid), json.dumps(manifest))
        return entry

    def find(self, rid, stored):
        """The manifest entry for a stored name, or None. Manifest-only resolution: never path-join
        the request segment."""
        return next((e for e in self.list(rid) if e.get("stored") == stored), None)

    def path(self, rid, stored):
        """Filesystem path of an already-resolved stored asset."""
        return os.path.join(self._dir(rid), stored)
