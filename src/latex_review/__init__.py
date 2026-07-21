"""Opt-in LaTeX paper review feature (MR-094).

Self-contained module wired into the core server only when MDREVIEW_ENABLE_LATEX is set. The core
never imports this package except inside that flag branch of Services.__init__; deleting this
directory with the flag off leaves the core untouched.

`build` is the composition entry point: it starts the compile worker, wraps ReviewService so a
latex review recompiles on create/put_source, and returns (module, wrapped_reviews). The caller
(Services) appends the module to its dispatch list and rebinds self.reviews to the wrapper.
"""
from latex_review.compiler import CompileWorker
from latex_review.decorator import LatexAwareReviews
from latex_review.module import LatexModule
from latex_review.templates import BundledCatalog, DataCache, TemplateService


def build(store, reviews, comments, assets):
    # Composition root: assemble the template resolver chain by config and inject it. The
    # RegistryPuller (download-on-miss) is added only when the registry is enabled (MR-104), so a
    # flag-on-but-registry-off deployment carries no network path. Core imports nothing of this.
    templates = TemplateService(BundledCatalog(), DataCache(store))
    worker = CompileWorker(store, reviews, assets, templates)
    worker.start()
    wrapped = LatexAwareReviews(reviews, worker, templates)
    module = LatexModule(store, wrapped, comments, worker, templates)
    return module, wrapped
