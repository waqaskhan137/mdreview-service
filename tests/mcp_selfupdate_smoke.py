#!/usr/bin/env python3
"""Smoke for the wrapper self-update (#90). Runnable: `python3 tests/mcp_selfupdate_smoke.py`.

Covers the paths that hurt if they break: a stale MANAGED wrapper self-heals from its server, a
SUPERSET wrapper converges (stale file removed) in one round, an UNMANAGED tree is never touched,
MDREVIEW_NO_AUTO_UPDATE opts out, and the path allowlist rejects traversal. Spins a throwaway
mdreview server on a scratch port; all temp state under .scratch (never /tmp — repo hook)."""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "src")
SCRATCH = os.path.join(REPO, ".scratch", "selfupdate")
PORT = 8151
BASE = "http://localhost:%d" % PORT

sys.path.insert(0, SRC)
from mcp import bundle, update  # noqa: E402


def _wrapper_run(root, extra_env=None):
    """Run the managed wrapper once (empty stdin -> update runs, serve loop exits). Returns stderr."""
    env = dict(os.environ, MDREVIEW_BASE=BASE)
    env.pop("MDREVIEW_TOKEN", None)
    env.pop("MDREVIEW_NO_AUTO_UPDATE", None)
    env["PYTHONPATH"] = os.path.join(root, "src")
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([sys.executable, os.path.join(root, "src", "mcp_server.py")],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=env)
    return p.stderr


def _make_managed():
    """A fresh installer-managed copy of the repo src (marker present, no .git)."""
    root = os.path.join(SCRATCH, "managed")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    shutil.copytree(SRC, os.path.join(root, "src"))
    open(os.path.join(root, ".managed"), "w").close()
    return root


def main():
    # --- pure guard checks (no server needed) ---
    assert update._managed_root() is None, "repo/dev tree (has .git) must never be managed"
    assert update._allowed("mcp_server.py") and update._allowed("mcp/client.py")
    for bad in ("../evil.py", "/etc/passwd", "mcp/../../x.py", "mcp/sub/x.py", "mcp/x.txt", "x.py"):
        assert not update._allowed(bad), "allowlist must reject %r" % bad
    print("ok: guard + allowlist")

    os.makedirs(SCRATCH, exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "mdreview"],
                              env=dict(os.environ, PYTHONPATH=SRC, PORT=str(PORT),
                                       MDREVIEW_DATA=os.path.join(SCRATCH, "data")),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(BASE + "/healthz", timeout=1).read()
                break
            except Exception:
                time.sleep(0.25)
        else:
            raise SystemExit("server did not come up on %d" % PORT)

        served = bundle.wrapper_version()  # server serves the pristine repo wrapper

        # 1) stale managed wrapper self-heals
        root = _make_managed()
        client_py = os.path.join(root, "src", "mcp", "client.py")
        pristine = open(client_py).read()
        with open(client_py, "a") as f:
            f.write("\n# tampered\n")
        assert bundle.wrapper_version(bundle.wrapper_files(os.path.join(root, "src"))) != served
        err = _wrapper_run(root)
        assert open(client_py).read() == pristine, "tampered file not restored: %s" % err
        assert os.path.isfile(client_py + ".bak"), "no .bak kept"
        assert bundle.wrapper_version(bundle.wrapper_files(os.path.join(root, "src"))) == served
        print("ok: stale wrapper self-healed (%s)" % err.strip().splitlines()[-1:])

        # 2) superset converges: an extra mcp/*.py the server does not serve is removed in one round
        extra = os.path.join(root, "src", "mcp", "extra.py")
        with open(extra, "w") as f:
            f.write("# not served\n")
        assert bundle.wrapper_version(bundle.wrapper_files(os.path.join(root, "src"))) != served
        _wrapper_run(root)
        assert not os.path.isfile(extra), "stale extra file not removed (never converges)"
        assert bundle.wrapper_version(bundle.wrapper_files(os.path.join(root, "src"))) == served
        print("ok: superset converged")

        # 3) opt-out: tamper, run with NO_AUTO_UPDATE=1 -> untouched
        with open(client_py, "a") as f:
            f.write("\n# tampered again\n")
        tampered = open(client_py).read()
        _wrapper_run(root, {"MDREVIEW_NO_AUTO_UPDATE": "1"})
        assert open(client_py).read() == tampered, "opt-out was ignored"
        print("ok: MDREVIEW_NO_AUTO_UPDATE respected")

        # 4) unmanaged (no .managed marker) -> untouched even when stale
        nomark = os.path.join(SCRATCH, "unmanaged")
        shutil.rmtree(nomark, ignore_errors=True)
        os.makedirs(nomark)
        shutil.copytree(SRC, os.path.join(nomark, "src"))
        with open(os.path.join(nomark, "src", "mcp", "client.py"), "a") as f:
            f.write("\n# tampered\n")
        marked = open(os.path.join(nomark, "src", "mcp", "client.py")).read()
        _wrapper_run(nomark)
        assert open(os.path.join(nomark, "src", "mcp", "client.py")).read() == marked, \
            "unmanaged tree must never be modified"
        print("ok: unmanaged tree untouched")

        print("PASS")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
        shutil.rmtree(SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    main()
