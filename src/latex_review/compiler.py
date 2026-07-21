"""Compile worker: turns a latex review's source into a PDF beside it.

A single background thread drains a queue of review ids with per-rid coalescing, so rapid source
pushes collapse to at most one in-flight compile plus one queued re-run. Each job runs in a fresh
empty directory; results land in <data>/<rid>/latex/{paper.pdf, compile.log, status.json},
siblings of source.md that snapshot_round never touches, so history and the PDF stay independent.

The compile runs as an unprivileged user (MR-095): the job dir lives OUTSIDE /data (which is mode
0700 root, so the compile user cannot `\input` another review's source), the subprocess drops to
the `tectonic` uid with a scrubbed environment (no MDREVIEW_* secrets reach /proc/self/environ),
and results are copied back into /data by the root worker. Outside the latex image (local dev with
no `tectonic` user or binary) the compile runs unhardened-as-self with a loud audit line, or simply
reports "not found".
"""
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time

# The compile subprocess identity + limits. COMPILE_USER matches the useradd in Dockerfile.latex;
# WORKDIR is set to an image path the compile user can traverse (never under /data). Both are env
# overridable so the image can point them without code change.
COMPILE_USER = os.environ.get("MDREVIEW_LATEX_USER", "tectonic")
WORKDIR = os.environ.get("MDREVIEW_LATEX_WORKDIR") or tempfile.gettempdir()
COMPILE_TIMEOUT_S = float(os.environ.get("MDREVIEW_LATEX_TIMEOUT_S", "60"))
MAX_PDF_BYTES = int(os.environ.get("MDREVIEW_LATEX_MAX_PDF", str(50 * 1024 * 1024)))


class CompileWorker:
    def __init__(self, store, reviews, assets):
        self.store = store
        self.reviews = reviews          # base ReviewService (meta/read_source are not overridden)
        self.assets = assets            # AssetService: figure copy-in for \includegraphics
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
        # Job dir lives OUTSIDE /data so the unprivileged compile user can use it (the compile user
        # cannot traverse the 0700 /data). Results are copied back into /data by the root worker.
        os.makedirs(WORKDIR, exist_ok=True)
        job = tempfile.mkdtemp(prefix="latexjob-", dir=WORKDIR)
        try:
            self._prepare_job(rid, job)
            ok, log = self._produce_pdf(job, rid)
            produced = os.path.join(job, "paper.pdf")
            if not os.path.isdir(review_dir):     # deleted mid-compile: skip the move (no orphan)
                return
            if ok and os.path.isfile(produced):
                os.makedirs(self._latex_dir(rid), exist_ok=True)
                # Copy across filesystems (job dir -> /data volume), then rename WITHIN /data so a
                # concurrent GET /pdf never sees a half-written file.
                tmp = self.pdf_path(rid) + ".tmp"
                shutil.copyfile(produced, tmp)
                os.replace(tmp, self.pdf_path(rid))
                self._write_status(rid, "ok", rev, log=log)
            else:
                # keep any previous PDF; record the failure + log so the viewer can show it
                self._write_status(rid, "failed", rev, log=log)
        finally:
            shutil.rmtree(job, ignore_errors=True)

    def _prepare_job(self, rid, job):
        """Write the review source as paper.tex and copy each attached figure into the job dir under
        the BASENAME of its manifest name. The manifest name is free-form user input, so any path
        separator, leading '/', or '..' segment is flattened to its basename: the copy can never
        escape the job dir (write-side traversal closed). Consequence: \\includegraphics must use a
        bare filename; subdirectory refs do not resolve (v1 non-goal)."""
        source = self.reviews.read_source(rid)
        with open(os.path.join(job, "paper.tex"), "w", encoding="utf-8") as f:
            f.write(source or "")
        for entry in self.assets.list(rid):
            name, stored = entry.get("name") or "", entry.get("stored") or ""
            if not stored:
                continue
            dest_name = os.path.basename(name.replace("\\", "/").rstrip("/")) or stored
            if dest_name in (".", ".."):
                dest_name = stored
            src = self.assets.path(rid, stored)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(job, dest_name))

    def _compile_identity(self):
        """(uid, gid) to drop the subprocess to, or None. None means run unhardened-as-self: only
        happens off the latex image (not root, or the compile user does not exist), where dev
        convenience beats isolation and a loud audit line records it."""
        if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            return None
        try:
            import pwd
            p = pwd.getpwnam(COMPILE_USER)
            return (p.pw_uid, p.pw_gid)
        except KeyError:
            return None

    def _produce_pdf(self, job, rid):
        """Run Tectonic over job/paper.tex, producing job/paper.pdf. Returns (ok, log_tail).

        Hardened: --untrusted (+ TECTONIC_UNTRUSTED_MODE=1 in the image) disables shell-escape and
        known-insecure features; --only-cached forbids network; a scrubbed env keeps MDREVIEW_*
        secrets out of the child; the process drops to the unprivileged compile uid so it cannot
        read /data. A 60s timeout and a PDF size cap bound resource use.
        """
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": job,
            "TECTONIC_UNTRUSTED_MODE": "1",
        }
        cache = os.environ.get("TECTONIC_CACHE_DIR")
        if cache:
            env["TECTONIC_CACHE_DIR"] = cache      # so --only-cached finds the image-warmed bundle

        kwargs = dict(cwd=job, env=env, timeout=COMPILE_TIMEOUT_S,
                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ident = self._compile_identity()
        if ident:
            self._chown_tree(job, ident[0], ident[1])
            kwargs["user"], kwargs["group"] = ident[0], ident[1]
        else:
            self._audit_unhardened(rid)

        try:
            r = subprocess.run(
                ["tectonic", "-X", "compile", "--untrusted", "--only-cached", "--keep-logs",
                 "--outdir", ".", "paper.tex"], **kwargs)
        except FileNotFoundError:
            return False, "tectonic binary not found (this build is not the latex image)"
        except subprocess.TimeoutExpired as e:
            out = (e.output or b"").decode("utf-8", "replace")
            return False, "compile timed out after %ss\n%s" % (COMPILE_TIMEOUT_S, out)

        log = (r.stdout or b"").decode("utf-8", "replace")
        pdf = os.path.join(job, "paper.pdf")
        if r.returncode != 0 or not os.path.isfile(pdf):
            return False, log or ("tectonic exited %d with no PDF" % r.returncode)
        if os.path.getsize(pdf) > MAX_PDF_BYTES:
            os.remove(pdf)
            return False, "compiled PDF exceeds the %d-byte cap" % MAX_PDF_BYTES
        return True, log

    @staticmethod
    def _chown_tree(root, uid, gid):
        os.chown(root, uid, gid)
        for dirpath, dirnames, filenames in os.walk(root):
            for n in dirnames + filenames:
                try:
                    os.chown(os.path.join(dirpath, n), uid, gid)
                except OSError:
                    pass

    @staticmethod
    def _audit_unhardened(rid):
        print("AUDIT " + json.dumps({"event": "latex_compile_unhardened", "rid": rid}), flush=True)

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
