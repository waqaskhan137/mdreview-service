"""Opt-in LaTeX paper review feature (MR-094).

Self-contained module wired into the core server only when MDREVIEW_ENABLE_LATEX is set. The core
never imports this package except inside that flag branch of Services.__init__; deleting this
directory with the flag off leaves the core untouched.

`build` is the composition entry point: it starts the compile worker, wraps ReviewService so a
latex review recompiles on create/put_source, and returns (module, wrapped_reviews). The caller
(Services) appends the module to its dispatch list and rebinds self.reviews to the wrapper.
"""
import os

from mdreview import config
from latex_review.compiler import CompileWorker
from latex_review.decorator import LatexAwareReviews
from latex_review.module import LatexModule
from latex_review.puller import RegistryPuller
from latex_review.templates import BundledCatalog, DataCache, TemplateService

_DEFAULT_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registry.json")


def build(store, reviews, comments, assets):
    # Composition root: assemble the template resolver chain by config and inject it. The
    # RegistryPuller (download-on-miss) is added ONLY when downloads are enabled, so an air-gapped
    # deployment (MDREVIEW_LATEX_TEMPLATE_DOWNLOAD=0) carries no network path. Core imports nothing.
    puller = None
    if config.LATEX_TEMPLATE_DOWNLOAD:
        puller = RegistryPuller(config.LATEX_TEMPLATE_REGISTRY or _DEFAULT_REGISTRY, store)
    templates = TemplateService(BundledCatalog(), DataCache(store), puller)
    worker = CompileWorker(store, reviews, assets, templates)
    worker.start()
    wrapped = LatexAwareReviews(reviews, worker, templates)
    module = LatexModule(store, wrapped, comments, worker, templates)
    return module, wrapped
