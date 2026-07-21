"""LatexModule: the feature's HTTP surface, dispatched from H.route's module loop (MR-094).

`handle(h, m, path)` returns True once it has fully handled the request (response written), False
to let the core router try its own arms. It claims:
  - GET /review/{rid}         only when that review's kind == "latex"  -> the split viewer page
  - GET /api/latex/{rid}/pdf   -> the latest compiled PDF (inline; the viewer iframe consumes it)
  - GET /api/latex/{rid}/compile -> the compile status/log for the poller

Every /api/latex route authenticates exactly like a core arm: h._authz first (404-not-403 for a
missing or foreign review), then a disk-floor check before any write (the self-heal enqueue).
"""
import os
import re

from mdreview.config import RID, WEB_DIR


class LatexModule:
    def __init__(self, store, reviews, comments, worker, templates=None):
        self.store = store
        self.reviews = reviews
        self.comments = comments
        self.worker = worker
        self.templates = templates      # TemplateService: catalog listing (used in MR-105)
        self._page_path = os.path.join(WEB_DIR, "latex-viewer.html")

    def _is_latex(self, rid):
        return self.reviews.exists(rid) and self.reviews.meta(rid).get("kind") == "latex"

    def handle(self, h, m, path):
        if m != "GET":
            return False

        if path == "/api/latex/templates":
            # The catalog: which template ids an agent can pass to create_review. Not review-scoped
            # data (no rid, no owner), so no _authz; `cached` is the shared/global download set, not
            # tenant data, so it leaks nothing across users.
            avail = self.templates.available() if self.templates else {"bundled": [], "registry": [], "cached": []}
            h._json(200, avail)
            return True

        mo = re.fullmatch(r"/review/" + RID, path)
        if mo:
            rid = mo.group(1)
            # Only claim the canonical viewer URL for latex reviews; markdown reviews (and unknown
            # ids) fall through to the core arm untouched. Reading meta.kind here leaks nothing.
            if not self._is_latex(rid):
                return False
            uid, plane = h._authz(rid)
            if plane is None:
                return True                       # 401/404 already written
            h._send(200, self.store.read_bytes(self._page_path), "text/html; charset=utf-8")
            return True

        mo = re.fullmatch(r"/api/latex/" + RID + r"/(pdf|compile)", path)
        if mo:
            rid, what = mo.group(1), mo.group(2)
            uid, plane = h._authz(rid)
            if plane is None:
                return True
            if self.reviews.meta(rid).get("kind") != "latex":
                h._json(404, {"error": "not a latex review"})
                return True
            if not h._disk_low():                 # self-heal writes a status file; respect the floor
                self._self_heal(rid)
            if what == "compile":
                self._serve_compile(h, rid)
            else:
                self._serve_pdf(h, rid)
            return True

        return False

    def _self_heal(self, rid):
        """Enqueue a compile for the two orphan states: no status at all (created flag-off, or a
        never-compiled review), or a PDF built from an older revision with nothing pending. A
        failed compile at the CURRENT revision is left alone, so the 2s poll never stacks compiles
        against a persistently-failing source."""
        st = self.worker.status(rid)
        rev = int(self.reviews.meta(rid).get("revision", 0) or 0)
        if st is None:
            self.worker.enqueue(rid)
        elif st.get("state") in ("ok", "failed") and int(st.get("revision", -1)) < rev:
            self.worker.enqueue(rid)

    def _serve_compile(self, h, rid):
        st = self.worker.status(rid) or {"state": "queued",
                                         "revision": int(self.reviews.meta(rid).get("revision", 0) or 0),
                                         "finished_at": None, "log_tail": ""}
        h._json(200, st)

    def _serve_pdf(self, h, rid):
        p = self.worker.pdf_path(rid)
        if not os.path.isfile(p):
            # No PDF yet (never compiled, or the first compile failed): report the compile status
            # so the viewer can show "compiling..." or the error log instead of a blank frame.
            h._json(404, {"error": "no pdf yet", "compile": self.worker.status(rid)})
            return
        h._send(200, self.store.read_bytes(p), "application/pdf")
