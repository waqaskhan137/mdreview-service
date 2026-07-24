#!/usr/bin/env python3
"""Access/identity seam oracle (#103).

Proves the HTTP API is BYTE-IDENTICAL before vs after the seam extraction, for BOTH tiers, and that
the read-order inversion (can_read consulted BEFORE identity is demanded) is behaviour-preserving:

  before = origin/dev            -> _authz demands identity first, THEN checks ownership
  after  = this working tree     -> _authz consults the AccessPolicy first, THEN 401s if anonymous

For each tier it boots the before code and the after code on their own scratch ports with FRESH,
empty throwaway MDREVIEW_DATA dirs (gitignored .scratch/), then diffs the normalized transcripts via
tests/golden_transcript.sh. A non-empty diff = drift = fail.

  - local  (REQUIRE_AUTH off): the everything-open transcript is unchanged.
  - hosted (REQUIRE_AUTH on):  the owner transcript is unchanged AND, asserted explicitly on top of
    the diff, the denial rows are present and correct:
        unauthenticated -> 401 ;  authenticated non-owner -> 404 (not 403/200) ;
        unauthenticated to an ABSENT review -> 401, NOT 404  (the row that catches a botched
        inversion that checks existence before anonymity).

Run: python3 tests/access_seam_oracle.py
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRATCH = os.path.join(REPO, ".scratch", "oracle")
BEFORE_SRC = os.path.join(SCRATCH, "before", "src")
AFTER_SRC = os.path.join(REPO, "src")
WEB = os.path.join(REPO, "web", "app")
SECRET = "oracle-proxy-secret"
PEPPER = "oracle-token-pepper"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # bypass a dead loopback proxy


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def prepare_before():
    """Extract origin/dev's src (the pre-#103 code) independent of the working tree."""
    os.makedirs(os.path.join(SCRATCH, "before"), exist_ok=True)
    arch = subprocess.Popen(["git", "archive", "origin/dev", "src"], cwd=REPO, stdout=subprocess.PIPE)
    untar = subprocess.Popen(["tar", "-x", "-C", os.path.join(SCRATCH, "before")], stdin=arch.stdout)
    arch.stdout.close()
    untar.communicate()
    if untar.returncode != 0 or not os.path.isfile(os.path.join(BEFORE_SRC, "mdreview", "server.py")):
        sys.exit("FAIL: could not extract origin/dev src into .scratch")


def boot(src, mode):
    """Start one mdreview instance from `src` on a fresh port + empty data dir. Returns (proc, base)."""
    port = free_port()
    data = os.path.join(SCRATCH, "data-%s-%d" % (mode, port))
    shutil.rmtree(data, ignore_errors=True)
    os.makedirs(data)
    env = {**os.environ, "PYTHONPATH": src, "MDREVIEW_DATA": data, "PORT": str(port),
           "MDREVIEW_WEB_DIR": WEB}
    if mode == "hosted":
        # MDREVIEW_SESSION_SECRET joined the REQUIRE_AUTH boot guard in #67; harmless/unused on the
        # pre-#67 "before" tree (unknown env), required on the "after" tree. The transcript is
        # unaffected, so the byte-identical assertion still holds.
        env.update(MDREVIEW_REQUIRE_AUTH="1", MDREVIEW_PROXY_SECRET=SECRET, MDREVIEW_TOKEN_PEPPER=PEPPER,
                   MDREVIEW_SESSION_SECRET="oracle-session-secret")
    proc = subprocess.Popen([sys.executable, "-m", "mdreview"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    for _ in range(60):
        if proc.poll() is not None:
            sys.exit("FAIL: %s instance (%s) exited on boot (rc=%s)" % (mode, src, proc.returncode))
        try:
            if OPENER.open(base + "/healthz", timeout=5).status == 200:
                return proc, base
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    proc.terminate()
    sys.exit("FAIL: %s instance (%s) did not answer /healthz on %s" % (mode, src, base))


def run_tier(mode, before_base, after_base):
    r = subprocess.run(
        ["bash", os.path.join(HERE, "golden_transcript.sh"), before_base, after_base, mode, SECRET],
        cwd=REPO, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.returncode == 0, r.stdout


# The denial rows the hosted transcript must contain (asserted on top of the before/after diff, so a
# regression that made BOTH tiers wrong the same way still fails). Paths are post-scrub (rid -> RID).
HOSTED_DENIALS = [
    ("unauthenticated, existing review -> 401", "### GET /api/reviews/RID -> 401"),
    ("authenticated non-owner, existing review -> 404", "### GET /api/reviews/RID -> 404"),
    ("unauthenticated, ABSENT review -> 401 (inversion-critical)", "### GET /api/reviews/nope00000000 -> 401"),
    ("authenticated non-owner, ABSENT review -> 404", "### GET /api/reviews/nope00000000 -> 404"),
    ("unauthenticated write (PUT source) -> 401", "### PUT /api/reviews/RID/source -> 401"),
    ("authenticated non-owner delete -> 404", "### DELETE /api/reviews/RID -> 404"),
]


def main():
    shutil.rmtree(SCRATCH, ignore_errors=True)
    os.makedirs(SCRATCH)
    prepare_before()

    procs = []
    diffs_ok = True
    hosted_out = ""
    try:
        for mode in ("local", "hosted"):
            print("\n===== tier: %s =====" % mode)
            bproc, bbase = boot(BEFORE_SRC, mode); procs.append(bproc)
            aproc, abase = boot(AFTER_SRC, mode); procs.append(aproc)
            passed, out = run_tier(mode, bbase, abase)
            diffs_ok = diffs_ok and passed
            if mode == "hosted":
                hosted_out = out
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

    print("\n===== hosted denial assertions =====")
    denials_ok = True
    for label, needle in HOSTED_DENIALS:
        present = needle in hosted_out
        denials_ok = denials_ok and present
        print(("  ok   " if present else "  FAIL ") + label)

    print("\n===== RESULT =====")
    print("  before/after byte-identical (both tiers): " + ("PASS" if diffs_ok else "FAIL"))
    print("  hosted denials present + correct:          " + ("PASS" if denials_ok else "FAIL"))
    ok = diffs_ok and denials_ok
    print("\n" + ("ORACLE PASS: API byte-identical before vs after, both tiers; hosted fails closed."
                  if ok else "ORACLE FAIL: see drift/denial output above."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
