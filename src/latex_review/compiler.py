"""Compile worker: turns a latex review's source into a PDF beside it.

A single background thread drains a queue of review ids with per-rid coalescing, so rapid source
pushes collapse to at most one in-flight compile plus one queued re-run. Each job runs in a fresh
empty directory; results land in <data>/<rid>/latex/{paper.pdf, compile.log, status.json},
siblings of source.md that snapshot_round never touches, so history and the PDF stay independent.

MR-094 builds the queue/coalescing/status machinery and the on-disk contract; `_produce_pdf` is a
stub here. MR-095 replaces `_produce_pdf` with the hardened Tectonic subprocess (unprivileged uid,
scrubbed env, --untrusted --only-cached) and adds the asset copy-in and size cap.
"""
import json
import os
import queue
import shutil
import tempfile
import threading
import time


class CompileWorker:
    def __init__(self, store, reviews):
        self.store = store
        self.reviews = reviews          # base ReviewService (meta/read_source are not overridden)
        self._q = queue.Queue()
        # Coalescing state, guarded by _lock: a rid waiting in the queue is in _queued; the rid
        # being compiled right now is _running; a source push that arrives while a rid is running
        # marks _redo so exactly one more compile follows (never a lost update, never a pile-up).
        self._lock = threading.Lock()
        self._queued = set()
        self._running = None
        self._redo = set()
        self._thread = threading.Thread(target=self._run, name="latex-compile", daemon=True)

    def start(self):
        self._thread.start()

    # ---- paths ----
    def _latex_dir(self, rid):
        return os.path.join(self.store.dir(rid), "latex")

    def pdf_path(self, rid):
        return os.path.join(self._latex_dir(rid), "paper.pdf")

    def status(self, rid):
        return self.store.read_json(os.path.join(self._latex_dir(rid), "status.json"), None)

    def _revision(self, rid):
        return int(self.reviews.meta(rid).get("revision", 0) or 0)

    # ---- enqueue (coalescing) ----
    def enqueue(self, rid):
        """Queue a compile for rid. Idempotent while the rid is already queued; if the rid is
        compiling right now, schedules exactly one re-run for when it finishes. Cheap and
        non-blocking: writes a small status(queued) and returns, so it is safe to call under
        store.lock from put_source."""
        with self._lock:
            if rid == self._running:
                self._redo.add(rid)
                return
            if rid in self._queued:
                return
            self._queued.add(rid)
        self._write_status(rid, "queued", self._revision(rid))
        self._q.put(rid)

    # ---- worker loop ----
    def _run(self):
        while True:
            rid = self._q.get()
            with self._lock:
                self._queued.discard(rid)
                self._running = rid
                self._redo.discard(rid)
            try:
                self._compile(rid)
            except Exception as e:               # a bad job must never kill the worker thread
                self._write_status(rid, "failed", self._revision(rid),
                                   log="worker error: %r" % e)
            finally:
                with self._lock:
                    self._running = None
                    redo = rid in self._redo
                    if redo:
                        self._redo.discard(rid)
                        self._queued.add(rid)
                if redo:
                    self._q.put(rid)
                self._q.task_done()

    def _compile(self, rid):
        review_dir = self.store.dir(rid)
        if not os.path.isdir(review_dir):
            return                                # review deleted before we got to it; drop
        rev = self._revision(rid)
        self._write_status(rid, "running", rev)
        job = tempfile.mkdtemp(prefix="latexjob-")
        try:
            self._prepare_job(rid, job)
            ok, log = self._produce_pdf(job, rid)
            produced = os.path.join(job, "paper.pdf")
            if not os.path.isdir(review_dir):     # deleted mid-compile: skip the move (no orphan)
                return
            os.makedirs(self._latex_dir(rid), exist_ok=True)
            if ok and os.path.isfile(produced):
                os.replace(produced, self.pdf_path(rid))   # overwrite the single latest PDF
                self._write_status(rid, "ok", rev, log=log)
            else:
                # keep any previous PDF; record the failure + log so the viewer can show it
                self._write_status(rid, "failed", rev, log=log)
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def _prepare_job(self, rid, job):
        """Write the review source into the job dir as paper.tex. Asset copy-in (basename-mapped,
        traversal-safe) is added in MR-095 alongside the real compiler."""
        source = self.reviews.read_source(rid)
        with open(os.path.join(job, "paper.tex"), "w", encoding="utf-8") as f:
            f.write(source or "")

    def _produce_pdf(self, job, rid):
        """Run the LaTeX engine over job/paper.tex, producing job/paper.pdf. Returns (ok, log).

        MR-094 stub: no engine yet, so every compile reports failed. MR-095 replaces this with the
        hardened Tectonic subprocess.
        """
        return False, "compiler not wired yet (MR-095)"

    # ---- status persistence ----
    def _write_status(self, rid, state, revision, log=""):
        d = self._latex_dir(rid)
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            return                                # review dir vanished; nothing to record
        payload = {"state": state, "revision": revision,
                   "finished_at": time.time() if state in ("ok", "failed") else None,
                   "log_tail": (log or "")[-4000:]}
        self.store.write_text(os.path.join(d, "status.json"), json.dumps(payload))
