#!/usr/bin/env python3
"""tests/latex_disposable_fixture.py — mint a disposable "failed-with-a-surviving-PDF" latex
review (#318).

THE PROBLEM THIS REPLACES: three tickets' acceptance criteria (#205, #250, #280) verified the
failed-compile UI against ONE standing review, hand-minted on staging, that anyone or anything
could advance. It did: a later successful compile left it `ok`, and every AC that cited it as
"failed at v2 with a good v1 PDF" went stale in place — a check against it could go green while
proving nothing. A shared mutable fixture on a live environment is not a fixture.

THIS FILE mints the SAME shape on demand instead: `mint()` creates a fresh latex review, drives it
through v1 (compiles ok, a real PDF) then v2 (`\\undefinedcommandhere`, compiles failed), and
verifies the result before handing back the id — a mint that silently lands `ok` is a bug in the
mint, not a fixture a caller should trust. `release()` deletes what was minted and confirms it is
actually gone. Two `mint()` calls never share state: each is its own review, its own id, its own
cleanup. Base URL and token are ordinary arguments (also readable from `MDREVIEW_BASE` /
`MDREVIEW_TOKEN`, the names `src/mcp/client.py` already uses) — nothing here is hardcoded to any
particular host, staging included.

Run standalone (no args): boots its own throwaway LOCAL instance (needs a LaTeX toolchain on
PATH — tectonic or pdflatex; MDREVIEW_ENABLE_LATEX=1) and proves, by independently re-reading the
HTTP API (not by trusting `mint()`'s own verdict), that the minted shape is real and that release
leaves nothing behind.

  python3 tests/latex_disposable_fixture.py                     (exit 0 = pass)

Usable directly against a running instance too — mints one fixture and prints its id:

  python3 tests/latex_disposable_fixture.py BASE_URL [TOKEN]
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAPER_OK = ("\\documentclass{article}\n\\begin{document}\n"
            "Disposable fixture, revision 1.\n\\end{document}\n")
# Named literally by AC1. Verified directly against tectonic before this file was written: exit 1,
# no paper.pdf produced (`! Undefined control sequence`) — a real, reliable compile failure, not a
# guess dressed as one.
PAPER_BROKEN = ("\\documentclass{article}\n\\begin{document}\n"
                "\\undefinedcommandhere\n\\end{document}\n")


class FixtureUnavailable(RuntimeError):
    """This environment cannot produce the shape at all (no LaTeX toolchain on PATH) — distinct
    from the shape genuinely failing to hold. Mirrors tests/latex_smoke.py's exit-3 convention: an
    unrunnable environment is not the same finding as a broken mint, and conflating them is how a
    real regression starts getting explained away as "just the sandbox"."""


def _req(base, path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if token:
        # Bearer plane needs no CSRF token (src/mdreview/hosted/compose.py's check_csrf is a no-op
        # without a session cookie) — the same posture tests/latex_recompile_selfcheck.py asserts.
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _wait_compile(base, rid, token=None, timeout=90):
    deadline = time.time() + timeout
    st = {}
    while time.time() < deadline:
        code, _, raw = _req(base, "/api/latex/%s/compile" % rid, token=token)
        st = json.loads(raw) if code == 200 else {}
        if st.get("state") in ("ok", "failed"):
            return st
        time.sleep(0.5)
    return st


def verify_shape(base, rid, token=None):
    """Read the review's compile status + served PDF back from the HTTP API and confirm the shape
    (AC3): the CURRENT compile is failed, and an EARLIER revision's PDF survives it. Raises
    RuntimeError, loudly and by name, the instant the shape does not hold — a silent `ok` compile
    is a failed mint, never a pass. Returns the parsed /compile status on success.
    """
    code, _, raw = _req(base, "/api/latex/%s/compile" % rid, token=token)
    if code != 200:
        raise RuntimeError("verify_shape: GET /compile returned %d, not 200: %r" % (code, raw[:200]))
    st = json.loads(raw)
    if st.get("state") != "failed":
        raise RuntimeError("verify_shape: state=%r, want 'failed' (the mint never reached the "
                            "shape)" % st.get("state"))
    if st.get("has_pdf") is not True:
        raise RuntimeError("verify_shape: has_pdf=%r; the earlier revision's PDF did not survive "
                            "the failed recompile: %r" % (st.get("has_pdf"), st))
    pdf_rev, rev = st.get("pdf_revision"), st.get("revision")
    # Strict '<', not merely '!=': the claim is specifically that an EARLIER revision survived, and
    # pdf_revision is legitimately 0 (falsy) on the very first compile, so a truthiness check here
    # would silently pass a broken mint too.
    if pdf_rev is None or rev is None or not (pdf_rev < rev):
        raise RuntimeError("verify_shape: pdf_revision=%r must be an earlier revision than the "
                            "failed attempt revision=%r" % (pdf_rev, rev))
    code, hdrs, raw = _req(base, "/api/latex/%s/pdf" % rid, token=token)
    if code != 200 or not raw.startswith(b"%PDF"):
        raise RuntimeError("verify_shape: GET /pdf did not serve a surviving PDF: code=%d body=%r"
                            % (code, raw[:16]))
    if hdrs.get("X-Compile-State") != "failed":
        raise RuntimeError("verify_shape: /pdf's X-Compile-State header=%r, want 'failed'"
                            % hdrs.get("X-Compile-State"))
    return st


def mint(base, token=None, title="disposable-205-fixture"):
    """Mint ONE disposable review in the failed-with-a-surviving-PDF shape (AC1): v1 compiles ok
    with a real PDF, v2 is `\\undefinedcommandhere` and fails, and v1's PDF survives. Returns the
    new review id. Every call creates its own review (AC2) — nothing here is a singleton. Raises
    FixtureUnavailable if this environment cannot compile at all, or RuntimeError if the shape
    still did not hold despite a working toolchain (AC3): both are loud failures, on purpose.
    """
    code, _, raw = _req(base, "/api/reviews", "POST",
                        {"title": title, "kind": "latex", "markdown": PAPER_OK}, token=token)
    if code != 201:
        raise RuntimeError("mint: create returned %d, not 201: %r" % (code, raw[:200]))
    rid = json.loads(raw)["id"]

    # v1 MUST reach a verdict before v2 is pushed. CompileWorker.enqueue coalesces a push that
    # arrives while a compile is already running/queued for this rid (compiler.py's _queued/_redo
    # bookkeeping), and _compile reads the CURRENT revision at compile start — so racing the two
    # writes risks the broken source getting compiled against the wrong revision, or a poll here
    # reading v1's stale 'ok' instead of v2's 'failed'. Serializing is load-bearing, not caution.
    st1 = _wait_compile(base, rid, token=token)
    if st1.get("state") != "ok":
        log = (st1.get("log_tail") or "")
        # "timed out" (compiler.py's COMPILE_TIMEOUT_S, 60s default): a cold Tectonic bundle cache
        # fetches CTAN packages mid-compile on its first run anywhere, which can outrun the timeout
        # through no fault of the mint. That is an environment limitation, not a broken shape —
        # exactly the distinction FixtureUnavailable exists to keep separate from a real regression.
        if ("not found" in log or "not the latex image" in log or "timed out" in log):
            raise FixtureUnavailable("mint: v1 (the good revision) could not compile in this "
                                      "environment: %s" % log[:200])
        raise RuntimeError("mint: v1 (the good revision) did not compile ok: %r" % st1)

    code, _, raw = _req(base, "/api/reviews/%s" % rid, token=token)
    if code != 200:
        raise RuntimeError("mint: GET meta returned %d after v1 compiled ok: %r" % (code, raw[:200]))
    rev = json.loads(raw).get("revision", 0)

    code, _, raw = _req(base, "/api/reviews/%s/source" % rid, "PUT",
                        {"markdown": PAPER_BROKEN, "expected_revision": rev}, token=token)
    if code != 200:
        raise RuntimeError("mint: PUT the broken v2 source returned %d, not 200: %r"
                            % (code, raw[:200]))

    _wait_compile(base, rid, token=token)
    verify_shape(base, rid, token=token)   # AC3: fail loudly here, not a silent 'ok' handed back
    return rid


def release(base, rid, token=None):
    """Delete a minted review and PROVE it is gone (AC4): a DELETE that 200s but leaves the
    directory on disk would still accumulate reviews on repeated runs. Returns True; raises
    RuntimeError if the review is still readable afterward.
    """
    code, _, raw = _req(base, "/api/reviews/%s" % rid, "DELETE", token=token)
    if code != 200:
        raise RuntimeError("release: DELETE returned %d, not 200: %r" % (code, raw[:200]))
    code, _, raw = _req(base, "/api/reviews/%s" % rid, token=token)
    if code != 404:
        raise RuntimeError("release: %s still readable after delete (code=%d) — not actually gone"
                            % (rid, code))
    return True


# ================= standalone self-check: boots its OWN throwaway local instance ==================

def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _boot():
    data = tempfile.mkdtemp(prefix="mdr318-")
    port = _free_port()
    env = dict(os.environ, MDREVIEW_DATA=data, PORT=str(port), MDREVIEW_ENABLE_LATEX="1",
               MDREVIEW_WEB_DIR=os.path.join(ROOT, "web", "app"), PYTHONPATH=os.path.join(ROOT, "src"))
    log = open(os.path.join(data, "server.log"), "w")
    srv = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env, stdout=log, stderr=log)
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        try:
            _req(base, "/healthz"); break
        except Exception:
            time.sleep(0.25)
    return srv, base, data


def _selfcheck():
    failed = []

    def check(name, cond, detail=""):
        print(("ok   - " if cond else "FAIL - ") + name
              + (("  (%s)" % detail) if detail and not cond else ""))
        if not cond:
            failed.append(name)

    _UNAVAILABLE = object()

    def try_mint(name):
        """Wrap mint() so a raised exception becomes a NAMED failure (AC3's guard proven from the
        outside), not an uncaught traceback that happens to exit non-zero for an unrelated reason.
        Distinguishes "this sandbox cannot compile at all" from "the shape genuinely broke" —
        conflating the two is how a real regression gets waved off as an environment quirk."""
        try:
            rid = mint(base)
            check(name, True)
            return rid
        except FixtureUnavailable as e:
            print("SKIP - %s (%s)" % (name, e))
            return _UNAVAILABLE
        except RuntimeError as e:
            check(name, False, str(e))
            return None

    srv, base, data = _boot()
    try:
        rid1 = try_mint("mint: reaches the failed-with-surviving-PDF shape")
        if rid1 is _UNAVAILABLE:
            print("\nno LaTeX toolchain in this environment; nothing further to check")
            return 0
        if rid1 is None:
            print("\n%d case(s) failed" % len(failed))
            return 1

        # Independent re-read (AC's own check requirement): asserts the ACTUAL API state itself,
        # via a fresh /compile + /pdf request, rather than trusting mint()'s internal verdict. This
        # block is what a mutated/weakened verify_shape() cannot fool — see the mutation test in
        # the ticket's report.
        code, _, raw = _req(base, "/api/latex/%s/compile" % rid1)
        st = json.loads(raw) if code == 200 else {}
        check("independent re-read: compile state is 'failed'", st.get("state") == "failed", st)
        check("independent re-read: has_pdf is true (a prior revision's PDF survives)",
              st.get("has_pdf") is True, st)
        check("independent re-read: pdf_revision names a STRICTLY earlier revision",
              st.get("pdf_revision") is not None and st.get("revision") is not None
              and st.get("pdf_revision") < st.get("revision"), st)
        code, hdrs, raw = _req(base, "/api/latex/%s/pdf" % rid1)
        check("independent re-read: /pdf serves the surviving document (200, %PDF bytes)",
              code == 200 and raw.startswith(b"%PDF"), (code, raw[:16]))
        check("independent re-read: /pdf's X-Compile-State header says failed",
              hdrs.get("X-Compile-State") == "failed", hdrs.get("X-Compile-State"))

        # AC2: a second mint is a DISTINCT review, independently in the same shape.
        rid2 = try_mint("mint x2: a second call reaches the shape independently")
        if rid2 not in (None, _UNAVAILABLE):
            check("mint x2: two distinct review ids", rid1 != rid2, (rid1, rid2))
        else:
            rid2 = None

        # AC4: release cleans up, and this proves the cleanup happened (not just that release()
        # returned without raising).
        release(base, rid1)
        code, _, _ = _req(base, "/api/reviews/%s" % rid1)
        check("release: the first minted review 404s after release", code == 404, code)
        if rid2 is not None:
            release(base, rid2)
            code, _, _ = _req(base, "/api/reviews/%s" % rid2)
            check("release: the second minted review 404s after release", code == 404, code)
    finally:
        srv.terminate()
        shutil.rmtree(data, ignore_errors=True)

    print("\n" + ("%d case(s) failed" % len(failed) if failed else "all disposable-fixture cases pass"))
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(_selfcheck())
    base_arg = sys.argv[1]
    token_arg = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("MDREVIEW_TOKEN")
    print(mint(base_arg, token=token_arg))
