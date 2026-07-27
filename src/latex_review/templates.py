"""Template resolution for latex reviews (MR-102 foundation).

A `TemplateService` resolves a template id to:
  - a starter `.tex` (our authored skeleton, always shipped in the bundled catalog), and
  - a companion file-set (the document class/style files), looked up in order:
    bundled bytes -> the shared /data cache -> (MR-104) download from the pinned registry.

CTAN classes (IEEE/ACM/arXiv/LNCS/Elsevier) need NO companion file: Tectonic fetches the class from
its bundle at compile time, so their companion set is empty. Only non-CTAN conference styles carry
companion files, bundled outright for the top ones or downloaded on miss for the tail.

The service is assembled in latex_review.build() and injected; the RegistryPuller is added only when
the registry is enabled (MR-104), so this file has no network. `UnknownTemplate` subclasses the
core-defined `ReviewWriteRejected` so the core POST arm catches it without importing this module.
"""
import os

from mdreview.errors import ReviewWriteRejected

_BUNDLED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class UnknownTemplate(ReviewWriteRejected):
    def __init__(self, template_id, available):
        super().__init__(
            "unknown template %r" % template_id,
            status=400,
            payload={"error": "unknown template", "template": template_id, "available": available},
        )


class BundledCatalog:
    """The template ids we ship: one directory per id under templates/, each with manifest.json +
    starter.tex, plus (for a bundled-outright non-CTAN style) its companion files as bytes on disk.
    A directory that ships only manifest.json + starter.tex has an empty bundled companion set and
    relies on the /data cache or the registry for its style files."""

    _META = ("manifest.json", "starter.tex")

    def __init__(self, root=_BUNDLED_DIR):
        self._root = root

    def ids(self):
        try:
            return {d for d in os.listdir(self._root)
                    if os.path.isfile(os.path.join(self._root, d, "starter.tex"))}
        except FileNotFoundError:
            return set()

    def starter(self, template_id):
        p = os.path.join(self._root, template_id, "starter.tex")
        try:
            with open(p, encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, NotADirectoryError):
            return None

    def companion_files(self, template_id):
        """(filename, bytes) for each shipped companion file (everything in the dir except the two
        meta files). Empty for a CTAN class or a download-only style."""
        d = os.path.join(self._root, template_id)
        if not os.path.isdir(d):
            return []
        out = []
        for name in sorted(os.listdir(d)):
            if name in self._META:
                continue
            p = os.path.join(d, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    out.append((name, f.read()))
        return out


class DataCache:
    """Previously-downloaded companion file-sets, persisted under <data>/.templates/<id>/. Shared and
    global (not per-review/per-tenant), root-owned (0700 /data). MR-104's puller writes here; this
    reads. `companion_files` returns None when the id has never been cached (distinct from an empty
    list, which means 'known here with no files')."""

    _DIR = ".templates"

    def __init__(self, store):
        self._store = store

    def _dir(self, template_id):
        return os.path.join(self._store.data_dir, self._DIR, template_id)

    def ids(self):
        base = os.path.join(self._store.data_dir, self._DIR)
        try:
            return {d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))}
        except FileNotFoundError:
            return set()

    def companion_files(self, template_id):
        d = self._dir(template_id)
        if not os.path.isdir(d):
            return None
        out = []
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    out.append((name, f.read()))
        return out


class TemplateService:
    """Resolves starters + companion file-sets by id. Assembled in build(); `puller` is None until
    the registry is enabled (MR-104)."""

    def __init__(self, bundled, cache, puller=None):
        self._bundled = bundled
        self._cache = cache
        self._puller = puller

    def _registry_ids(self):
        return self._puller.ids() if self._puller else set()

    def known_ids(self):
        return self._bundled.ids() | self._registry_ids() | self._cache.ids()

    def available(self):
        return {
            "bundled": sorted(self._bundled.ids()),
            "registry": sorted(self._registry_ids()),
            "cached": sorted(self._cache.ids()),
        }

    def require(self, template_id):
        """Raise UnknownTemplate (a core ReviewWriteRejected) if the id is not offered anywhere."""
        if template_id not in self.known_ids():
            av = self.available()
            everything = sorted(set(av["bundled"]) | set(av["registry"]) | set(av["cached"]))
            raise UnknownTemplate(template_id, everything)

    def starter(self, template_id):
        """Our shipped skeleton for the id (always local), or None."""
        return self._bundled.starter(template_id)

    def companion_files(self, template_id):
        """Ordered lookup: bundled bytes -> registry (cache-aware download, MR-104) -> plain /data
        cache. Returns a list of (filename, bytes); a CTAN class returns []. Raises UnknownTemplate
        for an unoffered id, or TemplatePullError if a registry download/verify fails."""
        self.require(template_id)
        bundled = self._bundled.companion_files(template_id)
        if bundled:
            return bundled
        if self._puller and template_id in self._registry_ids():
            return self._puller.materialize(template_id)   # cache-hit re-verify + download-on-miss
        cached = self._cache.companion_files(template_id)   # cached-but-not-in-registry edge
        return cached or []
