"""ReviewService decorator that recompiles a latex review after each source write.

Wraps the real ReviewService, delegating every method unchanged via __getattr__, and adds only the
post-write compile enqueue on create() and put_source(). This is how the core PUT /source arm
triggers a recompile without any change to server.py beyond the module-dispatch seam: Services
rebinds self.reviews to this wrapper when the flag is on, so app.reviews.put_source is this
override.

enqueue is O(1) and non-blocking, so calling it from put_source (which runs under store.lock) never
holds the lock across a compile: the compile itself runs on the worker thread.

It also REJECTS a write whose body could not compile (#188). Note carefully that this class wraps
app.reviews for EVERY review kind, not just latex ones, so both guards below are gated on
meta.kind == "latex"; an ungated check here would reject every markdown write in the product.
"""
from mdreview import latexguard
from mdreview.errors import ReviewWriteRejected

# What the offending agent actually reads: mcp/client.py surfaces the raw response body in its
# ToolError, so this text is the entire value of the fix over a Tectonic error 200 lines downstream.
# It has to name the kind, what is missing, and the way out.
_NOT_TEX = ('this review is kind="latex", so its source must be a LaTeX document, but the body has '
            'no \\documentclass, \\begin{document}, \\input or \\include. Nothing was saved. If you '
            'meant to send markdown, create a markdown review instead (kind="markdown").')


def _require_tex(markdown, allow_empty):
    """Reject a body that cannot compile as paper.tex (#188).

    A latex review's source is written VERBATIM to paper.tex by compiler._prepare_job, so a body
    that is not TeX has no path to a PDF; failing here names the real mistake at the moment it is
    made, instead of surfacing as a Tectonic parse error against generated output.

    allow_empty is True only on create: starting a blank paper and filling it in later is a real
    workflow, but an empty PUT would snapshot-and-overwrite a working paper into exactly the
    failed-compile state this guard exists to prevent.
    """
    if allow_empty and not (markdown or "").strip():
        return
    if not latexguard.is_tex_source(markdown):
        raise ReviewWriteRejected(_NOT_TEX)


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
        # unknown id raises UnknownTemplate, a core ReviewWriteRejected, which the POST arm renders
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
        # #188: reject a non-TeX body BEFORE the review exists, so a bad create leaves nothing
        # behind. After the seeding above, so a template starter (all of which carry
        # \documentclass) satisfies it. Inside the kind test: markdown creates are none of our
        # business. create() takes markdown positionally (reviews.py:109) and server.py:434 passes
        # it that way, but kwargs is honored too since the wrapper's own signature is *args.
        if kind == "latex":
            _require_tex(args[0] if args else kwargs.get("markdown", ""), allow_empty=True)
        rid = self._inner.create(*args, **kwargs)
        if self._inner.meta(rid).get("kind") == "latex":
            self._worker.enqueue(rid)
        return rid

    def put_source(self, rid, markdown):
        # kind is read BEFORE the write: put_source snapshots a history round and overwrites
        # source.md, so a body rejected afterwards would already have destroyed the good one.
        is_latex = self._inner.meta(rid).get("kind") == "latex"
        if is_latex:
            _require_tex(markdown, allow_empty=False)
        self._inner.put_source(rid, markdown)
        if is_latex:
            self._worker.enqueue(rid)
