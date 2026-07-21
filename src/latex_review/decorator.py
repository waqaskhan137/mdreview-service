"""ReviewService decorator that recompiles a latex review after each source write.

Wraps the real ReviewService, delegating every method unchanged via __getattr__, and adds only the
post-write compile enqueue on create() and put_source(). This is how the core PUT /source arm
triggers a recompile without any change to server.py beyond the module-dispatch seam: Services
rebinds self.reviews to this wrapper when the flag is on, so app.reviews.put_source is this
override.

enqueue is O(1) and non-blocking, so calling it from put_source (which runs under store.lock) never
holds the lock across a compile: the compile itself runs on the worker thread.
"""


class LatexAwareReviews:
    def __init__(self, inner, worker, templates=None):
        self._inner = inner
        self._worker = worker
        self._templates = templates     # TemplateService: seed source + validate id (used in MR-103)

    def __getattr__(self, name):
        # Every method not overridden below (exists, meta, summary, list_reviews, bump,
        # snapshot_round, read_source, delete, ...) delegates to the wrapped service unchanged.
        return getattr(self._inner, name)

    def create(self, *args, **kwargs):
        # For a latex review created from a template: validate the id BEFORE any review exists (an
        # unknown id raises UnknownTemplate, a core ReviewCreateRejected, which the POST arm renders
        # as a 400 with the available list), and seed the source from the template's starter .tex
        # ONLY when the caller supplied no source (an explicit markdown wins; the template still
        # contributes its companion files at compile time via the worker).
        kind = kwargs.get("kind", "markdown")
        template = kwargs.get("template", "")
        if kind == "latex" and template and self._templates is not None:
            self._templates.require(template)
            markdown = args[0] if args else kwargs.get("markdown", "")
            if not (markdown or "").strip():
                starter = self._templates.starter(template) or ""
                if args:
                    args = (starter,) + tuple(args[1:])
                else:
                    kwargs = {**kwargs, "markdown": starter}
        rid = self._inner.create(*args, **kwargs)
        if self._inner.meta(rid).get("kind") == "latex":
            self._worker.enqueue(rid)
        return rid

    def put_source(self, rid, markdown):
        self._inner.put_source(rid, markdown)
        if self._inner.meta(rid).get("kind") == "latex":
            self._worker.enqueue(rid)
