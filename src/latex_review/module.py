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
        # #250: the ONE write on this surface. Everything else stays GET-only below.
        mo = re.fullmatch(r"/api/latex/" + RID + r"/recompile", path)
        if mo and m == "POST":
            return self._recompile(h, mo.group(1))
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

    def _recompile(self, h, rid):
        """POST /api/latex/{rid}/recompile — the sanctioned exception to _self_heal's anti-stacking
        rule (#250). The poll NEVER retries a failed compile at the current revision, by design;
        one explicit human click may. The worker's coalescing (_queued/_redo) bounds a click-storm
        to at most 1 queued + 1 re-run, so this needs no rate limit of its own.

        Auth mirrors every /api/latex arm (h._authz: 401 anon, 404 non-owner/absent). CSRF mirrors
        SharingModule._owner(mutating=True): only the app-owned session cookie presents (and must
        pass) a token; the bearer-token plane carries no cookie and passes — the documented sharing
        posture. app.sessions exists only on the hosted composition; the plain local tier has no
        cookie plane, so the getattr gate is correctly absent there."""
        uid, plane = h._authz(rid)
        if plane is None:
            return True
        if self.reviews.meta(rid).get("kind") != "latex":
            h._json(404, {"error": "not a latex review"})
            return True
        sessions = getattr(h.server.app, "sessions", None)
        if sessions is not None:
            from mdreview.hosted.sessions import SessionService
            cookie = SessionService.read_cookie(h)
            sess = sessions.verify(cookie) if cookie else None
            if sess and not sessions.check_csrf(sess, h.headers.get("X-CSRF-Token", "")):
                h._json(403, {"error": "missing or invalid CSRF token"})
                return True
        if h._disk_low():
            # 507, never a silent skip: the click must not report queued while nothing was queued.
            h._json(507, {"error": "insufficient storage; compile not queued"})
            return True
        self.worker.enqueue(rid)
        # Respond through the same status shape the poller reads (#213 precedent: the button renders
        # what the server SAID, not what the click hoped).
        self._serve_compile(h, rid)
        return True

    def _serve_compile(self, h, rid):
        st = self.worker.status(rid) or {"state": "queued",
                                         "revision": int(self.reviews.meta(rid).get("revision", 0) or 0),
                                         "finished_at": None, "log_tail": ""}
        # #205: two facts the client cannot derive on a COLD load, where it has no prior `ok` in
        # session memory. `has_pdf` says a document exists at all; `pdf_revision` names which
        # revision produced it, or is null for status files written before this field existed.
        # Deliberately NOT defaulting pdf_revision to `revision`: that is the ATTEMPTED revision,
        # so on a failure it names a revision whose PDF was never written. Null means "unknown",
        # which the viewer must render as unknown rather than guessing.
        st = dict(st)
        st["has_pdf"] = os.path.isfile(self.worker.pdf_path(rid))
        st.setdefault("pdf_revision", None)
        h._json(200, st)

    def _serve_pdf(self, h, rid):
        p = self.worker.pdf_path(rid)
        if not os.path.isfile(p):
            # No PDF yet (never compiled, or the first compile failed): report the compile status
            # so the viewer can show "compiling..." or the error log instead of a blank frame.
            h._json(404, {"error": "no pdf yet", "compile": self.worker.status(rid)})
            return
        # #205: name the revision this PDF came from, on the response itself. A machine caller (and
        # the viewer on a COLD load, with no prior `ok` in session memory) otherwise has no way to
        # tell a current PDF from one left behind by a failed recompile.
        # `status.json`'s `revision` is deliberately NOT used as a fallback: that is the ATTEMPTED
        # revision, so on a failed compile it names a revision whose PDF was never written. Absent
        # is honest; wrong is not. Legacy status files predate the field and correctly report absent.
        st = self.worker.status(rid) or {}
        headers = [("X-Compile-State", str(st.get("state") or "unknown"))]
        pdf_rev = st.get("pdf_revision")
        if pdf_rev is not None:
            headers.append(("X-PDF-Revision", str(pdf_rev)))
        h._send(200, self.store.read_bytes(p), "application/pdf", extra_headers=headers)
